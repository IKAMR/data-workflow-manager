from __future__ import annotations

import json
import threading
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox

import customtkinter as ctk

from app.job_workflow_policy import configured_sequence
from app.work_output_layout import effective_work_operations
from noark5_workflow.app import build_registry
from noark5_workflow.core.context import OperationContext
from noark5_workflow.core.job import Job, JobBatch, JobStatus
from noark5_workflow.core.output_lock import OutputLock, OutputLockedError
from noark5_workflow.core.workflow import Workflow
from noark5_workflow.executors.local import LocalExecutor
from noark5_workflow.sources.noark5_extraction import Noark5Extraction
from version import APP_NAME, VERSION
from settings import load_config, save_config
from . import theme
from .dias_dialog import DiasParamDialog
from .jobs_window import JobsWindow
from .log_panel import LogPanel
from .operations_panel import OperationsPanel
from .settings_dialog import SettingsDialog
from .source_panel import SourcePanel
from .status_bar import StatusBar
from .workflow_panel import WorkflowPanel


class WorkflowApp(ctk.CTk):
    def __init__(self) -> None:
        super().__init__()
        self.title(f"{APP_NAME} v{VERSION}")
        self.geometry("1500x900")
        self.minsize(1180, 720)
        self.configure(fg_color=theme.APP_BG)

        self.registry = build_registry()
        self.workflow = Workflow()
        self.jobs = JobBatch()
        if not hasattr(self.jobs, "output_subfolder_rule"):
            self.jobs.output_subfolder_rule = ""
        self.current_job: Job | None = None
        self.jobs_window: JobsWindow | None = None
        self.executor = LocalExecutor()
        self.extraction: Noark5Extraction | None = None
        self.cancel_requested = False
        self.batch_running = False
        self.batch_cancel_requested = False
        self.settings = load_config()
        theme.FontRegistry.set_offset(int(self.settings.get("font_offset", 0)))

        self._build_ui()
        self.status_bar.set_temp(self.settings.get("temp_dir") or None)

    def _build_ui(self) -> None:
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(1, weight=1)

        self._build_header()

        left = ctk.CTkFrame(self, fg_color=theme.APP_BG, width=theme.LEFT_WIDTH, corner_radius=0)
        left.grid(row=1, column=0, padx=(10, 5), pady=4, sticky="nsew")
        left.grid_propagate(False)
        left.grid_columnconfigure(0, weight=1)
        left.grid_rowconfigure(0, weight=0)
        left.grid_rowconfigure(1, weight=0)
        left.grid_rowconfigure(2, weight=1)
        self.left = left
        self._left_source_height = max(100, min(240, int(self.settings.get("left_source_height", 170))))
        self._left_dragging = False
        self._left_split_start_y = 0
        self._left_split_start_height = 0

        self.source_panel = SourcePanel(left, self._source_changed)
        self.source_panel.grid(row=0, column=0, padx=0, pady=(0, 0), sticky="nsew")
        self._apply_left_source_height()

        self.left_splitter = ctk.CTkFrame(
            left,
            height=10,
            fg_color=theme.PANEL_BG_DARK,
            border_width=1,
            border_color=theme.BLUE_DIM,
            cursor="sb_v_double_arrow",
            corner_radius=5,
        )
        self.left_splitter.grid(row=1, column=0, padx=0, pady=0, sticky="ew")
        self.left_splitter.bind("<ButtonPress-1>", self._start_left_drag)
        self.left_splitter.bind("<B1-Motion>", self._drag_left_split)
        self.left_splitter.bind("<ButtonRelease-1>", self._end_left_drag)
        self.left_splitter.bind("<Button-1>", self._start_left_drag)
        self.left_splitter.bind("<Enter>", lambda _event: self.left_splitter.configure(fg_color=theme.BLUE_DIM))
        self.left_splitter.bind("<Leave>", lambda _event: self.left_splitter.configure(fg_color=theme.PANEL_BG_DARK if not self._left_dragging else theme.BLUE_DIM))

        self.workflow_panel = WorkflowPanel(left, self.registry, self.workflow, self._run_workflow)
        self.workflow_panel.grid(row=2, column=0, padx=0, pady=0, sticky="nsew")

        left.bind("<Configure>", self._sync_left_split_after_resize)

        right = ctk.CTkFrame(self, fg_color=theme.APP_BG, corner_radius=0)
        right.grid(row=1, column=1, padx=(5, 10), pady=4, sticky="nsew")
        right.grid_columnconfigure(0, weight=1)
        right.grid_rowconfigure(0, weight=0)
        right.grid_rowconfigure(1, weight=0)
        right.grid_rowconfigure(2, weight=1)
        self.right = right

        self.operations_panel = OperationsPanel(right, self.registry, self._add_operation)
        self.operations_panel.grid(row=0, column=0, padx=0, pady=(0, 8), sticky="ew")

        self._bottom_panel_height = max(30, min(360, int(self.settings.get("bottom_panel_height", 220))))
        self._bottom_dragging = False
        self._bottom_split_start_y = 0
        self._bottom_split_start_height = 0

        self.bottom_splitter = ctk.CTkFrame(
            right,
            height=10,
            fg_color=theme.PANEL_BG_DARK,
            border_width=1,
            border_color=theme.BLUE_DIM,
            cursor="sb_v_double_arrow",
            corner_radius=5,
        )
        self.bottom_splitter.grid(row=1, column=0, padx=0, pady=0, sticky="ew")
        self.bottom_splitter.bind("<ButtonPress-1>", self._start_bottom_drag)
        self.bottom_splitter.bind("<B1-Motion>", self._drag_bottom_split)
        self.bottom_splitter.bind("<ButtonRelease-1>", self._end_bottom_drag)
        self.bottom_splitter.bind("<Button-1>", self._start_bottom_drag)
        self.bottom_splitter.bind("<Enter>", lambda _event: self.bottom_splitter.configure(fg_color=theme.BLUE_DIM))
        self.bottom_splitter.bind("<Leave>", lambda _event: self.bottom_splitter.configure(fg_color=theme.PANEL_BG_DARK if not self._bottom_dragging else theme.BLUE_DIM))

        self.log_panel = LogPanel(right)
        self.log_panel.grid(row=2, column=0, padx=0, pady=0, sticky="nsew")
        self._apply_bottom_panel_height()
        right.bind("<Configure>", self._sync_bottom_split_after_resize)

        self.status_bar = StatusBar(self)
        self.status_bar.grid(row=2, column=0, columnspan=2, sticky="ew")

    def _coerce_left_source_height(self, value: int | float) -> int:
        panel = self.__dict__.get("left")
        total = max(200, int(panel.winfo_height()) if panel is not None and panel.winfo_exists() else 520)
        minimum = 90
        maximum = max(minimum, total - 180)
        return max(minimum, min(int(value), maximum))

    def _apply_left_source_height(self) -> None:
        if not hasattr(self, "left") or not self.left.winfo_exists():
            return
        self._left_source_height = self._coerce_left_source_height(self._left_source_height)
        height = self._left_source_height
        self.left.grid_rowconfigure(0, minsize=height)
        self.left.grid_rowconfigure(1, minsize=8)
        self.left.grid_rowconfigure(2, weight=1)
        try:
            self.source_panel.configure(height=height)
        except Exception:
            pass

    def _sync_left_split_after_resize(self, _event=None) -> None:
        if self.__dict__.get("_left_dragging", False):
            return
        current = self.__dict__.get("_left_source_height", self.settings.get("left_source_height", 170))
        self._left_source_height = self._coerce_left_source_height(current)
        self._apply_left_source_height()

    def _start_left_drag(self, event) -> None:
        self._left_dragging = True
        self._left_split_start_y = int(event.y_root)
        self._left_split_start_height = self._left_source_height
        self.left_splitter.configure(fg_color=theme.BLUE_DIM)

    def _drag_left_split(self, event) -> None:
        if not self.__dict__.get("_left_dragging", False):
            return
        delta = int(event.y_root) - self._left_split_start_y
        new_height = self._left_split_start_height + delta
        self._left_source_height = self._coerce_left_source_height(new_height)
        self._apply_left_source_height()

    def _end_left_drag(self, _event=None) -> None:
        self._left_dragging = False
        self.left_splitter.configure(fg_color=theme.PANEL_BG)
        try:
            self._left_source_height = self._coerce_left_source_height(self._left_source_height)
            self.settings["left_source_height"] = int(self._left_source_height)
            save_config({"left_source_height": int(self._left_source_height)})
        except Exception:
            pass

    def _coerce_bottom_panel_height(self, value: int | float) -> int:
        panel = self.__dict__.get("right")
        total = max(180, int(panel.winfo_height()) if panel is not None and panel.winfo_exists() else 420)
        minimum = 30
        maximum = max(minimum, total - 120)
        return max(minimum, min(int(value), maximum))

    def _apply_bottom_panel_height(self) -> None:
        if not hasattr(self, "right") or not self.right.winfo_exists():
            return
        self._bottom_panel_height = self._coerce_bottom_panel_height(self._bottom_panel_height)
        height = self._bottom_panel_height
        self.right.grid_rowconfigure(0, weight=0)
        self.right.grid_rowconfigure(1, minsize=8)
        self.right.grid_rowconfigure(2, minsize=height)
        self.right.grid_rowconfigure(2, weight=1)
        try:
            self.log_panel.configure(height=height)
        except Exception:
            pass

    def _sync_bottom_split_after_resize(self, _event=None) -> None:
        if self.__dict__.get("_bottom_dragging", False):
            return
        current = self.__dict__.get("_bottom_panel_height", self.settings.get("bottom_panel_height", 220))
        self._bottom_panel_height = self._coerce_bottom_panel_height(current)
        self._apply_bottom_panel_height()

    def _start_bottom_drag(self, event) -> None:
        self._bottom_dragging = True
        self._bottom_split_start_y = int(event.y_root)
        self._bottom_split_start_height = self._bottom_panel_height
        self.bottom_splitter.configure(fg_color=theme.BLUE_DIM)

    def _drag_bottom_split(self, event) -> None:
        if not self.__dict__.get("_bottom_dragging", False):
            return
        delta = int(event.y_root) - self._bottom_split_start_y
        new_height = self._bottom_split_start_height - delta
        self._bottom_panel_height = self._coerce_bottom_panel_height(new_height)
        self._apply_bottom_panel_height()

    def _end_bottom_drag(self, _event=None) -> None:
        self._bottom_dragging = False
        self.bottom_splitter.configure(fg_color=theme.PANEL_BG)
        try:
            self._bottom_panel_height = self._coerce_bottom_panel_height(self._bottom_panel_height)
            self.settings["bottom_panel_height"] = int(self._bottom_panel_height)
            save_config({"bottom_panel_height": int(self._bottom_panel_height)})
        except Exception:
            pass

    def _build_header(self) -> None:
        header = ctk.CTkFrame(self, fg_color=theme.APP_BG, height=theme.HEADER_HEIGHT, corner_radius=0)
        header.grid(row=0, column=0, columnspan=2, sticky="ew")
        header.grid_propagate(False)
        header.grid_columnconfigure(3, weight=1)

        ctk.CTkLabel(
            header,
            text=APP_NAME.upper(),
            font=theme.font(theme.TITLE_SIZE, "bold"),
            text_color=theme.BLUE,
        ).grid(row=0, column=0, padx=(16, 18), pady=10, sticky="w")

        ctk.CTkOptionMenu(
            header,
            values=["-- profil --"],
            width=135,
            height=28,
            font=theme.font(theme.SMALL_SIZE),
        ).grid(row=0, column=1, padx=6, pady=8)

        ctk.CTkLabel(
            header,
            text=f"v{VERSION}",
            font=theme.font(theme.SMALL_SIZE),
            text_color=theme.TEXT_MUTED,
        ).grid(row=0, column=2, padx=8, pady=8, sticky="w")

        self.active_job_label = ctk.CTkLabel(
            header,
            text="AKTIV JOBB: ingen",
            font=theme.font(theme.SMALL_SIZE, "bold"),
            text_color=theme.TEXT_SUB,
            anchor="w",
        )
        self.active_job_label.grid(row=0, column=3, padx=12, pady=8, sticky="ew")

        ctk.CTkButton(
            header,
            text="Jobber",
            width=78,
            height=28,
            font=theme.font(theme.SMALL_SIZE),
            fg_color=theme.BLUE_DIM,
            hover_color=theme.BLUE,
            command=self._open_jobs,
        ).grid(row=0, column=4, padx=(6, 4), pady=8)

        ctk.CTkButton(
            header,
            text="Endre temp-mappe",
            width=110,
            height=28,
            font=theme.font(theme.SMALL_SIZE),
            fg_color=theme.BUTTON_BG,
            hover_color=theme.BUTTON_HOVER,
            command=self._change_temp_dir,
        ).grid(row=0, column=5, padx=(6, 4), pady=8)

        ctk.CTkButton(
            header,
            text="Innstillinger",
            width=100,
            height=28,
            font=theme.font(theme.SMALL_SIZE),
            fg_color=theme.BUTTON_BG,
            hover_color=theme.BUTTON_HOVER,
            command=self._open_settings,
        ).grid(row=0, column=6, padx=4, pady=8)

        ctk.CTkButton(
            header, text="A-", width=34, height=28,
            font=theme.font(theme.SMALL_SIZE),
            fg_color=theme.BUTTON_BG, hover_color=theme.BUTTON_HOVER,
            command=lambda: self._font_scale(-1),
        ).grid(row=0, column=7, padx=2, pady=8)
        ctk.CTkButton(
            header, text="A+", width=34, height=28,
            font=theme.font(theme.SMALL_SIZE),
            fg_color=theme.BUTTON_BG, hover_color=theme.BUTTON_HOVER,
            command=lambda: self._font_scale(+1),
        ).grid(row=0, column=8, padx=2, pady=8)
        ctk.CTkButton(
            header, text="?", width=34, height=28, state="disabled",
            font=theme.font(theme.SMALL_SIZE), fg_color=theme.BUTTON_BG,
        ).grid(row=0, column=9, padx=(2, 10), pady=8)

    def _get_app_work_subfolder(self) -> str:
        value = self.settings.get("app_work_subfolder", "dwm")
        return str(value if value is not None else "dwm").strip()

    def _job_position(self, job: Job) -> int:
        for index, candidate in enumerate(self.jobs.jobs(), start=1):
            if candidate.job_id == job.job_id:
                return index
        return 1

    def _apply_effective_work_operations(self, job: Job | None) -> None:
        if job is None:
            return
        rule = str(getattr(self.jobs, "output_subfolder_rule", "") or "")
        job._effective_work_operations = effective_work_operations(
            job.work_operations,
            self._get_app_work_subfolder(),
            rule,
            job,
            self._job_position(job),
        )

    def _open_jobs(self) -> None:
        self._capture_job_operation_params(self.current_job)
        if self.jobs_window is not None and self.jobs_window.winfo_exists():
            self.jobs_window.focus()
            self.jobs_window.lift()
            self.jobs_window.focus_force()
            self.jobs_window.refresh()
            return
        self.jobs_window = JobsWindow(
            self, self.jobs, self._open_job, self._create_job, self._start_all_jobs, self._stop_batch
        )
        self.jobs_window.update_idletasks()
        self.jobs_window.lift()
        self.jobs_window.focus_force()

    def _capture_job_operation_params(self, job: Job | None) -> None:
        if not job:
            return
        job.set_workflow(self.workflow.operation_ids())
        for operation_id in job.workflow_ids:
            operation = self.registry.get(operation_id)
            params = getattr(operation, "params", None)
            if isinstance(params, dict):
                job.set_operation_params(operation_id, params)

    def _apply_job_operation_params(self, job: Job) -> None:
        for operation_id in job.workflow_ids:
            params = job.get_operation_params(operation_id)
            if not params:
                continue
            operation = self.registry.get(operation_id)
            configure = getattr(operation, "configure", None)
            if callable(configure):
                configure(params)

    def _job_log(self, job: Job, text: str, *, show: bool = True) -> None:
        entry = f"[{datetime.now().strftime('%H:%M:%S')}] {text.rstrip()}"
        job.log_entries.append(entry)
        job.log_entries = job.log_entries[-2000:]
        if show:
            self.after(0, lambda e=entry, jid=job.job_id: self.log_panel.append(f"[{jid}] {e}", timestamp=False))

    def _show_job_log(self, job: Job) -> None:
        self.log_panel.clear()
        if not job.log_entries:
            self.log_panel.append(f"Jobb åpnet: {job.job_id} - {job.name}")
            return
        for entry in job.log_entries:
            self.log_panel.append(entry, timestamp=False)

    def _apply_default_noark5_workflow(self, job: Job | None) -> None:
        if job is None:
            return
        if job.workflow_ids:
            return
        sequence = configured_sequence(self.settings, profile_id="noark5")
        if sequence is None:
            return
        job.profile_id = "noark5"
        job.set_workflow(sequence.operation_ids)

    def _create_job(self, source_root: Path) -> Job:
        job = self.jobs.new_job(source_root)
        self._apply_default_noark5_workflow(job)
        self._apply_effective_work_operations(job)
        return job

    def _refresh_active_job_label(self) -> None:
        if not self.current_job:
            self.active_job_label.configure(text="AKTIV JOBB: ingen", text_color=theme.TEXT_SUB)
            return
        count = len(self.workflow.operation_ids())
        if count == 0:
            suffix = "Workflow: 0 operasjoner - legg til operasjoner"
        elif count == 1:
            suffix = "Workflow: 1 operasjon"
        else:
            suffix = f"Workflow: {count} operasjoner"
        self.active_job_label.configure(
            text=f"AKTIV JOBB: {self.current_job.job_id} | {self.current_job.name} | {suffix}",
            text_color=theme.BLUE,
        )

    def _ensure_job_for_current_source(self) -> Job | None:
        root = self.source_panel.path_var.get().strip()
        if not root:
            return None
        path = Path(root)
        if self.current_job and self.current_job.source_root == path:
            return self.current_job
        existing = next((job for job in self.jobs.jobs() if job.source_root == path), None)
        if existing:
            self.current_job = existing
            self._refresh_active_job_label()
            return existing
        self.current_job = self.jobs.new_job(path)
        if self.workflow.operation_ids():
            self.current_job.set_workflow(self.workflow.operation_ids())
        self._apply_default_noark5_workflow(self.current_job)
        self._apply_effective_work_operations(self.current_job)
        self._refresh_active_job_label()
        return self.current_job

    def _open_job(self, job: Job) -> None:
        self._capture_job_operation_params(self.current_job)
        self.current_job = job
        self.workflow.clear()
        for operation_id in job.workflow_ids:
            self.workflow.add(operation_id)
        self._apply_job_operation_params(job)
        self._apply_effective_work_operations(job)
        self.workflow_panel.refresh()
        self.source_panel.set_path(str(job.source_root))
        self._refresh_active_job_label()
        if self.batch_running:
            self.status_bar.set_status(f"Kjører {job.job_id}: {job.name}")
        else:
            self.status_bar.set_status(f"Åpnet {job.job_id}: {job.name}")
        self._show_job_log(job)

    def _font_scale(self, delta: int) -> None:
        """Juster skriftstørrelsen dynamisk, på samme måte som SIARD Workflow Manager."""
        theme.FontRegistry.scale(delta)
        offset = theme.FontRegistry.current_offset()
        self.settings["font_offset"] = offset
        save_config({"font_offset": offset})
        sign = f"+{offset}" if offset > 0 else str(offset)
        self.status_bar.set_status(f"Skriftstørrelse: {sign}")

    def _change_temp_dir(self) -> None:
        folder = filedialog.askdirectory(title="Velg temp-mappe")
        if folder:
            self.settings["temp_dir"] = folder
            save_config({"temp_dir": folder})
            self.status_bar.set_temp(folder)
            self.log_panel.append(f"Temp-mappe endret: {folder}")

    def _source_changed(self, extraction: Noark5Extraction | None) -> None:
        self.extraction = extraction
        if extraction:
            self._ensure_job_for_current_source()
            detection = "Noark 5" if extraction.is_noark5_candidate else "ukjent"
            self.status_bar.update_storage(extraction.root, detection=detection)
            if extraction.is_noark5_candidate:
                self.status_bar.set_status("Noark 5-uttrekk funnet")
                self.log_panel.append(f"Uttrekk valgt: {extraction.root}")
            else:
                self.status_bar.set_status("arkivstruktur.xml ble ikke funnet")
        else:
            self.status_bar.set_status("Klar")

    def _add_operation(self, operation_id: str) -> None:
        if self.batch_running:
            messagebox.showwarning(APP_NAME, "Workflow kan ikke endres mens Start alle kjører.")
            return
        if operation_id == "dias_package":
            operation = self.registry.get(operation_id)
            extraction_root = self.extraction.root if self.extraction else None
            initial_params = self.current_job.get_operation_params(operation_id) if self.current_job else {}

            def add_configured(params: dict) -> None:
                operation.configure(params)
                if self.workflow_panel.add(operation_id):
                    if self.current_job:
                        self.current_job.output_root = Path(params["output_dir"]) if params.get("output_dir") else None
                        self.current_job.set_workflow(self.workflow.operation_ids())
                        self.current_job.set_operation_params(operation_id, params)
                    self._refresh_active_job_label()
                    self.log_panel.append(f"Lagt til i workflow: {operation.definition.name}")
                    self.log_panel.append(f"DIAS-utdata: {params.get('output_dir') or '(ikke valgt)'}")
                else:
                    # Existing operation: configuration still belongs to this job.
                    if self.current_job:
                        self.current_job.output_root = Path(params["output_dir"]) if params.get("output_dir") else None
                        self.current_job.set_operation_params(operation_id, params)
                    self.status_bar.set_status("DIAS-konfigurasjon oppdatert for aktiv jobb")

            DiasParamDialog(self, initial_params, extraction_root, add_configured)
            return

        if self.workflow_panel.add(operation_id):
            if self.current_job:
                self.current_job.set_workflow(self.workflow.operation_ids())
            self._refresh_active_job_label()
            operation = self.registry.get(operation_id)
            self.log_panel.append(f"Lagt til i workflow: {operation.definition.name}")
        else:
            self.status_bar.set_status("Operasjonen finnes allerede i workflow")

    def _progress_callback_for_job(self, job: Job, value: float, message: str) -> None:
        job.progress = max(0.0, min(1.0, float(value)))
        self.after(0, lambda: self.status_bar.set_status(message or f"{job.job_id}: {value:.0%}"))
        if self.jobs_window is not None and self.jobs_window.winfo_exists():
            self.after(0, self.jobs_window.schedule_refresh)

    def _configure_operation_for_job(self, job: Job, operation_id: str):
        operation = self.registry.get(operation_id)
        params = job.get_operation_params(operation_id)
        configure = getattr(operation, "configure", None)
        if params and callable(configure):
            configure(params)
        return operation

    def _execute_job(self, job: Job, *, batch_mode: bool) -> bool:
        op_ids = list(job.workflow_ids)
        if not op_ids:
            job.status = JobStatus.SKIPPED
            job.message = "Ingen operasjoner i workflow"
            self._job_log(job, "HOPPET OVER: Ingen operasjoner i workflow")
            return True

        job.status = JobStatus.RUNNING
        job.progress = 0.0
        job.message = "Workflow startet"
        self._job_log(job, "Workflow startet")
        if self.jobs_window is not None and self.jobs_window.winfo_exists():
            self.after(0, lambda: self._open_job(job))
            self.after(0, self.jobs_window.schedule_refresh)

        output_lock = None
        try:
            if job.output_root:
                output_lock = OutputLock(job.output_root, job.job_id)
                output_lock.acquire()
                self._job_log(job, f"Utdata låst: {job.output_root}")

            source = Noark5Extraction.detect(job.source_root)
            ctx = OperationContext(
                extraction_root=job.source_root,
                source=source,
                settings=self.settings,
                progress_cb=lambda value, message: self._progress_callback_for_job(job, value, message),
                log_cb=lambda msg: self._job_log(job, msg),
                cancelled_cb=lambda: self.batch_cancel_requested if batch_mode else self.cancel_requested,
            )
            total = len(op_ids)
            all_ok = True
            for index, op_id in enumerate(op_ids, start=1):
                if (self.batch_cancel_requested if batch_mode else self.cancel_requested):
                    job.status = JobStatus.SKIPPED
                    job.message = "Avbrutt"
                    self._job_log(job, "AVBRUTT før neste operasjon")
                    return False
                operation = self._configure_operation_for_job(job, op_id)
                self._job_log(job, f"START: {operation.definition.name}")
                result = self.executor.execute(operation, ctx)
                all_ok = all_ok and result.ok
                self._job_log(job, result.message)
                for warning in result.warnings:
                    self._job_log(job, f"ADVARSEL: {warning}")
                if result.data:
                    self._job_log(job, json.dumps(result.data, ensure_ascii=False, indent=2))
                self._job_log(job, f"{'OK' if result.ok else 'FEIL'}: {operation.definition.name}")
                job.progress = index / total
                job.message = result.message
                if self.jobs_window is not None and self.jobs_window.winfo_exists():
                    self.after(0, self.jobs_window.schedule_refresh)
                if not result.ok:
                    break

            job.status = JobStatus.OK if all_ok else JobStatus.FAILED
            job.progress = 1.0 if all_ok else job.progress
            job.message = "Workflow fullført" if all_ok else "Workflow stoppet med feil"
            self._job_log(job, job.message)
            return all_ok
        except OutputLockedError as exc:
            job.status = JobStatus.FAILED
            job.message = str(exc)
            self._job_log(job, f"FEIL: {exc}")
            return False
        except Exception as exc:
            job.status = JobStatus.FAILED
            job.message = str(exc)
            self._job_log(job, f"FEIL: {exc}")
            return False
        finally:
            if output_lock is not None:
                output_lock.release()
            if self.jobs_window is not None and self.jobs_window.winfo_exists():
                self.after(0, self.jobs_window.schedule_refresh)

    def _run_workflow(self) -> None:
        if self.batch_running:
            messagebox.showwarning(APP_NAME, "Start alle kjører allerede.")
            return
        op_ids = self.workflow.operation_ids()
        if not op_ids:
            messagebox.showwarning(APP_NAME, "Legg til minst én operasjon i workflow først.")
            return
        root = self.source_panel.path_var.get().strip()
        if not root:
            messagebox.showwarning(APP_NAME, "Velg en uttrekksmappe først.")
            return

        job = self._ensure_job_for_current_source()
        if job is None:
            return
        job.set_workflow(op_ids)
        self._capture_job_operation_params(job)
        self.workflow_panel.run_button.configure(state="disabled")
        self.cancel_requested = False

        def worker() -> None:
            ok = self._execute_job(job, batch_mode=False)
            final = "Workflow fullført" if ok else "Workflow stoppet med feil"
            self.after(0, lambda: self.status_bar.set_status(final))
            self.after(0, lambda: self.workflow_panel.run_button.configure(state="normal"))

        threading.Thread(target=worker, daemon=True).start()

    def _start_all_jobs(self) -> None:
        if self.batch_running:
            return
        if len(self.jobs) == 0:
            messagebox.showwarning(APP_NAME, "Det finnes ingen jobber å kjøre.")
            return
        self._capture_job_operation_params(self.current_job)
        self.batch_running = True
        self.batch_cancel_requested = False
        self.workflow_panel.run_button.configure(state="disabled")
        if self.jobs_window is not None and self.jobs_window.winfo_exists():
            self.jobs_window.set_batch_running(True)
        self.log_panel.append("BATCH START: kjører alle jobber sekvensielt")

        def worker() -> None:
            jobs = self.jobs.jobs()
            for job in jobs:
                if self.batch_cancel_requested:
                    if job.status == JobStatus.READY:
                        job.status = JobStatus.SKIPPED
                        job.message = "Ikke startet - batch avbrutt"
                    continue
                # Re-running a batch is explicit: reset terminal status before execution.
                job.status = JobStatus.READY
                job.progress = 0.0
                self.after(0, lambda j=job: self._open_job(j))
                self._execute_job(job, batch_mode=True)

            counts = self.jobs.counts()
            summary = (
                f"BATCH FERDIG: totalt={len(jobs)}, ferdig={counts[JobStatus.OK]}, "
                f"feil={counts[JobStatus.FAILED]}, hoppet over={counts[JobStatus.SKIPPED]}"
            )
            self.after(0, lambda s=summary: self.log_panel.append(s))
            self.after(0, lambda s=summary: self.status_bar.set_status(s))
            self.batch_running = False
            self.after(0, lambda: self.workflow_panel.run_button.configure(state="normal"))
            if self.jobs_window is not None and self.jobs_window.winfo_exists():
                self.after(0, lambda: self.jobs_window.set_batch_running(False))
                self.after(0, self.jobs_window.schedule_refresh)

        threading.Thread(target=worker, daemon=True).start()

    def _stop_batch(self) -> None:
        if not self.batch_running:
            return
        self.batch_cancel_requested = True
        self.status_bar.set_status("Stopper batch etter aktiv operasjon / ved neste avbruddspunkt...")
        self.log_panel.append("BATCH: stopp forespurt")

    def _log_result(self, result) -> None:
        self.log_panel.append(result.message)
        for warning in result.warnings:
            self.log_panel.append(f"ADVARSEL: {warning}")
        if result.data:
            self.log_panel.append(json.dumps(result.data, ensure_ascii=False, indent=2), timestamp=False)

    def _open_settings(self) -> None:
        SettingsDialog(self, self.settings, self._save_settings)

    def _save_settings(self, settings: dict) -> None:
        self.settings = dict(settings)
        self.settings["font_offset"] = theme.FontRegistry.current_offset()
        save_config(self.settings)
        self.status_bar.set_temp(self.settings.get("temp_dir") or None)
        self.status_bar.set_status("Innstillinger oppdatert")


def run_gui() -> None:
    theme.apply_theme()
    app = WorkflowApp()
    app.mainloop()
