from __future__ import annotations

import customtkinter as ctk

from . import theme
from .jobs_window_v017_a1 import V017A1JobsWindow


class V017A2JobsWindow(V017A1JobsWindow):
    """Selected-job reporting and read-only evidence inventory.

    KDRS Query *import* stays in the active JOBB window. This button only
    inspects existing imports for selected jobs (or all if none are selected).
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        parent = self.report_selected_button.master
        self.evidence_status_button = ctk.CTkButton(
            parent, text='Evidensstatus', width=112,
            fg_color=theme.BUTTON_BG,
            hover_color=theme.BUTTON_HOVER,
            command=self._open_evidence_status,
        )
        self.evidence_status_button.pack(
            side='left', padx=(0, 6), before=self.report_selected_button,
        )

    def _open_evidence_status(self):
        """Read-only: no implicit source migration, import or XPath rerun."""
        from .external_evidence_status_a18 import open_evidence_status_dialog
        selected = tuple(self._selected_for_action())
        chosen = selected if selected else tuple(self.batch.jobs())
        if chosen:
            open_evidence_status_dialog(self, chosen, all_jobs=not bool(selected))
