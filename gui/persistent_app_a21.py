from __future__ import annotations

from pathlib import Path

from noark5_workflow.core.job import Job, JobBatch

from .persistent_app_a20 import WorkflowApp as A20WorkflowApp
from .storage_roles_dialog_a11 import StorageRolesDialog


def _resequence_job_batch_for_new_list(batch: JobBatch) -> list[tuple[Job, str, str]]:
    """Give a Save As copy a fresh job identity sequence from JOB-001.

    Job order is preserved. A default job name that only mirrored the old
    job_id follows the new id, while an explicit user name is preserved.
    The returned snapshot can restore the original identities if writing the
    new job-list file fails.
    """
    jobs = batch.jobs()
    snapshots: list[tuple[Job, str, str]] = []

    for number, job in enumerate(jobs, start=1):
        old_id = job.job_id
        old_name = job.name
        new_id = f"JOB-{number:03d}"
        snapshots.append((job, old_id, old_name))

        job.job_id = new_id
        if not old_name or old_name == old_id:
            job.name = new_id

    # Rebuild the batch index so the next explicitly created job continues
    # after the new sequence rather than after the old list's highest id.
    batch.replace_all(jobs)
    return snapshots


def _restore_job_batch_identities(
    batch: JobBatch,
    snapshots: list[tuple[Job, str, str]],
) -> None:
    """Restore pre-Save-As identities after a failed write."""
    if not snapshots:
        return

    for job, old_id, old_name in snapshots:
        job.job_id = old_id
        job.name = old_name

    batch.replace_all(batch.jobs())


class WorkflowApp(A20WorkflowApp):
    """a11 runtime additions for generic Source / Work / Storage job setup."""

    def _show_storage_roles(self, job: Job) -> None:
        existing = self._storage_roles_dialog
        if existing is not None and existing.winfo_exists():
            existing.focus()
            existing.lift()
            return
        dialog = StorageRolesDialog(
            self,
            job,
            lambda values: self._save_storage_roles(job, values),
        )
        self._storage_roles_dialog = dialog
        dialog.bind(
            "<Destroy>",
            lambda _e, d=dialog: self._storage_dialog_closed(d),
            add="+",
        )

    def _new_job_list(self) -> bool:
        """Create JOB-001 immediately and open its generic role dialog.

        A new job list starts in the Default profile. Opening an existing job
        list or switching between existing jobs does not trigger this behaviour.
        """
        created = super()._new_job_list()
        if not created:
            return False

        # A new job list always starts from the generic profile boundary.
        self._apply_profile(None, persist=False)

        # Explicit job creation already owns the established behaviour for a
        # blank job and schedules the Mapper dialog. Reuse it for JOB-001.
        job = self._create_job(None)
        job.profile_id = None

        if self.jobs_window is not None and self.jobs_window.winfo_exists():
            self.jobs_window.refresh()
        self.status_bar.set_status("Ny jobbliste - konfigurer Source, Work og Storage")
        return True

    def _reset_jobs_for_new_job_list_copy(self) -> None:
        """Reset run history and assign fresh identities for a Save As copy.

        The parent a19 layer calls this only when an already-saved job list is
        saved to a different target path. Saving to the same path keeps the
        existing job identities.
        """
        super()._reset_jobs_for_new_job_list_copy()
        self._a11_save_as_identity_snapshot = _resequence_job_batch_for_new_list(
            self.jobs
        )

    def _restore_a11_save_as_identities(self) -> None:
        snapshots = getattr(self, "_a11_save_as_identity_snapshot", [])
        if not snapshots:
            return

        _restore_job_batch_identities(self.jobs, snapshots)
        self._a11_save_as_identity_snapshot = []
        self._refresh_active_job_label()

        if self.jobs_window is not None:
            try:
                if self.jobs_window.winfo_exists():
                    self.jobs_window.refresh()
            except Exception:
                pass

    def _save_job_list_as_in(self, directory: Path) -> bool:
        """Extend Save As with fresh JOB-001.. identity in a new target list.

        The established a19 Save As transaction still owns path selection,
        execution-history reset, explicit writing and activation of the target.
        This layer only adds job-id resequencing and rollback of those identities
        if the new file cannot be written.
        """
        self._a11_save_as_identity_snapshot = []

        try:
            written = super()._save_job_list_as_in(directory)
        except Exception:
            self._restore_a11_save_as_identities()
            raise

        if not written:
            self._restore_a11_save_as_identities()
            return False

        self._a11_save_as_identity_snapshot = []
        self._refresh_active_job_label()

        if self.jobs_window is not None:
            try:
                if self.jobs_window.winfo_exists():
                    self.jobs_window.refresh()
            except Exception:
                pass

        return True


def run_gui() -> None:
    app = WorkflowApp()
    app.mainloop()
