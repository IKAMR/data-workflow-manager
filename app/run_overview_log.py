from __future__ import annotations

from datetime import datetime
from pathlib import Path
from uuid import uuid4

from app.runtime_environment import capture_runtime_environment
from app.workspace import ensure_workspace, run_log_dir
from noark5_workflow.core.events import WorkflowEvent
from noark5_workflow.core.identity import UserIdentity
from noark5_workflow.logging_pipeline import (
    TEXT_RUN_LOG_SINK,
    build_event_dispatcher,
    find_sink,
)


def _status_text(job) -> str:
    status = getattr(job, "status", "")
    value = getattr(status, "value", None)
    if value is not None:
        return str(value)
    name = getattr(status, "name", None)
    if name is not None:
        return str(name)
    return str(status)


def _owner_snapshot(job) -> dict[str, str]:
    return {
        "user_id": str(getattr(job, "owner_user_id", "") or ""),
        "username": str(getattr(job, "owner_username", "") or ""),
        "name": str(getattr(job, "owner_name", "") or ""),
        "email": str(getattr(job, "owner_email", "") or ""),
    }


def _effective_work_operations(job) -> str:
    return str(
        getattr(job, "_effective_work_operations", None)
        or getattr(job, "work_operations", "")
        or ""
    )


class RunOverviewLog:
    """Compatibility facade that emits canonical runtime events."""

    def __init__(
        self,
        settings: dict,
        *,
        run_type: str,
        app_version: str,
        job_list_path: Path | None = None,
        planned_jobs: int | None = None,
    ) -> None:
        ensure_workspace(settings)
        self.settings = settings

        now = datetime.now().astimezone()
        self.run_id = f"RUN-{now.strftime('%Y%m%d-%H%M%S')}-{uuid4().hex[:8]}"
        event_store_path = run_log_dir(settings) / f"{self.run_id}.events.jsonl"

        settings["_current_run_id"] = self.run_id
        settings["_current_event_store_path"] = str(event_store_path)

        # Capture once per run. All jobs/operations in the run receive the same
        # environment snapshot, which makes benchmark/result comparison stable.
        self.environment = capture_runtime_environment()
        settings["_current_run_environment"] = dict(self.environment)

        self.dispatcher = build_event_dispatcher(
            settings,
            scope="run",
            run_type=run_type,
            app_version=app_version,
            job_list_path=job_list_path,
            planned_jobs=planned_jobs,
            run_id=self.run_id,
        )
        self.sink = find_sink(self.dispatcher, TEXT_RUN_LOG_SINK)
        self.event_store_path = event_store_path

        user = UserIdentity.from_mapping(settings.get("_current_user_identity"))
        self._emit(WorkflowEvent.now(
            "run.started",
            run_id=self.run_id,
            user=user,
            data={
                "run_type": run_type,
                "app_version": app_version,
                "job_list_path": str(job_list_path or ""),
                "planned_jobs": planned_jobs,
                "environment": self.environment,
            },
        ))

    def __getattr__(self, name):
        if self.sink is not None and hasattr(self.sink, name):
            return getattr(self.sink, name)
        raise AttributeError(name)

    @property
    def path(self) -> Path:
        if self.sink is not None:
            return self.sink.path
        return self.event_store_path

    def _event_user(self) -> UserIdentity | None:
        return UserIdentity.from_mapping(self.settings.get("_current_user_identity"))

    def _emit(self, event: WorkflowEvent) -> None:
        self.dispatcher.emit(event)

    def set_phase(self, phase: str) -> None:
        self._emit(WorkflowEvent.now(
            "run.phase",
            run_id=self.run_id,
            user=self._event_user(),
            data={"phase": str(phase)},
        ))

    def start_job(self, job) -> None:
        source_root = str(getattr(job, "source_root", "") or "")
        source_extraction = str(getattr(job, "source_extraction", "") or "")
        active_source = str(getattr(job, "active_extraction_root", "") or source_root)
        work_root = str(getattr(job, "work_root", "") or "")
        work_operations_base = str(getattr(job, "work_operations", "") or "")
        work_operations_effective = _effective_work_operations(job)
        archive_root = str(getattr(job, "archive_root", "") or "")
        output = archive_root or str(getattr(job, "output_root", "") or "")
        self._emit(WorkflowEvent.now(
            "job.started",
            run_id=self.run_id,
            job_id=str(getattr(job, "job_id", "") or ""),
            user=self._event_user(),
            data={
                "name": str(getattr(job, "name", "") or ""),
                "source": active_source,
                "source_root": source_root,
                "source_extraction": source_extraction,
                "work_root": work_root,
                "work_operations": work_operations_effective,
                "work_operations_base": work_operations_base,
                "work_operations_effective": work_operations_effective,
                "archive_root": archive_root,
                "output": output,
                "owner": _owner_snapshot(job),
            },
        ))

    def finish_job(self, job) -> None:
        archive_root = str(getattr(job, "archive_root", "") or "")
        output = archive_root or str(getattr(job, "output_root", "") or "")
        work_operations_base = str(getattr(job, "work_operations", "") or "")
        work_operations_effective = _effective_work_operations(job)
        self._emit(WorkflowEvent.now(
            "job.finished",
            run_id=self.run_id,
            job_id=str(getattr(job, "job_id", "") or ""),
            user=self._event_user(),
            message=str(getattr(job, "message", "") or ""),
            data={
                "status": _status_text(job),
                "work_root": str(getattr(job, "work_root", "") or ""),
                "work_operations": work_operations_effective,
                "work_operations_base": work_operations_base,
                "work_operations_effective": work_operations_effective,
                "archive_root": archive_root,
                "output": output,
            },
        ))

    def fail(self, exc: BaseException | str) -> Path:
        self._emit(WorkflowEvent.now(
            "run.failed",
            run_id=self.run_id,
            user=self._event_user(),
            success=False,
            message=str(exc),
        ))
        return self.path

    def finish(self, status: str = "FERDIG") -> Path:
        self._emit(WorkflowEvent.now(
            "run.finished",
            run_id=self.run_id,
            user=self._event_user(),
            data={"status": status},
        ))
        return self.path
