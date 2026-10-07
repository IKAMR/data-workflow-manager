from __future__ import annotations

from pathlib import Path
import json
from tkinter import filedialog, messagebox
import webbrowser

import customtkinter as ctk

from noark5_workflow.reporting import write_job_overview_html
from noark5_workflow.reporting.depot_metadata import (
    job_display_name,
    scan_and_import_info_xml_for_jobs,
)
from version import APP_NAME, VERSION

from .depot_metadata_dialog_v017_a1 import DepotMetadataDialog
from .depot_metadata_editor_v017_a1 import DepotMetadataEditor
from .depot_result_center_v017_a1 import V017A1DepotResultCenterDialog
from .window_placement import enable_native_work_window, present_native_work_window
from . import theme
from .jobs_window_v017_a1 import V017A1JobsWindow
from .persistent_app_a39_runtime import WorkflowApp as A39WorkflowApp
from .info_panel import InfoPanel
from settings import save_config


def _v017_job_display_name(job) -> str:
    """Human-facing extraction identity: depot LABEL, then source folder, then technical name."""
    display = str(job_display_name(job) or "").strip()
    technical = str(getattr(job, "name", "") or "").strip()
    job_id = str(getattr(job, "job_id", "") or "").strip()
    if display and display not in {technical, job_id}:
        return display
    source_root = getattr(job, "source_root", None)
    if source_root:
        folder = Path(source_root).name.strip()
        if folder:
            return folder
    return display or technical or job_id or "Ukjent uttrekk"


