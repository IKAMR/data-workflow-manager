from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace

from noark5_workflow.core.context import OperationContext
from noark5_workflow.core.operation import BaseOperation, ExecutionTarget, OperationDefinition
from noark5_workflow.core.result import OperationResult
from noark5_workflow.external_tools.arkade5_auto_import import import_arkade5_run_outputs
from noark5_workflow.external_tools.arkade5_jobs import (
    ARKADE5_NOARK5,
    ARKADE5_PRONOM,
    Arkade5BatchRunSummary, Arkade5JobRun,
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
        from app import validator_failure_v027_a22 as a22

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

        from app.recovery_v027_a19 import verified_pronom_run
        reuse = None
        if self.arkade_operation == ARKADE5_PRONOM and ctx.metadata.get("a19_resume_operation"):
            reuse = verified_pronom_run(plans[0])
            if reuse is None and a22.has_pronom_history(plans[0], ctx.settings):
                return OperationResult(False, "A19: tidligere PRONOM-output kan ikke verifiseres. Velg eksplisitt ny deljobb ved behov.")
        before = None
        try:
            if self.arkade_operation == ARKADE5_PRONOM and reuse is None:
                before = a22.file_snapshot(plans[0].output_dir)
            if reuse is not None:
                ctx.log("A19: gjenbruker bevart Arkade PRONOM-kjøring " + reuse)
                summary = Arkade5BatchRunSummary((Arkade5JobRun(
                    plan=replace(plans[0], run_id=reuse), ok=True,
                    message="Gjenbrukt " + reuse),))
            else:
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
            details = {}
            if self.arkade_operation == ARKADE5_NOARK5 and run is not None:
                failure = a22.access_failure(run, ctx.extraction_root)
                if failure is not None:
                    details['a22_validator_failure'] = failure
            return OperationResult(False, f"Arkade 5 feilet teknisk: {message}", data=details)

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

        outputs = []
        if run.plan is not None:
            outputs.append(str(run.plan.output_dir))

        warnings = [item.message for item in imported.items if item.message]
        missing_pronom = (
            self.arkade_operation == ARKADE5_PRONOM
            and imported.pronom_attached == 0
        )
        missing_noark = (self.arkade_operation == ARKADE5_NOARK5
                         and imported.imported + imported.already_imported == 0)
        if missing_noark:
            warnings.append('A150: CLI fullfort, men ingen Noark 5-rapport ble importert.')
        standalone = None
        if missing_pronom and imported.failed + imported.pronom_failed == 0:
            try:
                from noark5_workflow.core.work_paths import resolve_dwm_work_root
                from noark5_workflow.external_evidence.arkade5_pronom_standalone_v027_a20 import (
                    import_preserved_pronom, verify_standalone_reference,
                )
                settings = ctx.settings
                work = resolve_dwm_work_root(ctx.work_operations, settings=settings)
                uid = str(ctx.metadata.get('job_uid') or ctx.settings.get('_current_job_uid') or '')
                if not uid or run.plan is None:
                    raise ValueError('PRONOM mangler varig jobbidentitet eller kjoreplan')
                if reuse is None and not a22.fresh_output(before, a22.file_snapshot(run.plan.output_dir)):
                    raise ValueError('PRONOM-output mangler eller er ikke fornyet av denne kjøringen')
                ids = dict(job_id=run.plan.job_id, job_uid=uid)
                standalone = import_preserved_pronom(work, **ids, expected_run_id=run.plan.run_id)
                if not standalone or not verify_standalone_reference(work, standalone, **ids):
                    raise ValueError('Selvstendig PRONOM kunne ikke verifiseres')
                missing_pronom = False
                ctx.log('A22: Arkade PRONOM bevart som selvstendig evidens for samme kjøring.')
            except (OSError, ValueError, RuntimeError, TypeError, KeyError, AttributeError) as exc:
                standalone = None
                warnings.append('A22: ' + str(exc))
        if missing_pronom:
            output_location = outputs[0] if outputs else "ukjent output-mappe"
            detail = (
                "PRONOM-statistikk ble ikke koblet til Work, selv om Arkade CLI "
                "returnerte teknisk suksess. Kontroller at resultatmappen "
                f"{output_location} inneholder en fil med filformatinfo-statistikk*.csv, "
                "og undersøk loggen fra Arkade 5 PRONOM-analyse."
            )
            warnings.append(detail)
            ctx.log("[Arkade 5/PRONOM] " + detail)

        ctx.progress(1.0, f"{self.definition.name} fullført")
        message = (
            f"Arkade 5 fullført teknisk. Nye rapporter importert: {imported.imported}; "
            f"allerede importert: {imported.already_imported}; "
            f"PRONOM koblet: {imported.pronom_attached}; "
            f"importfeil: {imported.failed + imported.pronom_failed}."
        )
        if missing_noark:
            message += " Noark 5-rapport mangler; kontrollen er ikke dokumentert."
        if standalone:
            message += " PRONOM er bevart som selvstendig evidens."
        if missing_pronom:
            message += " PRONOM-evidens mangler; se kjørelogg og Arkade-output."
        return OperationResult(
            ok=(imported.failed + imported.pronom_failed) == 0 and not missing_pronom and not missing_noark,
            message=message,
            data={
                "arkade_operation": self.arkade_operation,
                "cli_succeeded": True,
                "reused_external_run": reuse,
                "imported": imported.imported,
                "already_imported": imported.already_imported,
                "pronom_attached": imported.pronom_attached,
                "pronom_unattached": imported.pronom_unattached,
                "pronom_statistics_missing": missing_pronom,
                "standalone_pronom": standalone,
                "noark_report_missing": missing_noark,
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
