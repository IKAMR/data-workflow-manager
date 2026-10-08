from __future__ import annotations

from pathlib import Path
from tkinter import filedialog, messagebox

import customtkinter as ctk

from noark5_workflow.external_evidence.kdrs_query import (
    KdrsQueryImportError,
    import_kdrs_query_reports,
    migrate_legacy_kdrs_query_storage,
)
from noark5_workflow.external_evidence.result_bank import write_external_result_bank
from noark5_workflow.reporting.depot_metadata import migrate_metadata_storage
from version import APP_NAME

from . import theme
from .jobs_window_v017_a2 import V017A2JobsWindow
from .persistent_app_v017_a1 import WorkflowApp as V017A1WorkflowApp


class WorkflowApp(V017A1WorkflowApp):
    """v0.1.7-a2: KDRS Query evidence plus corrected DWM work placement."""

    def __init__(self) -> None:
        super().__init__()
        if self.current_job is not None:
            try:
                self._v017_a2_prepare_job_work_area(
                    self.current_job, migrate_metadata=True
                )
            except Exception:
                pass
        if self.current_job is not None:
            try:
                self._v017_a2_migrate_external_evidence(self.current_job)
            except Exception:
                pass
        self._install_kdrs_query_header_button()
        self._refresh_active_job_label()

    def _v017_a2_prepare_job_work_area(self, job, *, migrate_metadata: bool = False):
        """Resolve the effective DWM/job subfolder before job-owned data is used."""
        if job is None:
            return None
        apply_effective = getattr(self, "_apply_effective_work_operations", None)
        if callable(apply_effective):
            apply_effective(job)
        if migrate_metadata:
            return migrate_metadata_storage(job)
        return None

    def _v017_a2_migrate_external_evidence(self, job) -> None:
        if job is None or job.work_operations is None:
            return
        legacy_base = (
            Path(job.work_root) / "repository_operations"
            if job.work_root is not None
            else None
        )
        result = migrate_legacy_kdrs_query_storage(
            work_operations=job.work_operations,
            legacy_work_operations=legacy_base,
        )
        if int(result.get("migrated_imports", 0) or 0) > 0:
            write_external_result_bank(job.work_operations)

    def _install_kdrs_query_header_button(self) -> None:
        """Expose the single-job KDRS import beside Metadata in the main job view."""
        if hasattr(self, "kdrs_query_button"):
            return
        metadata = getattr(self, "metadata_button", None)
        if metadata is None:
            return
        header = metadata.master
        info = metadata.grid_info()
        column = int(info.get("column", 5)) + 1
        for child in header.winfo_children():
            if child is metadata:
                continue
            child_info = child.grid_info()
            if child_info and int(child_info.get("column", -1)) >= column:
                child.grid_configure(column=int(child_info["column"]) + 1)

        self.kdrs_query_button = ctk.CTkButton(
            header,
            text="KDRS Query",
            width=92,
            height=28,
            font=theme.font(theme.SMALL_SIZE),
            fg_color=theme.BUTTON_BG,
            hover_color=theme.BUTTON_HOVER,
            command=self._v017_a2_import_kdrs_query,
        )
        self.kdrs_query_button.grid(
            row=0, column=column, padx=(2, 2), pady=8
        )

    def _refresh_active_job_label(self) -> None:
        job = getattr(self, "current_job", None)
        if job is not None:
            try:
                self._v017_a2_prepare_job_work_area(job)
            except Exception:
                pass
        super()._refresh_active_job_label()
        button = getattr(self, "kdrs_query_button", None)
        if button is not None:
            button.configure(state="normal" if self.current_job is not None else "disabled")

    def _open_active_metadata_editor(self) -> None:
        job = self.current_job
        if job is not None:
            try:
                self._v017_a2_prepare_job_work_area(job, migrate_metadata=True)
            except Exception as exc:
                messagebox.showerror(
                    APP_NAME,
                    f"Kunne ikke klargjøre metadataområdet:\n{exc}",
                    parent=self,
                )
                return
        return super()._open_active_metadata_editor()

    def _v017_a1_edit_metadata(self, jobs) -> None:
        selected = tuple(jobs)
        try:
            for job in selected:
                self._v017_a2_prepare_job_work_area(job, migrate_metadata=True)
        except Exception as exc:
            messagebox.showerror(
                APP_NAME,
                f"Kunne ikke klargjøre metadataområdet:\n{exc}",
                parent=self.jobs_window or self,
            )
            return
        return super()._v017_a1_edit_metadata(selected)

    def _v017_a1_scan_metadata(self, jobs):
        selected = tuple(jobs)
        for job in selected:
            self._v017_a2_prepare_job_work_area(job)
        return super()._v017_a1_scan_metadata(selected)

    def _open_jobs(self) -> None:
        # Resolve the effective Work/operations path before labels/metadata are
        # rendered in the job list. This also honors a job-list subfolder rule.
        for job in self.jobs.jobs():
            try:
                self._v017_a2_prepare_job_work_area(job, migrate_metadata=True)
                self._v017_a2_migrate_external_evidence(job)
            except Exception:
                pass

        self._capture_job_operation_params(self.current_job)

        if self.jobs_window is not None:
            try:
                if self.jobs_window.winfo_exists():
                    if isinstance(self.jobs_window, V017A2JobsWindow):
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

        self.jobs_window = V017A2JobsWindow(
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

    @staticmethod
    def _v017_a2_kdrs_initial_dir(job) -> Path:
        for candidate in (
            job.work_operations,
            job.work_root,
            job.archive_root,
            job.active_extraction_root,
        ):
            if candidate is not None:
                path = Path(candidate)
                return path if path.is_dir() else path.parent
        return Path.cwd()

    def _v017_a2_import_kdrs_query(self) -> None:
        """Import KDRS Query results for the one active extraction/job."""
        job = self.current_job
        if job is None:
            messagebox.showinfo(
                APP_NAME,
                "Åpne en jobb før import av KDRS Query-resultater.",
                parent=self,
            )
            return

        try:
            self._v017_a2_prepare_job_work_area(job)
        except Exception as exc:
            messagebox.showerror(
                APP_NAME,
                f"Kunne ikke klargjøre Work - operations:\n{exc}",
                parent=self,
            )
            return
        if job.work_operations is None:
            messagebox.showerror(
                APP_NAME,
                "Jobben mangler Work - operations. Sett lagringsroller før import.",
                parent=self,
            )
            return

        paths = filedialog.askopenfilenames(
            parent=self,
            title="Velg KDRS Query-resultater: standard, U1 og/eller U2",
            initialdir=str(self._v017_a2_kdrs_initial_dir(job)),
            filetypes=[("KDRS Query tekst", "*.txt"), ("Alle filer", "*.*")],
        )
        if not paths:
            return

        try:
            legacy_base = (
                Path(job.work_root) / "repository_operations"
                if job.work_root is not None
                else None
            )
            manifest = import_kdrs_query_reports(
                paths,
                work_operations=job.work_operations,
                imported_by={
                    "mode": "manual_gui_import",
                    "job_id": str(job.job_id or ""),
                },
                legacy_work_operations=legacy_base,
            )
            bank_path = write_external_result_bank(job.work_operations)
        except KdrsQueryImportError as exc:
            messagebox.showerror(
                APP_NAME,
                f"Kunne ikke importere KDRS Query-resultatene:\n{exc}",
                parent=self,
            )
            return
        except Exception as exc:
            messagebox.showerror(
                APP_NAME,
                f"Uventet feil ved KDRS Query-import:\n{exc}",
                parent=self,
            )
            return

        types = ", ".join(
            str(value).upper() for value in manifest.get("report_types") or []
        )
        self.status_bar.set_status(
            f"KDRS Query importert for {job.job_id}: {types or '-'}"
        )
        messagebox.showinfo(
            APP_NAME,
            (
                f"KDRS Query-resultater er importert for {job.job_id}.\n\n"
                f"Typer: {types or '-'}\n"
                f"Import-ID: {manifest.get('import_id')}\n\n"
                "Originalfilene er bevart uendret under external_evidence. "
                "Normaliserte data er lagt i resultatbanken og overstyrer ikke "
                "DWM-masterresultater.\n\n"
                f"Resultatbank:\n{bank_path}"
            ),
            parent=self,
        )


def run_gui() -> None:
    theme.apply_theme()
    app = WorkflowApp()
    app.mainloop()