class WorkflowApp(A39WorkflowApp):
    """v0.1.7-a1: reports plus persistent depot metadata and metadata editing."""

    def __init__(self) -> None:
        self._depot_metadata_editor = None
        self._v017_depot_result_windows = {}
        super().__init__()
        self._install_metadata_header_button()
        self._install_active_job_navigation()
        self._v017_arrange_log_actions()
        self.after_idle(self._v017_arrange_log_actions)
        self.after(300, self._v017_arrange_log_actions)
        self._refresh_active_job_label()
        self.after_idle(self._v017_restore_info_panel_state)
        # Restore Jobbliste before mainloop starts. Creating a CTkToplevel from
        # the scaling tracker's own after-loop can mutate its window registry
        # during iteration on Windows/Python 3.14.
        self._v017_restore_job_list_window()



    def _v017_arrange_log_actions(self) -> None:
        """Keep interpreted Depotvurdering before technical raw results."""
        header = getattr(getattr(self, "log_panel", None), "header", None)
        if header is None:
            return
        buttons = {}
        for child in header.winfo_children():
            if not isinstance(child, ctk.CTkButton):
                continue
            try:
                label = str(child.cget("text"))
            except Exception:
                continue
            buttons[label] = child
        raw = buttons.get("Resultater") or buttons.get("Råresultater")
        if raw is not None:
            try:
                raw.configure(text="Råresultater", width=92)
            except Exception:
                pass
        # Re-read after any rename and place the main work action first.
        buttons = {}
        for child in header.winfo_children():
            if not isinstance(child, ctk.CTkButton):
                continue
            try:
                buttons[str(child.cget("text"))] = child
            except Exception:
                pass
        for label, column in (("Depotvurdering", 1), ("Råresultater", 2), ("Tøm", 3)):
            button = buttons.get(label)
            if button is not None and button.grid_info():
                try:
                    button.grid_configure(column=column)
                except Exception:
                    pass
        try:
            header.grid_columnconfigure(0, weight=1)
            for column in range(1, 4):
                header.grid_columnconfigure(column, weight=0)
        except Exception:
            pass

    def _install_active_job_navigation(self) -> None:
        """Place compact previous/next controls immediately before active-job text."""
        if hasattr(self, "_v017_prev_job_button"):
            return
        header = self.active_job_label.master

        # Keep the inherited label object for compatibility with older runtime
        # layers, but replace its visible grid cell with one compact strip.
        try:
            current_text = str(self.active_job_label.cget("text") or "AKTIV JOBB: ingen")
        except Exception:
            current_text = "AKTIV JOBB: ingen"
        try:
            self.active_job_label.grid_remove()
        except Exception:
            pass

        nav = ctk.CTkFrame(header, fg_color=theme.APP_BG, corner_radius=0)
        nav.grid(row=0, column=3, padx=(8, 8), pady=8, sticky="ew")
        nav.grid_columnconfigure(2, weight=1)
        self._v017_job_nav_frame = nav

        self._v017_prev_job_button = ctk.CTkButton(
            nav, text="◀", width=34, height=28,
            font=theme.font(theme.NORMAL_SIZE + 2, "bold"),
            fg_color=theme.BUTTON_BG, hover_color=theme.BUTTON_HOVER,
            command=lambda: self._v017_step_active_job(-1),
        )
        self._v017_prev_job_button.grid(row=0, column=0, padx=(0, 2))
        self._v017_next_job_button = ctk.CTkButton(
            nav, text="▶", width=34, height=28,
            font=theme.font(theme.NORMAL_SIZE + 2, "bold"),
            fg_color=theme.BUTTON_BG, hover_color=theme.BUTTON_HOVER,
            command=lambda: self._v017_step_active_job(1),
        )
        self._v017_next_job_button.grid(row=0, column=1, padx=(0, 6))
        self._v017_active_job_display_label = ctk.CTkLabel(
            nav,
            text=current_text,
            font=theme.font(theme.SMALL_SIZE, "bold"),
            text_color=theme.TEXT_SUB,
            anchor="w",
        )
        self._v017_active_job_display_label.grid(row=0, column=2, sticky="ew")

        # Earlier a1 fixes temporarily used a second header row.  The compact
        # navigation strip belongs in the established top row instead.
        try:
            header.configure(height=int(theme.HEADER_HEIGHT))
        except Exception:
            pass

    def _v017_step_active_job(self, delta: int) -> None:
        jobs = list(self.jobs.jobs())
        if not jobs or self.current_job is None:
            return
        try:
            index = next(i for i, job in enumerate(jobs) if job.job_id == self.current_job.job_id)
        except StopIteration:
            return
        if len(jobs) == 1:
            return
        target_index = (index + int(delta)) % len(jobs)
        self._open_job(jobs[target_index])
        if self.jobs_window is not None:
            try:
                if self.jobs_window.winfo_exists():
                    self.jobs_window.refresh()
            except Exception:
                pass

    def _v017_update_job_navigation_state(self, position: int, total: int) -> None:
        if not hasattr(self, "_v017_prev_job_button"):
            return
        state = "normal" if total > 1 and position > 0 else "disabled"
        self._v017_prev_job_button.configure(state=state)
        self._v017_next_job_button.configure(state=state)

    def _v017_set_active_job_text(self, text: str, color) -> None:
        # Update both the inherited compatibility label and the visible a1 strip.
        try:
            self.active_job_label.configure(text=text, text_color=color)
        except Exception:
            pass
        visible = getattr(self, "_v017_active_job_display_label", None)
        if visible is not None:
            try:
                visible.configure(text=text, text_color=color)
            except Exception:
                pass

    def _v017_restore_job_list_window(self) -> None:
        """Reopen Jobbliste when it was still open at the previous app shutdown."""
        if not bool(self.settings.get("job_list_window_open", False)):
            return
        try:
            self._open_jobs()
        except Exception:
            pass

    def _v017_find_info_panel(self):
        def walk(widget):
            for child in widget.winfo_children():
                if isinstance(child, InfoPanel):
                    return child
                found = walk(child)
                if found is not None:
                    return found
            return None
        try:
            return walk(self)
        except Exception:
            return None

    def _v017_restore_info_panel_state(self) -> None:
        """Persist and restore the deliberate INFO open/closed choice."""
        panel = self._v017_find_info_panel()
        if panel is None:
            try:
                self.after(250, self._v017_restore_info_panel_state)
            except Exception:
                pass
            return
        if getattr(panel, "_v017_visibility_bound", False):
            return
        panel._v017_visibility_bound = True

        original_close = getattr(panel, "on_close", None)
        startup = {"settled": False, "closed_callback_used": False}

        def persist(value: bool) -> None:
            self.settings["info_panel_visible"] = bool(value)
            try:
                save_config({"info_panel_visible": bool(value)})
            except Exception:
                pass

        def close_and_persist() -> None:
            persist(False)
            if callable(original_close):
                original_close()
            else:
                try:
                    panel.grid_remove()
                except Exception:
                    pass

        panel.on_close = close_and_persist

        def mapped(_event=None) -> None:
            # Ignore mapping generated by application startup/layout. After the
            # startup state has settled, a Map means the user reopened INFO.
            if not startup["settled"]:
                return
            try:
                if panel.winfo_ismapped():
                    persist(True)
            except Exception:
                pass

        panel.bind("<Map>", mapped, add="+")

        def apply_saved_state() -> None:
            if bool(self.settings.get("info_panel_visible", True)):
                return
            try:
                # Run the inherited close callback at most once so any layout
                # bookkeeping is updated, then enforce hidden state directly.
                if callable(original_close) and not startup["closed_callback_used"]:
                    startup["closed_callback_used"] = True
                    original_close()
                try:
                    panel.grid_remove()
                except Exception:
                    pass
            except Exception:
                pass

        apply_saved_state()
        try:
            self.after(350, apply_saved_state)
            self.after(900, apply_saved_state)
            self.after(1100, lambda: startup.__setitem__("settled", True))
        except Exception:
            startup["settled"] = True

    def _v017_persist_info_panel_actual_state(self) -> None:
        """Persist the actual INFO visibility immediately before app shutdown."""
        panel = self._v017_find_info_panel()
        if panel is None:
            return
        try:
            visible = bool(panel.winfo_ismapped()) and bool(panel.grid_info())
        except Exception:
            return
        self.settings["info_panel_visible"] = visible
        try:
            save_config({"info_panel_visible": visible})
        except Exception:
            pass

    def _close_with_persistence(self) -> None:
        self._v017_persist_info_panel_actual_state()
        return super()._close_with_persistence()

    def _install_metadata_header_button(self) -> None:
        if hasattr(self, "metadata_button"):
            return
        header = self.active_job_label.master
        storage = getattr(self, "storage_button", None)
        storage_info = storage.grid_info() if storage is not None else {}
        column = int(storage_info.get("column", 4)) + 1
        for child in header.winfo_children():
            if child is storage:
                continue
            info = child.grid_info()
            if info and int(info.get("column", -1)) >= column:
                child.grid_configure(column=int(info["column"]) + 1)
        self.metadata_button = ctk.CTkButton(
            header,
            text="Metadata",
            width=82,
            height=28,
            font=theme.font(theme.SMALL_SIZE),
            fg_color=theme.BUTTON_BG,
            hover_color=theme.BUTTON_HOVER,
            command=self._open_active_metadata_editor,
        )
        self.metadata_button.grid(row=0, column=column, padx=(2, 2), pady=8)


    def _open_active_metadata_editor(self) -> None:
        job = self.current_job
        if job is None:
            return
        existing = self._depot_metadata_editor
        if existing is not None:
            try:
                if existing.winfo_exists():
                    existing.lift()
                    existing.focus_force()
                    return
            except Exception:
                self._depot_metadata_editor = None

        def saved() -> None:
            self._refresh_active_job_label()
            if self.jobs_window is not None:
                try:
                    if self.jobs_window.winfo_exists():
                        self.jobs_window.refresh()
                except Exception:
                    pass

        editor = DepotMetadataEditor(self, job, on_saved=saved)
        self._depot_metadata_editor = editor
        editor.bind(
            "<Destroy>",
            lambda event, d=editor: self._metadata_editor_closed(event, d),
            add="+",
        )
        editor.lift()
        editor.focus_force()

    def _metadata_editor_closed(self, event, dialog) -> None:
        if event.widget is dialog and self._depot_metadata_editor is dialog:
            self._depot_metadata_editor = None

    def _refresh_active_job_label(self) -> None:
        if not self.current_job:
            self._v017_set_active_job_text("AKTIV JOBB: ingen", theme.TEXT_SUB)
            try:
                self.title(f"{APP_NAME} v{VERSION}")
            except Exception:
                pass
            if hasattr(self, "metadata_button"):
                self.metadata_button.configure(state="disabled")
            self._v017_update_job_navigation_state(0, len(self.jobs.jobs()))
            return

        jobs = self.jobs.jobs()
        try:
            position = next(
                index
                for index, job in enumerate(jobs, start=1)
                if job.job_id == self.current_job.job_id
            )
        except StopIteration:
            position = 0
        count = len(self.workflow.operation_ids())
        if count == 0:
            workflow_text = "Workflow: 0 operasjoner - legg til operasjoner"
        elif count == 1:
            workflow_text = "Workflow: 1 operasjon"
        else:
            workflow_text = f"Workflow: {count} operasjoner"
        position_text = f"{position} av {len(jobs)}" if position else f"? av {len(jobs)}"
        display_name = _v017_job_display_name(self.current_job)
        self._v017_set_active_job_text(
            f"AKTIV JOBB: {position_text} | {self.current_job.job_id} | {workflow_text}",
            theme.BLUE,
        )
        try:
            self.title(f"{APP_NAME} v{VERSION} – {display_name}")
        except Exception:
            pass
        if hasattr(self, "metadata_button"):
            self.metadata_button.configure(state="normal")
        self._v017_update_job_navigation_state(position, len(jobs))

    def _open_depot_assessment(self) -> None:
        """Open one Resultatvisninger window per job and keep other jobs open."""
        self._hide_workflow_tooltips()
        job = self.current_job
        if job is None:
            return super()._open_depot_assessment()

        report_path, _work_operations, _unavailable_path = self._depot_report_for_job(job)
        if report_path is None:
            return super()._open_depot_assessment()

        key = str(job.job_id)
        existing = self._v017_depot_result_windows.get(key)
        if existing is not None:
            try:
                if existing.winfo_exists():
                    existing.deiconify()
                    present_native_work_window(existing)
                    return
            except Exception:
                pass
            self._v017_depot_result_windows.pop(key, None)

        try:
            model = json.loads(Path(report_path).read_text(encoding="utf-8"))
        except Exception:
            return super()._open_depot_assessment()

        display_name = _v017_job_display_name(job)
        dialog = V017A1DepotResultCenterDialog(
            self,
            model=model,
            report_path=report_path,
            user_identity=self.current_user_identity(),
            display_name=display_name,
        )
        self._v017_depot_result_windows[key] = dialog
        self._depot_assessment_dialog = dialog
        enable_native_work_window(dialog)
        present_native_work_window(dialog)
        dialog.bind(
            "<Destroy>",
            lambda event, d=dialog, k=key: self._v017_depot_result_closed(event, d, k),
            add="+",
        )

    def _v017_depot_result_closed(self, event, dialog, key: str) -> None:
        if event.widget is not dialog:
            return
        if self._v017_depot_result_windows.get(key) is dialog:
            self._v017_depot_result_windows.pop(key, None)
        if getattr(self, "_depot_assessment_dialog", None) is dialog:
            self._depot_assessment_dialog = None

    def _v017_remember_jobs_window_open(self) -> None:
        self.settings["job_list_window_open"] = True
        try:
            save_config({"job_list_window_open": True})
        except Exception:
            pass

    def _open_jobs(self) -> None:
        self._capture_job_operation_params(self.current_job)

        if self.jobs_window is not None:
            try:
                if self.jobs_window.winfo_exists():
                    if isinstance(self.jobs_window, V017A1JobsWindow):
                        self.jobs_window.deiconify()
                        self.jobs_window.refresh()
                        self.jobs_window.lift()
                        self.jobs_window.focus_force()
                        self._v017_remember_jobs_window_open()
                        return
                    self.jobs_window.destroy()
            except Exception:
                pass
            self.jobs_window = None

        self.jobs_window = V017A1JobsWindow(
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
            on_discover_arkade5_results=self._v017_a1_discover_results_and_metadata,
            on_run_arkade5=self._a266_open_arkade5_run,
            on_apply_standard=self._a37_apply_standard,
            on_apply_workflow=self._a37_apply_workflow,
            on_report_selected=self._v017_a1_report_selected,
            on_edit_metadata=self._v017_a1_edit_metadata,
        )
        self.jobs_window.lift()
        self.jobs_window.focus_force()
        self._v017_remember_jobs_window_open()

    def _v017_a1_report_initial_dir(self, jobs) -> Path:
        if self.job_list_path is not None:
            return Path(self.job_list_path).parent
        for job in jobs:
            for candidate in (
                job.archive_root,
                job.work_root,
                job.output_root,
                job.active_extraction_root,
            ):
                if candidate is not None:
                    path = Path(candidate)
                    return path if path.is_dir() else path.parent
        return Path.cwd()

    def _v017_a1_scan_metadata(self, jobs):
        return scan_and_import_info_xml_for_jobs(tuple(jobs))

    def _v017_a1_discover_results_and_metadata(self, jobs) -> None:
        self._a251_discover_arkade5_results(jobs)
        try:
            self._v017_a1_scan_metadata(jobs)
        finally:
            if self.jobs_window is not None:
                try:
                    if self.jobs_window.winfo_exists():
                        self.jobs_window.refresh()
                except Exception:
                    pass

    def _v017_a1_edit_metadata(self, jobs) -> None:
        selected = tuple(jobs)
        if not selected:
            return
        if len(selected) == 1:
            self.current_job = selected[0]
            self._refresh_active_job_label()
            self._open_active_metadata_editor()
            return

        def saved() -> None:
            self.status_bar.set_status("Depotmetadata oppdatert")
            self._refresh_active_job_label()
            if self.jobs_window is not None:
                try:
                    if self.jobs_window.winfo_exists():
                        self.jobs_window.refresh()
                except Exception:
                    pass

        DepotMetadataDialog(
            self.jobs_window or self,
            selected,
            on_saved=saved,
        )

    def _v017_a1_report_selected(self, jobs) -> None:
        selected = tuple(jobs)
        if not selected:
            return
        try:
            self._v017_a1_scan_metadata(selected)
        except Exception:
            pass
        if self.jobs_window is not None:
            try:
                if self.jobs_window.winfo_exists():
                    self.jobs_window.refresh()
            except Exception:
                pass

        target = filedialog.asksaveasfilename(
            parent=self.jobs_window,
            title="Lagre HTML-rapport",
            initialdir=str(self._v017_a1_report_initial_dir(selected)),
            initialfile="noark5-tilstand-og-omfang.html",
            defaultextension=".html",
            filetypes=[("HTML", "*.html"), ("Alle filer", "*.*")],
        )
        if not target:
            return

        try:
            report_path = write_job_overview_html(Path(target), selected)
        except Exception as exc:
            messagebox.showerror(
                APP_NAME,
                f"Kunne ikke lage rapporten:\n{exc}",
                parent=self.jobs_window,
            )
            return

        self.status_bar.set_status(
            f"HTML-rapport laget for {len(selected)} jobb(er): {report_path}"
        )
        try:
            webbrowser.open(report_path.resolve().as_uri())
        except Exception:
            messagebox.showinfo(
                APP_NAME,
                f"Rapporten er lagret:\n{report_path}",
                parent=self.jobs_window,
            )


def run_gui() -> None:
    from . import theme

    theme.apply_theme()
    app = WorkflowApp()
    app.mainloop()
