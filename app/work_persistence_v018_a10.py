"""Work-first persistence for the DWM GUI-independent workbench.

The .n5jobs file is an index; an approved Work area owns a job's complete
identity, definition, state, history and run logs. Old v1-v4 joblists can be
loaded without migrating or modifying any files. Work migration is explicit.
"""
from __future__ import annotations

from pathlib import Path
from uuid import UUID, uuid4

from app.application_api import DwmApiError
from app.work_output_layout import effective_work_operations
from noark5_workflow.core.job import Job
from noark5_workflow.core.job_store import save_job_list
from noark5_workflow.core.work_job_store import WorkJobStore, WorkJobStoreError
from version import VERSION


def _path_overlap(path: Path, other: Path | None) -> bool:
    if other is None:
        return False
    try:
        a = path.resolve(strict=False)
        b = Path(other).resolve(strict=False)
        return a == b or a in b.parents or b in a.parents
    except (OSError, ValueError):
        return True  # refuse uncertain safety decisions


class WorkPersistenceMixin:
    """Mixin before SelectiveSubjobMixin and DwmApplication in the MRO."""

    def _work_root_for(self, job: Job, *, ignore_reference: bool = False) -> Path:
        ref = self._work_references.get(job.job_id)
        if ref is not None and not ignore_reference:
            return ref.parent
        position = next(
            (i for i, other in enumerate(self._batch.jobs(), 1)
             if other.job_id == job.job_id), None,
        )
        if position is None:
            raise DwmApiError("Jobben er ikke i den aktive jobblisten")
        effective = effective_work_operations(
            job.work_operations,
            str(self.settings.get("app_work_subfolder", "dwm") or ""),
            str(getattr(self._batch, "output_subfolder_rule", "") or ""),
            job, position,
        )
        if effective is None:
            raise DwmApiError("Jobben mangler Work operations")
        return effective

    def _work_root_validated(self, job: Job) -> Path:
        folder = self._work_root_for(job)
        if not folder.is_dir():
            raise DwmApiError("Klargjør Work-mappen og godkjenn opprettelse før lagring i Work")
        for source in (job.source_root, job.source_tar, job.source_unzipped, job.source_extraction):
            if _path_overlap(folder, source):
                raise DwmApiError("DWM Work kan ikke ligge inne i eller omslutte Source")
        for aip in (job.archive_root, job.output_root):
            if _path_overlap(folder, aip):
                raise DwmApiError("DWM Work kan ikke overlappe AIP/arkivutdata")
        return folder

    def _work_store_for(self, job: Job) -> WorkJobStore:
        ref = self._work_references.get(job.job_id)
        if ref is None:
            raise DwmApiError("Jobben er ennå ikke registrert med varig Work-ID")
        if job.job_id in self._unavailable_work_ids:
            raise DwmApiError("Work er frakoblet. Koble til arbeidsområdet før jobben endres.")
        return WorkJobStore(ref.parent)

    def _persist_work_event(self, job: Job, kind: str = "", detail: str = "") -> None:
        ref = self._work_references.get(job.job_id)
        if ref is None:
            return  # Explicitly unprovisioned draft; keep data in the joblist.
        try:
            self._work_store_for(job).write(
                job, event_kind=kind, detail=detail,
                origin_joblist=str(self._path or ""),
            )
        except (OSError, WorkJobStoreError) as exc:
            raise DwmApiError("Kunne ikke lagre autoritativ jobbstatus i Work: " + str(exc)) from exc

    def _register_work_job(self, job_id: str, *, reason: str) -> Path:
        """Only call after approved provision or explicit user action/run."""
        job = self._require_job(job_id)
        if job_id in self._unavailable_work_ids:
            raise DwmApiError("Jobben har et frakoblet Work-område. Koble det til først.")
        folder = self._work_root_validated(job)
        old = self._work_references.get(job_id)
        if old is not None and old.parent.resolve() != folder.resolve():
            raise DwmApiError(
                "Jobben har allerede autoritativ historikk i et annet Work-område. "
                "Flytting krever en egen, kontrollert migrering; ingen data er flyttet."
            )
        # The identity is persistent across joblists and not JOB-001.
        uid = str(getattr(job, "job_uid", "") or "")
        if not uid:
            job.job_uid = str(uuid4())
        else:
            try:
                job.job_uid = str(UUID(uid))
            except ValueError as exc:
                raise DwmApiError("Jobben har en ugyldig varig jobb-ID") from exc
        store = WorkJobStore(folder)
        try:
            store.assert_compatible(job)
            store.write(job, event_kind=reason, origin_joblist=str(self._path or ""))
        except (OSError, WorkJobStoreError) as exc:
            raise DwmApiError("Kan ikke ta i bruk Work som jobblager: " + str(exc)) from exc
        self._work_references[job_id] = store.definition_path
        self._dirty = True
        return store.definition_path

    def migrate_job_to_work(self, job_id: str) -> Path:
        """Explicit migration command; caller must ask the user for approval."""
        with self._guard:
            self._assert_idle()
            self._require_job(job_id)
        return self._register_work_job(job_id, reason="work.migrated")

    def recover_job_from_work(self, folder: str | Path):
        """Add a standalone Work job to this list, without modifying Work."""
        root = Path(folder)
        if root.is_file():
            if root.name != "job.json":
                raise DwmApiError("Velg DWM-mappen eller job.json")
            root = root.parent
        store = WorkJobStore(root)
        try:
            job = store.load()
        except (OSError, WorkJobStoreError) as exc:
            raise DwmApiError("Kunne ikke gjenopprette jobb fra Work: " + str(exc)) from exc
        with self._guard:
            self._assert_idle()
            existing = self._batch.jobs()
            if any(getattr(other, "job_uid", "") == job.job_uid for other in existing):
                raise DwmApiError("Denne Work-jobben finnes allerede i jobblisten")
            present = {other.job_id for other in existing}
            if job.job_id in present:
                number = 1
                while f"JOB-{number:03d}" in present:
                    number += 1
                job.job_id = f"JOB-{number:03d}"
            self._batch.add(job)
            self._work_references[job.job_id] = store.definition_path
            self._active_job_id = job.job_id
            self._dirty = True
            position = next(i for i, candidate in enumerate(self._batch.jobs(), 1)
                            if candidate.job_id == job.job_id)
            view = self._view(job, position)
        self._emit("job.recovered_from_work", message=str(root))
        return view

    def work_job_info(self, job_id: str) -> dict[str, str | bool]:
        """Read-only information for GUI and later cross-job inventory."""
        job = self._require_job(job_id)
        ref = self._work_references.get(job_id)
        return {
            "job_uid": str(getattr(job, "job_uid", "") or ""),
            "profile_id": str(job.profile_id or ""),
            "production_system_ref": str(getattr(job, "production_system_ref", "") or ""),
            "work_manifest": str(ref or ""),
            "work_is_authoritative": ref is not None,
            "work_available": bool(ref and ref.is_file() and job_id not in self._unavailable_work_ids),
        }

    def _write_job_list_file(self, target: Path, active_job_id: str | None) -> Path:
        """Publish Work state before the lightweight index reference."""
        for job in self._batch.jobs():
            if job.job_id in self._work_references and job.job_id not in self._unavailable_work_ids:
                self._persist_work_event(job)
        return save_job_list(
            target, self._batch, active_job_id=active_job_id,
            app_version=VERSION, work_references=self._work_references,
        )

    def _persist_updated_job(self, job: Job, active_job_id: str) -> None:
        """Never let a completed run depend on saving the .n5jobs file."""
        if job.job_id not in self._work_references:
            raise DwmApiError("Kjøringen mangler autoritativ Work-jobb. Klargjør først.")
        self._persist_work_event(job, "run.state", job.message)
        if self._path is not None:
            try:
                self._write_job_list_file(self._path, active_job_id)
                self._work_index_warning = ""
            except OSError as exc:
                # The job-list is only an index. An offline job-list drive
                # must never turn an otherwise successful analysis into a
                # failed job after the authoritative Work state was committed.
                self._work_index_warning = (
                    "Jobblistens indeks kunne ikke lagres; autoritativ Work-status "
                    "er bevart: " + str(exc)
                )
                super()._emit("joblist.index_write_failed", job,
                              message=self._work_index_warning)

    def _emit(self, kind, job=None, *, message="", progress=None):
        if job is not None and kind in {
            "job.storage_changed", "job.workflow_changed", "job.checkpoint_changed",
            "job.renamed", "run.finished", "run.error",
            "subjob.started", "subjob.finished", "subjob.error",
        }:
            self._persist_work_event(job, kind, str(message or ""))
        return super()._emit(kind, job, message=message, progress=progress)
