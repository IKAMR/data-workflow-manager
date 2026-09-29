from __future__ import annotations

import tkinter as tk

from . import theme
from .depot_result_center_a21_12 import DepotResultCenterDialogA21_12
from .depot_result_views_a29 import _missing_archive_fields


class DepotResultCenterDialogA21_13(DepotResultCenterDialogA21_12):
    """a21.13: show the full archive-part title on hover when the card is shortened."""

    def __init__(self, master, **kwargs) -> None:
        self._a2113_tooltip = None
        super().__init__(master, **kwargs)
        self._a2113_refresh_archive_queue()

    def _a2113_hide_tooltip(self, _event=None) -> None:
        tooltip = getattr(self, "_a2113_tooltip", None)
        self._a2113_tooltip = None
        if tooltip is not None:
            try:
                tooltip.destroy()
            except Exception:
                pass

    def _a2113_show_tooltip(self, event, text: str) -> None:
        self._a2113_hide_tooltip()
        if not text:
            return

        tooltip = tk.Toplevel(self)
        self._a2113_tooltip = tooltip
        tooltip.wm_overrideredirect(True)
        try:
            tooltip.attributes("-topmost", True)
        except Exception:
            pass

        label = tk.Label(
            tooltip,
            text=text,
            justify="left",
            anchor="w",
            padx=10,
            pady=7,
            relief="solid",
            borderwidth=1,
            wraplength=560,
        )
        label.pack()
        tooltip.wm_geometry(f"+{event.x_root + 14}+{event.y_root + 14}")

    def _a2113_bind_full_title(self, button, raw_title: str, shown_title: str) -> None:
        # Hover help is only needed where the queue has actually shortened the title.
        if raw_title.strip() != shown_title.strip():
            button.bind(
                "<Enter>",
                lambda event, text=raw_title: self._a2113_show_tooltip(event, text),
            )
            button.bind("<Leave>", self._a2113_hide_tooltip)
        else:
            button.unbind("<Enter>")
            button.unbind("<Leave>")

    def _a2113_refresh_archive_queue(self) -> None:
        parts = list(getattr(self, "_archive_parts", []) or [])
        buttons = list(getattr(self, "_archive_buttons", []) or [])
        if not parts or not buttons:
            return

        for index, button in enumerate(buttons):
            if index >= len(parts):
                break

            row = parts[index]
            missing = _missing_archive_fields(row)
            status = "Komplett data" if not missing else f"Mangler data: {len(missing)}"
            period = self._a2111_observed_period(row)
            period_line = f"({period})" if period else ""

            if row.get("is_all_archive_parts"):
                raw_title = "Alle arkivdeler"
                title = raw_title
            else:
                _system_id, raw_title = self._a2110_identity(row, index)
                raw_title = " ".join(str(raw_title or "Uten tittel").split())
                title = self._a2112_title(raw_title)

            lines = [title]
            if period_line:
                lines.append(period_line)
            lines.append(status)

            try:
                button.configure(
                    text="\n".join(lines),
                    height=72,
                    anchor="center",
                    font=theme.font(theme.SMALL_SIZE),
                )
                self._a2113_bind_full_title(button, raw_title, title)
            except Exception:
                continue

        self._a217_mark_selected_archive()

    def _show_archive_part(self, index: int) -> None:
        self._a2113_hide_tooltip()
        super()._show_archive_part(index)
        self._a2113_refresh_archive_queue()
