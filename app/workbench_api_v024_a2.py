"""v0.2.4-a2: explicit, Work-first resume of failures and reset commands.

All execution still uses the existing DwmWorkbenchAPI, preflight and
A39JobRunner. No source, result history or checkpoint files are deleted.
"""
from __future__ import annotations

from app.application_api import DwmApiError
from app.job_run_actions_v024_a2 import ResumeOption, can_reset, resume_option
from app.workbench_api_v020_a2 import DwmWorkbenchAPI as _V020WorkbenchAPI
from noark5_workflow.core.job import JobStatus
from app.recovery_v027_a19 import recover_completed_stop


class DwmWorkbenchAPI(_V020WorkbenchAPI):
    def resume_option_for_job(self, job_id: str):
        job = self._require_job(job_id)
        if job_id in self._unavailable_work_ids:
            return ResumeOption(reason='Work er frakoblet; koble til riktig arbeidsomr\u00e5de.')
        cursor = int(job.next_operation_index or 0)
        prev = bool(0 < cursor <= len(job.workflow_ids)
                    and job.has_checkpoint(job.workflow_ids[cursor - 1]))
        option = resume_option(status=job.status, cursor=cursor,
                               total=len(job.workflow_ids),
                               previous_checkpoint=prev, message=job.message)
        if option.mode == 'failed_operation' and job_id not in self._work_references:
            return ResumeOption(reason='Feilet jobb mangler verifisert Work-historikk.')
        # Read-only preview: do not move the durable cursor until the operator
        # confirms Continue. Show the actual next operation in both GUI modes.
        if option.allowed and job.status == JobStatus.SKIPPED:
            ref = self._work_references.get(job_id)
            if ref is not None and recover_completed_stop(job, ref.parent):
                return ResumeOption(option.mode, cursor + 1, option.total)
        return option

    def run_job(self, job_id: str, *, allow_rerun: bool = False,
                continue_waiting: bool = False,
                acknowledge_warnings: bool = False) -> bool:
        """Interpret an explicit Continue click for checkpoint or failed cursor.

        The legacy boolean is used ONLY by the existing GUI worker when the
        operator selects Continue; it does not make ordinary Run auto-resume.
        """
        if not continue_waiting:
            return super().run_job(
                job_id, allow_rerun=allow_rerun,
                continue_waiting=False,
                acknowledge_warnings=acknowledge_warnings)
        if allow_rerun:
            raise DwmApiError('Fortsett og start p\u00e5 nytt kan ikke velges samtidig.')
        with self._guard:
            self._assert_idle()
            option = self.resume_option_for_job(job_id)
        if not option.allowed:
            raise DwmApiError('Fortsett er ikke tilgjengelig: ' + option.reason)
        if option.mode == 'checkpoint':
            return super().run_job(
                job_id, allow_rerun=False, continue_waiting=True,
                acknowledge_warnings=acknowledge_warnings)
        if option.mode == 'partial_ready':
            # The core already knows how to run READY from a valid partial
            # cursor. Keep the existing Work evidence and execution cursor.
            return super().run_job(
                job_id, allow_rerun=False, continue_waiting=False,
                acknowledge_warnings=acknowledge_warnings)

        # A FAILED job cannot enter the old checkpoint-only continue path.
        # Perform the SAME preflight without modifying the job, then record an
        # explicit Work event before changing FAILED to READY. The ordinary
        # runner will resume from the failed operation's zero-based cursor.
        report = self.preflight_job(job_id)
        if report.errors:
            raise DwmApiError('Kontroll f\u00f8r fortsettelse feilet: ' + '; '.join(
                issue.message for issue in report.errors))
        if report.actions:
            raise DwmApiError('Work m\u00e5 klargj\u00f8res f\u00f8r fortsettelse.')
        if report.warnings and not acknowledge_warnings:
            raise DwmApiError('Avvik m\u00e5 godkjennes f\u00f8r fortsettelse.')
        with self._guard:
            self._assert_idle()
            job = self._require_job(job_id)
            current = self.resume_option_for_job(job_id)
            if current != option:
                raise DwmApiError('Jobbstatus ble endret f\u00f8r fortsettelse. Pr\u00f8v p\u00e5 nytt.')
            previous = (job.status, job.message, self._dirty, job.next_operation_index, job.progress)
            if option.index != job.next_operation_index:
                # The read-only plan was revalidated inside the guard above.
                if job.status != JobStatus.SKIPPED or option.index != job.next_operation_index + 1:
                    raise DwmApiError('Ugyldig gjenoppretting av kjoremarkor.')
                job.mark_operation_completed(job.next_operation_index)
            job.status = JobStatus.READY
            job.message = f'Fortsettelse fra deljobb {job.next_operation_index + 1} av {option.total}'
            self._dirty = True
            try:
                # Work is canonical and its event history is append-only.
                # If the write fails, do not allow a new run from uncertain state.
                if job_id not in self._work_references:
                    raise DwmApiError('Kan ikke fortsette en feilet jobb uten verifisert Work-historikk.')
                self._persist_work_event(job, 'job.resume_requested', job.message)
            except Exception:
                job.status, job.message, self._dirty, job.next_operation_index, job.progress = previous
                raise
        return super().run_job(
            job_id, allow_rerun=False, continue_waiting=False,
            acknowledge_warnings=acknowledge_warnings)

    def reset_job_execution(self, job_id: str):
        """Reset ONLY cursor/status; preserve Source, Work, files and history."""
        with self._guard:
            self._assert_idle()
            job = self._require_job(job_id)
            if job_id in self._unavailable_work_ids:
                raise DwmApiError('Work er frakoblet. Ingen jobbstatus er endret.')
            if not can_reset(status=job.status, cursor=job.next_operation_index,
                             progress=job.progress):
                raise DwmApiError('Jobben har ingen kj\u00f8restatus som kan nullstilles.')
            previous = (job.status, job.message, job.progress,
                        job.next_operation_index, self._dirty, self._active_job_id)
            self._active_job_id = job_id
            job.reset_execution('Manuelt nullstilt - klar for ny kj\u00f8ring')
            self._dirty = True
            try:
                self._persist_work_event(job, 'job.execution_reset',
                                         'Kun status og mark\u00f8r nullstilt; gamle resultater beholdes')
            except Exception:
                (job.status, job.message, job.progress,
                 job.next_operation_index, self._dirty, self._active_job_id) = previous
                raise
        # The authoritative Work state is saved first. The disposable .n5jobs
        # index can be saved afterwards; disconnected index storage must never
        # undo a successful, durably recorded reset.
        self._v024_a2_reset_index_warning = ''
        if self._path is not None:
            try:
                self.save_job_list()
            except (OSError, DwmApiError) as exc:
                self._dirty = True
                self._v024_a2_reset_index_warning = (
                    'Jobben er nullstilt i Work, men .n5jobs kunne ikke oppdateres: ' + str(exc))
                self._emit('joblist.index_write_failed', job,
                           message=self._v024_a2_reset_index_warning)
        self._emit('job.execution_reset', job, message=job.message)
        return self.job_details(job_id)
