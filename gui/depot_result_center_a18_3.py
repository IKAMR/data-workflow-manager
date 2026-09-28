from __future__ import annotations

import customtkinter as ctk

from . import theme
from .depot_result_center_a18_2 import DepotResultCenterDialogA18_2


class DepotResultCenterDialogA18_3(DepotResultCenterDialogA18_2):
    """a18.3: keep period review controls visible inside the reviewed-period panel."""

    def __init__(self, master, **kwargs) -> None:
        self._a183_inline_review_label = None
        self._a183_inline_review_frame = None
        super().__init__(master, **kwargs)
        self._a183_integrate_review_controls()
        if getattr(self, "_archive_parts", None):
            self._a181_refresh_period_review(getattr(self, "_archive_index", 0))

    def _a183_integrate_review_controls(self) -> None:
        """Move the a18 review surface into the already visible period panel.

        a18.1/a18.2 placed a separate review frame below the reviewed-period panel.
        On ordinary work screens that extra row could fall below the visible tab area.
        Keep the old widgets alive for compatibility, but hide their parent and expose
        the same actions in the reviewed-period panel without adding vertical height.
        """
        panel = getattr(self, "_a1616_period_panel", None)
        legacy_button = getattr(self, "_a181_period_review_button", None)
        if panel is None or legacy_button is None:
            return

        # Hide the separate a18.1/a18.2 review section that was clipped below screen.
        try:
            legacy_panel = legacy_button.master
            legacy_panel.grid_remove()
        except Exception:
            pass

        # Compact the existing status line slightly to make room for one inline row.
        status = getattr(self, "_a1616_period_status", None)
        if status is not None:
            try:
                status.grid_configure(pady=(0, 3))
            except Exception:
                pass

        frame = ctk.CTkFrame(panel, fg_color="transparent")
        frame.grid(row=4, column=0, columnspan=5, sticky="ew", padx=12, pady=(0, 8))
        frame.grid_columnconfigure(5, weight=1)
        self._a183_inline_review_frame = frame

        ctk.CTkLabel(
            frame,
            text="Periodevurdering:",
            anchor="w",
            text_color=theme.TEXT_SUB,
            font=theme.font(theme.SMALL_SIZE, weight="bold"),
        ).grid(row=0, column=0, sticky="w", padx=(0, 8))

        ctk.CTkButton(
            frame,
            text="+",
            width=40,
            command=lambda: self._a182_quick_set("approved"),
        ).grid(row=0, column=1, padx=(0, 5))
        ctk.CTkButton(
            frame,
            text="−",
            width=40,
            command=lambda: self._a182_quick_set("rejected"),
            fg_color=theme.BUTTON_BG,
            hover_color=theme.BUTTON_HOVER,
        ).grid(row=0, column=2, padx=(0, 5))
        ctk.CTkButton(
            frame,
            text="?",
            width=40,
            command=lambda: self._a182_quick_set("pending"),
            fg_color=theme.BUTTON_BG,
            hover_color=theme.BUTTON_HOVER,
        ).grid(row=0, column=3, padx=(0, 8))
        ctk.CTkButton(
            frame,
            text="Kommentar…",
            width=100,
            command=self._a181_open_period_review,
            fg_color=theme.BUTTON_BG,
            hover_color=theme.BUTTON_HOVER,
        ).grid(row=0, column=4, padx=(0, 10))

        self._a183_inline_review_label = ctk.CTkLabel(
            frame,
            text="?  Ikke ferdig vurdert",
            anchor="w",
            justify="left",
            text_color=theme.TEXT_MUTED,
            font=theme.font(theme.SMALL_SIZE),
        )
        self._a183_inline_review_label.grid(row=0, column=5, sticky="ew")

        self._a183_refresh_inline_review(getattr(self, "_archive_index", 0))

    def _a183_refresh_inline_review(self, index: int) -> None:
        label = self._a183_inline_review_label
        frame = self._a183_inline_review_frame
        if label is None or frame is None or not getattr(self, "_archive_parts", None):
            return

        scope_id, _scope_label = self._a181_scope(index)
        enabled = bool(scope_id and getattr(self, "report_path", None))
        for child in frame.winfo_children():
            if isinstance(child, ctk.CTkButton):
                try:
                    child.configure(state="normal" if enabled else "disabled")
                except Exception:
                    pass

        if not scope_id:
            label.configure(text="–  Virtuelt utvalg kan ikke vurderes som én arkivdel")
            return

        current = self._a181_current(index)
        status = str(current.get("status") or "pending")
        comment = str(current.get("comment") or "").strip()
        text = {
            "approved": "+  Kontrollert og vurdert OK",
            "rejected": "−  Avvik / tiltak kreves",
            "pending": "?  Ikke ferdig vurdert",
        }.get(status, "?  Ikke ferdig vurdert")
        if comment:
            text += f"  |  Kommentar: {comment}"
        label.configure(text=text)

    def _a181_refresh_period_review(self, index: int) -> None:
        super()._a181_refresh_period_review(index)
        if getattr(self, "_a183_inline_review_label", None) is not None:
            self._a183_refresh_inline_review(index)

    def _show_archive_part(self, index: int) -> None:
        super()._show_archive_part(index)
        if getattr(self, "_a183_inline_review_label", None) is not None:
            self._a183_refresh_inline_review(index)
