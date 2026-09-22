from __future__ import annotations

from pathlib import Path
import threading
import time
from tkinter import messagebox

from app.batch_resource_strategy import recommend_batch_execution
from app.exception_monitor import AppExceptionMonitor
from settings import save_config
from version import APP_NAME

from . import theme
from .jobs_window_a22 import A22JobsWindow
from .persistent_app import _TERMINAL_STATUSES
from .persistent_app_a36 import (
    RuleAwareJobRunner,
    WorkflowApp as A36WorkflowApp,
)


class WorkflowApp(A36WorkflowApp):
    """v0.1.4-a5: adaptive parallel batch execution in the desktop client."""

    def __init__(self) -> None:
        super().__init__()
        # a4 BatchRunner supports run_parallel. Recreate with the current
        # RuleAwareJobRunner so each worker gets the effective Work path.
        from noark5_workflow.core.batch_runner import BatchRunner

        self.job_runner = RuleAwareJobRunner(
            self.registry,
            self.executor,
            self.settings,
        )
        self.batch_runner = BatchRunner(self.job_runner)
        self.exception_monitor = AppExceptionMonitor(self)

    def _capture_job_operation_params(self, job) -> None:
        """Do not let a stale empty GUI workflow erase a populated Job workflow.

        Jobs are authoritative for batch execution. The workflow panel may be
        temporarily empty after discovery/import while the Job already has its
        persisted/default sequence. In that state, preserving the Job prevents
        an accidental 6 -> 0 operation rewrite during save or batch startup.

        Non-empty GUI workflows are still written back normally.
        """
        if job is None:
            return

        panel_ids = list(self.workflow.operation_ids())
        job_ids = list(getattr(job, "workflow_ids", ()) or ())

        if not panel_ids and job_ids:
            return

        job.set_workflow(panel_ids)

    def _get_batch_execution_config(self) -> dict:
        return {
            "mode": str(self.settings.get("batch_execution_mode", "auto") or "auto"),
            "max_workers": int(self.settings.get("batch_max_workers", 0) or 0),
        }

    def _set_batch_execution_config(
        self,
        mode: str,
        max_workers: int,
    ) -> tuple[bool, str]:
        mode = str(mode or "auto").strip().lower()
        if mode not in {"auto", "sequential", "parallel"}:
            return False, f"Ugyldig batchmodus: {mode}"
        try:
            max_workers = int(max_workers or 0)
        except (TypeError, ValueError):
            return False, "Maks workers må være et heltall."
        if max_workers < 0 or max_workers > 32:
            return False, "Maks workers må være mellom 1 og 32, eller Auto."

        self.settings["batch_execution_mode"] = mode
        self.settings["batch_max_workers"] = max_workers
        save_config({
            "batch_execution_mode": mode,
            "batch_max_workers": max_workers,
        })
        return True, "Batchinnstilling lagret."

    def _set_output_subfolder_rule(
        self,
        rule: str,
    ) -> tuple[bool, str]:
        """Apply and persist the rule, then materialize its effective folders.

        Loading/restoring a job list remains side-effect free in a36. Folder
        creation happens only here because "Bruk regel" is an explicit user
        action.
        """
        previous_rule = self._get_output_subfolder_rule()
        previous_effective = {
            job.job_id: getattr(job, "_effective_work_operations", None)
            for job in self.jobs.jobs()
        }

        ok, message = super()._set_output_subfolder_rule(rule)
        if not ok:
            return ok, message

        created = []
        try:
            for job in self.jobs.jobs():
                effective = getattr(job, "_effective_work_operations", None)
                if effective is None:
                    continue
                path = Path(effective)
                path.mkdir(parents=True, exist_ok=True)
                created.append(str(path))
        except OSError as exc:
            # Restore the in-memory rule/path calculation. Directories already
            # created before the failure are harmless and intentionally not
            # deleted automatically.
            self.jobs.output_subfolder_rule = previous_rule
            for job in self.jobs.jobs():
                job._effective_work_operations = previous_effective.get(job.job_id)
            if self.job_list_path is not None:
                try:
                    self._save_job_list()
                except Exception:
                    pass
            return (
                False,
                "Kunne ikke opprette Work-undermappene for regelen.\n\n"
                f"{exc}",
            )

        return (
            True,
            f"Undermappe-regel lagret. {len(created)} Work-mappe(r) er klare.",
        )

    def _reset_job_execution(self, job) -> tuple[bool, str]:
        """Reset one existing job without deleting any persisted artifacts."""
        if self.batch_running:
            return False, "Kan ikke nullstille en jobb mens batchkjøring pågår."

        job.reset_execution(
            "Kjørestatus nullstilt - tidligere resultatfiler beholdt"
        )
        if self.job_list_path is not None and not self._save_job_list():
            return False, "Jobben ble nullstilt, men jobblisten kunne ikke lagres."

        if self.current_job is not None and self.current_job.job_id == job.job_id:
            self._open_job(job)

        if self.jobs_window is not None and self.jobs_window.winfo_exists():
            self.jobs_window.refresh()

        return True, "Kjørestatus/cursor er nullstilt."

    def _open_jobs(self) -> None:
        self._capture_job_operation_params(self.current_job)
        if self.jobs_window is not None and self.jobs_window.winfo_exists():
            self.jobs_window.focus()
            self.jobs_window.refresh()
            return

        self.jobs_window = A22JobsWindow(
            self,
            self.jobs,
            self._open_job,
            self._create_job,
            self._start_all_jobs,
            self._stop_batch,
            self._new_job_list,
            self._open_job_list_dialog,
            self._save_job_list,
            self._save_job_list_as,
            lambda: self.job_list_path,
            lambda: self.current_job.job_id if self.current_job else None,
            get_output_subfolder_rule=self._get_output_subfolder_rule,
            set_output_subfolder_rule=self._set_output_subfolder_rule,
            get_batch_execution_config=self._get_batch_execution_config,
            set_batch_execution_config=self._set_batch_execution_config,
            reset_job_execution=self._reset_job_execution,
        )

    def _parallel_progress(self, job, value: float, message: str) -> None:
        self.after(
            0,
            lambda j=job, v=value, m=message:
                self._progress_callback_for_job(j, v, m),
        )

    def _parallel_log(self, job, message: str) -> None:
        self.after(
            0,
            lambda j=job, m=message: self._job_log(j, m),
        )

    def _parallel_state_changed(self, job) -> None:
        self.after(
            0,
            lambda j=job: self._runner_state_changed(j),
        )

    def _start_all_jobs(self) -> None:
        if self.batch_running:
            messagebox.showwarning(APP_NAME, "Batch-kjøring er allerede aktiv.")
            return
        if len(self.jobs) == 0:
            messagebox.showwarning(APP_NAME, "Det finnes ingen jobber å kjøre.")
            return

        jobs = self.jobs.jobs()
        for job in jobs:
            self._normalise_job_before_run(job)

        if not self._validate_unique_outputs(jobs):
            return

        terminal = [job for job in jobs if job.status in _TERMINAL_STATUSES]
        if terminal and not self._confirm_rerun(terminal):
            return

        cfg = self._get_batch_execution_config()
        max_workers = int(cfg.get("max_workers", 0) or 0)
        decision = recommend_batch_execution(
            jobs,
            environment=self.settings.get("_current_run_environment") or {},
            requested_mode=str(cfg.get("mode", "auto") or "auto"),
            max_workers=(max_workers or None),
        )

        self._capture_job_operation_params(self.current_job)
        self.batch_running = True
        self.batch_cancel_requested = False
        self.workflow_panel.run_button.configure(state="disabled")
        if self.jobs_window is not None and self.jobs_window.winfo_exists():
            self.jobs_window.set_batch_running(True)

        overview = self._new_run_log("batch", planned_jobs=len(jobs))
        overview.set_phase("Batch opprettet - worker ikke startet ennå")

        # The RunOverviewLog created above captures the runtime environment and
        # stores it in settings. Re-evaluate now so the decision uses the exact
        # environment snapshot for this RUN.
        decision = recommend_batch_execution(
            jobs,
            environment=self.settings.get("_current_run_environment") or {},
            requested_mode=str(cfg.get("mode", "auto") or "auto"),
            max_workers=(max_workers or None),
        )

        self.log_panel.append(
            "BATCH START: "
            f"{decision.selected_mode}, workers={decision.workers} | "
            f"{decision.reason}"
        )
        self.log_panel.append(f"OVERORDNET KJØRELOGG: {overview.path}")
        overview.set_phase(
            f"Batchstrategi: {decision.selected_mode}, workers={decision.workers}"
        )

        worker_started = threading.Event()
        first_job_registered = threading.Event()
        worker_finished = threading.Event()

        def preparing(job, position: int, total: int) -> None:
            self._set_batch_phase(
                overview,
                f"Forbereder {job.job_id} ({position} av {total})",
            )

        def registered(job, position: int, total: int, will_run: bool) -> None:
            self._set_batch_phase(
                overview,
                f"Registrerer {job.job_id} i kjørelogg",
            )
            overview.start_job(job)
            first_job_registered.set()
            if will_run:
                self._set_batch_phase(
                    overview,
                    f"Kjører {job.job_id} ({position} av {total})",
                )

        def finished(job, position: int, total: int) -> None:
            overview.finish_job(job)
            if self.job_list_path is not None:
                self._write_job_list(self.job_list_path)

        def worker() -> None:
            worker_started.set()
            try:
                self._set_batch_phase(overview, "Worker startet")

                common = dict(
                    cancelled_cb=lambda: self.batch_cancel_requested,
                    progress_cb=self._parallel_progress,
                    log_cb=self._parallel_log,
                    state_cb=self._parallel_state_changed,
                    preparing_cb=preparing,
                    registered_cb=registered,
                    finished_cb=finished,
                )

                if decision.selected_mode == "parallel" and decision.workers > 1:
                    outcome = self.batch_runner.run_parallel(
                        jobs,
                        max_workers=decision.workers,
                        **common,
                    )
                else:
                    outcome = self.batch_runner.run(jobs, **common)

                self._set_batch_phase(overview, "Avslutter batch")
                summary = (
                    f"BATCH FERDIG: totalt={outcome.total}, "
                    f"ferdig={outcome.finished}, venter={outcome.waiting}, "
                    f"feil={outcome.failed}, hoppet over={outcome.skipped}, "
                    f"workers={decision.workers}"
                )
                status = (
                    "FEIL"
                    if outcome.failed
                    else ("VENTER" if outcome.waiting else "FERDIG")
                )
                overview.finish(status)
                self.after(0, lambda s=summary: self.log_panel.append(s))
                self.after(0, lambda s=summary: self.status_bar.set_status(s))

            except Exception as exc:
                overview.set_phase("Batch stoppet med exception")
                overview.fail(exc)
                self.after(
                    0,
                    lambda e=str(exc):
                        self.log_panel.append(f"BATCH FEIL: {e}"),
                )
                self.after(
                    0,
                    lambda e=str(exc):
                        self.status_bar.set_status(f"Batch stoppet med feil: {e}"),
                )

            finally:
                worker_finished.set()
                if getattr(overview, "finished", None) is None:
                    overview.finish("AVBRUTT")
                self.after(
                    0,
                    lambda p=overview.path:
                        self.log_panel.append(f"KJØRELOGG LAGRET: {p}"),
                )
                self.batch_running = False
                self.after(
                    0,
                    lambda:
                        self.workflow_panel.run_button.configure(state="normal"),
                )
                self.after(0, self._update_run_button)
                if self.jobs_window is not None and self.jobs_window.winfo_exists():
                    self.after(
                        0,
                        lambda: self.jobs_window.set_batch_running(False),
                    )
                    self.after(0, self.jobs_window.refresh)

        thread = threading.Thread(
            target=worker,
            daemon=True,
            name="dwm-batch",
        )
        thread.start()

        def startup_watchdog() -> None:
            deadline = time.monotonic() + self._BATCH_STARTUP_TIMEOUT_SECONDS
            while time.monotonic() < deadline:
                if worker_finished.is_set() or first_job_registered.is_set():
                    return
                time.sleep(0.1)

            if not worker_started.is_set():
                message = "Batch-worker startet ikke innen timeout."
            else:
                message = (
                    "Batch-worker startet, men ingen jobb ble registrert innen "
                    f"{self._BATCH_STARTUP_TIMEOUT_SECONDS:.0f} sekunder."
                )

            overview.set_phase("Startup-failsafe utløst")
            overview.fail(message)
            self.batch_cancel_requested = True
            self.batch_running = False
            self.after(
                0,
                lambda m=message:
                    self.log_panel.append(f"BATCH STARTUP-FEIL: {m}"),
            )
            self.after(0, lambda m=message: self.status_bar.set_status(m))
            self.after(
                0,
                lambda:
                    self.workflow_panel.run_button.configure(state="normal"),
            )
            self.after(0, self._update_run_button)
            if self.jobs_window is not None and self.jobs_window.winfo_exists():
                self.after(
                    0,
                    lambda: self.jobs_window.set_batch_running(False),
                )
                self.after(0, self.jobs_window.refresh)

        threading.Thread(
            target=startup_watchdog,
            daemon=True,
            name="dwm-batch-watchdog",
        ).start()


def run_gui() -> None:
    theme.apply_theme()
    app = WorkflowApp()
    app.mainloop()
