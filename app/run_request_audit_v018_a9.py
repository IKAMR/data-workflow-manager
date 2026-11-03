"""Local, append-only trace of UI run requests (no source-data access).

This is deliberately separate from the operation event log. It records when
and why the GUI asks to start or rerun a job, even before a new job list is
saved.  Diagnostic errors never prevent or authorize a DWM run.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
from threading import Lock
from uuid import uuid4

_TERMINAL = frozenset({"Ferdig", "Feil", "Hoppet over"})
_RESET_MESSAGE = "Konfigurasjon endret - klar for ny kj\u00f8ring"


def rerun_reason(status: str, message: str) -> str:
    """Only historical execution state, never a reused JOB-001 identifier."""
    if str(status or "") in _TERMINAL:
        return "previous_status:" + str(status)
    if str(message or "") == _RESET_MESSAGE:
        return "workflow_changed_after_run"
    return ""


def new_request_id() -> str:
    return uuid4().hex[:16]


def default_diagnostic_path() -> Path:
    """Write only inside the current user's application-data directory."""
    local = os.environ.get("LOCALAPPDATA", "").strip()
    base = Path(local) if local else Path.home() / ".local" / "state"
    return base / "IKAMR" / "DWM" / "diagnostics" / "run_requests.jsonl"


class RunRequestAudit:
    """Thread-safe JSONL audit; does not touch Source, Work or .n5jobs."""

    def __init__(self, path: str | Path | None = None):
        self.path = Path(path) if path is not None else default_diagnostic_path()
        self.session_id = uuid4().hex[:16]
        self.last_error: str = ""
        self._lock = Lock()

    def record(self, event: str, **details) -> bool:
        entry = {
            "timestamp_utc": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
            "session_id": self.session_id,
            "process_id": os.getpid(),
            "event": str(event),
        }
        # Never accept full data structures, exception tracebacks or files.
        # A job list path is required for cross-checking JOB-001 identities.
        allowed = {
            "request_id", "joblist", "job_id", "status", "message", "progress",
            "operation_index", "operation_count", "worker_present", "api_running",
            "request_busy", "reason", "decision", "source", "result", "run_count",
        }
        for key, value in details.items():
            if key not in allowed or value is None:
                continue
            if isinstance(value, (bool, float, int)):
                entry[key] = value
            else:
                entry[key] = str(value)[:1024]
        try:
            serialized = json.dumps(entry, ensure_ascii=False, separators=(",", ":"))
            with self._lock:
                self.path.parent.mkdir(parents=True, exist_ok=True)
                with self.path.open("a", encoding="utf-8", newline="\n") as stream:
                    stream.write(serialized + "\n")
                self.last_error = ""
        except (OSError, ValueError, TypeError) as exc:
            self.last_error = str(exc)
            return False
        return True
