from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Iterable

from .storage_roles import StorageRoles


class JobStatus(str, Enum):
    READY = "Klar"
    RUNNING = "Kjører"
    WAITING = "Venter ved kontrollpunkt"
    OK = "Ferdig"
    FAILED = "Feil"
    SKIPPED = "Hoppet over"
    INTERRUPTED = "Avbrutt"


@dataclass
class Job:
    """One workflow execution. Source may be assigned after job creation."""

    job_id: str
    source_root: Path | None = None
    output_root: Path | None = None
    source_tar: Path | None = None
    source_unzipped: Path | None = None
    source_extraction: Path | None = None
    work_root: Path | None = None
    work_content: Path | None = None
    work_operations: Path | None = None
    archive_root: Path | None = None
    name: str = ""
    profile_id: str | None = None
    workflow_ids: list[str] = field(default_factory=list)
    operation_params: dict[str, dict] = field(default_factory=dict)
    status: JobStatus = JobStatus.READY
    progress: float = 0.0
    worker: str = "Lokal (denne PC-en)"
    message: str = ""
    log_entries: list[str] = field(default_factory=list)
    checkpoint_after: list[str] = field(default_factory=list)
    next_operation_index: int = 0

    # Stable owner identity snapshot. These fields identify who owns/created the
    # job; they are deliberately separate from the user who executes a later run.
    owner_user_id: str = ""
    owner_username: str = ""
    owner_name: str = ""
    owner_email: str = ""

    def __post_init__(self) -> None:
        for attr in (
            "source_root", "output_root", "source_tar", "source_unzipped",
            "source_extraction", "work_root", "work_content", "work_operations",
            "archive_root",
        ):
            value = getattr(self, attr)
            if value is not None:
                setattr(self, attr, Path(value))
        if self.archive_root is None and self.output_root is not None:
            self.archive_root = self.output_root
        if not self.name:
            active = self.active_extraction_root
            self.name = active.name if active is not None and active.name else self.job_id
        self._normalise_checkpoint_state()

    @property
    def active_extraction_root(self) -> Path | None:
        return self.source_extraction or self.source_root

    @property
    def storage_roles(self) -> StorageRoles:
        return StorageRoles(
            source_root=self.source_root,
            source_tar=self.source_tar,
            source_unzipped=self.source_unzipped,
            source_extraction=self.source_extraction,
            work_root=self.work_root,
            work_content=self.work_content,
            work_operations=self.work_operations,
            archive_root=self.archive_root,
        )

    @property
    def owner_identity(self) -> dict[str, str] | None:
        if not self.owner_user_id:
            return None
        return {
            "user_id": self.owner_user_id,
            "username": self.owner_username,
            "name": self.owner_name,
            "email": self.owner_email,
        }

    def set_owner_identity(self, identity: dict | None) -> None:
        """Set owner only while the job is unowned.

        Ownership is a stable job property. Re-running a job as another user must
        not silently rewrite who owns the job.
        """
        if self.owner_user_id or not identity:
            return
        self.owner_user_id = str(identity.get("user_id", "") or "").strip()
        self.owner_username = str(identity.get("username", "") or "").strip()
        self.owner_name = str(identity.get("name", "") or "").strip()
        self.owner_email = str(identity.get("email", "") or "").strip()

    def is_unused_draft(self) -> bool:
        """Return True only for a disposable, never-used draft job.

        Owner identity alone does not make a newly created blank draft historically
        significant. Any real source/storage assignment, workflow content,
        operation parameters, execution state or log history does.
        """
        has_storage = any((
            self.source_root,
            self.output_root,
            self.source_tar,
            self.source_unzipped,
            self.source_extraction,
            self.work_root,
            self.work_content,
            self.work_operations,
            self.archive_root,
        ))
        default_name = not self.name or self.name == self.job_id
        never_executed = (
            self.status == JobStatus.READY
            and float(self.progress or 0.0) == 0.0
            and int(self.next_operation_index or 0) == 0
            and not self.message
            and not self.log_entries
        )
        return (
            not has_storage
            and default_name
            and not self.workflow_ids
            and not self.operation_params
            and not self.checkpoint_after
            and never_executed
        )

    def _normalise_checkpoint_state(self) -> None:
        valid = set(self.workflow_ids)
        self.checkpoint_after = [oid for oid in dict.fromkeys(self.checkpoint_after) if oid in valid]
        try:
            index = int(self.next_operation_index)
        except (TypeError, ValueError):
            index = 0
        self.next_operation_index = max(0, min(index, len(self.workflow_ids)))

    def set_workflow(self, operation_ids: Iterable[str]) -> None:
        old_workflow = list(self.workflow_ids)
        self.workflow_ids = list(operation_ids)
        valid = set(self.workflow_ids)
        self.checkpoint_after = [oid for oid in self.checkpoint_after if oid in valid]
        if self.workflow_ids != old_workflow:
            self.next_operation_index = 0
            if self.status == JobStatus.WAITING:
                self.status = JobStatus.READY
                self.progress = 0.0
                self.message = "Workflow endret - klar for ny kjøring"
        else:
            self._normalise_checkpoint_state()

    def set_operation_params(self, operation_id: str, params: dict) -> None:
        self.operation_params[operation_id] = deepcopy(dict(params))

    def get_operation_params(self, operation_id: str) -> dict:
        return deepcopy(self.operation_params.get(operation_id, {}))

    def set_checkpoint(self, operation_id: str, enabled: bool) -> None:
        if operation_id not in self.workflow_ids:
            raise ValueError(f"Operasjonen finnes ikke i workflow: {operation_id}")
        current = list(self.checkpoint_after)
        if enabled and operation_id not in current:
            current.append(operation_id)
        elif not enabled and operation_id in current:
            current.remove(operation_id)
        self.checkpoint_after = [oid for oid in self.workflow_ids if oid in set(current)]

    def has_checkpoint(self, operation_id: str) -> bool:
        return operation_id in self.checkpoint_after

    def reset_execution(self, message: str = "") -> None:
        self.next_operation_index = 0
        self.progress = 0.0
        self.status = JobStatus.READY
        self.message = message

    def mark_operation_completed(self, operation_index: int) -> None:
        self.next_operation_index = max(0, min(operation_index + 1, len(self.workflow_ids)))
        if self.workflow_ids:
            self.progress = self.next_operation_index / len(self.workflow_ids)

    def is_complete(self) -> bool:
        return bool(self.workflow_ids) and self.next_operation_index >= len(self.workflow_ids)


