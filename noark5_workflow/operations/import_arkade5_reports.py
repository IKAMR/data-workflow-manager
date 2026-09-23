
from __future__ import annotations

from pathlib import Path

from noark5_workflow.core.context import OperationContext
from noark5_workflow.core.operation import (
    BaseOperation,
    ExecutionTarget,
    OperationDefinition,
)
from noark5_workflow.core.result import OperationResult
from noark5_workflow.external_evidence.arkade5_discovery import (
    import_discovered_arkade5_reports,
)


class ImportArkade5ReportsOperation(BaseOperation):
    definition = OperationDefinition(
        operation_id="import_arkade5_reports",
        name="Finn/importer Arkade 5-resultater",
        description=(
            "Finn lokale Arkade 5 Noark 5 JSON-rapporter og importer alle nye "
            "rapporter som versjonert ekstern evidens. Ingen rapport funnet er OK."
        ),
        execution_target=ExecutionTarget.EITHER,
        category="Rapport",
    )

    def can_run(self, ctx: OperationContext) -> tuple[bool, str]:
        if ctx.work_operations is None:
            return False, "Work - operations må være definert."
        return True, ""

    @staticmethod
    def _configured_roots(ctx: OperationContext) -> list[str]:
        raw = ctx.settings.get("arkade5_report_search_roots", [])
        if isinstance(raw, str):
            return [raw] if raw.strip() else []
        if isinstance(raw, (list, tuple)):
            return [str(value) for value in raw if str(value).strip()]
        return []

    def run(self, ctx: OperationContext) -> OperationResult:
        configured = self._configured_roots(ctx)
        ctx.progress(0.05, "Søker etter Arkade 5-rapporter")

        result = import_discovered_arkade5_reports(
            work_operations=Path(ctx.work_operations),
            work_root=ctx.work_root,
            source_root=ctx.extraction_root,
            configured_roots=configured,
            imported_by={
                "mode": "automatic_workflow_operation",
                "job_id": str(ctx.metadata.get("job_id") or ""),
                "run_id": str(ctx.metadata.get("run_id") or ""),
            },
        )

        ctx.progress(1.0, "Arkade 5-søk/import fullført")

        if result["failed"]:
            warnings = [
                f"{row['file']}: {row['error']}"
                for row in result["failed_files"]
            ]
            return OperationResult(
                True,
                (
                    "Arkade 5: "
                    f"funnet={result['found']}, importert={result['imported']}, "
                    f"hoppet over={result['skipped']}, feil={result['failed']}."
                ),
                data=result,
                warnings=warnings,
            )

        if result["found"] == 0:
            message = "Arkade 5: ingen lokale Noark 5-rapporter funnet."
        else:
            message = (
                "Arkade 5: "
                f"funnet={result['found']}, importert={result['imported']}, "
                f"hoppet over={result['skipped']}."
            )

        return OperationResult(True, message, data=result)
