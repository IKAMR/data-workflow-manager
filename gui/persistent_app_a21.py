from __future__ import annotations

from pathlib import Path
from tkinter import messagebox

from noark5_workflow.core.job import Job, JobBatch, JobStatus

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

    TOOLTIP_WATCHDOG_MS = 200

    def __init__(self) -> None:
        super().__init__()
        # Final safety net for stale workflow tooltips. Earlier lifecycle guards
        # hide on leave/click/focus loss, but a rebuilt/moved widget can otherwise
        # leave a transient Toplevel alive. The watchdog only hides a visible
        # tooltip when the pointer is no longer inside the widget that owns it.
        self.after(self.TOOLTIP_WATCHDOG_MS, self._a11_tooltip_watchdog)
        recovered = self._recover_append_only_state(self.current_job, persist=True)
        retry_recovered = self._recover_failed_append_retry_state(self.current_job, persist=True)
        if recovered or retry_recovered:
            self.after_idle(self._update_run_button)

    def _a11_tooltip_watchdog(self) -> None:
        panel = getattr(self, "workflow_panel", None)
        for tooltip in list(getattr(panel, "_tooltips", ()) or ()):
            if getattr(tooltip, "window", None) is None:
                continue
            widget = getattr(tooltip, "widget", None)
            try:
                if widget is None or not widget.winfo_exists():
                    tooltip._hide()
                    continue
                px = widget.winfo_pointerx()
                py = widget.winfo_pointery()
                left = widget.winfo_rootx()
                top = widget.winfo_rooty()
                right = left + widget.winfo_width()
                bottom = top + widget.winfo_height()
                if not (left <= px < right and top <= py < bottom):
                    tooltip._hide()
            except Exception:
                try:
                    tooltip._hide()
                except Exception:
                    pass

        try:
            if self.winfo_exists():
                self.after(self.TOOLTIP_WATCHDOG_MS, self._a11_tooltip_watchdog)
        except Exception:
            pass

    @staticmethod
    def _is_append_only_extension(
        old_ids: list[str],
        new_ids: list[str],
        *,
        old_status: JobStatus,
        old_cursor: int,
    ) -> bool:
        """True only when completed work is preserved and new work is appended."""
        return (
            old_status == JobStatus.OK
            and bool(old_ids)
            and len(new_ids) > len(old_ids)
            and new_ids[: len(old_ids)] == old_ids
            and int(old_cursor) >= len(old_ids)
        )

    def _completed_prefix_from_log(self, job: Job) -> int:
        """Recover a completed prefix from the latest successful persisted run."""
        entries = list(getattr(job, "log_entries", ()) or ())
        if not entries or len(job.workflow_ids) < 2:
            return 0

        finish = next((i for i in range(len(entries) - 1, -1, -1)
                       if "Workflow fullført" in entries[i]), -1)
        if finish < 0:
            return 0

        start = 0
        for i in range(finish, -1, -1):
            if "Workflow startet" in entries[i] or "Workflow fortsetter fra operasjon" in entries[i]:
                start = i
                break

        completed_names = []
        for entry in entries[start:finish + 1]:
            if "OK: " in entry:
                completed_names.append(entry.split("OK: ", 1)[1].strip())

        if not completed_names or len(completed_names) >= len(job.workflow_ids):
            return 0

        prefix_names = []
        for operation_id in job.workflow_ids[:len(completed_names)]:
            try:
                prefix_names.append(self.registry.get(operation_id).definition.name)
            except Exception:
                return 0
        return len(completed_names) if prefix_names == completed_names else 0

    def _recover_append_only_state(self, job: Job | None, *, persist: bool = False) -> bool:
        """Repair a11/a12 job lists where append state was reset to cursor 0."""
        if job is None or job.status != JobStatus.READY or int(job.next_operation_index or 0) != 0:
            return False
        prefix = self._completed_prefix_from_log(job)
        if prefix <= 0 or prefix >= len(job.workflow_ids):
            return False
        job.next_operation_index = prefix
        job.progress = prefix / len(job.workflow_ids)
        job.message = f"Workflow utvidet - fortsett fra operasjon {prefix + 1}"
        if persist and self.job_list_path is not None:
            self._write_job_list(self.job_list_path)
        return True


    def _recover_failed_append_retry_state(self, job: Job | None, *, persist: bool = False) -> bool:
        """Recover a failed append-resume after temporary Source/Work unavailability.

        a12.2 correctly preserved the cursor when operation 7 was started, but an
        unavailable external disk left the Job in FAILED state.  The persisted log
        still records that the run *continued* from the partial cursor.  Use that
        evidence to make the failed tail retryable without rerunning the completed
        prefix.
        """
        if job is None or job.status != JobStatus.FAILED:
            return False
        cursor = int(job.next_operation_index or 0)
        if cursor <= 0 or cursor >= len(job.workflow_ids):
            return False

        marker = f"Workflow fortsetter fra operasjon {cursor + 1}"
        entries = list(getattr(job, "log_entries", ()) or ())
        if not any(marker in entry for entry in entries[-80:]):
            return False
        if any("Workflow fullført" in entry for entry in entries[-20:]):
            return False

        job.progress = cursor / len(job.workflow_ids)
        job.message = f"Fortsettelse feilet - prøv igjen fra operasjon {cursor + 1}"
        if persist and self.job_list_path is not None:
            self._write_job_list(self.job_list_path)
        return True

    def _sync_active_workflow_to_job(self) -> None:
        """Synchronize workflow without destroying a completed append-only prefix."""
        job = self.current_job
        if job is None:
            return
        old_ids = list(job.workflow_ids)
        old_status = job.status
        old_cursor = int(job.next_operation_index or 0)
        new_ids = list(self.workflow.operation_ids())
        append_only = self._is_append_only_extension(
            old_ids, new_ids, old_status=old_status, old_cursor=old_cursor
        )
        super()._sync_active_workflow_to_job()
        if append_only:
            job.next_operation_index = len(old_ids)
            job.progress = len(old_ids) / len(new_ids)
            job.status = JobStatus.READY
            job.message = f"Workflow utvidet - fortsett fra operasjon {len(old_ids) + 1}"

    def _open_job(self, job: Job) -> None:
        super()._open_job(job)
        if self._recover_append_only_state(job, persist=True):
            self.status_bar.set_status(
                f"Tidligere fullført workflow gjenkjent - fortsett fra operasjon {job.next_operation_index + 1}"
            )
        elif self._recover_failed_append_retry_state(job, persist=True):
            self.status_bar.set_status(
                f"Fortsettelsen feilet tidligere - prøv igjen fra operasjon {job.next_operation_index + 1}"
            )
        self._update_run_button()

    def _workflow_changed(self, change_kind: str, operation_id: str | None) -> None:
        """Persist edits while preserving a completed prefix for append-only adds.

        The workflow-panel change hook fires *after* its visible workflow model has
        changed but *before* the active Job has been synchronized.  That boundary
        is therefore the authoritative place to compare the persisted completed
        workflow with the newly visible workflow.
        """
        job = self.current_job
        if job is None or self.batch_running:
            return

        old_ids = list(job.workflow_ids)
        old_status = job.status
        old_cursor = int(job.next_operation_index or 0)
        new_ids = list(self.workflow.operation_ids())

        append_only = (
            change_kind == "add"
            and self._is_append_only_extension(
                old_ids,
                new_ids,
                old_status=old_status,
                old_cursor=old_cursor,
            )
        )

        # Let the established a17 persistence path synchronize and autosave the
        # edit first.  For an ordinary edit it also invalidates terminal state.
        super()._workflow_changed(change_kind, operation_id)

        if not append_only:
            self._update_run_button()
            return

        # Restore only the execution cursor for the already completed prefix.
        # READY + partial cursor is append-resume; WAITING remains reserved for
        # real checkpoints and is handled by JobRunner.continue_job().
        job.next_operation_index = len(old_ids)
        job.progress = len(old_ids) / len(new_ids)
        job.status = JobStatus.READY
        job.message = f"Workflow utvidet - fortsett fra operasjon {len(old_ids) + 1}"
        self._job_log(
            job,
            f"WORKFLOW UTVIDET: fortsett fra operasjon {len(old_ids) + 1}",
        )
        if self.job_list_path is not None:
            self._write_job_list(self.job_list_path)
        self._refresh_active_job_label()
        self._update_run_button()

    def _rerun_context_for_job(self, job: Job) -> str:
        """Describe exactly what a confirmed rerun will do for one job."""
        total = len(job.workflow_ids)
        cursor = max(0, min(int(job.next_operation_index or 0), total))

        def operation_name(index: int) -> str:
            if index < 0 or index >= total:
                return ""
            try:
                return str(self.registry.get(job.workflow_ids[index]).definition.name)
            except Exception:
                return str(job.workflow_ids[index])

        failed_tail_retry = (
            job.status == JobStatus.FAILED
            and 0 < cursor < total
            and str(job.message or "").startswith(
                "Fortsettelse feilet - prøv igjen fra operasjon "
            )
        )
        append_resume = (
            job.status == JobStatus.READY
            and 0 < cursor < total
        )
        checkpoint_resume = (
            job.status == JobStatus.WAITING
            and 0 < cursor < total
        )

        if failed_tail_retry:
            first = cursor + 1
            name = operation_name(cursor)
            lines = [
                f"{job.job_id}",
                f"Prøver igjen fra operasjon {first} av {total}: {name}",
                f"Tidligere fullført: operasjon 1-{cursor} av {total}",
                (
                    f"Kjøres nå: operasjon {first} av {total}"
                    if first == total
                    else f"Kjøres nå: operasjon {first}-{total} av {total}"
                ),
            ]
            return "\n".join(lines)

        if append_resume:
            first = cursor + 1
            name = operation_name(cursor)
            lines = [
                f"{job.job_id}",
                f"Fortsetter fra operasjon {first} av {total}: {name}",
                f"Tidligere fullført: operasjon 1-{cursor} av {total}",
                (
                    f"Kjøres nå: operasjon {first} av {total}"
                    if first == total
                    else f"Kjøres nå: operasjon {first}-{total} av {total}"
                ),
            ]
            return "\n".join(lines)

        if checkpoint_resume:
            first = cursor + 1
            name = operation_name(cursor)
            return "\n".join([
                f"{job.job_id}",
                f"Fortsetter fra kontrollpunkt ved operasjon {first} av {total}: {name}",
                f"Tidligere fullført: operasjon 1-{cursor} av {total}",
                (
                    f"Kjøres nå: operasjon {first} av {total}"
                    if first == total
                    else f"Kjøres nå: operasjon {first}-{total} av {total}"
                ),
            ])

        return "\n".join([
            f"{job.job_id}",
            f"Kjøres på nytt fra operasjon 1 av {total}",
            f"Kjøres nå: operasjon 1-{total} av {total}" if total > 1 else "Kjøres nå: operasjon 1 av 1",
        ])

    def _confirm_rerun(self, jobs) -> bool:
        """Confirm reruns with per-job execution context instead of a generic warning."""
        previous = [
            job for job in jobs
            if job.status in {JobStatus.OK, JobStatus.FAILED, JobStatus.SKIPPED}
            or job.status == JobStatus.WAITING
            or (
                job.status == JobStatus.READY
                and 0 < int(job.next_operation_index or 0) < len(job.workflow_ids)
            )
            or job.message == "Konfigurasjon endret - klar for ny kjøring"
        ]
        if not previous:
            return True

        shown = previous[:6]
        sections = [self._rerun_context_for_job(job) for job in shown]
        if len(previous) > len(shown):
            sections.append(f"... og {len(previous) - len(shown)} jobb(er) til")

        message = (
            "Følgende kjøring er planlagt:\n\n"
            + "\n\n".join(sections)
            + "\n\nTidligere resultatmapper slettes ikke. "
              "Den nye kjøringen dokumenteres som en ny hendelse.\n\n"
              "Fortsette?"
        )
        return messagebox.askyesno(APP_NAME, message)

    def _update_run_button(self) -> None:
        job = self.current_job
        if (
            job is not None
            and job.status == JobStatus.READY
            and 0 < int(job.next_operation_index or 0) < len(job.workflow_ids)
        ):
            self.workflow_panel.set_run_text("Fortsett workflow")
            return
        if (
            job is not None
            and job.status == JobStatus.FAILED
            and 0 < int(job.next_operation_index or 0) < len(job.workflow_ids)
            and str(job.message or "").startswith("Fortsettelse feilet - prøv igjen fra operasjon ")
        ):
            self.workflow_panel.set_run_text("Prøv igjen")
            return
        super()._update_run_button()

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