class JobBatch:
    def __init__(self) -> None:
        self._jobs: list[Job] = []
        self._next_number = 1

    def new_job(self, source_root: Path | None = None, *, output_root: Path | None = None,
                name: str = "", workflow_ids: Iterable[str] = ()) -> Job:
        job = Job(
            job_id=f"JOB-{self._next_number:03d}", source_root=source_root,
            output_root=Path(output_root) if output_root else None,
            name=name, workflow_ids=list(workflow_ids),
        )
        self._next_number += 1
        self._jobs.append(job)
        return job

    def _update_next_number(self, job_id: str) -> None:
        if not job_id.startswith("JOB-"):
            return
        try:
            number = int(job_id[4:])
        except ValueError:
            return
        self._next_number = max(self._next_number, number + 1)

    def add(self, job: Job) -> None:
        if any(existing.job_id == job.job_id for existing in self._jobs):
            raise ValueError(f"Jobb-ID finnes allerede: {job.job_id}")
        self._jobs.append(job)
        self._update_next_number(job.job_id)

    def replace_all(self, jobs: Iterable[Job]) -> None:
        self._jobs = []
        self._next_number = 1
        for job in jobs:
            self.add(job)

    def clear(self) -> None:
        self._jobs = []
        self._next_number = 1

    def remove(self, job_id: str) -> bool:
        for index, job in enumerate(self._jobs):
            if job.job_id != job_id:
                continue
            recycle_number = None
            if job.is_unused_draft() and job.job_id.startswith("JOB-"):
                try:
                    number = int(job.job_id[4:])
                except ValueError:
                    number = None
                if number is not None and number == self._next_number - 1:
                    recycle_number = number
            del self._jobs[index]
            if recycle_number is not None:
                self._next_number = recycle_number
            return True
        return False

    def move_up(self, job_id: str) -> bool:
        for index, job in enumerate(self._jobs):
            if job.job_id == job_id:
                if index == 0:
                    return False
                self._jobs[index - 1], self._jobs[index] = self._jobs[index], self._jobs[index - 1]
                return True
        return False

    def move_down(self, job_id: str) -> bool:
        for index, job in enumerate(self._jobs):
            if job.job_id == job_id:
                if index >= len(self._jobs) - 1:
                    return False
                self._jobs[index], self._jobs[index + 1] = self._jobs[index + 1], self._jobs[index]
                return True
        return False

    def get(self, job_id: str) -> Job | None:
        return next((job for job in self._jobs if job.job_id == job_id), None)

    def jobs(self) -> list[Job]:
        return list(self._jobs)

    def __len__(self) -> int:
        return len(self._jobs)

    def counts(self) -> dict[JobStatus, int]:
        return {status: sum(job.status == status for job in self._jobs) for status in JobStatus}
