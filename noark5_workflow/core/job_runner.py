from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Callable

from noark5_workflow.core.context import OperationContext
from noark5_workflow.core.job import Job, JobStatus
from noark5_workflow.core.output_lock import OutputLock, OutputLockedError
from noark5_workflow.sources.noark5_extraction import Noark5Extraction

_TERMINAL_STATUSES = {JobStatus.OK, JobStatus.FAILED, JobStatus.SKIPPED}


@dataclass(frozen=True)
class JobRunOutcome:
    ok: bool
    persist_recommended: bool = False


class JobContinueError(RuntimeError):
    """Raised when an explicit continue request is invalid for the job state."""


class JobRunner:
    """GUI-independent execution of one Job through an executor."""

    def __init__(self, registry, executor, settings: dict, *, source_factory=Noark5Extraction.detect) -> None:
        self.registry = registry
        self.executor = executor
        self.settings = settings
        self.source_factory = source_factory

    def _configure_operation_for_job(self, job: Job, operation_id: str):
        operation = self.registry.get(operation_id)
        params = job.get_operation_params(operation_id)
        configure = getattr(operation, "configure", None)
        if params and callable(configure):
            configure(params)
        return operation

    def _context_for_job(self, job: Job, *, progress_cb=None, log_cb=None, cancelled_cb=None):
        extraction_root = job.active_extraction_root
        source = self.source_factory(extraction_root)
        ctx = OperationContext(
            extraction_root=extraction_root,
            source=source,
            output_root=job.output_root,
            work_root=job.work_root,
            work_content=job.work_content,
            work_operations=job.work_operations,
            archive_root=job.archive_root,
            settings=self.settings,
            progress_cb=progress_cb,
            log_cb=log_cb,
            cancelled_cb=cancelled_cb,
        )
        ctx.metadata["job_id"] = job.job_id
        ctx.metadata["run_id"] = str(self.settings.get("_current_run_id", "") or "")
        return ctx

    def _sync_dias_output(self, job: Job, op_id: str, operation, log) -> None:
        if op_id != "dias_package":
            return
        params = job.get_operation_params(op_id)
        configured_output = str(params.get("output_dir", "") or "").strip()
        archive_output = job.archive_root or job.output_root
        job_output = str(archive_output) if archive_output is not None else ""
        if job_output and configured_output != job_output:
            params["output_dir"] = job_output
            job.set_operation_params(op_id, params)
            operation.configure(params)
            log(f"DIAS-utdata synkronisert fra jobb: {job_output}")

    def continue_job(self, job: Job, *, progress_cb=None, log_cb=None, cancelled_cb=None, state_cb=None) -> JobRunOutcome:
        if job.status != JobStatus.WAITING:
            raise JobContinueError(f"Jobben kan ikke fortsettes fra status: {job.status.value}")
        total = len(job.workflow_ids)
        next_index = max(0, min(int(job.next_operation_index), total))
        if next_index <= 0 or next_index >= total:
            raise JobContinueError("Jobben har ikke en gyldig neste operasjon å fortsette med")
        previous_operation_id = job.workflow_ids[next_index - 1]
        if not job.has_checkpoint(previous_operation_id):
            raise JobContinueError("Jobben står som ventende, men execution cursor følger ikke et kontrollpunkt")
        return self.run(
            job,
            progress_cb=progress_cb,
            log_cb=log_cb,
            cancelled_cb=cancelled_cb,
            state_cb=state_cb,
        )

    def run_operation(
        self,
        job: Job,
        operation_id: str,
        *,
        progress_cb=None,
        log_cb=None,
        cancelled_cb=None,
        state_cb=None,
    ) -> JobRunOutcome:
        """Run exactly one existing workflow operation without moving the job cursor.

        This is a selective re-run, not a partial workflow resume. The Job's
        overall status/progress/cursor are deliberately preserved. Raw results
        are still persisted by the executor and therefore receive a new
        result_id while earlier raw results remain append-only history.
        """
        if operation_id not in job.workflow_ids:
            raise ValueError(f"Operasjonen finnes ikke i jobbens workflow: {operation_id}")

        def log(message: str) -> None:
            if log_cb:
                log_cb(message)

        snapshot = (job.status, job.progress, job.next_operation_index, job.message)
        position = job.workflow_ids.index(operation_id) + 1
        total = len(job.workflow_ids)
        output_lock = None
        try:
            if cancelled_cb and cancelled_cb():
                log("SELEKTIV GJENKJØRING AVBRUTT før start")
                return JobRunOutcome(False, False)

            if job.output_root:
                output_lock = OutputLock(job.output_root, job.job_id)
                output_lock.acquire()
                log(f"Utdata låst: {job.output_root}")

            ctx = self._context_for_job(
                job,
                progress_cb=progress_cb,
                log_cb=log_cb,
                cancelled_cb=cancelled_cb,
            )
            operation = self._configure_operation_for_job(job, operation_id)
            self._sync_dias_output(job, operation_id, operation, log)

            log(
                f"SELEKTIV GJENKJØRING: operasjon {position} av {total} - "
                f"{operation.definition.name} [{operation_id}]"
            )
            result = self.executor.execute(operation, ctx)
            log(result.message)
            for warning in result.warnings:
                log(f"ADVARSEL: {warning}")
            if result.data:
                log(json.dumps(result.data, ensure_ascii=False, indent=2))
            log(f"{'OK' if result.ok else 'FEIL'} SELEKTIV: {operation.definition.name}")
            if state_cb:
                state_cb(job)
            return JobRunOutcome(bool(result.ok), True)
        except OutputLockedError as exc:
            log(f"FEIL SELEKTIV: {exc}")
            return JobRunOutcome(False, False)
        except Exception as exc:
            log(f"FEIL SELEKTIV: {exc}")
            return JobRunOutcome(False, False)
        finally:
            job.status, job.progress, job.next_operation_index, job.message = snapshot
            if output_lock is not None:
                output_lock.release()
            if state_cb:
                state_cb(job)

    def run(self, job: Job, *, progress_cb=None, log_cb=None, cancelled_cb=None, state_cb=None) -> JobRunOutcome:
        def log(message: str) -> None:
            if log_cb:
                log_cb(message)

        def state_changed() -> None:
            if state_cb:
                state_cb(job)

        op_ids = list(job.workflow_ids)
        if not op_ids:
            job.status = JobStatus.SKIPPED
            job.message = "Ingen operasjoner i workflow"
            log("HOPPET OVER: Ingen operasjoner i workflow")
            state_changed()
            return JobRunOutcome(True, False)

        # READY + partial cursor is reserved for an append-only workflow
        # extension. It is not checkpoint continuation.
        failed_retry = (
            job.status == JobStatus.FAILED
            and 0 < int(job.next_operation_index or 0) < len(op_ids)
            and str(job.message or "").startswith("Fortsettelse feilet - prøv igjen fra operasjon ")
        )
        start_index = (
            job.next_operation_index
            if job.status in {JobStatus.WAITING, JobStatus.READY} or failed_retry
            else 0
        )
        start_index = max(0, min(start_index, len(op_ids)))
        if job.status in _TERMINAL_STATUSES and not failed_retry:
            start_index = 0
            job.next_operation_index = 0
            job.progress = 0.0
        if start_index >= len(op_ids):
            start_index = 0
            job.next_operation_index = 0
            job.progress = 0.0
        resuming = start_index > 0
        job.status = JobStatus.RUNNING
        job.message = (
            f"Workflow fortsetter fra operasjon {start_index + 1}"
            if resuming
            else "Workflow startet"
        )
        log(job.message)
        state_changed()
        output_lock = None
        try:
            if job.output_root:
                output_lock = OutputLock(job.output_root, job.job_id)
                output_lock.acquire()
                log(f"Utdata låst: {job.output_root}")
            ctx = self._context_for_job(
                job,
                progress_cb=progress_cb,
                log_cb=log_cb,
                cancelled_cb=cancelled_cb,
            )
            total = len(op_ids)
            all_ok = True
            for zero_index in range(start_index, total):
                op_id = op_ids[zero_index]
                if cancelled_cb and cancelled_cb():
                    job.status = JobStatus.SKIPPED
                    job.message = "Avbrutt"
                    log("AVBRUTT før neste operasjon")
                    state_changed()
                    return JobRunOutcome(False, False)
                operation = self._configure_operation_for_job(job, op_id)
                self._sync_dias_output(job, op_id, operation, log)
                log(f"START: {operation.definition.name}")
                result = self.executor.execute(operation, ctx)
                all_ok = all_ok and result.ok
                log(result.message)
                for warning in result.warnings:
                    log(f"ADVARSEL: {warning}")
                if result.data:
                    log(json.dumps(result.data, ensure_ascii=False, indent=2))
                log(f"{'OK' if result.ok else 'FEIL'}: {operation.definition.name}")
                job.message = result.message
                if not result.ok:
                    job.next_operation_index = zero_index
                    job.progress = zero_index / total
                    state_changed()
                    break
                job.mark_operation_completed(zero_index)
                state_changed()
                checkpoint_allowed = bool(getattr(operation, "allow_checkpoint", True))
                if checkpoint_allowed and job.has_checkpoint(op_id) and zero_index < total - 1:
                    job.status = JobStatus.WAITING
                    job.message = f"Venter ved kontrollpunkt etter {operation.definition.name}"
                    log(job.message)
                    state_changed()
                    return JobRunOutcome(True, True)
            if all_ok:
                job.status = JobStatus.OK
                job.progress = 1.0
                job.next_operation_index = total
                job.message = "Workflow fullført"
            else:
                job.status = JobStatus.FAILED
                job.message = (
                    f"Fortsettelse feilet - prøv igjen fra operasjon {job.next_operation_index + 1}"
                    if resuming and 0 <= job.next_operation_index < total
                    else "Workflow stoppet med feil"
                )
            log(job.message)
            state_changed()
            return JobRunOutcome(all_ok, True)
        except OutputLockedError as exc:
            job.status = JobStatus.FAILED
            job.message = (f"Fortsettelse feilet - prøv igjen fra operasjon {start_index + 1}" if resuming else str(exc))
            log(f"FEIL: {exc}")
            state_changed()
            return JobRunOutcome(False, False)
        except Exception as exc:
            job.status = JobStatus.FAILED
            job.message = (f"Fortsettelse feilet - prøv igjen fra operasjon {start_index + 1}" if resuming else str(exc))
            log(f"FEIL: {exc}")
            state_changed()
            return JobRunOutcome(False, False)
        finally:
            if output_lock is not None:
                output_lock.release()
