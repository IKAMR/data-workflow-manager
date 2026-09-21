from __future__ import annotations

import threading
from pathlib import Path
from tkinter import messagebox

from app.workflow_sequences import workflow_sequence_by_id
from noark5_workflow.core.job import JobStatus
from version import APP_NAME
from . import theme
from .jobs_window_a18 import A18JobsWindow
from .persistent_app_a28 import WorkflowApp as A28WorkflowApp


_RECOVERABLE_STORAGE_PREFIX = "Lagring utilgjengelig - kan fortsette"
_IO_MARKERS = (
    "[Errno ",
    "[WinError ",
    "Input/output error",
    "I/O error",
    "Invalid argument",
    "The device is not ready",
    "The network name is no longer available",
    "The specified network name is no longer available",
)


class WorkflowApp(A28WorkflowApp):
    """a16.3: batch preflight and recoverable storage interruption."""

    # ------------------------------------------------------------------
    # Job window
    # ------------------------------------------------------------------

    def _open_jobs(self) -> None:
        self._capture_job_operation_params(self.current_job)
        if self.jobs_window is not None and self.jobs_window.winfo_exists():
            self.jobs_window.focus()
            self.jobs_window.lift()
            self.jobs_window.refresh()
            return
        self.jobs_window = A18JobsWindow(
            self, self.jobs, self._open_job, self._create_job, self._start_all_jobs,
            self._stop_batch, self._new_job_list, self._open_job_list_dialog,
            self._save_job_list, self._save_job_list_as, lambda: self.job_list_path,
            lambda: self.current_job.job_id if self.current_job else None,
        )

    # ------------------------------------------------------------------
    # Preflight
    # ------------------------------------------------------------------

    @staticmethod
    def _recoverable_storage_failure(job) -> bool:
        return (
            job.status == JobStatus.FAILED
            and str(job.message or "").startswith(_RECOVERABLE_STORAGE_PREFIX)
        )

    @classmethod
    def _job_is_ready_for_batch(cls, job) -> bool:
        if not job.workflow_ids:
            return False
        if job.status in {JobStatus.READY, JobStatus.WAITING}:
            return True
        return cls._recoverable_storage_failure(job)

    @staticmethod
    def _looks_like_io_failure(message: str) -> bool:
        value = str(message or "")
        return any(marker.casefold() in value.casefold() for marker in _IO_MARKERS)

    @staticmethod
    def _nearest_existing_parent(path: Path) -> Path | None:
        candidate = Path(path)
        while True:
            try:
                if candidate.exists():
                    return candidate
            except OSError:
                pass
            parent = candidate.parent
            if parent == candidate:
                return None
            candidate = parent

    def _storage_problems(self, job) -> list[str]:
        problems: list[str] = []

        source = job.source_extraction or job.source_root
        if source is None:
            problems.append("Source mangler")
        else:
            try:
                if not Path(source).exists():
                    problems.append(f"Source er ikke tilgjengelig: {source}")
            except OSError as exc:
                problems.append(f"Source kan ikke leses: {source} ({exc})")

        # work_root is the authoritative workspace anchor. A deeper
        # work_operations directory may legitimately not exist yet.
        work_anchor = job.work_root
        if work_anchor is not None:
            try:
                if not Path(work_anchor).exists():
                    problems.append(f"Work er ikke tilgjengelig: {work_anchor}")
            except OSError as exc:
                problems.append(f"Work kan ikke leses: {work_anchor} ({exc})")
        elif job.work_operations is not None:
            existing = self._nearest_existing_parent(Path(job.work_operations))
            if existing is None:
                problems.append(
                    f"Work operations har ingen tilgjengelig overmappe: "
                    f"{job.work_operations}"
                )

        return problems

    def _default_sequence(self):
        workflow_id = str(
            self.settings.get(
                "noark5_discovery_workflow",
                "noark5_standard",
            )
            or "none"
        )
        return workflow_sequence_by_id(workflow_id)

    def _fill_default_workflow(self, jobs) -> list:
        sequence = self._default_sequence()
        if sequence is None:
            return []

        filled = []
        for job in jobs:
            if job.workflow_ids or job.profile_id != "noark5":
                continue
            job.set_workflow(sequence.operation_ids)
            job.message = (
                f"Standardworkflow lagt til i preflight: {sequence.name}"
            )
            filled.append(job)
            self._job_log(
                job,
                f"PREFLIGHT: standardworkflow lagt til ({sequence.name})",
            )
        return filled

    def _batch_preflight(self, jobs, *, action_label: str):
        jobs = list(jobs)
        if not jobs:
            return []

        empty = [job for job in jobs if not job.workflow_ids]
        if empty:
            shown = "\n".join(
                f"- {job.job_id}: {job.name}" for job in empty[:10]
            )
            if len(empty) > 10:
                shown += f"\n- ... og {len(empty) - 10} til"

            answer = messagebox.askyesnocancel(
                APP_NAME,
                f"{len(empty)} jobb(er) har ingen operasjoner i workflow:\n\n"
                f"{shown}\n\n"
                "Ja = legg til konfigurert Noark 5-standardworkflow der det er mulig\n"
                "Nei = fortsett uten disse jobbene\n"
                "Avbryt = ikke start batchen",
            )
            if answer is None:
                return None

            if answer:
                filled = self._fill_default_workflow(empty)
                remaining = [job for job in empty if not job.workflow_ids]
                if remaining:
                    messagebox.showwarning(
                        APP_NAME,
                        "Standardworkflow kunne ikke legges til alle tomme jobber.\n\n"
                        "Jobber uten Noark 5-profil eller uten konfigurert "
                        "standardworkflow blir hoppet over.",
                    )
                if filled and self.job_list_path is not None:
                    self._write_job_list(self.job_list_path)

            # Explicit user choice to continue makes this a controlled skip,
            # not a surprise discovered after execution has started.
            for job in empty:
                if job.workflow_ids:
                    continue
                job.status = JobStatus.SKIPPED
                job.progress = 0.0
                job.message = "Preflight: Ingen operasjoner i workflow"
                self._job_log(job, "PREFLIGHT: hoppet over - ingen operasjoner")

        runnable = [job for job in jobs if job.workflow_ids]
        unavailable: list[tuple[object, list[str]]] = []
        for job in runnable:
            problems = self._storage_problems(job)
            if problems:
                unavailable.append((job, problems))

        if unavailable:
            lines = []
            for job, problems in unavailable[:8]:
                lines.append(f"{job.job_id}: {job.name}")
                lines.extend(f"  - {problem}" for problem in problems)
            if len(unavailable) > 8:
                lines.append(f"... og {len(unavailable) - 8} jobb(er) til")
            messagebox.showerror(
                APP_NAME,
                f"{action_label} ble ikke startet.\n\n"
                "Source/Work må være tilgjengelig før batchstart:\n\n"
                + "\n".join(lines),
            )
            return None

        return runnable

    # ------------------------------------------------------------------
    # Recover after storage/network interruption
    # ------------------------------------------------------------------

    def _execute_job(self, job, *, batch_mode: bool) -> bool:
        recovering = self._recoverable_storage_failure(job)
        if recovering:
            # The existing runner already resumes WAITING at next_operation_index.
            # Reuse that tested cursor semantics instead of inventing a second
            # execution path. The persisted status remains FAILED until the user
            # deliberately starts a recovery run.
            self._job_log(
                job,
                f"GJENOPPTAR: operasjon {job.next_operation_index + 1} "
                "etter lagringsfeil",
            )
            job.status = JobStatus.WAITING
            job.message = "Gjenopptar etter lagringsfeil"

        ok = super()._execute_job(job, batch_mode=batch_mode)

        if not ok and job.status == JobStatus.FAILED:
            raw_message = str(job.message or "")
            if self._looks_like_io_failure(raw_message):
                if not raw_message.startswith(_RECOVERABLE_STORAGE_PREFIX):
                    job.message = (
                        f"{_RECOVERABLE_STORAGE_PREFIX}: {raw_message}"
                    )
                self._job_log(
                    job,
                    "LAGRINGSFEIL: jobben kan fortsette fra feilet operasjon "
                    "når Source/Work er tilgjengelig igjen",
                )
                if self.job_list_path is not None:
                    self._write_job_list(self.job_list_path)
                if self.jobs_window is not None:
                    try:
                        if self.jobs_window.winfo_exists():
                            self.after(0, self.jobs_window.refresh)
                    except Exception:
                        pass

        return ok

    # ------------------------------------------------------------------
    # Start ready
    # ------------------------------------------------------------------

    def _start_ready_jobs(self) -> None:
        if self.batch_running:
            return

        eligible = [
            job for job in self.jobs.jobs()
            if (
                job.status in {JobStatus.READY, JobStatus.WAITING}
                or self._recoverable_storage_failure(job)
            )
        ]
        if not eligible:
            messagebox.showinfo(
                APP_NAME,
                "Ingen jobber med status Klar, Venter eller "
                "«Feil - kan fortsette».",
            )
            return

        candidates = self._batch_preflight(
            eligible,
            action_label="Start klare",
        )
        if candidates is None:
            return
        candidates = [
            job for job in candidates
            if self._job_is_ready_for_batch(job)
        ]
        if not candidates:
            messagebox.showinfo(
                APP_NAME,
                "Ingen kjørbare jobber etter preflight.",
            )
            return

        if not self._validate_unique_outputs(candidates):
            return

        shown = "\n".join(
            f"- {job.job_id}: {job.name}" for job in candidates[:8]
        )
        if len(candidates) > 8:
            shown += f"\n- ... og {len(candidates) - 8} til"

        recovering = sum(
            1 for job in candidates
            if self._recoverable_storage_failure(job)
        )
        recovery_text = (
            f"\n\n{recovering} jobb(er) fortsetter fra feilet operasjon."
            if recovering else ""
        )

        if not messagebox.askyesno(
            APP_NAME,
            f"Kjøre {len(candidates)} klar(e) jobb(er)?\n\n"
            f"{shown}"
            f"{recovery_text}\n\n"
            "Ferdige jobber blir ikke kjørt på nytt.",
        ):
            return

        self._capture_job_operation_params(self.current_job)
        self.batch_running = True
        self.batch_cancel_requested = False
        self.workflow_panel.run_button.configure(state="disabled")
        if self.jobs_window is not None and self.jobs_window.winfo_exists():
            self.jobs_window.set_batch_running(True)

        self.log_panel.append(
            f"BATCH START KLARE: {len(candidates)} av "
            f"{len(self.jobs.jobs())} jobb(er)"
        )

        def worker() -> None:
            for job in candidates:
                if self.batch_cancel_requested:
                    if job.status == JobStatus.READY:
                        job.status = JobStatus.SKIPPED
                        job.message = "Ikke startet - batch avbrutt"
                    continue
                self._execute_job(job, batch_mode=True)

            self._finish_batch_ui(
                prefix="BATCH KLARE FERDIG",
                selected=len(candidates),
            )

        threading.Thread(
            target=worker,
            daemon=True,
            name="n5wfman-start-ready-a16-3",
        ).start()

    # ------------------------------------------------------------------
    # Start all
    # ------------------------------------------------------------------

    def _start_all_jobs(self) -> None:
        if self.batch_running:
            return
        all_jobs = self.jobs.jobs()
        if not all_jobs:
            messagebox.showwarning(APP_NAME, "Det finnes ingen jobber å kjøre.")
            return

        candidates = self._batch_preflight(
            all_jobs,
            action_label="Start alle",
        )
        if candidates is None:
            return
        if not candidates:
            messagebox.showinfo(
                APP_NAME,
                "Ingen kjørbare jobber etter preflight.",
            )
            return
        if not self._validate_unique_outputs(candidates):
            return

        terminal_reruns = [
            job for job in candidates
            if job.status in {JobStatus.OK, JobStatus.FAILED, JobStatus.SKIPPED}
            and not self._recoverable_storage_failure(job)
        ]
        if terminal_reruns and not self._confirm_rerun(terminal_reruns):
            return

        self._capture_job_operation_params(self.current_job)
        self.batch_running = True
        self.batch_cancel_requested = False
        self.workflow_panel.run_button.configure(state="disabled")
        if self.jobs_window is not None and self.jobs_window.winfo_exists():
            self.jobs_window.set_batch_running(True)

        self.log_panel.append(
            f"BATCH START: {len(candidates)} kjørbare av {len(all_jobs)} jobb(er)"
        )

        def worker() -> None:
            for job in candidates:
                if self.batch_cancel_requested:
                    if job.status == JobStatus.READY:
                        job.status = JobStatus.SKIPPED
                        job.message = "Ikke startet - batch avbrutt"
                    continue

                if (
                    job.status in {JobStatus.OK, JobStatus.FAILED, JobStatus.SKIPPED}
                    and not self._recoverable_storage_failure(job)
                ):
                    job.reset_execution("Klar for ny batchkjøring")

                self._execute_job(job, batch_mode=True)

            self._finish_batch_ui(
                prefix="BATCH FERDIG",
                selected=len(candidates),
            )

        threading.Thread(
            target=worker,
            daemon=True,
            name="n5wfman-start-all-a16-3",
        ).start()

    def _finish_batch_ui(self, *, prefix: str, selected: int) -> None:
        counts = self.jobs.counts()
        waiting = counts.get(JobStatus.WAITING, 0)
        recoverable = sum(
            1 for job in self.jobs.jobs()
            if self._recoverable_storage_failure(job)
        )
        summary = (
            f"{prefix}: valgt={selected}, totalt={len(self.jobs.jobs())}, "
            f"ferdig={counts[JobStatus.OK]}, venter={waiting}, "
            f"feil={counts[JobStatus.FAILED]}, "
            f"kan_fortsette={recoverable}, "
            f"hoppet_over={counts[JobStatus.SKIPPED]}"
        )
        self.after(0, lambda s=summary: self.log_panel.append(s))
        self.after(0, lambda s=summary: self.status_bar.set_status(s))
        self.batch_running = False
        self.after(
            0,
            lambda: self.workflow_panel.run_button.configure(state="normal"),
        )
        self.after(0, self._update_run_button)
        if self.jobs_window is not None and self.jobs_window.winfo_exists():
            self.after(
                0,
                lambda: self.jobs_window.set_batch_running(False),
            )
            self.after(0, self.jobs_window.refresh)


def run_gui() -> None:
    theme.apply_theme()
    app = WorkflowApp()
    app.mainloop()
