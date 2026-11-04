"""Authoritative, standalone DWM job records inside approved Work areas.

No Source scanning, no output deletion, no implicit directory creation.  The
Work directory holds the definition, latest execution state and append-only
history; a job-list file is not needed for reconstruction.

The schema is format-neutral: a future SIARD job can live beside a Noark 5
job, and jobs may share an optional production-system reference without
sharing execution status or storage locations.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID, uuid4

WORK_JOB_FILE_TYPE = "dwm-work-job"
WORK_STATE_FILE_TYPE = "dwm-work-job-state"
WORK_FORMAT_VERSION = 1
DEFINITION_FILE = "job.json"
STATE_FILE = "job-state.json"
EVENTS_FILE = "job-events.jsonl"

STATE_FIELDS = ("status", "progress", "message", "next_operation_index", "log_entries")


class WorkJobStoreError(ValueError):
    """Missing, inconsistent or conflicting job ownership in Work."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _load_object(path: Path) -> dict:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise WorkJobStoreError(f"Kunne ikke lese {path.name}: {exc}") from exc
    if not isinstance(raw, dict):
        raise WorkJobStoreError(f"Ugyldig JSON-objekt i {path.name}")
    return raw


def _uid(value: str) -> str:
    try:
        parsed = UUID(str(value))
    except (TypeError, ValueError, AttributeError) as exc:
        raise WorkJobStoreError("Jobbens varige Work-ID er ugyldig") from exc
    return str(parsed)


def _atomic_json(path: Path, payload: dict) -> None:
    """Publish completed JSON, never truncate an existing good snapshot."""
    tmp = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
    try:
        with tmp.open("x", encoding="utf-8", newline="\n") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, path)
    finally:
        if tmp.exists():
            tmp.unlink()


def _read_previous_state(events_file: Path, uid: str) -> dict | None:
    """Recover last state snapshot when the current state file is damaged.

    A finite Work-owned event stream is scanned once, not Source/archives.
    """
    if not events_file.is_file():
        return None
    previous = None
    try:
        with events_file.open("r", encoding="utf-8") as handle:
            for line in handle:
                try:
                    event = json.loads(line)
                except (ValueError, TypeError):
                    continue  # an incomplete final append is ignored
                if not isinstance(event, dict) or event.get("job_uid") != uid:
                    continue
                state = event.get("state")
                if isinstance(state, dict) and "status" in state:
                    previous = state
    except (OSError, UnicodeError) as exc:
        raise WorkJobStoreError(f"Kunne ikke lese hendelseshistorikken: {exc}") from exc
    return previous


