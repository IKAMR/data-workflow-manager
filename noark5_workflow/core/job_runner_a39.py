from __future__ import annotations

from noark5_workflow.core.job import JobStatus
from noark5_workflow.core.job_runner import JobRunOutcome, JobRunner


class A39JobRunner(JobRunner):
    """a39: XSD validation findings do not block the remaining workflow.

    A schema validation finding is different from a technical execution
    failure. The validate_xml_schema operation records the raw result with
    ok=False, preserving the failed validation as evidence. a39 then advances
    the execution cursor and continues with the next operation.

    Technical XSD failures (missing input/schema, exceptions, cancellation,
    output locking, etc.) remain blocking.
    """

    _NON_BLOCKING_OPERATION_ID = "validate_xml_schema"
    _NON_BLOCKING_MESSAGE_PREFIX = "XML/XSD-validering feilet med "

    def _failed_operation_is_xsd_validation(self, job) -> bool:
        index = int(getattr(job, "next_operation_index", 0) or 0)
        workflow_ids = list(getattr(job, "workflow_ids", ()) or ())
        return (
            0 <= index < len(workflow_ids)
            and workflow_ids[index] == self._NON_BLOCKING_OPERATION_ID
        )

    def run(
        self,
        job,
        *,
        progress_cb=None,
        log_cb=None,
        cancelled_cb=None,
        state_cb=None,
    ) -> JobRunOutcome:
        # JobRunner replaces job.message with "Workflow stoppet med feil" after
        # a failed operation. Therefore the operation result message must be
        # observed at the log boundary before that final status message replaces
        # it. This also keeps the distinction between a real schema finding and
        # a technical XSD execution failure.
        xsd_finding_seen = False

        def first_log(message: str) -> None:
            nonlocal xsd_finding_seen
            text = str(message or "")
            if text.startswith(self._NON_BLOCKING_MESSAGE_PREFIX):
                xsd_finding_seen = True
            if log_cb:
                log_cb(text)

        outcome = super().run(
            job,
            progress_cb=progress_cb,
            log_cb=first_log,
            cancelled_cb=cancelled_cb,
            state_cb=state_cb,
        )

        if (
            outcome.ok
            or not xsd_finding_seen
            or not self._failed_operation_is_xsd_validation(job)
        ):
            return outcome

        failed_index = int(job.next_operation_index)

        # The failed raw validation result/report is already persisted by the
        # executor. Advance only the execution cursor so the remaining workflow
        # can continue.
        job.mark_operation_completed(failed_index)
        job.status = JobStatus.READY
        job.message = "XSD-avvik registrert - workflow fortsetter"

        if log_cb:
            log_cb(
                "AVVIK: XML/XSD-valideringen fant skjemafeil. "
                "Resultatet er lagret, og workflow fortsetter med neste operasjon."
            )
        if state_cb:
            state_cb(job)

        continued = super().run(
            job,
            progress_cb=progress_cb,
            log_cb=log_cb,
            cancelled_cb=cancelled_cb,
            state_cb=state_cb,
        )

        if continued.ok and job.status == JobStatus.OK:
            job.message = "Workflow fullført med XSD-avvik"
            if log_cb:
                log_cb(job.message)
            if state_cb:
                state_cb(job)
            return JobRunOutcome(True, True)

        # A later failure remains authoritative. The earlier XSD finding is
        # already preserved in the raw result/report.
        return continued
