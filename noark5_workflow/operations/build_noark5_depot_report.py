from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from noark5_workflow.analysis.depot_report_builder import (
    build_depot_report_model,
    write_depot_report_html,
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

    def _latest_depot_presentation(self, work_operations: Path) -> Path | None:
        root = work_operations / "noark5_views"
        if not root.is_dir():
            return None
        candidates = []
        for run in root.iterdir():
            p = run / "presentations" / "depot.json"
            if p.is_file():
                candidates.append(p)
        return max(candidates, key=lambda p: p.parent.parent.name) if candidates else None

    def can_run(self, ctx: OperationContext) -> tuple[bool, str]:
        if ctx.work_operations is None:
            return False, "Jobben mangler Arbeid – operasjoner."
        if self._latest_depot_presentation(Path(ctx.work_operations)) is None:
            return False, (
                "Ingen materialisert depot-presentasjon finnes. "
                "Kjør Noark 5 XPath-tester 2026 og Noark 5 views/compositions først."
            )
        return True, ""

    def run(self, ctx: OperationContext) -> OperationResult:
        source = self._latest_depot_presentation(Path(ctx.work_operations))
        if source is None:
            return OperationResult(False, "Ingen depot-presentasjon finnes.")

        presentation = json.loads(source.read_text(encoding="utf-8"))
        model = build_depot_report_model(
            presentation,
            source_presentation_file=str(source),
        )

        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        out = Path(ctx.work_operations) / "noark5_reports" / "depot_validation" / stamp
        out.mkdir(parents=True, exist_ok=True)

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
                "source_presentation": str(source),
                "report_model": str(model_file),
                "report_html": str(html_file),
            },
        )
