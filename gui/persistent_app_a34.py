from __future__ import annotations

import re

from . import theme
from .persistent_app_a33 import WorkflowApp as A33WorkflowApp
from noark5_workflow.core.job import JobStatus


_TEST_START_RE = re.compile(
    r"TEST START\s+\d+/\d+\s+\|\s*([^|]+)\|\s*([^|]+)\|\s*([^|]+)\|\s*(.+)$"
)
_RESULT_FILE_RE = re.compile(r"[\\/](kdrs_[a-z0-9_]+)\.json[\'\"]?$", re.IGNORECASE)


class WorkflowApp(A33WorkflowApp):
    """a16.4.6: make exact stop/failure context visible in the GUI."""

    def __init__(self) -> None:
        super().__init__()
        self.workflow_panel.status_detail_provider = self._a1646_status_detail
        self.workflow_panel.refresh()

    @staticmethod
    def _operation_position(job, operation_id: str) -> tuple[int, int]:
        ids = list(getattr(job, "workflow_ids", ()) or ())
        try:
            return ids.index(operation_id) + 1, len(ids)
        except ValueError:
            return 0, len(ids)

    @staticmethod
    def _failure_test_context(job) -> str:
        entries = list(getattr(job, "log_entries", ()) or ())
        for line in reversed(entries):
            match = _TEST_START_RE.search(str(line))
            if match:
                test_id, short_id, noark_ref, title = [
                    part.strip() for part in match.groups()
                ]
                return f"{test_id} | {short_id} | {noark_ref} | {title}"

        message = str(getattr(job, "message", "") or "")
        match = _RESULT_FILE_RE.search(message)
        if match:
            stem = match.group(1)
            suffix = stem.split("_", 1)[1] if "_" in stem else stem
            return f"{stem.replace('_', '.')} | {suffix.upper()}"

        return ""

    def _failure_summary(self, job) -> str:
        if job is None:
            return ""

        ids = list(getattr(job, "workflow_ids", ()) or ())
        cursor = int(getattr(job, "next_operation_index", 0) or 0)
        if not ids or cursor < 0 or cursor >= len(ids):
            return str(getattr(job, "message", "") or "")

        operation_id = ids[cursor]
        try:
            operation = self.registry.get(operation_id)
            operation_name = operation.definition.name
        except Exception:
            operation_name = operation_id

        pos, total = self._operation_position(job, operation_id)
        test_context = self._failure_test_context(job)
        reason = str(getattr(job, "message", "") or "").strip()

        parts = [f"Stoppet på operasjon {pos}/{total}: {operation_name}"]
        if test_context:
            parts.append(f"Test: {test_context}")
        if reason:
            parts.append(f"Årsak: {reason}")
        return "\n".join(parts)

    def _a1646_status_detail(self, operation_id: str) -> str:
        job = self.current_job
        if job is None:
            return ""

        ids = list(getattr(job, "workflow_ids", ()) or ())
        try:
            index = ids.index(operation_id)
        except ValueError:
            return ""

        cursor = int(getattr(job, "next_operation_index", 0) or 0)
        status = getattr(job, "status", None)
        message = str(getattr(job, "message", "") or "")

        if status == JobStatus.FAILED and index == cursor:
            return self._failure_summary(job)

        if (
            status == JobStatus.WAITING
            and index == cursor
            and message.startswith("Gjenopptar fra operasjon")
        ):
            return self._failure_summary(job)

        return ""

    def _runner_state_changed(self, job) -> None:
        if getattr(job, "status", None) == JobStatus.FAILED:
            summary = self._failure_summary(job)
            if summary and not str(job.message or "").startswith("Stoppet på operasjon"):
                job.message = summary
        super()._runner_state_changed(job)

    def _execute_job(self, job, *, batch_mode: bool) -> bool:
        ok = super()._execute_job(job, batch_mode=batch_mode)

        if not ok and getattr(job, "status", None) == JobStatus.FAILED:
            summary = self._failure_summary(job)
            if summary:
                job.message = summary
                try:
                    self._job_log(
                        job,
                        "STOPPDETALJ: " + summary.replace("\n", " | "),
                    )
                except Exception:
                    pass
                try:
                    self.after(
                        0,
                        lambda j=job: self._refresh_active_workflow_status(j),
                    )
                except Exception:
                    pass
                if self.jobs_window is not None:
                    try:
                        if self.jobs_window.winfo_exists():
                            self.after(0, self.jobs_window.refresh)
                    except Exception:
                        pass

        return ok


def run_gui() -> None:
    theme.apply_theme()
    app = WorkflowApp()
    app.mainloop()
