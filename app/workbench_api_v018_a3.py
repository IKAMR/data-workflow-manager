"""Desktop-neutral workbench commands for DWM v0.1.8 through a7.

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
from app.work_output_layout import effective_work_operations, validate_layout
from noark5_workflow.core.output_subfolder import render_output_subfolder_rule
from app.job_preflight_v018_a6 import (
    PreflightIssue, PreflightReport, inspect_job, paths_to_create,
    propose_work_location,
)
from app.arkade5_setup_v018_a7 import (
    Arkade5Check, Arkade5DependencyChecker, requires_arkade_cli,
)
from app.work_output_layout import validate_app_work_subfolder
from settings import load_config, save_config
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
        self._arkade_checker = Arkade5DependencyChecker()

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

    # ---------- a7: shared Setup and external operation dependencies ----------
    def check_arkade5_cli(self, *, path: str | Path | None = None,
                          refresh: bool = False) -> Arkade5Check:
        """Check a proposed path without changing settings or job data."""
        selected = dict(self.settings)
        if path is not None:
            selected["arkade5_cli_path"] = str(path)
        return self._arkade_checker.check(selected, refresh=refresh)

    def save_setup(self, changes: Mapping[str, object]) -> dict:
        """Persist only approved global keys; no silent settings changes.

        Do not mix Qt's view-layout configuration with the DWM core's settings.
        This changes future runs, never historical results or Source files.
        """
        allowed = {
            "arkade5_cli_path", "arkade5_output_subfolder", "noark5_discovery_workflow",
            "app_work_subfolder", "temp_dir", "run_log_dir", "setup_dir",
            "job_list_dir", "operation_visibility",
        }
        unknown = set(changes) - allowed
        if unknown:
            raise DwmApiError("Ukjente Setup-innstillinger: " + ", ".join(sorted(unknown)))
        updated = {key: str(value or "").strip() for key, value in changes.items()
                   if key != "operation_visibility"}
        if "operation_visibility" in changes:
            try:
                visibility = int(changes["operation_visibility"])
            except (TypeError, ValueError) as exc:
                raise DwmApiError("Operasjonsnivå må være et tall fra 0 til 2.") from exc
            if visibility not in (0, 1, 2):
                raise DwmApiError("Operasjonsnivå må være 0, 1 eller 2.")
            updated["operation_visibility"] = visibility
        if "arkade5_cli_path" in updated:
            selected = updated["arkade5_cli_path"].strip('"')
            if selected and not Path(selected).is_absolute():
                raise DwmApiError("Arkade 5 CLI må angis med absolutt sti.")
            updated["arkade5_cli_path"] = selected
        if "app_work_subfolder" in updated:
            updated["app_work_subfolder"] = validate_app_work_subfolder(
                updated["app_work_subfolder"]
            )
        if "arkade5_output_subfolder" in updated:
            from noark5_workflow.external_tools.arkade5_jobs import resolve_arkade5_output_subfolder
            resolve_arkade5_output_subfolder(
                {"arkade5_output_subfolder": updated["arkade5_output_subfolder"]}, "2.13.1"
            )
        if "noark5_discovery_workflow" in updated:
            from app.workflow_sequences import workflow_sequence_by_id
            sequence = workflow_sequence_by_id(updated["noark5_discovery_workflow"])
            if sequence is None or sequence.profile_id != "noark5":
                raise DwmApiError("Ukjent standardprofil for Noark 5.")
        if "app_work_subfolder" in updated:
            # Reject collisions before changing a global Work rule; this is
            # otherwise easy to miss when several jobs share a Work base.
            try:
                validate_layout(
                    updated["app_work_subfolder"], self.output_subfolder_rule,
                    self._batch.jobs(),
                )
            except ValueError as exc:
                raise DwmApiError("Global DWM-undermappe gir ugyldig Work-oppsett: "
                                  + str(exc)) from exc
        with self._guard:
            self._assert_idle()
            if not updated:
                return dict(self.settings)
            saved = save_config(updated)  # disk first; memory unchanged if save fails
            self.settings.update(updated)
            self._arkade_checker.invalidate()
        self._emit("setup.changed", message="Setup lagret etter brukerens godkjenning")
        return dict(saved)

    def reload_setup(self) -> dict:
        """Synchronize in-memory settings after explicit portable import/reset."""
        with self._guard:
            self._assert_idle()
            updated = load_config()
            self.settings.clear()
            self.settings.update(updated)
            self._arkade_checker.invalidate()
        self._emit("setup.changed", message="Globalt Setup importert / tilbakestilt")
        return dict(updated)

    # ---------- per-job-list Work output rule (.n5jobs, NOT global Setup) ----------
    @property
    def output_subfolder_rule(self) -> str:
        return str(getattr(self._batch, "output_subfolder_rule", "") or "")

    def preview_output_subfolder_rule(self, rule: str) -> tuple[tuple[str, str, str], ...]:
        """Validate and preview effective Work paths without any writes.

        Work root is allowed before Work operations has been assigned, as in
        the beginner flow; preview must then match a6's preflight proposal.
        """
        from dataclasses import replace
        from types import SimpleNamespace

        proposed = str(rule or "").strip()
        jobs = self._batch.jobs()
        app_folder = str(self.settings.get("app_work_subfolder", "dwm") or "")
        try:
            # Validate tokens even with no jobs or no Work root.
            if proposed:
                probe = SimpleNamespace(
                    job_id="JOB-001", name="Jobb", active_extraction_root=None
                )
                render_output_subfolder_rule(proposed, probe, 1)
            projections = [
                replace(job, work_operations=(
                    job.work_operations or (
                        propose_work_location(
                            job.work_root, app_subfolder=app_folder,
                        ).work_operations
                        if job.work_root is not None else None
                    )
                ))
                for job in jobs
            ]
            old_paths = validate_layout(app_folder, self.output_subfolder_rule, projections)
            new_paths = validate_layout(app_folder, proposed, projections)
        except ValueError as exc:
            raise DwmApiError(f"Ugyldig undermappe-regel: {exc}") from exc
        previous = {job_id: str(path) if path is not None else "(ikke angitt)"
                    for job_id, path in old_paths}
        return tuple(
            (job_id, previous.get(job_id, "(ikke angitt)"),
             str(path) if path is not None else "(ikke angitt)")
            for job_id, path in new_paths
        )

    def set_output_subfolder_rule(self, rule: str, *, confirm_changes: bool = False) -> bool:
        """Change only the job-list rule, after preview and explicit consent.

        Historical files are never moved and no directory is created here.
        """
        proposed = str(rule or "").strip()
        with self._guard:
            self._assert_idle()
            old = self.output_subfolder_rule
            if proposed == old:
                return False
            preview = self.preview_output_subfolder_rule(proposed)
            changes = tuple(item for item in preview if item[1] != item[2])
            if changes and not confirm_changes:
                raise DwmApiError(
                    "Endringen vil påvirke eksisterende Work-stier. "
                    "Forhåndsvis og bekreft endringen før den brukes."
                )
            self._batch.output_subfolder_rule = proposed
            self._dirty = True
        self._emit("joblist.output_rule_changed", message=proposed)
        return True

    # ---------- a6: explicit preflight before every Qt/API run ----------
    def _inspect_job(self, job: Job) -> PreflightReport:
        """Read-only check against the complete effective Work path.

        If Work operations is missing, a set-role action is proposed from an
        already selected Work root; no configuration is changed here.
        """
        base = job.work_operations
        app_folder = str(self.settings.get("app_work_subfolder", "dwm") or "")
        if base is None and job.work_root is not None:
            try:
                base = propose_work_location(
                    job.work_root, app_subfolder=app_folder,
                ).work_operations
            except ValueError:
                base = None  # inspect_job adds a helpful blocking error
        position = next(i for i, candidate in enumerate(self._batch.jobs(), 1)
                        if candidate.job_id == job.job_id)
        effective = effective_work_operations(
            base,
            str(self.settings.get("app_work_subfolder", "dwm") or ""),
            str(getattr(self._batch, "output_subfolder_rule", "") or ""),
            job,
            position,
        )
        report = inspect_job(
            job, effective_work_operations=effective, app_subfolder=app_folder,
        )
        if not requires_arkade_cli(job.workflow_ids):
            return report
        check = self._arkade_checker.check(self.settings)
        if check.severity == "ok":
            return report
        severity = "error" if check.severity == "error" else "warning"
        return PreflightReport(
            report.job_id,
            report.issues + (PreflightIssue("ARKADE5_CLI_" + severity.upper(),
                                           severity, check.message),),
            report.actions,
        )

    def preflight_job(self, job_id: str) -> PreflightReport:
        """No writes, no role changes, no implicit folder creation."""
        with self._guard:
            self._assert_idle()
            return self._inspect_job(self._require_job(job_id))

    def provision_preflight(self, job_id: str, *, approved_report: PreflightReport,
                            consent: bool) -> PreflightReport:
        """Create ONLY the explicitly approved, currently valid Work/AIP paths.

        Refuse stale plans and blocking errors. Assignments never touch Source,
        and no source content, existing result or AIP file is modified.
        """
        if not consent:
            raise DwmApiError("Klargjøring krever brukerens uttrykkelige godkjenning.")
        with self._guard:
            self._assert_idle()
            job = self._require_job(job_id)
            current = self._inspect_job(job)
            if current != approved_report:
                raise DwmApiError("Mappeoppsettet er endret. Kontroller på nytt før du godkjenner.")
            if current.errors:
                raise DwmApiError(
                    "Klargjøring blokkert: " + "; ".join(issue.message for issue in current.errors)
                )
            assigned = next((Path(action.path) for action in current.actions
                             if action.kind == "set_work_operations"), None)
            original = job.work_operations
            original_work_root = job.work_root
            if assigned is not None:
                job.work_operations = assigned
                if job.work_root is not None:
                    job.work_root = propose_work_location(
                        job.work_root,
                        app_subfolder=str(self.settings.get("app_work_subfolder", "dwm") or ""),
                    ).work_root
            try:
                errors = self.check_storage()
                if errors:
                    raise DwmApiError("Ugyldig Work/AIP-oppsett: " + "; ".join(errors))
                # Check the re-computed effective path, not only the proposal.
                updated = self._inspect_job(job)
                if updated.errors:
                    raise DwmApiError("Klargjøring blokkert: " + "; ".join(
                        issue.message for issue in updated.errors))
                approved = set(paths_to_create(current.actions))
                actual = set(paths_to_create(updated.actions))
                if not actual.issubset(approved):
                    raise DwmApiError("Oppsettet krever andre mapper enn de godkjente. Kontroller på nytt.")
                for path in sorted(approved, key=lambda item: (len(item.parts), str(item))):
                    path.mkdir(parents=True, exist_ok=True)
                    if not path.is_dir():
                        raise OSError(f"Arbeidsområdet er ikke en mappe: {path}")
            except Exception as exc:
                job.work_operations = original
                job.work_root = original_work_root
                if isinstance(exc, DwmApiError):
                    raise
                raise DwmApiError(f"Kunne ikke opprette godkjente mapper: {exc}") from exc
            if assigned is not None:
                self._dirty = True  # Explicit save before execution.
            result = self._inspect_job(job)
        self._emit("preflight.provisioned", job, message="Godkjente mapper opprettet / lagringsroller satt")
        return result

    def run_job(self, job_id: str, *, allow_rerun: bool = False,
                continue_waiting: bool = False,
                acknowledge_warnings: bool = False) -> bool:
        """All DWM Qt workbench runs enforce the same preflight, even via API."""
        report = self.preflight_job(job_id)
        if report.errors:
            raise DwmApiError("Kontroll før kjøring feilet: " + "; ".join(
                issue.message for issue in report.errors))
        if report.actions:
            raise DwmApiError(
                "Manglende Work/AIP-mapper må godkjennes og klargjøres før kjøring: "
                + "; ".join(action.path for action in report.actions)
            )
        if report.warnings and not acknowledge_warnings:
            raise DwmApiError("Avvik krever brukerens godkjenning: " + "; ".join(
                issue.message for issue in report.warnings))
        return super().run_job(
            job_id, allow_rerun=allow_rerun, continue_waiting=continue_waiting,
        )

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
