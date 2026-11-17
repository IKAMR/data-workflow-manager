from __future__ import annotations

from noark5_workflow.core.job import JobStatus
from noark5_workflow.core.job_runner import JobRunOutcome, JobRunner


class A39JobRunner(JobRunner):
    """a39: real XSD findings may be nonblocking; a7: guard dependencies."""

    _NON_BLOCKING_OPERATION_ID = "validate_xml_schema"
    _NON_BLOCKING_MESSAGE_PREFIX = "XML/XSD-validering feilet med "

    def _failed_operation_is_xsd_validation(self, job) -> bool:
        index = int(getattr(job, 'next_operation_index', 0) or 0)
        ids = list(getattr(job, 'workflow_ids', ()) or ())
        return 0 <= index < len(ids) and ids[index] == self._NON_BLOCKING_OPERATION_ID

    def run_operation(self, job, operation_id, *, progress_cb=None, log_cb=None,
                      cancelled_cb=None, state_cb=None) -> JobRunOutcome:
        """Do not bypass required dependency completion with selective execution.

        A selective rerun preserves the main workflow cursor. Prerequisites must
        already belong to its completed prefix; evidence file presence alone
        does not imply that a prerequisite operation finished successfully.
        """
        from app.workflow_dependencies_v022_a7 import BY_ID, BY_NUMBER, validate_dependencies
        flow = tuple(getattr(job, 'workflow_ids', ()) or ())
        issues = validate_dependencies(flow)
        if operation_id in flow:
            spec = BY_ID.get(operation_id)
            if spec is not None:
                cursor = max(0, min(int(getattr(job, 'next_operation_index', 0) or 0), len(flow)))
                positions = {op: idx for idx, op in enumerate(flow)}
                for number in (*spec.follows, *spec.required):
                    prerequisite = BY_NUMBER[number].operation_id
                    if prerequisite in positions and positions[prerequisite] >= cursor:
                        issues += (f'{operation_id} krever fullfort A{number:03d} {prerequisite}.',)
        if issues:
            if log_cb:
                log_cb('BLOKKERT - selektiv deljobb: ' + ' | '.join(issues))
            return JobRunOutcome(False, False)
        return super().run_operation(
            job, operation_id, progress_cb=progress_cb, log_cb=log_cb,
            cancelled_cb=cancelled_cb, state_cb=state_cb,
        )

    def run(self, job, *, progress_cb=None, log_cb=None,
            cancelled_cb=None, state_cb=None) -> JobRunOutcome:
        from app.workflow_dependencies_v022_a7 import validate_dependencies
        issues = validate_dependencies(getattr(job, 'workflow_ids', ()) or ())
        if issues:
            message = ('Ugyldig rekkefolge/avhengigheter i deljobblisten: '
                       + ' | '.join(issues))
            if log_cb:
                log_cb('BLOKKERT: ' + message)
            job.status = JobStatus.FAILED
            job.message = message
            if state_cb:
                state_cb(job)
            return JobRunOutcome(False, False)

        xsd_finding_seen = False

        def first_log(message: str) -> None:
            nonlocal xsd_finding_seen
            text = str(message or '')
            if text.startswith(self._NON_BLOCKING_MESSAGE_PREFIX):
                xsd_finding_seen = True
            if log_cb:
                log_cb(text)

        outcome = super().run(
            job, progress_cb=progress_cb, log_cb=first_log,
            cancelled_cb=cancelled_cb, state_cb=state_cb,
        )
        if outcome.ok or not xsd_finding_seen or not self._failed_operation_is_xsd_validation(job):
            return outcome

        failed_index = int(job.next_operation_index)
        job.mark_operation_completed(failed_index)
        job.status = JobStatus.READY
        job.message = 'XSD-avvik registrert - workflow fortsetter'
        if log_cb:
            log_cb('AVVIK: XML/XSD-valideringen fant skjemafeil. '
                   'Resultatet er lagret, og workflow fortsetter med neste operasjon.')
        if state_cb:
            state_cb(job)
        continued = super().run(
            job, progress_cb=progress_cb, log_cb=log_cb,
            cancelled_cb=cancelled_cb, state_cb=state_cb,
        )
        if continued.ok and job.status == JobStatus.OK:
            job.message = 'Workflow fullført med XSD-avvik'
            if log_cb:
                log_cb(job.message)
            if state_cb:
                state_cb(job)
            return JobRunOutcome(True, True)
        return continued
