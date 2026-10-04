from __future__ import annotations

import threading
import time
from pathlib import Path
from tkinter import messagebox

import tkinter as tk
import customtkinter as ctk

from settings import save_config

from noark5_workflow.core.job import Job, JobStatus
from noark5_workflow.core.job_store import save_job_list
from version import APP_NAME, VERSION
from . import theme
from .jobs_window_a34 import A34JobsWindow
from .persistent_app_a27_2 import WorkflowApp as A27_2WorkflowApp


class WorkflowApp(A27_2WorkflowApp):
    """v0.1.6-a36: usable selection, resumable execution and external stop."""

    def __init__(self) -> None:
        super().__init__()
        self._install_workflow_controls_splitter()
        self.after_idle(self._a36_fix_splitters)

    def _a36_fix_splitters(self) -> None:
        """Use simple native Tk drag handles in the left column."""
        try:
            self.right.unbind("<Configure>")
        except Exception:
            pass
        try:
            self.bottom_splitter.grid_remove()
        except Exception:
            pass
        try:
            self.right.grid_rowconfigure(0, weight=0, minsize=0)
            self.right.grid_rowconfigure(1, weight=0, minsize=0)
            self.right.grid_rowconfigure(2, weight=1, minsize=0)
            self.log_panel.configure(height=1)
        except Exception:
            pass

        # Replace the CustomTkinter divider with a native Tk frame.  Native Tk
        # mouse grabs keep delivering motion/release events outside the handle.
        try:
            self.left.unbind("<Configure>")
        except Exception:
            pass
        try:
            self.left_splitter.destroy()
        except Exception:
            pass
        self.left_splitter = tk.Frame(
            self.left,
            height=8,
            bg=theme.BLUE_DIM,
            cursor="sb_v_double_arrow",
            bd=0,
            highlightthickness=0,
        )
        self.left_splitter.grid(row=1, column=0, sticky="ew")
        self.left_splitter.grid_propagate(False)

        self._left_dragging = False
        self._left_split_start_y = 0
        self._left_split_start_height = int(
            self.settings.get("left_source_height", self._left_source_height)
        )
        self.left_splitter.bind("<ButtonPress-1>", self._a36_start_left_drag)
        self.left_splitter.bind("<B1-Motion>", self._a36_drag_left_split)
        self.left_splitter.bind("<ButtonRelease-1>", self._a36_end_left_drag)
        self._left_source_height = self._a36_coerce_left_source_height(
            self._left_split_start_height
        )
        self._a36_apply_left_source_height()

    def _a36_coerce_left_source_height(self, value: int | float) -> int:
        try:
            total = max(1, int(self.left.winfo_height()))
        except Exception:
            total = 520
        minimum = 60
        maximum = max(minimum, total - 150)
        return max(minimum, min(int(value), maximum))

    def _a36_apply_left_source_height(self) -> None:
        height = self._a36_coerce_left_source_height(self._left_source_height)
        self._left_source_height = height
        self.left.grid_rowconfigure(0, weight=0, minsize=height)
        self.left.grid_rowconfigure(1, weight=0, minsize=8)
        self.left.grid_rowconfigure(2, weight=1, minsize=0)
        try:
            self.source_panel.configure(height=height)
            self.source_panel.grid_propagate(False)
        except Exception:
            pass

    def _a36_start_left_drag(self, event) -> None:
        self._left_dragging = True
        self._left_split_start_y = int(event.y_root)
        self._left_split_start_height = int(self.source_panel.winfo_height())
        try:
            self.left_splitter.grab_set()
        except Exception:
            pass

    def _a36_drag_left_split(self, event) -> None:
        if not self._left_dragging:
            return
        delta = int(event.y_root) - self._left_split_start_y
        self._left_source_height = self._a36_coerce_left_source_height(
            self._left_split_start_height + delta
        )
        self._a36_apply_left_source_height()
        # The lower divider has its own absolute position in the left column.
        # Recalculate only the workflow-list height so moving the upper divider
        # does not drag the lower divider with it.
        self._a36_apply_workflow_split_y()

    def _a36_end_left_drag(self, _event=None) -> None:
        if not self._left_dragging:
            return
        self._left_dragging = False
        try:
            self.left_splitter.grab_release()
        except Exception:
            pass
        self.settings["left_source_height"] = int(self._left_source_height)
        try:
            save_config({"left_source_height": int(self._left_source_height)})
        except Exception:
            pass

    def _install_workflow_controls_splitter(self) -> None:
        """Insert an independently positioned lower divider in WORKFLOW."""
        panel = self.workflow_panel
        run_row = panel.run_button.master
        buttons = panel.save_profile_button.master
        project_buttons = panel.open_project_button.master

        run_row.grid_configure(row=3)
        panel.regenerate_stale_button.grid_configure(row=4)
        buttons.grid_configure(row=5)
        project_buttons.grid_configure(row=6)

        self.workflow_controls_splitter = tk.Frame(
            panel,
            height=8,
            bg=theme.BLUE_DIM,
            cursor="sb_v_double_arrow",
            bd=0,
            highlightthickness=0,
        )
        self.workflow_controls_splitter.grid(
            row=2, column=0, padx=4, pady=(3, 3), sticky="ew"
        )
        self.workflow_controls_splitter.grid_propagate(False)

        self._workflow_split_dragging = False
        self._workflow_split_y = int(
            self.settings.get("left_workflow_split_y", 0) or 0
        )

        # Row 1 is explicitly sized from the absolute lower-divider position.
        # Row 7 absorbs unused room below the existing controls.
        panel.grid_rowconfigure(1, weight=0, minsize=0)
        panel.grid_rowconfigure(7, weight=1, minsize=0)
        self.after_idle(self._a36_initialise_workflow_split_y)

        self.workflow_controls_splitter.bind(
            "<ButtonPress-1>", self._start_workflow_controls_drag
        )
        self.workflow_controls_splitter.bind(
            "<B1-Motion>", self._drag_workflow_controls
        )
        self.workflow_controls_splitter.bind(
            "<ButtonRelease-1>", self._end_workflow_controls_drag
        )

    def _a36_workflow_split_bounds(self) -> tuple[int, int]:
        try:
            self.left.update_idletasks()
            panel_top = int(self.workflow_panel.winfo_y())
            total = max(1, int(self.left.winfo_height()))
        except Exception:
            panel_top, total = 180, 760
        minimum = panel_top + 90
        maximum = max(minimum, total - 170)
        return minimum, maximum

    def _a36_coerce_workflow_split_y(self, value: int | float) -> int:
        minimum, maximum = self._a36_workflow_split_bounds()
        return max(minimum, min(int(value), maximum))

    def _a36_initialise_workflow_split_y(self) -> None:
        self.left.update_idletasks()
        if self._workflow_split_y <= 0:
            # Preserve approximately the old default visual position on first
            # use, then persist an absolute left-column position thereafter.
            current = (
                int(self.workflow_panel.winfo_y())
                + int(self.workflow_panel.items.winfo_y())
                + max(60, int(self.workflow_panel.items.winfo_height()))
            )
            self._workflow_split_y = self._a36_coerce_workflow_split_y(current)
        self._a36_apply_workflow_split_y()

    def _a36_apply_workflow_split_y(self) -> None:
        if not hasattr(self, "workflow_controls_splitter"):
            return
        try:
            self.left.update_idletasks()
            self._workflow_split_y = self._a36_coerce_workflow_split_y(
                self._workflow_split_y
            )
            items_top_in_left = (
                int(self.workflow_panel.winfo_y())
                + int(self.workflow_panel.items.winfo_y())
            )
            height = max(60, self._workflow_split_y - items_top_in_left - 4)
            self.workflow_panel.grid_rowconfigure(1, weight=0, minsize=height)
            self.workflow_panel.items.configure(height=height)
            self.workflow_panel.items.grid_propagate(False)
        except Exception:
            pass

    def _start_workflow_controls_drag(self, _event) -> None:
        self._workflow_split_dragging = True
        try:
            self.workflow_controls_splitter.grab_set()
        except Exception:
            pass

    def _drag_workflow_controls(self, event) -> None:
        if not self._workflow_split_dragging:
            return
        try:
            pointer_y = int(event.y_root) - int(self.left.winfo_rooty())
        except Exception:
            return
        self._workflow_split_y = self._a36_coerce_workflow_split_y(pointer_y)
        self._a36_apply_workflow_split_y()

    def _end_workflow_controls_drag(self, _event=None) -> None:
        if not self._workflow_split_dragging:
            return
        self._workflow_split_dragging = False
        try:
            self.workflow_controls_splitter.grab_release()
        except Exception:
            pass
        self.settings["left_workflow_split_y"] = int(self._workflow_split_y)
        try:
            save_config({"left_workflow_split_y": int(self._workflow_split_y)})
        except Exception:
            pass

    def _open_jobs(self) -> None:
        self._capture_job_operation_params(self.current_job)
        if self.jobs_window is not None:
            try:
                if self.jobs_window.winfo_exists():
                    if isinstance(self.jobs_window, A34JobsWindow):
                        self.jobs_window.lift()
                        self.jobs_window.focus_force()
                        self.jobs_window.refresh()
                        return
                    self.jobs_window.destroy()
            except Exception:
                pass
            self.jobs_window = None

        self.jobs_window = A34JobsWindow(
            self,
            self.jobs,
            self._open_job,
            self._create_job,
            self._start_all_jobs,
            on_start_selected=self._start_selected_jobs,
            on_stop=self._stop_batch,
            on_new_list=self._new_job_list,
            on_open_list=self._open_job_list_dialog,
            on_save_list=self._save_job_list,
            on_save_list_as=self._save_job_list_as,
            get_list_path=lambda: self.job_list_path,
            get_active_job_id=lambda: self.current_job.job_id if self.current_job else None,
            get_output_subfolder_rule=self._get_output_subfolder_rule,
            set_output_subfolder_rule=self._set_output_subfolder_rule,
            get_batch_execution_config=self._get_batch_execution_config,
            set_batch_execution_config=self._set_batch_execution_config,
            reset_job_execution=self._reset_job_execution,
            get_app_work_subfolder=self._get_app_work_subfolder,
            open_validation_overview=self._open_validation_overview,
            has_validation_overview=self._has_validation_overview,
            on_extraction_discovery=self._a242_apply_discovery,
            on_fill_storage_suggestions=self._a246_fill_storage_suggestions,
            on_discover_arkade5_results=self._a251_discover_arkade5_results,
            on_run_arkade5=self._a266_open_arkade5_run,
            on_apply_standard=self._a36_apply_standard,
        )
        self.jobs_window.lift()
        self.jobs_window.focus_force()

    def _start_selected_jobs(self) -> None:
        """Run exactly the jobs selected in the open Jobbliste window."""
        if self.jobs_window is None:
            return
        try:
            selected = self.jobs_window._selected_jobs_for_run()
        except Exception:
            selected = ()
        self._start_batch_jobs(selected)

    def _a36_apply_standard(self, jobs: tuple[Job, ...], empty_only: bool) -> None:
        targets = tuple(job for job in jobs if not empty_only or not job.workflow_ids)
        if not targets:
            messagebox.showinfo(
                APP_NAME, "Ingen jobber trenger standard workflow.",
                parent=self.jobs_window
            )
            return

        if not empty_only:
            existing = [job for job in targets if job.workflow_ids]
            if existing and not messagebox.askyesno(
                APP_NAME,
                f"Erstatte eksisterende workflow på {len(existing)} av "
                f"{len(targets)} valgte jobb(er)?",
                parent=self.jobs_window,
            ):
                return

        assigned = self._bulk_assign_default_noark5_workflow(
            targets, include_empty_only=empty_only
        )
        if self.job_list_path is not None:
            self._write_job_list(self.job_list_path)
        if self.jobs_window is not None and self.jobs_window.winfo_exists():
            self.jobs_window.refresh()
        self.status_bar.set_status(
            f"Standard workflow satt på {len(assigned)} jobb(er)"
        )

    def _persist_execution_state(self, job: Job) -> None:
        if self.job_list_path is not None:
            try:
                save_job_list(
                    Path(self.job_list_path),
                    self.jobs,
                    active_job_id=(
                        self.current_job.job_id if self.current_job else job.job_id
                    ),
                    app_version=VERSION,
                )
            except Exception as exc:
                self._job_log(
                    job, f"ADVARSEL: kunne ikke persistere kjørestatus: {exc}"
                )
        if self.jobs_window is not None:
            try:
                if self.jobs_window.winfo_exists():
                    self.after(0, self.jobs_window.schedule_refresh)
            except Exception:
                pass

    @staticmethod
    def _elapsed_text(seconds: float) -> str:
        total = max(0, int(seconds))
        hours, rem = divmod(total, 3600)
        minutes, secs = divmod(rem, 60)
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"

    def _execute_job(self, job: Job, *, batch_mode: bool) -> bool:
        # Existing a36 path calculates the effective Work/operations folder.
        apply_effective = getattr(self, "_apply_effective_work_operations", None)
        if callable(apply_effective):
            apply_effective(job)

        cancelled = (
            (lambda: self.batch_cancel_requested)
            if batch_mode else
            (lambda: self.cancel_requested)
        )
        started = time.monotonic()
        heartbeat_stop = threading.Event()
        current = {"operation": "workflow"}

        def log(message: str) -> None:
            text = str(message or "")
            if text.startswith("START: "):
                current["operation"] = text[7:]
            self._job_log(job, text)

        def progress(value: float, message: str) -> None:
            if message:
                current["operation"] = message
            self._progress_callback_for_job(job, value, message)

        def state(updated: Job) -> None:
            self._persist_execution_state(updated)

        def heartbeat() -> None:
            while not heartbeat_stop.wait(30.0):
                if job.status != JobStatus.RUNNING:
                    continue
                self._job_log(
                    job,
                    f"KJØRER: {current['operation']} | "
                    f"tid {self._elapsed_text(time.monotonic() - started)}",
                )

        threading.Thread(
            target=heartbeat, name=f"{job.job_id}-heartbeat", daemon=True
        ).start()
        try:
            outcome = self.job_runner.run(
                job,
                progress_cb=progress,
                log_cb=log,
                cancelled_cb=cancelled,
                state_cb=state,
            )
            return bool(outcome.ok)
        finally:
            heartbeat_stop.set()
            self._persist_execution_state(job)

    def _start_batch_jobs(self, jobs) -> None:
        if self.batch_running:
            return

        runnable = self._eligible_batch_jobs(list(jobs))
        if not runnable:
            messagebox.showwarning(
                APP_NAME,
                "Det finnes ingen kjørbare jobber. "
                "Ferdige jobber blir ikke kjørt på nytt.",
            )
            return

        self._capture_job_operation_params(self.current_job)
        self.batch_running = True
        self.batch_cancel_requested = False
        self.cancel_requested = False
        self.workflow_panel.run_button.configure(state="disabled")
        if self.jobs_window is not None and self.jobs_window.winfo_exists():
            self.jobs_window.set_batch_running(True)

        def worker() -> None:
            try:
                for job in runnable:
                    if self.batch_cancel_requested:
                        break
                    if job.status in {JobStatus.OK, JobStatus.SKIPPED}:
                        continue
                    self.after(0, lambda j=job: self._open_job(j))
                    self._execute_job(job, batch_mode=True)
            finally:
                self.batch_running = False
                self.after(
                    0,
                    lambda: self.workflow_panel.run_button.configure(state="normal"),
                )
                if self.jobs_window is not None and self.jobs_window.winfo_exists():
                    self.after(
                        0, lambda: self.jobs_window.set_batch_running(False)
                    )
                    self.after(0, self.jobs_window.schedule_refresh)

        threading.Thread(
            target=worker, name="dwm-batch-a36", daemon=True
        ).start()

    def _start_ready_jobs(self) -> None:
        ready = tuple(
            job for job in self.jobs.jobs()
            if job.workflow_ids
            and job.status in {
                JobStatus.READY, JobStatus.WAITING, JobStatus.FAILED
            }
        )
        self._start_batch_jobs(ready)

    def _stop_batch(self) -> None:
        self.batch_cancel_requested = True
        self.cancel_requested = True
        self.status_bar.set_status(
            "Stopper aktiv ekstern prosess og avbryter batch …"
        )
        if self.current_job is not None:
            self._job_log(self.current_job, "STOPP forespurt av bruker")
