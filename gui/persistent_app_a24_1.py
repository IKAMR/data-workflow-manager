from __future__ import annotations

import os
from pathlib import Path
from tkinter import messagebox

from noark5_workflow.noark5_discovery import Noark5DiscoveryResult
from version import APP_NAME
from . import theme
from .jobs_window_a29 import A29JobsWindow
from .persistent_app_a23_15 import WorkflowApp as A23_15WorkflowApp


class WorkflowApp(A23_15WorkflowApp):
    """v0.1.6-a24.1: recursive discovery of Noark 5 extractions."""

    @staticmethod
    def _a241_path_key(path: Path | None) -> str:
        if path is None:
            return ""
        return os.path.normcase(os.path.abspath(os.fspath(path)))

    def _open_jobs(self) -> None:
        if self.jobs_window is not None:
            try:
                if self.jobs_window.winfo_exists():
                    if not isinstance(self.jobs_window, A29JobsWindow):
                        self.jobs_window.destroy()
                        self.jobs_window = None
                    else:
                        self.jobs_window.focus()
                        self.jobs_window.lift()
                        self.jobs_window.refresh()
                        self.jobs_window._refresh_output_rule_preview()
                        return
            except Exception:
                self.jobs_window = None

        self.jobs_window = A29JobsWindow(
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
            get_app_work_subfolder=self._get_app_work_subfolder,
            open_validation_overview=self._open_validation_overview,
            has_validation_overview=self._has_validation_overview,
            on_noark5_discovery=self._a241_apply_noark5_discovery,
        )

    def _a241_apply_noark5_discovery(self, result: Noark5DiscoveryResult) -> None:
        if not result.candidates:
            error_text = (
                f"\n\nMapper som ikke kunne leses: {len(result.errors)}"
                if result.errors else ""
            )
            messagebox.showinfo(
                APP_NAME,
                "Ingen Noark 5-uttrekk ble funnet.\n\n"
                f"Startmappe: {result.start_root}\n"
                f"Mapper kontrollert: {result.scanned_directories}"
                f"{error_text}",
                parent=self.jobs_window,
            )
            return

        existing = {
            self._a241_path_key(job.active_extraction_root)
            for job in self.jobs.jobs()
            if job.active_extraction_root is not None
        }
        new_candidates = [
            candidate
            for candidate in result.candidates
            if self._a241_path_key(candidate.root) not in existing
        ]
        duplicate_count = len(result.candidates) - len(new_candidates)

        if not new_candidates:
            messagebox.showinfo(
                APP_NAME,
                f"Fant {len(result.candidates)} Noark 5-uttrekk, men alle finnes allerede i jobblista.",
                parent=self.jobs_window,
            )
            return

        preview = "\n".join(f"- {candidate.root}" for candidate in new_candidates[:12])
        if len(new_candidates) > 12:
            preview += f"\n- ... og {len(new_candidates) - 12} til"

        details = (
            f"Fant totalt: {len(result.candidates)}\n"
            f"Nye jobber: {len(new_candidates)}\n"
            f"Allerede i jobblista: {duplicate_count}\n"
            f"Mapper kontrollert: {result.scanned_directories}"
        )
        if result.errors:
            details += f"\nMapper som ikke kunne leses: {len(result.errors)}"

        if not messagebox.askyesno(
            APP_NAME,
            "Legge de nye Noark 5-uttrekkene til i jobblista?\n\n"
            f"{details}\n\n{preview}",
            parent=self.jobs_window,
        ):
            return

        jobs_before = self.jobs.jobs()
        reusable = (
            jobs_before[0]
            if len(jobs_before) == 1 and jobs_before[0].is_unused_draft()
            else None
        )

        created = []
        for index, candidate in enumerate(new_candidates):
            root = candidate.root
            if index == 0 and reusable is not None:
                job = reusable
                job.source_root = root
                job.source_extraction = root
                job.name = root.name or job.job_id
            else:
                job = self._create_job(root)
                job.source_extraction = root

            if not job.profile_id:
                job.profile_id = "noark5"
            created.append(job)

        if reusable is not None and self.current_job is reusable:
            self._refresh_active_job_label()

        if self.job_list_path is not None:
            self._write_job_list(self.job_list_path)

        try:
            self.status_bar.set_status(
                f"La til {len(created)} Noark 5-uttrekk fra rekursivt søk"
            )
        except Exception:
            pass

        messagebox.showinfo(
            APP_NAME,
            f"{len(created)} Noark 5-uttrekk ble lagt til som jobber.",
            parent=self.jobs_window,
        )


def run_gui() -> None:
    theme.apply_theme()
    app = WorkflowApp()
    app.mainloop()
