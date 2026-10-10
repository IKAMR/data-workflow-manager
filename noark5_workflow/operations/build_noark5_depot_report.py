from __future__ import annotations

import json
from pathlib import Path

from noark5_workflow.analysis.depot_report_builder import build_depot_report_model, write_depot_report_html
from noark5_workflow.analysis.archive_parts_summary import build_all_archive_parts_summary
from noark5_workflow.analysis.period_reconciliation import build_period_reconciliation
from noark5_workflow.core.artifact_identity import artifact_belongs_to_context, artifact_run_dir, write_artifact_manifest
from noark5_workflow.core.context import OperationContext
from noark5_workflow.core.operation import BaseOperation, ExecutionTarget, OperationDefinition
from noark5_workflow.core.result import OperationResult
from noark5_workflow.external_evidence.depot_arkade5 import attach_arkade5_to_depot_model, inject_arkade5_html
from noark5_workflow.external_evidence.depot_report_pipeline_a5 import write_depot_evidence_outputs


class BuildNoark5DepotReportOperation(BaseOperation):
    definition = OperationDefinition(
        operation_id="build_noark5_depot_report",
        name="Noark 5 depotvalideringsrapport",
        description=(
            "Bygger depotets valideringsrapport fra siste materialiserte depot-presentasjon. "
            "Perioder og årsserier krysskontrolleres fra samme materialiserte XPath-kjøring. "
            "Importert Arkade 5-evidens legges til separat uten ny XML/XPath-analyse. "
            "Valgt KDRS Query-evidens legges til i separate, sporbare rapportfiler."
        ),
        execution_target=ExecutionTarget.EITHER,
        category="Rapport",
    )
    raw_result_record = True

    def _latest_depot_presentation(self, work_operations: Path, ctx: OperationContext | None = None) -> Path | None:
        root = work_operations / "noark5_views"
        if not root.is_dir():
            return None
        candidates = []
        for run in root.iterdir():
            if ctx is not None and not artifact_belongs_to_context(run, ctx):
                continue
            p = run / "presentations" / "depot.json"
            if p.is_file():
                candidates.append(p)
        return max(candidates, key=lambda p: p.parent.parent.name) if candidates else None

    def _latest_xpath_run(self, work_operations: Path, ctx: OperationContext | None = None) -> Path | None:
        root = work_operations / "noark5_tests" / "xpath"
        if not root.is_dir():
            return None
        candidates = []
        for run in root.iterdir():
            if ctx is not None and not artifact_belongs_to_context(run, ctx):
                continue
            if (run / "index.json").is_file() and (run / "results").is_dir():
                candidates.append(run)
        return max(candidates, key=lambda p: p.name) if candidates else None

    def can_run(self, ctx: OperationContext) -> tuple[bool, str]:
        if ctx.work_operations is None:
            return False, "Jobben mangler Arbeid – operasjoner."
        if self._latest_depot_presentation(Path(ctx.work_operations), ctx) is None:
            return False, (
                "Ingen materialisert depot-presentasjon finnes for denne jobben/kilden. "
                "Kjør Noark 5 XPath-tester 2026 og Noark 5 views/compositions først."
            )
        return True, ""

    def run(self, ctx: OperationContext) -> OperationResult:
        work = Path(ctx.work_operations)
        source = self._latest_depot_presentation(work, ctx)
        if source is None:
            return OperationResult(False, "Ingen depot-presentasjon finnes for denne jobben/kilden.")
        presentation = json.loads(source.read_text(encoding="utf-8"))
        model = build_depot_report_model(presentation, source_presentation_file=str(source))
        xpath_run = self._latest_xpath_run(work, ctx)
        if xpath_run is not None:
            period = build_period_reconciliation(xpath_run)
            model["period_reconciliation"] = period
            model.setdefault("evidence", {})["source_xpath_run"] = str(xpath_run)
            for finding in period.get("findings") or []:
                if not finding.get("requires_review"):
                    continue
                model.setdefault("deviations", []).append({
                    "category": finding.get("category", "period_reconciliation"),
                    "severity": "review", "summary": finding.get("summary", "Periodeavstemming krever vurdering."),
                    "requires_review": True, "period_evidence": finding,
                })
        model["all_archive_parts_summary"] = build_all_archive_parts_summary(model)
        for finding in model["all_archive_parts_summary"].get("cross_source_year_findings") or []:
            model.setdefault("deviations", []).append({
                "category": finding.get("category", "cross_source_year"),
                "severity": "review", "summary": finding.get("summary", "Årsdata krever vurdering."),
                "requires_review": True, "year_evidence": finding,
            })
        model = attach_arkade5_to_depot_model(model, work_operations=work)
        out = artifact_run_dir(ctx, "noark5_reports", "depot_validation", operation_id=self.definition.operation_id)
        write_artifact_manifest(ctx, out, operation_id=self.definition.operation_id, definition_id="noark5-depot-validation-report")
        model_file = out / "depot_validation_report.json"
        html_file = out / "depot_validation_report.html"
        model_file.write_text(json.dumps(model, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        write_depot_report_html(model, html_file)
        inject_arkade5_html(html_file, model)
        try:
            external = write_depot_evidence_outputs(model_file, work)
        except (OSError, ValueError, TypeError, KeyError) as exc:
            external = {"status": "error", "reason": str(exc)}
        arkade_summary = ((model.get("external_validation") or {}).get("arkade5") or {}).get("summary") or {}
        period_summary = model.get("period_reconciliation") or {}
        message = f"Noark 5 depotvalideringsrapport bygget. Resultat: {out}"
        if external['status'] == 'error':
            message += f". KDRS-evidens kunne ikke oppdateres: {external['reason']}"
        return OperationResult(True, message, data={
            "output_dir": str(out), "artifact_manifest": str(out / "artifact_manifest.json"),
            "source_presentation": str(source), "source_xpath_run": str(xpath_run) if xpath_run else "",
            "report_model": str(model_file), "report_html": str(html_file),
            "period_review_findings": int(period_summary.get("review_finding_count") or 0),
            "all_archive_parts_year_findings": int((model.get("all_archive_parts_summary") or {}).get("review_finding_count") or 0),
            "arkade5_imports": int(arkade_summary.get("imports") or 0),
            "arkade5_covered_by_arkade": int(arkade_summary.get("covered_by_arkade") or 0),
            "external_evidence": external,
        })
