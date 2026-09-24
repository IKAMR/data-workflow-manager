from __future__ import annotations
import customtkinter as ctk
from . import theme
from .persistent_app_a53 import WorkflowApp as A53WorkflowApp

class WorkflowApp(A53WorkflowApp):
    """v0.1.5-a19: single-job job-list controls in the main window."""
    def __init__(self) -> None:
        super().__init__()
        self._install_main_job_list_controls()
        self._refresh_main_job_list_controls()

    def _install_main_job_list_controls(self) -> None:
        panel = self.workflow_panel
        open_button = panel.open_project_button
        save_button = panel.save_project_button
        open_button.configure(text='Åpne jobbliste', command=self._open_job_list_dialog, state='normal')
        save_button.configure(text='Lagre jobbliste', command=self._save_job_list, state='normal')
        parent = open_button.master
        self.save_job_list_as_button = ctk.CTkButton(parent, text='Lagre som...', command=self._save_job_list_as, fg_color=theme.BUTTON_BG, hover_color=theme.BUTTON_HOVER, height=28, font=theme.font(theme.SMALL_SIZE))
        self.save_job_list_as_button.grid(row=1, column=0, columnspan=2, padx=0, pady=(6, 0), sticky='ew')

    def _refresh_main_job_list_controls(self) -> None:
        if not hasattr(self, 'workflow_panel'): return
        state = 'disabled' if self.batch_running else 'normal'
        self.workflow_panel.open_project_button.configure(state=state)
        self.workflow_panel.save_project_button.configure(state=state)
        if hasattr(self, 'save_job_list_as_button'): self.save_job_list_as_button.configure(state=state)

    def _refresh_effective_work_status(self) -> None:
        super()._refresh_effective_work_status()

    def _new_job_list(self) -> bool:
        created = super()._new_job_list(); self._refresh_main_job_list_controls(); return created

    def _load_job_list_file(self, path, *, show_error: bool) -> bool:
        loaded = super()._load_job_list_file(path, show_error=show_error); self._refresh_main_job_list_controls(); return loaded

    def _write_job_list(self, path) -> bool:
        saved = super()._write_job_list(path); self._refresh_main_job_list_controls(); return saved

def run_gui() -> None:
    theme.apply_theme(); app = WorkflowApp(); app.mainloop()
