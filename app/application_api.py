"""Headless application boundary for Data Workflow Manager.

v0.1.8-a1: deliberately independent of tkinter, Qt and the GUI runtime.
An adapter may call run_job() on its OWN worker thread and poll events on its
GUI thread; this module never creates GUI windows or background threads.

The existing v0.1.7 desktop application remains unchanged in a1.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from queue import Empty, Full, Queue
from threading import Event, Lock
from typing import Any, Callable

from app.work_output_layout import effective_work_operations, validate_layout
from noark5_workflow.core.job import Job, JobBatch, JobStatus
from noark5_workflow.core.job_store import load_job_list, save_job_list
from noark5_workflow.core.preflight import JobPreflight
from settings import load_config
from version import VERSION


class DwmApiError(RuntimeError):
    """Invalid application command; safe to display in any frontend."""


@dataclass(frozen=True)
class DwmEvent:
    kind: str
    job_id: str | None = None
    message: str = ""
    status: str = ""
    progress: float | None = None


@dataclass(frozen=True)
class JobView:
    """JSON-friendly, immutable view; never expose a mutable Job to frontends."""
    job_id: str
    name: str
    status: str
    progress: float
    current_operation: int
    operation_count: int
    source_root: str | None
    source_extraction: str | None
    work_root: str | None
    work_content: str | None
    work_operations: str | None
    effective_work_operations: str | None
    archive_root: str | None
    output_root: str | None

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class WorkspaceView:
    job_list_path: str | None
    active_job_id: str | None
    jobs: tuple[JobView, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "job_list_path": self.job_list_path,
            "active_job_id": self.active_job_id,
            "jobs": [job.as_dict() for job in self.jobs],
        }


class DwmApplication:
    """A thin command/query facade above the established DWM core.

    Thread contract: one run at a time. run_job() is synchronous and must be
    called off a GUI event loop. poll_events() is safe from the UI thread.
    Modifying commands are rejected during execution. No GUI toolkit imported.

    This is an a1 contract, not a replacement for the mature GUI's complete
    batch execution, retry, checkpoint and persistence machinery.
    """

    def __init__(
        self,
        *,
        settings: dict[str, Any] | None = None,
        runner_factory: Callable[[dict[str, Any]], Any] | None = None,
    ) -> None:
        self.settings = dict(load_config() if settings is None else settings)
        self._runner_factory = runner_factory or self._default_runner
        self._batch = JobBatch()
        self._path: Path | None = None
        self._active_job_id: str | None = None
        self._work_references: dict[str, Path] = {}
        self._unavailable_work_ids: frozenset[str] = frozenset()
        self._events: Queue[DwmEvent] = Queue(maxsize=4096)
        self._running = False
        self._guard = Lock()
        self._cancel = Event()

    @staticmethod
    def _default_runner(settings: dict[str, Any]):
        # Import only when executing. Inspection/open/save needs no operation
        # registry, GUI or analysis dependencies beyond the core job model.
        from noark5_workflow.app import build_registry
        from noark5_workflow.core.job_runner_a39 import A39JobRunner
        from noark5_workflow.executors.local import LocalExecutor
        return A39JobRunner(build_registry(), LocalExecutor(), settings)

    def _emit(self, kind: str, job: Job | None = None, *, message: str = "", progress: float | None = None) -> None:
        event = DwmEvent(
            kind=kind,
            job_id=job.job_id if job is not None else None,
            message=str(message),
            status=job.status.value if job is not None else "",
            progress=progress,
        )
        # UI notifications are bounded, not an archival log. Never block a
        # worker on a slow/closed frontend; drop the oldest UI event instead.
        try:
            self._events.put_nowait(event)
        except Full:
            try:
                self._events.get_nowait()
            except Empty:
                pass
            try:
                self._events.put_nowait(event)
            except Full:
                pass

    def poll_events(self, limit: int = 100) -> tuple[DwmEvent, ...]:
        """Drain up to limit queued events; safe for Tk.after or Qt timers."""
        if limit <= 0:
            return ()
        result: list[DwmEvent] = []
        for _ in range(min(limit, 10_000)):
            try:
                result.append(self._events.get_nowait())
            except Empty:
                break
        return tuple(result)

    def _assert_idle(self) -> None:
        if self._running:
            raise DwmApiError("En jobb kjører. Endringer i jobblisten er låst.")

    def open_job_list(self, path: str | Path) -> WorkspaceView:
        with self._guard:
            self._assert_idle()
            target = Path(path)
            loaded = load_job_list(target)
            self._batch = loaded.batch
            self._path = target
            self._active_job_id = loaded.active_job_id
            self._work_references = dict(loaded.work_references)
            self._unavailable_work_ids = loaded.unavailable_work_job_ids
            view = self.workspace()
        self._emit("joblist.opened", message=str(target))
        return view

    def workspace(self) -> WorkspaceView:
        return WorkspaceView(
            job_list_path=str(self._path) if self._path is not None else None,
            active_job_id=self._active_job_id,
            jobs=tuple(self._view(job, position) for position, job in enumerate(self._batch.jobs(), 1)),
        )

    def _view(self, job: Job, position: int) -> JobView:
        def path(value: Path | None) -> str | None:
            return str(value) if value is not None else None

        rule = str(getattr(self._batch, "output_subfolder_rule", "") or "")
        if job.job_id in self._work_references:
            # A Work-backed job keeps its actual Work location even if a local
            # job-list output rule or global setting is later changed.
            output = self._work_references[job.job_id].parent
        else:
            output = effective_work_operations(
                job.work_operations,
                str(self.settings.get("app_work_subfolder", "dwm") or ""),
                rule, job, position,
            )
        status = (
            f"Frakoblet (sist: {job.status.value})"
            if job.job_id in self._unavailable_work_ids else job.status.value
        )
        return JobView(
            job_id=job.job_id,
            name=job.name,
            status=status,
            progress=float(job.progress),
            current_operation=int(job.next_operation_index),
            operation_count=len(job.workflow_ids),
            source_root=path(job.source_root),
            source_extraction=path(job.source_extraction),
            work_root=path(job.work_root),
            work_content=path(job.work_content),
            work_operations=path(job.work_operations),
            effective_work_operations=path(output),
            archive_root=path(job.archive_root),
            output_root=path(job.output_root),
        )

    def select_job(self, job_id: str) -> JobView:
        with self._guard:
            self._assert_idle()
            job = self._require_job(job_id)
            self._active_job_id = job_id
            position = next(i for i, item in enumerate(self._batch.jobs(), 1) if item.job_id == job_id)
            view = self._view(job, position)
        self._emit("job.selected", job)
        return view

    def _require_job(self, job_id: str) -> Job:
        job = self._batch.get(job_id)
        if job is None:
            raise DwmApiError(f"Ukjent jobb: {job_id}")
        return job

    def _write_job_list_file(self, target: Path, active_job_id: str | None) -> Path:
        """Overridden by Work-first workbenches; legacy callers keep v4."""
        return save_job_list(
            target, self._batch, active_job_id=active_job_id, app_version=VERSION,
        )

    def _persist_updated_job(self, job: Job, active_job_id: str) -> None:
        """Runner callback. Work-first backends persist Work before the index."""
        assert self._path is not None
        self._write_job_list_file(self._path, active_job_id)

    def save_job_list(self, path: str | Path | None = None) -> Path:
        with self._guard:
            self._assert_idle()
            target = Path(path) if path is not None else self._path
            if target is None:
                raise DwmApiError("Ingen lagringssti for jobblisten er valgt.")
            output = self._write_job_list_file(target, self._active_job_id)
            self._path = output
        self._emit("joblist.saved", message=str(output))
        return output

    def check_storage(self) -> tuple[str, ...]:
        """Read-only checks; never create, move or copy Source/Work/AIP."""
        problems: list[str] = []
        jobs = self._batch.jobs()
        for conflict in JobPreflight().check_outputs(jobs):
            problems.append(f"AIP/utdata-kollisjon: {conflict.first_job_id} / {conflict.second_job_id}: {conflict.output_root}")
        try:
            if not self._work_references:
                validate_layout(
                    str(self.settings.get("app_work_subfolder", "dwm") or ""),
                    str(getattr(self._batch, "output_subfolder_rule", "") or ""),
                    jobs,
                )
            else:
                # Pinned Work paths are canonical. Different joblists can
                # group Noark 5/SIARD jobs without inheriting an older folder
                # rule, even when their original Work bases are identical.
                from app.work_output_layout import validate_app_work_subfolder
                validate_app_work_subfolder(
                    str(self.settings.get("app_work_subfolder", "dwm") or "")
                )
                seen: dict[str, str] = {}
                for position, job in enumerate(jobs, 1):
                    path = self._view(job, position).effective_work_operations
                    if path is None:
                        continue
                    key = str(Path(path).resolve(strict=False)).casefold()
                    other = seen.get(key)
                    if other and other != job.job_id:
                        problems.append(
                            f"To jobber peker til samme Work-område: {other} og {job.job_id}"
                        )
                    seen[key] = job.job_id
        except ValueError as exc:
            problems.append(str(exc))
        return tuple(problems)

    def request_cancel(self) -> None:
        """Cooperative request; operation code controls when it can stop."""
        self._cancel.set()
        self._emit("run.cancel_requested")

    def run_job(self, job_id: str, *, allow_rerun: bool = False, continue_waiting: bool = False) -> bool:
        """Run one existing job using A39JobRunner (or injected runner).

        Caller owns the worker thread. No implicit reruns, storage relocation,
        batch scheduling or GUI updates. The job list is saved on state changes.
        """
        with self._guard:
            self._assert_idle()
            if self._path is None:
                raise DwmApiError("Åpne og lagre en jobbliste før kjøring.")
            job = self._require_job(job_id)
            if not job.workflow_ids:
                raise DwmApiError(f"{job_id} har ingen operasjoner.")
            if job.active_extraction_root is None or not job.active_extraction_root.is_dir():
                raise DwmApiError(f"Uttrekket er ikke tilgjengelig: {job.active_extraction_root}")
            if job.status == JobStatus.RUNNING:
                raise DwmApiError(f"{job_id} står allerede som kjørende.")
            if job.status == JobStatus.WAITING and not continue_waiting:
                raise DwmApiError("Jobben venter ved kontrollpunkt. Velg eksplisitt fortsettelse.")
            if job.status != JobStatus.WAITING and continue_waiting:
                raise DwmApiError("Fortsettelse krever status Venter ved kontrollpunkt.")
            if JobPreflight().find_reruns([job]) and not allow_rerun and not continue_waiting:
                raise DwmApiError("Tidligere kjørt jobb krever eksplisitt godkjenning av ny kjøring.")
            errors = self.check_storage()
            if errors:
                raise DwmApiError("Ugyldig lagringsoppsett: " + "; ".join(errors))
            position = next(i for i, item in enumerate(self._batch.jobs(), 1) if item.job_id == job_id)
            effective = effective_work_operations(
                job.work_operations,
                str(self.settings.get("app_work_subfolder", "dwm") or ""),
                str(getattr(self._batch, "output_subfolder_rule", "") or ""),
                job,
                position,
            )
            if job_id in self._work_references:
                # Work is canonical, including when the original list/rule is gone.
                effective = self._work_references[job_id].parent
            self._running = True
            self._cancel.clear()
            self._active_job_id = job_id
            # The authoritative storage roles stay unchanged on the Job.
            job._effective_work_operations = effective

        self._emit("run.started", job)

        def persist(updated: Job) -> None:
            # The Work-first adapter writes the authoritative Work state
            # before updating its disposable job-list index.
            self._persist_updated_job(updated, job_id)
            self._emit("run.state", updated, message=updated.message, progress=updated.progress)

        def progress(value: float, message: str) -> None:
            self._emit("run.progress", job, message=message, progress=float(value))

        def log(message: str) -> None:
            self._emit("run.log", job, message=message)

        try:
            # A10: one stable identity for the whole workflow.  Never mutate
            # global Setup settings: a future job/batch may run in another
            # process or thread with its own run/job identity.
            from uuid import uuid4
            runtime_settings = dict(self.settings)
            run_id = str(getattr(job, "_active_run_id", "") or "")
            generated_here = not run_id
            if generated_here:
                run_id = "RUN-" + uuid4().hex
                job._active_run_id = run_id
            runtime_settings["_current_run_id"] = run_id
            runtime_settings["_current_job_uid"] = str(getattr(job, "job_uid", "") or "")
            runtime_settings["_current_run_kind"] = "workflow"
            runner = self._runner_factory(runtime_settings)
            callbacks = dict(progress_cb=progress, log_cb=log,
                             cancelled_cb=self._cancel.is_set, state_cb=persist)
            if continue_waiting:
                outcome = runner.continue_job(job, **callbacks)
            else:
                outcome = runner.run(job, **callbacks)
            persist(job)
            self._emit("run.finished", job, progress=job.progress)
            return bool(outcome.ok)
        except Exception as exc:
            if job.status == JobStatus.RUNNING:
                job.status = JobStatus.FAILED
                job.message = f"Teknisk feil ved kjøring: {exc}"
                try:
                    persist(job)
                except Exception:
                    # Preserve the original exception; the caller may need to
                    # recover the job list on a temporarily unavailable disk.
                    pass
            self._emit("run.error", job, message=str(exc))
            raise
        finally:
            # Avoid stale effective path when a different adapter changes the
            # storage role or output rule before the next run.
            if hasattr(job, "_effective_work_operations"):
                delattr(job, "_effective_work_operations")
            if "generated_here" in locals() and generated_here and hasattr(job, "_active_run_id"):
                delattr(job, "_active_run_id")
            with self._guard:
                self._running = False
                self._cancel.clear()
