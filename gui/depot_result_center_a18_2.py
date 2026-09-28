from __future__ import annotations

import customtkinter as ctk

from noark5_workflow.analysis.depot_review_status import set_area_status
from . import theme
from .depot_result_center_a18_1 import DepotResultCenterDialogA18_1, _PeriodReviewDialog


_CARD_MARKERS = {
    "approved": "+",
    "rejected": "−",
    "pending": "?",
}


class DepotResultCenterDialogA18_2(DepotResultCenterDialogA18_1):
    """a18.2: quick period review controls and visible archive-card status."""

    def __init__(self, master, **kwargs) -> None:
        self._a182_quick_frame = None
        super().__init__(master, **kwargs)
        self._a182_install_quick_review()
        self._a182_refresh_all_card_statuses()
        if getattr(self, "_archive_parts", None):
            self._a182_refresh_quick_review(getattr(self, "_archive_index", 0))

    def _a182_install_quick_review(self) -> None:
        button = getattr(self, "_a181_period_review_button", None)
        if button is None:
            return
        panel = button.master
        frame = ctk.CTkFrame(panel, fg_color="transparent")
        frame.grid(row=2, column=0, columnspan=3, sticky="ew", padx=12, pady=(0, 10))
        frame.grid_columnconfigure(4, weight=1)
        ctk.CTkLabel(
            frame,
            text="Hurtigvurdering:",
            anchor="w",
            text_color=theme.TEXT_SUB,
            font=theme.font(theme.SMALL_SIZE),
        ).grid(row=0, column=0, sticky="w", padx=(0, 8))
        ctk.CTkButton(
            frame,
            text="+",
            width=42,
            command=lambda: self._a182_quick_set("approved"),
        ).grid(row=0, column=1, padx=(0, 6))
        ctk.CTkButton(
            frame,
            text="−",
            width=42,
            command=lambda: self._a182_quick_set("rejected"),
            fg_color=theme.BUTTON_BG,
            hover_color=theme.BUTTON_HOVER,
        ).grid(row=0, column=2, padx=(0, 6))
        ctk.CTkButton(
            frame,
            text="?",
            width=42,
            command=lambda: self._a182_quick_set("pending"),
            fg_color=theme.BUTTON_BG,
            hover_color=theme.BUTTON_HOVER,
        ).grid(row=0, column=3, padx=(0, 10))
        ctk.CTkLabel(
            frame,
            text="+ godkjent   − avvik (kommentar kreves)   ? ikke ferdig",
            anchor="w",
            text_color=theme.TEXT_MUTED,
            font=theme.font(theme.SMALL_SIZE),
        ).grid(row=0, column=4, sticky="w")
        self._a182_quick_frame = frame

    def _a182_save_status(self, index: int, status: str, comment: str) -> None:
        scope_id, scope_label = self._a181_scope(index)
        if not scope_id or getattr(self, "report_path", None) is None:
            return
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
        self._a182_refresh_all_card_statuses()

    def _a182_quick_set(self, status: str) -> None:
        if not getattr(self, "_archive_parts", None):
            return
        index = getattr(self, "_archive_index", 0)
        scope_id, _scope_label = self._a181_scope(index)
        if not scope_id or getattr(self, "report_path", None) is None:
            return

        current = self._a181_current(index)
        current_comment = str(current.get("comment") or "")
        if status == "rejected":
            def save_rejected(_status: str, comment: str) -> None:
                self._a182_save_status(index, "rejected", comment)

            dialog = _PeriodReviewDialog(
                self,
                initial_status="rejected",
                initial_comment=current_comment,
                on_save=save_rejected,
            )
            try:
                dialog._status.set("rejected")
            except Exception:
                pass
            return

        self._a182_save_status(index, status, current_comment if status == "approved" else "")

    def _a182_refresh_quick_review(self, index: int) -> None:
        frame = self._a182_quick_frame
        if frame is None or not getattr(self, "_archive_parts", None):
            return
        scope_id, _scope_label = self._a181_scope(index)
        state = "normal" if scope_id and getattr(self, "report_path", None) else "disabled"
        for child in frame.winfo_children():
            if isinstance(child, ctk.CTkButton):
                child.configure(state=state)

    @staticmethod
    def _a182_card_text_with_status(text: str, marker: str) -> str:
        lines = [line for line in str(text or "").splitlines() if not line.startswith("Periodevurdering:")]
        lines.append(f"Periodevurdering: {marker}")
        return "\n".join(lines)

    def _a182_refresh_all_card_statuses(self) -> None:
        buttons = list(getattr(self, "_archive_buttons", []) or [])
        parts = list(getattr(self, "_archive_parts", []) or [])
        if not buttons or not parts:
            return
        for index, button in enumerate(buttons):
            if index >= len(parts):
                break
            current = self._a181_current(index)
            status = str(current.get("status") or "pending")
            marker = _CARD_MARKERS.get(status, "?")
            try:
                text = button.cget("text")
                button.configure(text=self._a182_card_text_with_status(text, marker))
            except Exception:
                continue

    def _a181_refresh_period_review(self, index: int) -> None:
        super()._a181_refresh_period_review(index)
        if getattr(self, "_a182_quick_frame", None) is not None:
            self._a182_refresh_quick_review(index)
            self._a182_refresh_all_card_statuses()

    def _show_archive_part(self, index: int) -> None:
        super()._show_archive_part(index)
        if getattr(self, "_a182_quick_frame", None) is not None:
            self._a182_refresh_quick_review(index)
            self._a182_refresh_all_card_statuses()
