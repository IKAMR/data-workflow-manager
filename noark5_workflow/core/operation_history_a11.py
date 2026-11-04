"""A11: append-only operation history in the authoritative DWM Work folder.

Separate *execution outcome* from a repository/depot quality assessment. Each
record belongs to one persistent job UID and one actual run, and references
only existing paths inside the job's Work area. Does not inspect Source.
The format-neutral read models will also serve a13 Resultatvisninger.
"""
from __future__ import annotations

import json
import os
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from itertools import islice
from pathlib import Path
from typing import Any, Iterable
from uuid import UUID, uuid4

SCHEMA_VERSION = 1
_LOCK = threading.Lock()
_RESULT_KEYS = frozenset({
    "report_html", "report_pdf", "report_json", "report_model", "report_file",
    "source_presentation", "artifact_manifest", "output_dir", "output_path",
    "raw_store", "report_path", "model_file", "html_file", "json_file",
    "output_file", "result_file", "file_path", "path", "normalized_file",
})
_MAX_LINKS = 24
_MAX_TEXT = 1600


@dataclass(frozen=True)
class OperationRun:
    event_id: str
    recorded_at: str
    job_uid: str
    run_id: str
    operation_id: str
    operation_name: str
    run_kind: str
    execution_status: str
    execution_ok: bool | None
    message: str
    warning_count: int
    result_id: str
    work_results: tuple[str, ...]
    job_id_at_time: str = ""


@dataclass(frozen=True)
class OperationResultLink:
    """A non-executable link already checked to be inside existing Work."""
    run_id: str
    operation_id: str
    path: Path
    relative_path: str
    is_directory: bool


def _inside_work(value: Any, work: Path) -> str | None:
    """A result path is a *local Work reference*, not a new scan root."""
    if not isinstance(value, (str, Path)) or not str(value).strip():
        return None
    candidate = Path(value)
    if not candidate.is_absolute():
        candidate = work / candidate
    try:
        resolved_work = work.resolve(strict=True)
        resolved = candidate.resolve(strict=True)
        rel = resolved.relative_to(resolved_work)
        if not rel.parts or not (resolved.is_file() or resolved.is_dir()):
            return None
        return rel.as_posix()
    except (OSError, ValueError, RuntimeError):
        return None


def result_paths(work: Path, result: Any) -> tuple[str, ...]:
    """Capture a bounded set of *existing* Work artifacts without recursing.

    Never record a link to Source or AIP, nor a relative `../` escape. The
    source evidence can still be recorded elsewhere; this navigation view
    deliberately contains only assets safe to open as Work results.
    """
    choices: list[Any] = list(islice(iter(getattr(result, "outputs", ()) or ()), 64))
    data = getattr(result, "data", None)
    if isinstance(data, dict):
        # Support a13's future adapters without depending on Noark5-specific
        # result data, and cap depth/size for very large analysis payloads.
        def collect(mapping: dict, depth: int = 0) -> None:
            if depth > 2 or len(choices) >= 64:
                return
            for key, value in mapping.items():
                name = str(key).casefold()
                if name in _RESULT_KEYS or name.endswith(("_file", "_path", "_dir")):
                    if isinstance(value, (str, Path)):
                        choices.append(value)
                if isinstance(value, dict) and depth < 2:
                    collect(value, depth + 1)
        collect(data)
    paths = []
    for value in choices:
        rel = _inside_work(value, work)
        if rel and rel not in paths:
            paths.append(rel)
        if len(paths) >= _MAX_LINKS:
            break
    return tuple(paths)


