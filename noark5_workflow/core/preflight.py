from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

from noark5_workflow.core.job import Job, JobBatch, JobStatus


_TERMINAL_STATUSES = {JobStatus.OK, JobStatus.PARTIAL, JobStatus.FAILED, JobStatus.SKIPPED, JobStatus.INTERRUPTED}


@dataclass(frozen=True)
class OutputConflict:
    first_job_id: str
    second_job_id: str
    output_root: Path


@dataclass(frozen=True)
class PreflightChange:
    job_id: str
    code: str
    message: str


@dataclass
class PreflightReport:
    changes: list[PreflightChange] = field(default_factory=list)
    output_conflicts: list[OutputConflict] = field(default_factory=list)
    rerun_jobs: list[Job] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.output_conflicts

    @property
    def rerun_required(self) -> bool:
        return bool(self.rerun_jobs)


class JobPreflight:
    """GUI-independent checks and safe normalization before execution.

    The preflight layer reports facts and performs only safe state normalization.
    It does not ask users questions and does not decide whether reruns are allowed.
    """

    @staticmethod
    def _jobs(jobs: JobBatch | Iterable[Job]) -> list[Job]:
        return jobs.jobs() if isinstance(jobs, JobBatch) else list(jobs)

    @staticmethod
    def _path_key(path: Path) -> str:
        try:
            resolved = path.resolve()
        except OSError:
            resolved = path.absolute()
        return str(resolved).casefold()

    def normalize_job(self, job: Job) -> list[PreflightChange]:
        changes: list[PreflightChange] = []

        if job.status == JobStatus.RUNNING:
            job.reset_execution("Tidligere kjøring var ikke aktiv - klar for ny kjøring")
            changes.append(
                PreflightChange(job.job_id, "stale_running", "Stale RUNNING-status satt til Klar")
            )

        try:
            index = int(job.next_operation_index)
        except (TypeError, ValueError):
            index = -1

        if index < 0 or index > len(job.workflow_ids):
            job.next_operation_index = 0
            if job.status == JobStatus.WAITING:
                job.status = JobStatus.READY
                job.progress = 0.0
                job.message = "Ugyldig execution cursor fra import - klar for ny kjøring"
            changes.append(
                PreflightChange(job.job_id, "invalid_cursor", "Ugyldig execution cursor satt til 0")
            )

        return changes

    def normalize(self, jobs: JobBatch | Iterable[Job]) -> list[PreflightChange]:
        changes: list[PreflightChange] = []
        for job in self._jobs(jobs):
            changes.extend(self.normalize_job(job))
        return changes

    def check_outputs(self, jobs: JobBatch | Iterable[Job]) -> list[OutputConflict]:
        seen: dict[str, Job] = {}
        conflicts: list[OutputConflict] = []
        for job in self._jobs(jobs):
            if job.output_root is None:
                continue
            key = self._path_key(job.output_root)
            other = seen.get(key)
            if other is not None and other.job_id != job.job_id:
                conflicts.append(OutputConflict(other.job_id, job.job_id, job.output_root))
            else:
                seen[key] = job
        return conflicts

    def find_reruns(self, jobs: JobBatch | Iterable[Job]) -> list[Job]:
        return [
            job
            for job in self._jobs(jobs)
            if job.status in _TERMINAL_STATUSES
            or job.message == "Konfigurasjon endret - klar for ny kjøring"
        ]

    def check(self, jobs: JobBatch | Iterable[Job], *, normalize: bool = True) -> PreflightReport:
        ordered = self._jobs(jobs)
        return PreflightReport(
            changes=self.normalize(ordered) if normalize else [],
            output_conflicts=self.check_outputs(ordered),
            rerun_jobs=self.find_reruns(ordered),
        )