class WorkJobStore:
    def __init__(self, folder: str | Path):
        self.folder = Path(folder)
        self.definition_path = self.folder / DEFINITION_FILE
        self.state_path = self.folder / STATE_FILE
        self.events_path = self.folder / EVENTS_FILE

    def exists(self) -> bool:
        return self.definition_path.is_file()

    def _definition(self) -> dict:
        definition = _load_object(self.definition_path)
        if (definition.get("file_type") != WORK_JOB_FILE_TYPE
                or definition.get("format_version") != WORK_FORMAT_VERSION):
            raise WorkJobStoreError("Ikke en støttet DWM-jobbdefinisjon i Work")
        definition["job_uid"] = _uid(definition.get("job_uid"))
        if not isinstance(definition.get("job"), dict):
            raise WorkJobStoreError("Work-jobben mangler fullstendig jobbdefinisjon")
        return definition

    def assert_compatible(self, job) -> None:
        """Refuse collisions, including the same JOB-001 from another list."""
        if not self.folder.is_dir():
            raise WorkJobStoreError(f"Work-området er ikke klargjort: {self.folder}")
        if not self.exists():
            # Do not overwrite unexplained orphan state/history files.
            if self.state_path.exists() or self.events_path.exists():
                raise WorkJobStoreError(
                    "Work har jobbstatus/historikk uten job.json. Gjenopprett området manuelt."
                )
            return
        definition = self._definition()
        candidate = str(getattr(job, "job_uid", "") or "")
        if not candidate or _uid(candidate) != definition["job_uid"]:
            raise WorkJobStoreError(
                "Work-området tilhører en annen jobbidentitet. "
                "Åpne den eksisterende jobben fra Work i stedet for å overskrive."
            )
        if self.state_path.is_file():
            state = _load_object(self.state_path)
            if state.get("job_uid") != candidate:
                raise WorkJobStoreError("Jobbstatus og jobbdefinisjon har forskjellig Work-ID")

    def write(self, job, *, event_kind: str = "", detail: str = "", origin_joblist: str = "") -> Path:
        """Persist definition + current state, and optionally an audit event.

        Requires an existing, explicitly approved Work folder. All writes are
        limited to three known files in this directory.
        """
        if not self.folder.is_dir():
            raise WorkJobStoreError(f"Work-området er ikke klargjort: {self.folder}")
        if not getattr(job, "job_uid", ""):
            job.job_uid = str(uuid4())
        job.job_uid = _uid(job.job_uid)
        self.assert_compatible(job)
        previous = self._definition() if self.exists() else None
        from .job_store import _job_to_dict
        entire = _job_to_dict(job)
        state = {key: entire.pop(key) for key in STATE_FIELDS}
        now = _now()
        definition = {
            "file_type": WORK_JOB_FILE_TYPE,
            "format_version": WORK_FORMAT_VERSION,
            "job_uid": job.job_uid,
            "created_at": previous.get("created_at", now) if previous else now,
            "updated_at": now,
            "origin_joblist": (
                str(origin_joblist) if origin_joblist else
                str(previous.get("origin_joblist", "")) if previous else ""
            ),
            # JOB-001 is list-local. Preserve previous aliases so old a8/a9
            # run_logs/JOB-001 remain visible after recovery as JOB-002.
            "job_list_aliases": list(dict.fromkeys([
                *(previous.get("job_list_aliases", [previous["job"].get("job_id", "")])
                  if previous else []),
                str(job.job_id),
            ])),
            # Reserved grouping fields are format-neutral and NEVER inferred.
            "relationships": (
                previous.get("relationships", {"related_job_uids": []})
                if previous else {"related_job_uids": []}
            ),
            "job": entire,
        }
        last_run_id = str(getattr(job, "_active_run_id", "") or "")
        if not last_run_id and self.state_path.is_file():
            try:
                former = _load_object(self.state_path)
                if former.get("job_uid") == job.job_uid:
                    last_run_id = str(former.get("last_run_id", "") or "")
            except WorkJobStoreError:
                pass  # Existing recovery from job-events remains available.
        current_state = {
            "file_type": WORK_STATE_FILE_TYPE,
            "format_version": WORK_FORMAT_VERSION,
            "job_uid": job.job_uid,
            "updated_at": now,
            "last_run_id": last_run_id,
            "state": state,
        }
        _atomic_json(self.definition_path, definition)
        _atomic_json(self.state_path, current_state)
        if event_kind:
            event = {
                "event_id": str(uuid4()),
                "at": now,
                "job_uid": job.job_uid,
                "job_id_at_time": job.job_id,
                "run_id": str(getattr(job, "_active_run_id", "") or ""),
                "run_kind": str(getattr(job, "_active_run_kind", "") or ""),
                "kind": str(event_kind),
                "detail": str(detail),
                "state": state,
            }
            with self.events_path.open("a", encoding="utf-8", newline="\n") as handle:
                handle.write(json.dumps(event, ensure_ascii=False, separators=(",", ":")) + "\n")
                handle.flush()
                os.fsync(handle.fileno())
        return self.definition_path

    def load(self):
        """Rebuild the complete Job without any .n5jobs or Source file."""
        definition = self._definition()
        uid = definition["job_uid"]
        state = None
        if self.state_path.is_file():
            try:
                doc = _load_object(self.state_path)
                if doc.get("job_uid") != uid or doc.get("file_type") != WORK_STATE_FILE_TYPE:
                    raise WorkJobStoreError("Jobbstatusen har feil identitet eller filtype")
                state = doc.get("state")
                if not isinstance(state, dict) or "status" not in state:
                    raise WorkJobStoreError("Ugyldig statusinnhold i Work")
            except WorkJobStoreError:
                state = _read_previous_state(self.events_path, uid)
                if state is None:
                    raise
        else:
            state = _read_previous_state(self.events_path, uid)
        if state is None:
            raise WorkJobStoreError("Work mangler jobbstatus og gjenopprettbar hendelseshistorikk")
        merged = dict(definition["job"])
        merged.update({key: state[key] for key in STATE_FIELDS if key in state})
        merged["job_uid"] = uid
        from .job_store import _job_from_dict
        try:
            job = _job_from_dict(merged, format_version=4)
        except (TypeError, ValueError) as exc:
            raise WorkJobStoreError("Ugyldig jobbdefinisjon/status i Work: " + str(exc)) from exc
        if job.job_uid != uid:
            raise WorkJobStoreError("Ulik jobbidentitet ved gjenoppretting")
        aliases = definition.get("job_list_aliases", [job.job_id])
        job._work_job_aliases = tuple(
            str(value) for value in aliases if isinstance(value, str) and value
        )
        return job
