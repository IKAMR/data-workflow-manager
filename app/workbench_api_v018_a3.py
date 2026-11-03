"""Desktop-neutral workbench commands for DWM v0.1.8-a3 and a4.

The PySide6 UI and future UI implementations use this facade. It deliberately
reuses the authoritative .n5jobs store, Job model and A39JobRunner from a1.
No GUI package is imported here; storage paths remain independent.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Mapping

from app.application_api import DwmApiError, DwmApplication, JobView, WorkspaceView
from app.job_workflow_policy import configured_sequence
from noark5_workflow.core.job import Job, JobBatch, JobStatus


@dataclass(frozen=True)
class OperationView:
    operation_id: str
    name: str
    category: str
    position: int
    completed: bool
    checkpoint: bool
    configured: bool


@dataclass(frozen=True)
class JobDetails:
    job: JobView
    operations: tuple[OperationView, ...]
    message: str
    storage: dict[str, str]


STORAGE_FIELDS = (
    "source_root", "source_tar", "source_unzipped", "source_extraction",
    "work_root", "work_content", "work_operations", "archive_root",
)


class DwmWorkbenchAPI(DwmApplication):
    """GUI-agnostic workbench with read models and explicit editing commands.

    Commands mutate the existing in-memory job list only when execution is idle.
    Save is explicit. Existing paths/results are never moved or deleted.
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._dirty = False
        self._catalog = None

    @property
    def dirty(self) -> bool:
        return self._dirty

    @property
    def running(self) -> bool:
        return self._running

    def open_job_list(self, path: str | Path) -> WorkspaceView:
        view = super().open_job_list(path)
        self._dirty = False
        return view

    def save_job_list(self, path: str | Path | None = None) -> Path:
        output = super().save_job_list(path)
        self._dirty = False
        return output

    def new_job_list(self) -> WorkspaceView:
        with self._guard:
            self._assert_idle()
            self._batch = JobBatch()
            self._batch.output_subfolder_rule = ""
            self._path = None
            self._active_job_id = None
            self._dirty = False
            view = self.workspace()
        self._emit("joblist.new", message="Ny jobbliste")
        return view

    def _registry_catalog(self) -> dict[str, tuple[str, str]]:
        if self._catalog is None:
            # Importing the operation registry is safe for headless/CLI use.
            # Registry construction need not happen at application startup.
            from noark5_workflow.app import build_registry
            self._catalog = {
                op.definition.operation_id: (
                    str(op.definition.name), str(op.definition.category)
                )
                for op in build_registry().all()
            }
        return self._catalog

    def available_operations(self) -> tuple[OperationView, ...]:
        return tuple(
            OperationView(key, name, category, i, False, False, False)
            for i, (key, (name, category)) in enumerate(self._registry_catalog().items(), 1)
        )

    def job_details(self, job_id: str) -> JobDetails:
        job = self._require_job(job_id)
        position = next(
            i for i, item in enumerate(self._batch.jobs(), 1)
            if item.job_id == job_id
        )
        catalog = self._registry_catalog()
        operations = tuple(
            OperationView(
                operation_id=operation_id,
                name=catalog.get(operation_id, (operation_id, "Ukjent"))[0],
                category=catalog.get(operation_id, (operation_id, "Ukjent"))[1],
                position=i,
                completed=i <= int(job.next_operation_index),
                checkpoint=job.has_checkpoint(operation_id),
                configured=bool(job.get_operation_params(operation_id)),
            )
            for i, operation_id in enumerate(job.workflow_ids, 1)
        )
        return JobDetails(
            job=self._view(job, position), operations=operations,
            message=str(job.message or ""),
            storage={field: str(getattr(job, field) or "") for field in STORAGE_FIELDS},
        )

    def create_job(
        self, *, source_extraction: str | Path | None = None,
        work_operations: str | Path | None = None, name: str = "",
        profile_id: str = "noark5",
    ) -> JobView:
        with self._guard:
            self._assert_idle()
            source = Path(source_extraction) if source_extraction else None
            work = Path(work_operations) if work_operations else None
            job = self._batch.new_job(source_root=source, name=name or (source.name if source else ""))
            job.source_extraction = source
            job.work_operations = work
            job.profile_id = profile_id
            default = configured_sequence(self.settings, profile_id=profile_id)
            if default is not None:
                job.set_workflow(default.operation_ids)
            self._active_job_id = job.job_id
            self._dirty = True
            position = len(self._batch.jobs())
            view = self._view(job, position)
        self._emit("job.created", job)
        return view

    def update_storage(self, job_id: str, paths: Mapping[str, str | Path | None]) -> JobDetails:
        unknown = set(paths) - set(STORAGE_FIELDS)
        if unknown:
            raise DwmApiError("Ukjente lagringsroller: " + ", ".join(sorted(unknown)))
        with self._guard:
            self._assert_idle()
            job = self._require_job(job_id)
            for field, value in paths.items():
                setattr(job, field, Path(value) if value else None)
            self._dirty = True
        self._emit("job.storage_changed", job)
        return self.job_details(job_id)

    def set_workflow(self, job_id: str, operation_ids: Iterable[str]) -> JobDetails:
        ids = [str(item) for item in operation_ids]
        if not ids or len(ids) != len(set(ids)):
            raise DwmApiError("Arbeidsflyten må inneholde unike operasjoner.")
        unknown = set(ids) - set(self._registry_catalog())
        if unknown:
            raise DwmApiError("Ukjente operasjoner: " + ", ".join(sorted(unknown)))
        with self._guard:
            self._assert_idle()
            job = self._require_job(job_id)
            if list(job.workflow_ids) == ids:
                return self.job_details(job_id)
            previously_run = (
                job.status in {JobStatus.OK, JobStatus.FAILED, JobStatus.SKIPPED, JobStatus.WAITING}
                or job.next_operation_index > 0
            )
            job.set_workflow(ids)
            if previously_run:
                job.reset_execution("Konfigurasjon endret - klar for ny kjøring")
            self._dirty = True
        self._emit("job.workflow_changed", job)
        return self.job_details(job_id)

    def set_checkpoint(self, job_id: str, operation_id: str, enabled: bool) -> JobDetails:
        with self._guard:
            self._assert_idle()
            job = self._require_job(job_id)
            job.set_checkpoint(operation_id, enabled)
            self._dirty = True
        self._emit("job.checkpoint_changed", job)
        return self.job_details(job_id)

    # ---------- a4: job-list editing without touching extraction/results ----------
    def _effective_path_map(self, jobs: Iterable[Job]) -> dict[str, str | None]:
        """Resolve effective Work paths before and after a list mutation.

        A job-list rule may use <nnn> or <name>. A reorder or rename must not
        silently redirect reports/evidence to a different folder.
        """
        return {
            job.job_id: self._view(job, position).effective_work_operations
            for position, job in enumerate(jobs, 1)
        }

    def _assert_work_paths_unchanged(self, before: dict[str, str | None],
                                     proposed: Iterable[Job]) -> None:
        after = self._effective_path_map(proposed)
        changed = [job_id for job_id, path in after.items()
                   if job_id in before and path != before[job_id]]
        if changed:
            raise DwmApiError(
                "Endringen ville endre effektiv Work – operations-sti for "
                + ", ".join(changed)
                + ". Juster jobbregel eller lagringsoppsett eksplisitt først."
            )

    def rename_job(self, job_id: str, name: str) -> JobDetails:
        """Change only the human-facing job name; preserve identity and results."""
        cleaned = str(name or "").strip()
        if not cleaned or len(cleaned) > 255:
            raise DwmApiError("Jobbnavnet må være mellom 1 og 255 tegn.")
        with self._guard:
            self._assert_idle()
            job = self._require_job(job_id)
            modified = job.name != cleaned
            if modified:
                before = self._effective_path_map(self._batch.jobs())
                original = job.name
                job.name = cleaned
                try:
                    self._assert_work_paths_unchanged(before, self._batch.jobs())
                except Exception:
                    job.name = original
                    raise
                self._dirty = True
        if modified:
            self._emit("job.renamed", job)
        return self.job_details(job_id)

    def move_job(self, job_id: str, direction: int) -> WorkspaceView:
        """Reorder jobs only when no effective Work path would change."""
        if direction not in (-1, 1):
            raise DwmApiError("Flytteretning må være -1 eller 1.")
        with self._guard:
            self._assert_idle()
            job = self._require_job(job_id)
            before_jobs = self._batch.jobs()
            old_index = next(i for i, item in enumerate(before_jobs)
                             if item.job_id == job_id)
            new_index = old_index + direction
            moved = 0 <= new_index < len(before_jobs)
            if moved:
                before = self._effective_path_map(before_jobs)
                proposed = list(before_jobs)
                proposed[old_index], proposed[new_index] = proposed[new_index], proposed[old_index]
                self._assert_work_paths_unchanged(before, proposed)
                moved = (self._batch.move_up(job_id) if direction == -1
                         else self._batch.move_down(job_id))
                self._dirty = True
            result = self.workspace()
        if moved:
            self._emit("job.moved", job)
        return result

    def remove_job(self, job_id: str) -> WorkspaceView:
        """Remove a job-list reference only; never delete on-disk data."""
        with self._guard:
            self._assert_idle()
            job = self._require_job(job_id)
            jobs_before = self._batch.jobs()
            old_index = next(i for i, item in enumerate(jobs_before)
                             if item.job_id == job_id)
            before = self._effective_path_map(jobs_before)
            remaining = [item for item in jobs_before if item.job_id != job_id]
            self._assert_work_paths_unchanged(before, remaining)
            if not self._batch.remove(job_id):
                raise DwmApiError(f"Kunne ikke fjerne jobb {job_id}.")
            if self._active_job_id == job_id:
                self._active_job_id = (
                    remaining[min(old_index, len(remaining) - 1)].job_id
                    if remaining else None
                )
            self._dirty = True
            result = self.workspace()
        self._emit("job.removed", job)
        return result
