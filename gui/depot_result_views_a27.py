from __future__ import annotations

import customtkinter as ctk

from . import theme
from .depot_result_views_a26 import DepotResultViewsDialogA26


class DepotResultViewsDialogA27(DepotResultViewsDialogA26):
    """v0.1.6-a7: archive-part work queue based on data availability only."""

    FILTER_ALL = "Alle"
    FILTER_MISSING = "Mangler data"
    FILTER_COMPLETE = "Komplett"

    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        self._install_a7_archive_part_queue()

    def _install_a7_archive_part_queue(self) -> None:
        if not getattr(self, "_archive_parts", None):
            return
        if not getattr(self, "_archive_buttons", None):
            return
        if not getattr(self, "_archive_health", None):
            return
        navigation = getattr(self, "_archive_navigation", None)
        if navigation is None:
            return

        # Move inherited archive-part buttons down one row. Row 0 becomes a
        # compact queue/filter header without rebuilding the a3-a6 navigation.
        for index, button in enumerate(self._archive_buttons):
            button.grid_configure(row=index + 1)

        queue = ctk.CTkFrame(navigation)
        queue.grid(row=0, column=0, sticky="ew", padx=4, pady=(3, 8))
        queue.grid_columnconfigure(0, weight=1)

        complete = sum(
            1 for health in self._archive_health
            if health["missing"] == 0
        )
        incomplete = len(self._archive_health) - complete

        self._queue_summary = ctk.CTkLabel(
            queue,
            text=(
                f"Datagrunnlag: {complete} komplett  |  "
                f"{incomplete} med manglende nøkkelfelt"
            ),
            anchor="w",
            justify="left",
            text_color=theme.TEXT_MUTED,
            font=theme.font(theme.SMALL_SIZE),
        )
        self._queue_summary.grid(
            row=0, column=0, sticky="ew", padx=8, pady=(8, 5)
        )

        self._archive_filter_var = ctk.StringVar(value=self.FILTER_ALL)
        self._archive_filter = ctk.CTkSegmentedButton(
            queue,
            values=[
                self.FILTER_ALL,
                self.FILTER_MISSING,
                self.FILTER_COMPLETE,
            ],
            variable=self._archive_filter_var,
            command=lambda _value: self._filter_archive_parts(),
            font=theme.font(theme.SMALL_SIZE),
        )
        self._archive_filter.grid(
            row=1, column=0, sticky="ew", padx=8, pady=(0, 8)
        )
        self._archive_filter.set(self.FILTER_ALL)

        health_frame = getattr(self, "_health_frame", None)
        if health_frame is not None:
            self._next_missing_button = ctk.CTkButton(
                health_frame,
                text="Neste med mangler",
                width=130,
                command=self._next_archive_part_with_missing_data,
                fg_color=theme.BUTTON_BG,
                hover_color=theme.BUTTON_HOVER,
            )
            self._next_missing_button.grid(
                row=0, column=4, padx=(4, 10), pady=7
            )

        self._filter_archive_parts()
        self._update_a7_queue_controls()

    def _matches_archive_filter(self, index: int) -> bool:
        if not hasattr(self, "_archive_filter_var"):
            return True
        mode = self._archive_filter_var.get()
        missing = self._archive_health[index]["missing"]

        if mode == self.FILTER_MISSING:
            return missing > 0
        if mode == self.FILTER_COMPLETE:
            return missing == 0
        return True

    def _filter_archive_parts(self) -> None:
        """Combine inherited free-text search with the a7 availability filter."""
        if not getattr(self, "_archive_buttons", None):
            return

        needle = ""
        if hasattr(self, "_archive_search_var"):
            needle = self._archive_search_var.get().strip().casefold()

        visible = 0
        first_match = None

        for index, (button, searchable) in enumerate(
            zip(self._archive_buttons, self._archive_search_text)
        ):
            text_match = not needle or needle in searchable
            filter_match = self._matches_archive_filter(index)
            match = text_match and filter_match

            if match:
                button.grid()
                visible += 1
                if first_match is None:
                    first_match = index
            else:
                button.grid_remove()

        no_match = getattr(self, "_archive_no_match", None)
        if no_match is not None:
            if visible:
                no_match.grid_remove()
            else:
                no_match.grid(
                    row=len(self._archive_buttons) + 2,
                    column=0,
                    sticky="ew",
                    padx=6,
                    pady=10,
                )

        # When the user actively searches/filters, show the first matching part
        # immediately. Plain construction with "Alle" keeps the inherited first
        # archive part.
        mode = (
            self._archive_filter_var.get()
            if hasattr(self, "_archive_filter_var")
            else self.FILTER_ALL
        )
        if first_match is not None and (needle or mode != self.FILTER_ALL):
            self._show_archive_part(first_match)

    def _clear_archive_filter(self) -> None:
        # "Nullstill" now resets both search text and availability filtering.
        if hasattr(self, "_archive_search_var"):
            self._archive_search_var.set("")
        if hasattr(self, "_archive_filter_var"):
            self._archive_filter_var.set(self.FILTER_ALL)
            try:
                self._archive_filter.set(self.FILTER_ALL)
            except Exception:
                pass
        self._filter_archive_parts()

    def _show_archive_part(self, index: int) -> None:
        super()._show_archive_part(index)
        if hasattr(self, "_next_missing_button"):
            self._update_a7_queue_controls()

    def _next_archive_part_with_missing_data(self) -> None:
        if not getattr(self, "_archive_health", None):
            return

        total = len(self._archive_health)
        if total <= 1:
            return

        start = self._archive_index
        for step in range(1, total + 1):
            index = (start + step) % total
            if self._archive_health[index]["missing"] > 0:
                self._show_archive_part(index)
                return

    def _update_a7_queue_controls(self) -> None:
        button = getattr(self, "_next_missing_button", None)
        if button is None or not getattr(self, "_archive_health", None):
            return

        current = self._archive_index
        has_other_missing = any(
            index != current and health["missing"] > 0
            for index, health in enumerate(self._archive_health)
        )
        button.configure(state="normal" if has_other_missing else "disabled")
