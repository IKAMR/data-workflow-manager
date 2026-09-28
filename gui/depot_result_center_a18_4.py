from __future__ import annotations

import customtkinter as ctk

from . import theme
from .depot_result_center_a18_3 import DepotResultCenterDialogA18_3


class DepotResultCenterDialogA18_4(DepotResultCenterDialogA18_3):
    """a18.4: place period-review actions on the always-visible period action row."""

    def __init__(self, master, **kwargs) -> None:
        self._a184_action_frame = None
        self._a184_status_label = None
        super().__init__(master, **kwargs)
        self._a184_install_visible_actions()
        if getattr(self, "_archive_parts", None):
            self._a184_refresh_visible_actions(getattr(self, "_archive_index", 0))

    def _a184_install_visible_actions(self) -> None:
        panel = getattr(self, "_a1616_period_panel", None)
        if panel is None:
            return

        # a18.3's extra row is still too low on common 1080p work screens.
        # Remove it and put the review actions on the same row as Bruk forslag/Lagre.
        old_inline = getattr(self, "_a183_inline_review_frame", None)
        if old_inline is not None:
            try:
                old_inline.grid_remove()
            except Exception:
                pass

        actions = None
        try:
            for child in panel.winfo_children():
                info = child.grid_info()
                if int(info.get("row", -1)) == 1 and int(info.get("column", -1)) == 4:
                    actions = child
                    break
        except Exception:
            actions = None
        if actions is None:
            return

        self._a184_action_frame = actions

        # Move inherited period buttons to the right, leaving fixed visible space
        # for + / - / ? / comment on the very same row.
        try:
            inherited = list(actions.winfo_children())
            if len(inherited) >= 1:
                inherited[0].grid_configure(row=0, column=5, padx=(12, 6))
            if len(inherited) >= 2:
                inherited[1].grid_configure(row=0, column=6, padx=(0, 0))
        except Exception:
            pass

        ctk.CTkLabel(
            actions,
            text="Vurdering:",
            anchor="w",
            text_color=theme.TEXT_SUB,
            font=theme.font(theme.SMALL_SIZE, weight="bold"),
        ).grid(row=0, column=0, padx=(0, 6))
        ctk.CTkButton(
            actions, text="+", width=34,
            command=lambda: self._a182_quick_set("approved"),
        ).grid(row=0, column=1, padx=(0, 4))
        ctk.CTkButton(
            actions, text="−", width=34,
            command=lambda: self._a182_quick_set("rejected"),
            fg_color=theme.BUTTON_BG, hover_color=theme.BUTTON_HOVER,
        ).grid(row=0, column=2, padx=(0, 4))
        ctk.CTkButton(
            actions, text="?", width=34,
            command=lambda: self._a182_quick_set("pending"),
            fg_color=theme.BUTTON_BG, hover_color=theme.BUTTON_HOVER,
        ).grid(row=0, column=3, padx=(0, 4))
        ctk.CTkButton(
            actions, text="Kommentar…", width=92,
            command=self._a181_open_period_review,
            fg_color=theme.BUTTON_BG, hover_color=theme.BUTTON_HOVER,
        ).grid(row=0, column=4, padx=(0, 0))

        self._a184_status_label = getattr(self, "_a1616_period_status", None)

    def _a184_refresh_visible_actions(self, index: int) -> None:
        actions = self._a184_action_frame
        if actions is None or not getattr(self, "_archive_parts", None):
            return
        scope_id, _scope_label = self._a181_scope(index)
        enabled = bool(scope_id and getattr(self, "report_path", None))
        try:
            children = list(actions.winfo_children())
            # Only the four review buttons are columns 1..4. Period buttons remain usable.
            for child in children:
                if not isinstance(child, ctk.CTkButton):
                    continue
                col = int(child.grid_info().get("column", -1))
                if 1 <= col <= 4:
                    child.configure(state="normal" if enabled else "disabled")
        except Exception:
            pass

    def _a181_refresh_period_review(self, index: int) -> None:
        super()._a181_refresh_period_review(index)
        if getattr(self, "_a184_action_frame", None) is not None:
            self._a184_refresh_visible_actions(index)

    def _show_archive_part(self, index: int) -> None:
        super()._show_archive_part(index)
        if getattr(self, "_a184_action_frame", None) is not None:
            self._a184_refresh_visible_actions(index)
