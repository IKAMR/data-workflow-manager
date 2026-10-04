from __future__ import annotations

from types import SimpleNamespace

from noark5_workflow.core.context import OperationContext
from noark5_workflow.core.operation import BaseOperation, ExecutionTarget, OperationDefinition
from noark5_workflow.core.result import OperationResult
from noark5_workflow.external_tools.arkade5_auto_import import import_arkade5_run_outputs
from noark5_workflow.external_tools.arkade5_jobs import (
    ARKADE5_NOARK5,
    ARKADE5_PRONOM,
    build_arkade5_plan,
    run_arkade5_plan,
)


class _Arkade5WorkflowOperation(BaseOperation):
    raw_result_record = True
    arkade_operation: str = ""

    def can_run(self, ctx: OperationContext) -> tuple[bool, str]:
        if ctx.work_operations is None:
            return False, "Work - operations må være definert."
        if ctx.extraction_root is None:
            return False, "Source - extraction må være definert."
        cli_path = str(ctx.settings.get("arkade5_cli_path") or "").strip()
        if not cli_path:
            return False, "Arkade 5 CLI må være konfigurert i Setup."
        return True, ""

    def _job_projection(self, ctx: OperationContext):
        return SimpleNamespace(
            job_id=str(ctx.metadata.get("job_id") or "JOB"),
            name=str(ctx.metadata.get("job_name") or ctx.metadata.get("name") or "Arkade 5"),
            active_extraction_root=ctx.extraction_root,
            source_extraction=ctx.extraction_root,
            work_operations=ctx.work_operations,
        )

    def run(self, ctx: OperationContext) -> OperationResult:
        ctx.progress(0.02, f"Forbereder {self.definition.name}")
        try:
            plans = build_arkade5_plan(
                ctx.settings,
                [self._job_projection(ctx)],
                [self.arkade_operation],
            )
        except Exception as exc:
            return OperationResult(False, f"Kunne ikke forberede Arkade 5: {exc}")

        if not plans:
            return OperationResult(
                False,
                "Arkade 5-kjøringen kunne ikke planlegges for denne jobben. Kontroller Source - extraction og Work - operations.",
            )

        def on_progress(index, total, plan, status):
            fraction = 0.05 if status == "starter" else 0.82
            ctx.progress(fraction, f"Arkade 5: {status}")

        def on_output(index, total, plan, stream, text):
            line = str(text or "").rstrip()
            if line:
                ctx.log(f"[Arkade 5/{stream}] {line}")

        try:
            summary = run_arkade5_plan(
                ctx.settings,
                plans,
                on_progress=on_progress,
                on_output=on_output,
                cancelled_cb=ctx.cancelled,
            )
        except Exception as exc:
            return OperationResult(False, f"Arkade 5 kunne ikke kjøres: {exc}")

        if ctx.cancelled():
            return OperationResult(False, "Arkade 5-kjøringen ble avbrutt av bruker.")

        run = summary.runs[0] if summary.runs else None
        if run is None or not run.ok:
            message = run.message if run is not None else "Ingen Arkade 5-kjøring ble utført."
            return OperationResult(False, f"Arkade 5 feilet teknisk: {message}")

        ctx.progress(0.86, "Importerer Arkade 5-evidens")
        try:
            imported = import_arkade5_run_outputs(
                summary,
                on_progress=ctx.log,
            )
        except Exception as exc:
            return OperationResult(
                False,
                f"Arkade 5 fullførte teknisk, men automatisk import feilet: {exc}",
                data={"cli_succeeded": True},
            )

        ctx.progress(1.0, f"{self.definition.name} fullført")
        outputs = []
        if run.plan is not None:
            outputs.append(str(run.plan.output_dir))

        warnings = [item.message for item in imported.items if item.message]
        message = (
            f"Arkade 5 fullført teknisk. Nye rapporter importert: {imported.imported}; "
            f"allerede importert: {imported.already_imported}; "
            f"PRONOM koblet: {imported.pronom_attached}; "
            f"importfeil: {imported.failed + imported.pronom_failed}."
        )
        return OperationResult(
            ok=(imported.failed + imported.pronom_failed) == 0,
            message=message,
            data={
                "arkade_operation": self.arkade_operation,
                "cli_succeeded": True,
                "imported": imported.imported,
                "already_imported": imported.already_imported,
                "pronom_attached": imported.pronom_attached,
                "pronom_unattached": imported.pronom_unattached,
                "import_failed": imported.failed + imported.pronom_failed,
            },
            warnings=warnings,
            outputs=outputs,
        )


class Arkade5Noark5TestOperation(_Arkade5WorkflowOperation):
    definition = OperationDefinition(
        operation_id="arkade5_noark5_test",
        name="Arkade 5 – Noark 5-test",
        description=(
            "Kjør Arkade 5 CLI sin Noark 5-test på jobbens Source - extraction og importer "
            "resultatet automatisk som ekstern evidens på samme DWM-jobb."
        ),
        execution_target=ExecutionTarget.EITHER,
        category="Systemspesifikt",
    )
    arkade_operation = ARKADE5_NOARK5


class Arkade5PronomAnalysisOperation(_Arkade5WorkflowOperation):
    definition = OperationDefinition(
        operation_id="arkade5_pronom_analysis",
        name="Arkade 5 – PRONOM-analyse",
        description=(
            "Kjør Arkade 5 CLI sin filformatanalyse (Siegfried/PRONOM) på jobbens "
            "Source - extraction og koble statistikken til jobbens Arkade-evidens."
        ),
        execution_target=ExecutionTarget.EITHER,
        category="Systemspesifikt",
    )
    arkade_operation = ARKADE5_PRONOM
