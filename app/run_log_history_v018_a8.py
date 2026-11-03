"""Durable, per-job, per-run logs for the GUI-independent DWM workbench.

Logs are written only to a job's already validated effective Work-operations
folder.  Read operations never create directories and never scan Source/DOKUMENT.
"""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,80}$")
_RUN_RE = re.compile(r"^\d{8}T\d{6}Z-[0-9a-f]{8}$")


def _job_id(value: str) -> str:
    value = str(value)
    if not _ID_RE.fullmatch(value):
        raise ValueError("Ugyldig jobb-ID for kjørelogg")
    return value


def _run_id(value: str) -> str:
    value = str(value)
    if not _RUN_RE.fullmatch(value):
        raise ValueError("Ugyldig kjørings-ID")
    return value


@dataclass(frozen=True)
class RunLogInfo:
    run_id: str
    job_id: str
    started_at: str
    status: str
    log_path: Path


class RunLogStore:
    """Owns only effective_work_operations/run_logs/<job_id>.

    The persistent log is separate from raw results, provenance and the job list.
    """

    def __init__(self, effective_work_operations: str | Path, job_id: str):
        self.base = Path(effective_work_operations)
        self.job_id = _job_id(job_id)
        self.folder = self.base / "run_logs" / self.job_id

    def begin(self, *, job_name: str, job_list_path: str = "") -> "RunLogWriter":
        run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid4().hex[:8]
        started = datetime.now(timezone.utc).isoformat(timespec="seconds")
        self.folder.mkdir(parents=True, exist_ok=True)
        log_file = self.folder / (run_id + ".log")
        # Exclusive open prevents accidentally overwriting a previous session.
        handle = log_file.open("x", encoding="utf-8", newline="\n")
        writer = RunLogWriter(self, run_id, started, handle)
        try:
            writer._save_metadata("running", job_name=job_name, job_list_path=job_list_path)
            writer.append(f"DWM kjøring startet: {started}")
            writer.append(f"Jobb: {self.job_id} | {job_name}")
            writer.append(f"Jobbliste: {job_list_path}")
        except Exception:
            handle.close()
            raise
        return writer

    def list_runs(self, *, limit: int = 100) -> tuple[RunLogInfo, ...]:
        if not self.folder.is_dir():
            return ()
        found = []
        for meta in sorted(self.folder.glob("*.json"), reverse=True):
            if len(found) >= max(0, min(limit, 500)):
                break
            try:
                run_id = _run_id(meta.stem)
                data = json.loads(meta.read_text(encoding="utf-8"))
                if data.get("job_id") != self.job_id or data.get("run_id") != run_id:
                    continue
                log = self.folder / (run_id + ".log")
                if not log.is_file():
                    continue
                found.append(RunLogInfo(run_id, self.job_id,
                                        str(data.get("started_at", "")),
                                        str(data.get("status", "unknown")), log))
            except (OSError, ValueError, TypeError, json.JSONDecodeError):
                continue
        return tuple(found)

    def read(self, run_id: str, *, max_bytes: int = 2_000_000) -> str:
        log = self.folder / (_run_id(run_id) + ".log")
        with log.open("rb") as handle:
            size = handle.seek(0, os.SEEK_END)
            capped = max(1_000, min(int(max_bytes), 16_000_000))
            if size > capped:
                handle.seek(-capped, os.SEEK_END)
                tail = handle.read()
                first_newline = tail.find(b"\n")
                if first_newline >= 0:
                    tail = tail[first_newline + 1:]
                return "[Viser siste del av loggen; originalfilen er bevart.]\n" + tail.decode("utf-8", errors="replace")
            handle.seek(0)
            return handle.read().decode("utf-8", errors="replace")


class RunLogWriter:
    def __init__(self, store: RunLogStore, run_id: str, started_at: str, handle):
        self.store = store
        self.run_id = run_id
        self.started_at = started_at
        self._handle = handle
        self._closed = False
        self._metadata = {}

    def _save_metadata(self, status: str, **extra) -> None:
        self._metadata.update(extra)
        self._metadata.update({
            "format_version": 1,
            "job_id": self.store.job_id,
            "run_id": self.run_id,
            "started_at": self.started_at,
            "status": status,
        })
        path = self.store.folder / (self.run_id + ".json")
        temp = self.store.folder / (self.run_id + ".json.tmp")
        temp.write_text(json.dumps(self._metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        temp.replace(path)

    @property
    def log_path(self) -> Path:
        return self.store.folder / (self.run_id + ".log")

    def append(self, message: str) -> None:
        if self._closed:
            return
        text = str(message or "")
        self._handle.write(text + ("" if text.endswith("\n") else "\n"))
        self._handle.flush()

    def finish(self, status: str = "finished") -> None:
        if self._closed:
            return
        try:
            self.append("Kjøring avsluttet: " + status)
            self._save_metadata(status, completed_at=datetime.now(timezone.utc).isoformat(timespec="seconds"))
        finally:
            self._closed = True
            self._handle.close()
