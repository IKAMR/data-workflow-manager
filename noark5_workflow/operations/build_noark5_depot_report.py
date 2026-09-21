from __future__ import annotations

import json
from pathlib import Path

from noark5_workflow.analysis.depot_report_builder import (
    build_depot_report_model,
    write_depot_report_html,
)
from noark5_workflow.core.artifact_identity import (
    artifact_belongs_to_context,
    artifact_run_dir,
    write_artifact_manifest,
)
from noark5_workflow.core.context import OperationContext
from noark5_workflow.core.operation import BaseOperation, ExecutionTarget, OperationDefinition
from noark5_workflow.core.result import OperationResult


class BuildNoark5DepotReportOperation(BaseOperation):
    definition = OperationDefinition(
        operation_id="build_noark5_depot_report",
        name="Noark 5 depotvalideringsrapport",
        description=(
            "Bygger depotets valideringsrapport fra siste materialiserte depot-presentasjon. "
            "Ingen XML/XPath eller nye tellere kjøres."
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
        source = self._latest_depot_presentation(Path(ctx.work_operations), ctx)
        if source is None:
            return OperationResult(False, "Ingen depot-presentasjon finnes for denne jobben/kilden.")

        presentation = json.loads(source.read_text(encoding="utf-8"))
        model = build_depot_report_model(
            presentation,
            source_presentation_file=str(source),
        )

        out = artifact_run_dir(
            ctx,
            "noark5_reports",
            "depot_validation",
            operation_id=self.definition.operation_id,
        )
        write_artifact_manifest(
            ctx,
            out,
            operation_id=self.definition.operation_id,
            definition_id="noark5-depot-validation-report",
        )

        model_file = out / "depot_validation_report.json"
        html_file = out / "depot_validation_report.html"

        model_file.write_text(
            json.dumps(model, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        write_depot_report_html(model, html_file)

        return OperationResult(
            True,
            f"Noark 5 depotvalideringsrapport bygget. Resultat: {out}",
            data={
                "output_dir": str(out),
                "artifact_manifest": str(out / "artifact_manifest.json"),
                "source_presentation": str(source),
                "report_model": str(model_file),
                "report_html": str(html_file),
            },
        )
