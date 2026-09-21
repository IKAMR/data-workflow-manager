from __future__ import annotations

from noark5_workflow.core.job import Job, JobStatus
from .jobs_window_a18 import A18JobsWindow


_RECOVERABLE_STORAGE_PREFIX = "Lagring utilgjengelig - kan fortsette"
_IO_MARKERS = (
    "[Errno ",
    "[WinError ",
    "Input/output error",
    "I/O error",
    "Invalid argument",
    "The device is not ready",
    "The network name is no longer available",
    "The specified network name is no longer available",
)


def _looks_like_io_failure(message: str) -> bool:
    value = str(message or "")
    return any(marker.casefold() in value.casefold() for marker in _IO_MARKERS)


class A19JobsWindow(A18JobsWindow):
    """a16.3.1: recognise storage failures created before a16.3."""

    @staticmethod
    def _is_recoverable_storage_failure(job: Job) -> bool:
        if job.status != JobStatus.FAILED:
            return False
        message = str(job.message or "")
        return (
            message.startswith(_RECOVERABLE_STORAGE_PREFIX)
            or _looks_like_io_failure(message)
        )

    @staticmethod
    def _is_ready_to_run(job: Job) -> bool:
        if not job.workflow_ids:
            return False
        if job.status in {JobStatus.READY, JobStatus.WAITING}:
            return True
        return A19JobsWindow._is_recoverable_storage_failure(job)

    def _status_text(self, job: Job) -> str:
        if self._is_recoverable_storage_failure(job):
            return "Feil - kan fortsette"
        return super()._status_text(job)
