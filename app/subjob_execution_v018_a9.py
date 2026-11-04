"""Selective execution of one DWM operation, preserving its parent job state.

This mixin is GUI independent. It reuses A39JobRunner.run_operation() and
RunLogStore. A subjob gets its own durable event log and cannot silently
advance or reset the parent job's workflow cursor or completion status.
"""
from __future__ import annotations

from pathlib import Path

from app.application_api import DwmApiError
from app.run_log_history_v018_a8 import RunLogStore
from noark5_workflow.core.job import JobStatus


class SelectiveSubjobMixin:
    def run_subjob(self, job_id: str, operation_id: str, *,
                   allow_rerun: bool = False,
                   acknowledge_warnings: bool = False) -> bool:
        """Synchronously run one selected operation; caller owns worker thread.

        The operation can create its documented results in Work, but the parent
        job's overall status/progress/cursor remain untouched. Approval for
        previous execution and preflight warnings is explicit.
        """
        report = self.preflight_subjob(job_id, operation_id)
        if report.errors:
            raise DwmApiError("Deljobb blokkert: " + "; ".join(i.message for i in report.errors))
        if report.actions:
            raise DwmApiError("Work/AIP ma klargjores og godkjennes for kjoring.")
        if report.warnings and not acknowledge_warnings:
            raise DwmApiError("Avvik krever godkjenning: " + "; ".join(i.message for i in report.warnings))

        with self._guard:
            self._assert_idle()
            if self._path is None:
                raise DwmApiError("Lagre jobblisten for du kjorer en deljobb.")
            job = self._require_job(job_id)
            if operation_id not in job.workflow_ids:
                raise DwmApiError("Deljobben finnes ikke i arbeidsflyten: " + operation_id)
            if job.status in (JobStatus.RUNNING, JobStatus.WAITING):
                raise DwmApiError("Kan ikke kjore deljobb mens hovedjobben kjorer eller venter.")
            position = job.workflow_ids.index(operation_id) + 1
            if (position <= job.next_operation_index or job.status == JobStatus.OK) and not allow_rerun:
                raise DwmApiError("Deljobben er allerede fullfort; omkjoring krever godkjenning.")
            problems = self.check_storage()
            if problems:
                raise DwmApiError("Ugyldig lagringsoppsett: " + "; ".join(problems))
            job_position = next(i for i, current in enumerate(self._batch.jobs(), 1)
                                if current.job_id == job_id)
            view = self._view(job, job_position)
            if not view.effective_work_operations:
                raise DwmApiError("Deljobben mangler godkjent Work operations.")
            work_path = Path(view.effective_work_operations)
            name = self._registry_catalog().get(operation_id, (operation_id, ""))[0]
            self._running = True
            self._cancel.clear()
            self._active_job_id = job_id
            job._effective_work_operations = work_path
            parent_state = (job.status, job.progress, job.next_operation_index, job.message)

        writer = None
        self._a8_log_warning = ""
        try:
            try:
                writer = RunLogStore(work_path, job_id).begin(
                    job_name=view.name, job_list_path=str(self._path),
                    run_kind="subjob", operation_id=operation_id,
                    operation_name=name,
                    job_uid=str(getattr(job, "job_uid", "") or ""),
                )
            except OSError as exc:
                raise DwmApiError("Kan ikke opprette deljobblogg i Work: " + str(exc)) from exc
            self._a8_run_writer = writer
            job._active_run_id = writer.run_id
            job._active_run_kind = "subjob"
            self._emit("subjob.started", job, message=f"Deljobb {position}: {name}", progress=0.0)

            def on_log(message: str) -> None:
                self._emit("subjob.log", job, message=message)

            def on_progress(fraction: float, message: str) -> None:
                self._emit("subjob.progress", job, message=message, progress=float(fraction))

            def on_state(updated) -> None:
                # Not a parent job status transition: do not write .n5jobs.
                self._emit("subjob.state", updated, message=updated.message)

            runtime_settings = dict(self.settings)
            runtime_settings["_current_run_id"] = writer.run_id
            runtime_settings["_current_job_uid"] = str(getattr(job, "job_uid", "") or "")
            runtime_settings["_current_run_kind"] = "subjob"
            runner = self._runner_factory(runtime_settings)
            method = getattr(runner, "run_operation", None)
            if not callable(method):
                raise DwmApiError("Arbeidsmotoren stotter ikke selektiv kjoring.")
            result = method(
                job, operation_id, progress_cb=on_progress,
                log_cb=on_log, cancelled_cb=self._cancel.is_set,
                state_cb=on_state,
            )
            ok = bool(result.ok)
            job.status, job.progress, job.next_operation_index, job.message = parent_state
            writer.append("DELJOBB RESULTAT: " + ("OK" if ok else "FEIL"))
            writer.finish("finished" if ok else "failed")
            self._emit("subjob.finished", job,
                       message=name + (": OK" if ok else ": FEIL"),
                       progress=1.0 if ok else None)
            return ok
        except Exception as exc:
            if writer is not None:
                try:
                    writer.append("DELJOBB FEIL: " + str(exc))
                    writer.finish("failed")
                except OSError:
                    pass
            self._emit("subjob.error", job, message=str(exc))
            raise
        finally:
            job.status, job.progress, job.next_operation_index, job.message = parent_state
            self._a8_run_writer = None
            for attribute in ("_active_run_id", "_active_run_kind", "_effective_work_operations"):
                if hasattr(job, attribute):
                    delattr(job, attribute)
            with self._guard:
                self._running = False
                self._cancel.clear()
