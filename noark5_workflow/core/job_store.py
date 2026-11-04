"""Versioned DWM job-list persistence.

v1-v4 remain self-contained historical formats. v5 is a hybrid *index*:
Work-backed entries contain only a stable Work reference and last-known status;
unprovisioned drafts retain their complete definition until Work is approved.
The authoritative state of a Work-backed job is always read from Work.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Mapping

from .job import Job, JobBatch, JobStatus

FILE_TYPE = "noark5-workflow-manager-job-list"
FORMAT_VERSION = 4  # Legacy full-job file format for existing direct callers.
WORK_INDEX_FORMAT_VERSION = 5
SUPPORTED_FORMAT_VERSIONS = {1, 2, 3, 4, 5}
FILE_EXTENSION = ".n5jobs"


class JobListFormatError(ValueError):
    pass


@dataclass(frozen=True)
class LoadedJobList:
    batch: JobBatch
    active_job_id: str | None
    created_at: str
    modified_at: str
    app_version: str
    output_subfolder_rule: str = ""
    work_references: dict[str, Path] = field(default_factory=dict)
    unavailable_work_job_ids: frozenset[str] = frozenset()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _json_value(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, dict):
        return {str(k): _json_value(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_value(v) for v in value]
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    raise TypeError(f"Kan ikke lagre verdi av type {type(value).__name__} i jobblisten")


def _path_text(value: Path | None) -> str | None:
    return str(value) if value is not None else None


def _job_to_dict(job: Job) -> dict[str, Any]:
    """Stable complete legacy/draft representation, also used by Work."""
    return {
        "job_id": job.job_id,
        "job_uid": str(getattr(job, "job_uid", "") or ""),
        "name": job.name,
        "profile_id": job.profile_id,
        "source_root": _path_text(job.source_root),
        "source_tar": _path_text(job.source_tar),
        "source_unzipped": _path_text(job.source_unzipped),
        "source_extraction": _path_text(job.source_extraction),
        "work_root": _path_text(job.work_root),
        "work_content": _path_text(job.work_content),
        "work_operations": _path_text(job.work_operations),
        "archive_root": _path_text(job.archive_root),
        "output_root": _path_text(job.output_root),
        "workflow_ids": list(job.workflow_ids),
        "operation_params": _json_value(job.operation_params),
        "status": job.status.value,
        "progress": float(job.progress),
        "worker": job.worker,
        "message": job.message,
        "log_entries": list(job.log_entries),
        "checkpoint_after": list(job.checkpoint_after),
        "next_operation_index": int(job.next_operation_index),
        "owner_user_id": job.owner_user_id,
        "owner_username": job.owner_username,
        "owner_name": job.owner_name,
        "owner_email": job.owner_email,
        # Optional future cross-job grouping; this is never inferred from Source.
        "production_system_ref": str(getattr(job, "production_system_ref", "") or ""),
    }


def _optional_path(data: dict[str, Any], key: str) -> Path | None:
    value = data.get(key)
    return Path(str(value)) if value else None


def _job_from_dict(data: dict[str, Any], *, format_version: int) -> Job:
    job_id = str(data.get("job_id", "")).strip()
    source_root = str(data.get("source_root", "") or "").strip()
    if not job_id:
        raise JobListFormatError("Jobb mangler job_id")
    if format_version < 3 and not source_root:
        raise JobListFormatError(f"{job_id} mangler source_root")
    try:
        status = JobStatus(data.get("status", JobStatus.READY.value))
    except ValueError:
        status = JobStatus.READY
    message = str(data.get("message", ""))
    if status == JobStatus.RUNNING:
        status = JobStatus.READY
        message = "Forrige kjøring var aktiv da jobblisten ble lagret"
    try:
        progress = max(0.0, min(1.0, float(data.get("progress", 0.0))))
    except (TypeError, ValueError):
        progress = 0.0
    params = data.get("operation_params", {})
    if not isinstance(params, dict):
        raise JobListFormatError(f"{job_id} har ugyldige operation_params")
    workflow_ids = data.get("workflow_ids", [])
    if not isinstance(workflow_ids, list):
        raise JobListFormatError(f"{job_id} har ugyldig workflow_ids")
    logs = data.get("log_entries", [])
    logs = logs if isinstance(logs, list) else []
    checkpoints = data.get("checkpoint_after", []) if format_version >= 2 else []
    checkpoints = checkpoints if isinstance(checkpoints, list) else []
    try:
        next_index = int(data.get("next_operation_index", 0)) if format_version >= 2 else 0
    except (TypeError, ValueError):
        next_index = 0
    output_root = _optional_path(data, "output_root")
    job = Job(
        job_id=job_id, source_root=Path(source_root) if source_root else None,
        output_root=output_root,
        source_tar=_optional_path(data, "source_tar") if format_version >= 3 else None,
        source_unzipped=_optional_path(data, "source_unzipped") if format_version >= 3 else None,
        source_extraction=_optional_path(data, "source_extraction") if format_version >= 3 else None,
        work_root=_optional_path(data, "work_root") if format_version >= 3 else None,
        work_content=_optional_path(data, "work_content") if format_version >= 3 else None,
        work_operations=_optional_path(data, "work_operations") if format_version >= 3 else None,
        archive_root=_optional_path(data, "archive_root") if format_version >= 3 else output_root,
        name=str(data.get("name", "")),
        profile_id=(str(data.get("profile_id")).strip() if data.get("profile_id") else None),
        workflow_ids=[str(v) for v in workflow_ids],
        operation_params=_json_value(params), status=status, progress=progress,
        worker=str(data.get("worker", "Lokal (denne PC-en)")), message=message,
        log_entries=[str(v) for v in logs][-2000:],
        checkpoint_after=[str(v) for v in checkpoints], next_operation_index=next_index,
        owner_user_id=str(data.get("owner_user_id", "") or ""),
        owner_username=str(data.get("owner_username", "") or ""),
        owner_name=str(data.get("owner_name", "") or ""),
        owner_email=str(data.get("owner_email", "") or ""),
    )
    job.job_uid = str(data.get("job_uid", "") or "")
    job.production_system_ref = str(data.get("production_system_ref", "") or "")
    return job


def _existing_created_at(path: Path) -> str | None:
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if isinstance(data, dict) and data.get("file_type") == FILE_TYPE:
        value = str(data.get("created_at", "")).strip()
        return value or None
    return None


def save_job_list(
    path: Path, batch: JobBatch, *, active_job_id: str | None = None,
    app_version: str = "", work_references: Mapping[str, str | Path] | None = None,
) -> Path:
    """Save v4 for legacy callers, v5 index for the a10 Work-first frontend.

    No Work directories are created here. Work snapshots must be persisted by
    the caller *before* publishing new references in the job-list index.
    """
    path = Path(path)
    if path.suffix.lower() != FILE_EXTENSION:
        path = path.with_suffix(FILE_EXTENSION)
    path.parent.mkdir(parents=True, exist_ok=True)
    now = _now_iso()
    indexed = work_references is not None
    # Prevent older GUI/CLI clients from silently converting the canonical
    # Work index back into an embedded v4 copy of the job definition.
    if path.is_file():
        try:
            old_data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError):
            old_data = None
        if (not indexed and isinstance(old_data, dict)
                and old_data.get("file_type") == FILE_TYPE
                and old_data.get("format_version") == WORK_INDEX_FORMAT_VERSION):
            raise JobListFormatError(
                "Dette er en Work-basert v5-jobbliste. Den kan ikke lagres "
                "som v4 fra et eldre grensesnitt. Bruk DWM v0.1.8-a10."
            )
        # Preserve the original full v1-v4 list before replacing its records
        # with reference-only v5 entries. Never replace an existing backup.
        if (indexed and isinstance(old_data, dict)
                and old_data.get("file_type") == FILE_TYPE
                and old_data.get("format_version") in {1, 2, 3, 4}):
            import shutil
            backup = path.with_name(path.name + ".pre-a10.bak")
            if not backup.exists():
                shutil.copy2(path, backup)
    refs = dict(work_references or {})
    valid_ids = {job.job_id for job in batch.jobs()}
    if set(refs) - valid_ids:
        raise JobListFormatError("Work-referanse finnes for jobb som ikke er i jobblisten")
    jobs = []
    for job in batch.jobs():
        if not indexed:
            jobs.append(_job_to_dict(job))
        elif job.job_id in refs:
            ref = Path(refs[job.job_id])
            if ref.name != "job.json" or not ref.is_absolute():
                raise JobListFormatError("Work-referanse må være absolutt sti til job.json")
            jobs.append({
                "entry_type": "work_ref",
                "job_id": job.job_id,
                "job_uid": str(getattr(job, "job_uid", "") or ""),
                "name": job.name,
                "profile_id": job.profile_id,
                "status": job.status.value,
                "progress": float(job.progress),
                "work_manifest_path": str(ref),
                "last_seen_at": now,
            })
        else:
            jobs.append({"entry_type": "draft", "job": _job_to_dict(job)})
    payload = {
        "file_type": FILE_TYPE,
        "format_version": WORK_INDEX_FORMAT_VERSION if indexed else FORMAT_VERSION,
        "app_version": app_version,
        "created_at": _existing_created_at(path) or now,
        "modified_at": now,
        "active_job_id": active_job_id,
        "output_subfolder_rule": str(getattr(batch, "output_subfolder_rule", "") or ""),
        "jobs": jobs,
    }
    temp_path = path.with_name(path.name + ".tmp")
    try:
        temp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        temp_path.replace(path)
    finally:
        if temp_path.exists():
            try:
                temp_path.unlink()
            except OSError:
                pass
    return path


def _offline_placeholder(ref: dict[str, Any]) -> Job:
    """Only a clearly stale index snapshot, never a fabricated job definition."""
    try:
        status = JobStatus(ref.get("status", JobStatus.READY.value))
    except ValueError:
        status = JobStatus.READY
    try:
        progress = float(ref.get("progress", 0.0))
    except (ValueError, TypeError):
        progress = 0.0
    job = Job(
        job_id=str(ref["job_id"]), name=str(ref.get("name") or ref["job_id"]),
        profile_id=str(ref.get("profile_id") or "") or None,
        status=status, progress=max(0.0, min(1.0, progress)),
        message="Work frakoblet: informasjon fra jobblisten er bare sist kjent status",
    )
    job.job_uid = str(ref.get("job_uid", "") or "")
    return job


def load_job_list(path: Path) -> LoadedJobList:
    path = Path(path)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise JobListFormatError(f"Kunne ikke lese jobblisten: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise JobListFormatError(f"Ugyldig JSON i jobblisten: {exc}") from exc
    if not isinstance(data, dict):
        raise JobListFormatError("Jobblisten må inneholde et JSON-objekt")
    if data.get("file_type") != FILE_TYPE:
        raise JobListFormatError("Filen er ikke en Noark 5 Workflow Manager-jobbliste")
    version = data.get("format_version")
    if version not in SUPPORTED_FORMAT_VERSIONS:
        raise JobListFormatError(
            f"Jobblisteformat {version!r} støttes ikke "
            f"(støttede versjoner: {sorted(SUPPORTED_FORMAT_VERSIONS)})"
        )
    raw_jobs = data.get("jobs", [])
    if not isinstance(raw_jobs, list):
        raise JobListFormatError("Feltet jobs må være en liste")
    batch = JobBatch()
    references: dict[str, Path] = {}
    unavailable = set()
    for raw in raw_jobs:
        if not isinstance(raw, dict):
            raise JobListFormatError("Ugyldig jobb i jobs-listen")
        if version == WORK_INDEX_FORMAT_VERSION:
            entry_type = raw.get("entry_type")
            if entry_type == "draft":
                definition = raw.get("job")
                if not isinstance(definition, dict):
                    raise JobListFormatError("Jobbutkast mangler jobbdefinisjon")
                job = _job_from_dict(definition, format_version=4)
            elif entry_type == "work_ref":
                raw_path = str(raw.get("work_manifest_path", "") or "").strip()
                if not raw_path:
                    raise JobListFormatError("Work-referanse mangler manifeststi")
                ref = Path(raw_path)
                if not ref.is_absolute():
                    ref = path.parent / ref
                if ref.name != "job.json":
                    raise JobListFormatError("Work-referanse må peke på job.json")
                job_id = str(raw.get("job_id", "") or "")
                if not job_id:
                    raise JobListFormatError("Work-referanse mangler jobb-ID")
                references[job_id] = ref
                if not ref.is_file():
                    job = _offline_placeholder(raw)
                    unavailable.add(job_id)
                else:
                    # Strict identity validation. Never let a different job at
                    # the same path replace the referenced job silently.
                    from .work_job_store import WorkJobStore, WorkJobStoreError
                    try:
                        job = WorkJobStore(ref.parent).load()
                    except WorkJobStoreError as exc:
                        raise JobListFormatError(f"Kan ikke lese Work-jobben {job_id}: {exc}") from exc
                    expected_uid = str(raw.get("job_uid", "") or "")
                    if expected_uid and expected_uid != getattr(job, "job_uid", ""):
                        raise JobListFormatError(
                            f"Work-identitet avviker for {job_id}. Filene blir ikke overskrevet."
                        )
                    job.job_id = job_id  # job list-local alias, not Work identity
            else:
                raise JobListFormatError("Ukjent jobboppføring i v5-jobblisten")
        else:
            job = _job_from_dict(raw, format_version=int(version))
        batch.add(job)
    rule = str(data.get("output_subfolder_rule", "") or "") if int(version) >= 4 else ""
    batch.output_subfolder_rule = rule
    active = data.get("active_job_id")
    if active is not None:
        active = str(active)
        if batch.get(active) is None:
            active = None
    return LoadedJobList(
        batch=batch, active_job_id=active,
        created_at=str(data.get("created_at", "")),
        modified_at=str(data.get("modified_at", "")),
        app_version=str(data.get("app_version", "")),
        output_subfolder_rule=rule,
        work_references=references,
        unavailable_work_job_ids=frozenset(unavailable),
    )