class OperationHistoryStore:
    """One job's durable operation runs, rooted in its established DWM Work.

    Reading never creates folders. Writing requires job.json to identify the
    exact job and refuses to silently append to another job's Work history.
    """

    def __init__(self, work: str | Path, job_uid: str):
        self.work = Path(work)
        self.job_uid = str(UUID(str(job_uid)))
        self.path = self.work / "run_history" / "operations.jsonl"

    def _assert_owner(self) -> None:
        manifest = self.work / "job.json"
        try:
            data = json.loads(manifest.read_text(encoding="utf-8"))
        except (OSError, ValueError, UnicodeError) as exc:
            raise ValueError("Work mangler en lesbar, autoritativ job.json") from exc
        if data.get("job_uid") != self.job_uid:
            raise ValueError("Work tilhorer en annen varig jobbidentitet")

    def append(self, *, run_id: str, job_id: str, operation_id: str,
               operation_name: str, run_kind: str = "workflow",
               execution_status: str, execution_ok: bool | None,
               message: str = "", warnings: Iterable[Any] = (),
               result: Any = None) -> OperationRun:
        self._assert_owner()
        if not run_id or len(str(run_id)) > 180 or not operation_id or len(str(operation_id)) > 180:
            raise ValueError("Operasjonshistorikk krever run_id og operation_id")
        if execution_status not in {"completed", "blocked", "exception"}:
            raise ValueError("Ugyldig teknisk operasjonsstatus")
        if run_kind not in {"workflow", "subjob"}:
            raise ValueError("Ugyldig kjoretype")
        data = getattr(result, "data", None)
        ref = data.get("_result_ref") if isinstance(data, dict) else None
        result_id = str(ref.get("result_id") or "") if isinstance(ref, dict) else ""
        record = OperationRun(
            event_id=str(uuid4()),
            recorded_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
            job_uid=self.job_uid,
            run_id=str(run_id),
            operation_id=str(operation_id),
            operation_name=str(operation_name or operation_id),
            run_kind=run_kind,
            execution_status=execution_status,
            execution_ok=execution_ok if isinstance(execution_ok, bool) else None,
            message=str(message or "")[:_MAX_TEXT],
            warning_count=len(tuple(warnings)),
            result_id=result_id,
            work_results=result_paths(self.work, result),
            job_id_at_time=str(job_id or ""),
        )
        payload = vars(record).copy()
        payload["schema_version"] = SCHEMA_VERSION
        payload["work_results"] = list(record.work_results)
        line = json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n"
        with _LOCK:
            self._assert_owner()  # detect a moved or replaced Work while running
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8", newline="\n") as handle:
                handle.write(line)
                handle.flush()
                os.fsync(handle.fileno())
        return record

    def list_runs(self, *, operation_id: str | None = None,
                  limit: int = 250) -> tuple[OperationRun, ...]:
        if not self.path.is_file():
            return ()
        maximum = max(0, min(int(limit), 1000))
        if maximum == 0:
            return ()
        # Work-only, bounded tail; avoids loading multi-year histories at once.
        with self.path.open("rb") as handle:
            length = handle.seek(0, os.SEEK_END)
            cap = 8_000_000
            if length > cap:
                handle.seek(length - cap)
                handle.readline()  # drop the incomplete first JSONL record
            else:
                handle.seek(0)
            rows = handle.read().decode("utf-8", errors="replace").splitlines()
        collected = []
        for line in reversed(rows):
            try:
                data = json.loads(line)
                if not isinstance(data, dict) or data.get("schema_version") != SCHEMA_VERSION:
                    continue
                if data.get("job_uid") != self.job_uid:
                    continue
                if operation_id is not None and data.get("operation_id") != operation_id:
                    continue
                artifacts = data.get("work_results") or []
                if not isinstance(artifacts, list):
                    continue
                collected.append(OperationRun(
                    event_id=str(data["event_id"]), recorded_at=str(data["recorded_at"]),
                    job_uid=self.job_uid, run_id=str(data["run_id"]),
                    operation_id=str(data["operation_id"]),
                    operation_name=str(data.get("operation_name") or data["operation_id"]),
                    run_kind=str(data.get("run_kind") or "workflow"),
                    execution_status=str(data.get("execution_status") or ""),
                    execution_ok=data.get("execution_ok") if isinstance(data.get("execution_ok"), bool) else None,
                    message=str(data.get("message") or ""),
                    warning_count=int(data.get("warning_count") or 0),
                    result_id=str(data.get("result_id") or ""),
                    work_results=tuple(str(x) for x in artifacts[:_MAX_LINKS] if isinstance(x, str)),
                    job_id_at_time=str(data.get("job_id_at_time") or ""),
                ))
            except (ValueError, TypeError, KeyError):
                continue  # malformed historical row does not suppress valid rows
            if len(collected) >= maximum:
                break
        return tuple(collected)

    def result_links(self, *, operation_id: str, run_id: str | None = None,
                     latest_only: bool = True) -> tuple[OperationResultLink, ...]:
        rows = self.list_runs(operation_id=operation_id, limit=500)
        if run_id is not None:
            rows = tuple(row for row in rows if row.run_id == run_id)
        elif latest_only and rows:
            rows = rows[:1]
        links = []
        used = set()
        for row in rows:
            for relative in row.work_results:
                path = self.work / relative
                safe = _inside_work(path, self.work)
                if safe is None or safe != relative or safe in used:
                    continue
                used.add(safe)
                links.append(OperationResultLink(row.run_id, operation_id,
                                                 path.resolve(), safe, path.is_dir()))
        return tuple(links)


def record_operation(ctx: Any, operation: Any, *, status: str, result: Any = None,
                     message: str = "") -> OperationRun | None:
    """Centralized executor hook; legacy/non-Work runs remain unchanged."""
    settings = getattr(ctx, "settings", {}) or {}
    metadata = getattr(ctx, "metadata", {}) or {}
    uid = str(metadata.get("job_uid") or settings.get("_current_job_uid") or "")
    run_id = str(metadata.get("run_id") or settings.get("_current_run_id") or "")
    work = getattr(ctx, "work_operations", None)
    if not (uid and run_id and work):
        return None
    name = getattr(operation, "definition", None)
    return OperationHistoryStore(work, uid).append(
        run_id=run_id,
        job_id=str(metadata.get("job_id") or ""),
        operation_id=str(getattr(name, "operation_id", "") or ""),
        operation_name=str(getattr(name, "name", "") or ""),
        run_kind=str(metadata.get("run_kind") or settings.get("_current_run_kind") or "workflow"),
        execution_status=status,
        execution_ok=bool(result.ok) if status == "completed" and result is not None else None,
        message=message or str(getattr(result, "message", "") or ""),
        warnings=getattr(result, "warnings", ()) if result is not None else (),
        result=result,
    )
