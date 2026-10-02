from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable


@dataclass(frozen=True)
class JobListContext:
    """Read-only projection of DWM's current job-list working context.

    The authoritative mutable state remains the existing job batch/list,
    current job and job-list path owned by the runtime.  This object merely
    gives later GUI, CLI and server layers one explicit, shared vocabulary.

    A job list is a working context even when it has only one job or has not
    yet been saved to a file.
    """

    jobs: tuple[Any, ...]
    active_job: Any | None
    job_list_path: Path | None

    @classmethod
    def from_runtime_state(
        cls,
        jobs: Iterable[Any],
        active_job: Any | None,
        job_list_path: str | Path | None,
    ) -> "JobListContext":
        path = Path(job_list_path) if job_list_path else None
        return cls(tuple(jobs), active_job, path)

    @property
    def job_count(self) -> int:
        return len(self.jobs)

    @property
    def is_single_job(self) -> bool:
        return self.job_count == 1

    @property
    def is_saved(self) -> bool:
        return self.job_list_path is not None

    @property
    def active_job_id(self) -> str | None:
        if self.active_job is None:
            return None
        value = getattr(self.active_job, "job_id", None)
        return str(value) if value is not None else None

    @property
    def active_position(self) -> int | None:
        """1-based position of the active job in the job list."""
        if self.active_job is None:
            return None
        for index, job in enumerate(self.jobs, start=1):
            if job is self.active_job:
                return index
        return None

    @property
    def has_consistent_active_job(self) -> bool:
        """Whether active-job identity agrees with the current job list."""
        if not self.jobs:
            return self.active_job is None
        return self.active_position is not None

    @property
    def display_identity(self) -> str:
        if self.job_list_path is None:
            return "Ulagret jobbliste"
        return self.job_list_path.name

    def require_consistent(self) -> "JobListContext":
        """Fail explicitly at boundaries that require a valid active job."""
        if not self.jobs:
            raise ValueError("Jobblista inneholder ingen jobber.")
        if self.active_job is None:
            raise ValueError("Jobblista har ingen aktiv jobb.")
        if self.active_position is None:
            raise ValueError("Aktiv jobb tilhører ikke gjeldende jobbliste.")
        return self
