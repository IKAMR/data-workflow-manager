"""a16.1: independent job-document persistence, opt-in until migration is ready.

No existing .n5jobs format is modified by this module.  A persistent UUID is
separate from the list-local JOB-001 label.  Work operations is a writable
working location, not the immutable source extraction.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID, uuid4

from .job import Job
from .job_store import _job_from_dict, _job_to_dict

FILE_TYPE = "data-workflow-manager-job"
FORMAT_VERSION = 1
_FILENAME = "job.json"


class JobDocumentError(ValueError):
    pass


@dataclass(frozen=True)
class LoadedJobDocument:
    stable_id: str
    job: Job
    path: Path
    modified_at: str


def _validate_uuid(stable_id: str) -> str:
    try:
        value = UUID(str(stable_id))
    except (TypeError, ValueError, AttributeError) as exc:
        raise JobDocumentError("Ugyldig stabil jobbidentitet") from exc
    if value.version != 4 or str(value) != str(stable_id).lower():
        raise JobDocumentError("Stabil jobbidentitet ma vaere UUID v4")
    return str(value)


def new_stable_job_id() -> str:
    return str(uuid4())


def job_document_path(work_operations: Path, stable_id: str) -> Path:
    """File beneath a job's working area; no data written to extraction root."""
    return Path(work_operations) / "dwm" / "jobs" / _validate_uuid(stable_id) / _FILENAME


def save_job_document(path: Path, job: Job, *, stable_id: str, expected_id: str | None = None) -> Path:
    """Atomically save a complete independent job snapshot.

    expected_id prevents accidentally replacing another job's document. For
    existing documents the stable identity is always checked before writing.
    """
    stable_id = _validate_uuid(stable_id)
    path = Path(path)
    if path.name != _FILENAME or path.parent.name != stable_id:
        raise JobDocumentError("Jobbdokumentet ma ligge i UUID-mappe som job.json")
    if expected_id is not None and _validate_uuid(expected_id) != stable_id:
        raise JobDocumentError("Forventet jobbidentitet stemmer ikke")
    if path.exists():
        existing = load_job_document(path)
        if existing.stable_id != stable_id:
            raise JobDocumentError("Kan ikke overskrive en annen jobb")
    data = {
        "file_type": FILE_TYPE,
        "format_version": FORMAT_VERSION,
        "stable_job_id": stable_id,
        "modified_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "job": _job_to_dict(job),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    try:
        with tmp.open("x", encoding="utf-8") as handle:
            json.dump(data, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        tmp.replace(path)
    finally:
        tmp.unlink(missing_ok=True)
    return path


def load_job_document(path: Path) -> LoadedJobDocument:
    path = Path(path)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise JobDocumentError(f"Kunne ikke lese jobbdokument: {exc}") from exc
    if not isinstance(data, dict) or data.get("file_type") != FILE_TYPE:
        raise JobDocumentError("Ugyldig jobbdokumenttype")
    if data.get("format_version") != FORMAT_VERSION:
        raise JobDocumentError("Ukjent jobbdokumentversjon")
    stable_id = _validate_uuid(data.get("stable_job_id"))
    if path.name != _FILENAME or path.parent.name != stable_id:
        raise JobDocumentError("Jobbdokumentets filsti stemmer ikke med identiteten")
    raw_job = data.get("job")
    if not isinstance(raw_job, dict):
        raise JobDocumentError("Jobbdokumentet mangler jobbdata")
    try:
        job = _job_from_dict(raw_job, format_version=4)
    except (ValueError, TypeError, KeyError) as exc:
        raise JobDocumentError(f"Ugyldige jobbdata: {exc}") from exc
    return LoadedJobDocument(stable_id, job, path, str(data.get("modified_at", "")))
