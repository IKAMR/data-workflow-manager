from __future__ import annotations

import customtkinter as ctk

from noark5_workflow.analysis.depot_review_status import get_area_status, set_area_status
from . import theme
from .depot_result_center_a17_4 import DepotResultCenterDialogA17_4


_STATUS_TEXT = {
    "approved": "+",
    "rejected": "−",
    "pending": "?",
}


class _PeriodReviewDialog(ctk.CTkToplevel):
    def __init__(self, master, *, initial_status: str, initial_comment: str, on_save):
        super().__init__(master)
        self.title("Vurder periode")
        self.geometry("560x360")
        self.minsize(500, 320)
        self.transient(master)
        self.grab_set()
        self._on_save = on_save
        self._status = ctk.StringVar(value=initial_status or "pending")

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)
        ctk.CTkLabel(
            self,
            text="Faglig vurdering av periode / ytterår",
            anchor="w",
            font=theme.font(theme.NORMAL_SIZE, weight="bold"),
        ).grid(row=0, column=0, sticky="ew", padx=16, pady=(16, 8))

        choices = ctk.CTkFrame(self, fg_color="transparent")
        choices.grid(row=1, column=0, sticky="w", padx=16, pady=(0, 8))
        for col, (value, label) in enumerate((("approved", "+ OK"), ("rejected", "− Avvik"), ("pending", "? Ikke ferdig"))):
            ctk.CTkRadioButton(choices, text=label, variable=self._status, value=value).grid(
                row=0, column=col, padx=(0, 14)
            )

        self._comment = ctk.CTkTextbox(self, wrap="word", height=150)
        self._comment.grid(row=2, column=0, sticky="nsew", padx=16, pady=(0, 10))
        if initial_comment:
            self._comment.insert("1.0", initial_comment)

        bottom = ctk.CTkFrame(self, fg_color="transparent")
        bottom.grid(row=3, column=0, sticky="ew", padx=16, pady=(0, 16))
        bottom.grid_columnconfigure(0, weight=1)
        self._error = ctk.CTkLabel(bottom, text="", anchor="w", text_color=theme.DANGER_TEXT)
        self._error.grid(row=0, column=0, sticky="ew")
        ctk.CTkButton(bottom, text="Lagre", width=90, command=self._save).grid(row=0, column=1, padx=(8, 0))
        ctk.CTkButton(
            bottom, text="Avbryt", width=90, command=self.destroy,
            fg_color=theme.BUTTON_BG, hover_color=theme.BUTTON_HOVER,
        ).grid(row=0, column=2, padx=(8, 0))

    def _save(self):
        status = self._status.get()
        comment = self._comment.get("1.0", "end").strip()
        if status == "rejected" and not comment:
            self._error.configure(text="Minus-status krever kommentar.")
            return
        try:
            self._on_save(status, comment)
        except Exception as exc:
            self._error.configure(text=str(exc))
            return
        self.destroy()


class DepotResultCenterDialogA18_1(DepotResultCenterDialogA17_4):
    """a18.1: persistent + / - / ? period review with comments per archive part."""

    def __init__(self, master, **kwargs) -> None:
        self._a181_period_review_label = None
        self._a181_period_review_button = None
        super().__init__(master, **kwargs)
        self._a181_install_period_review()
        if getattr(self, "_archive_parts", None):
            self._a181_refresh_period_review(getattr(self, "_archive_index", 0))

    def _a181_install_period_review(self) -> None:
        tabs = getattr(self, "_a10_tabs", None)
        if tabs is None:
            return
        try:
            tab = tabs.tab("Per år")
        except Exception:
            return

        panel = ctk.CTkFrame(tab)
        panel.grid(row=2, column=1, sticky="new", padx=(10, 4), pady=(6, 4))
        panel.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(
            panel, text="Faglig vurdering", anchor="w",
            font=theme.font(theme.NORMAL_SIZE, weight="bold"),
        ).grid(row=0, column=0, columnspan=3, sticky="ew", padx=12, pady=(9, 4))

        self._a181_period_review_label = ctk.CTkLabel(
            panel, text="?  Ikke vurdert", anchor="w", justify="left",
            text_color=theme.TEXT_SUB, font=theme.font(theme.SMALL_SIZE),
        )
        self._a181_period_review_label.grid(row=1, column=0, columnspan=2, sticky="ew", padx=12, pady=(2, 9))
        self._a181_period_review_button = ctk.CTkButton(
            panel, text="Vurder / kommenter…", width=150,
            command=self._a181_open_period_review,
            fg_color=theme.BUTTON_BG, hover_color=theme.BUTTON_HOVER,
        )
        self._a181_period_review_button.grid(row=1, column=2, sticky="e", padx=12, pady=(2, 9))

    def _a181_scope(self, index: int) -> tuple[str, str]:
        row = self._archive_parts[index]
        if row.get("is_virtual_selection"):
            return "", "Virtuelt utvalg"
        if row.get("is_all_archive_parts"):
            return "__ALL_ARCHIVE_PARTS__", "Alle arkivdeler"
        identity = row.get("archive_part") or {}
        scope_id = str(identity.get("system_id") or f"archive-part-{index}")
        scope_label = str(identity.get("title") or identity.get("name") or scope_id)
        return scope_id, scope_label

    def _a181_current(self, index: int) -> dict:
        report_path = getattr(self, "report_path", None)
        scope_id, _scope_label = self._a181_scope(index)
        if report_path is None or not scope_id:
            return {}
        try:
            return get_area_status(report_path, scope_id=scope_id, area="period") or {}
        except Exception:
            return {}

    def _a181_refresh_period_review(self, index: int) -> None:
        label = self._a181_period_review_label
        button = self._a181_period_review_button
        if label is None or button is None or not getattr(self, "_archive_parts", None):
            return
        scope_id, _scope_label = self._a181_scope(index)
        if not scope_id:
            label.configure(text="–  Virtuelt utvalg kan ikke vurderes som én arkivdel")
            button.configure(state="disabled")
            return
        button.configure(state="normal" if getattr(self, "report_path", None) else "disabled")
        current = self._a181_current(index)
        status = str(current.get("status") or "pending")
        symbol = _STATUS_TEXT.get(status, "?")
        comment = str(current.get("comment") or "").strip()
        text = {
            "approved": f"{symbol}  Kontrollert og vurdert OK",
            "rejected": f"{symbol}  Kontrollert – avvik / tiltak kreves",
            "pending": f"{symbol}  Ikke ferdig vurdert",
        }.get(status, "?  Ikke ferdig vurdert")
        if comment:
            text += f"  |  Kommentar: {comment}"
        label.configure(text=text)

    def _a181_open_period_review(self) -> None:
        if not getattr(self, "_archive_parts", None):
            return
        index = getattr(self, "_archive_index", 0)
        scope_id, scope_label = self._a181_scope(index)
        if not scope_id or getattr(self, "report_path", None) is None:
            return
        current = self._a181_current(index)

        def save(status: str, comment: str) -> None:
            set_area_status(
                self.report_path,
                scope_id=scope_id,
                scope_label=scope_label,
                area="period",
                status=status,
                comment=comment,
                user=dict(getattr(self, "user_identity", None) or {}),
            )
            self._a181_refresh_period_review(index)

        _PeriodReviewDialog(
            self,
            initial_status=str(current.get("status") or "pending"),
            initial_comment=str(current.get("comment") or ""),
            on_save=save,
        )

    def _show_archive_part(self, index: int) -> None:
        super()._show_archive_part(index)
        if self._a181_period_review_label is not None:
            self._a181_refresh_period_review(index)
