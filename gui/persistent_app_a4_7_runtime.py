"""Receiving-folder action added to the current, stable DWM runtime.

v0.1.8-a2 adds a laptop workbench while retaining the same job engine.
"""
from __future__ import annotations

import customtkinter as ctk

from . import theme
from .embedded_jobs_v018_a2 import EmbeddedJobsMixin
from .persistent_app_a4_6_runtime import WorkflowApp as A46WorkflowApp


class WorkflowApp(EmbeddedJobsMixin, A46WorkflowApp):
    def __init__(self):
        super().__init__()
        self._install_receiving_folder_action()
        self._a2_install_workbench()

    def _v017_restore_job_list_window(self):
        """a2 starts with embedded Jobs, not a restored floating Jobbliste."""
        return

    def _install_receiving_folder_action(self):
        if getattr(self, 'receiving_folder_button', None) is not None:
            return
        neighbour = getattr(self, 'metadata_button', None)
        if neighbour is None:
            return
        header = neighbour.master
        grid = neighbour.grid_info()
        if not grid:
            return
        insert_at = int(grid.get('column', 0))
        # Preserve existing header actions by moving them one column right.
        move = []
        for child in header.winfo_children():
            info = child.grid_info()
            if info and int(info.get('row', 0)) == int(grid.get('row', 0)) and int(info.get('column', -1)) >= insert_at:
                move.append((int(info['column']), child))
        for column, child in sorted(move, reverse=True):
            child.grid_configure(column=column + 1)
        self.receiving_folder_button = ctk.CTkButton(
            header, text='Mottak / Ingest', width=122, height=28,
            font=theme.font(theme.SMALL_SIZE),
            fg_color=theme.BUTTON_BG, hover_color=theme.BUTTON_HOVER,
            command=self._open_receiving_folder_dialog,
        )
        self.receiving_folder_button.grid(row=int(grid.get('row', 0)), column=insert_at,
                                          padx=(2, 2), pady=8)

    def _open_receiving_folder_dialog(self):
        from .receiving_folder_dialog import open_receiving_folder_dialog
        open_receiving_folder_dialog(self)
