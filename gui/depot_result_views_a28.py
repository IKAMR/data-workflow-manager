from __future__ import annotations

import customtkinter as ctk

from . import theme
from .depot_result_views_a27 import DepotResultViewsDialogA27
from .depot_result_views_a22 import _identity


class DepotResultViewsDialogA28(DepotResultViewsDialogA27):
    """v0.1.6-a8: sortable archive-part queue with filter-aware navigation."""

    SORT_ORIGINAL = "Original"
    SORT_MISSING = "Flest mangler"
    SORT_TITLE = "Tittel"

    def __init__(self, master, **kwargs):
        self._visible_archive_indices: list[int] = []
        super().__init__(master, **kwargs)
        self._install_a8_queue_sorting()
        self._filter_archive_parts()

    def _install_a8_queue_sorting(self) -> None:
        navigation = getattr(self, "_archive_navigation", None)
        queue_summary = getattr(self, "_queue_summary", None)
        if navigation is None or queue_summary is None:
            return

        queue = queue_summary.master
        try:
            self._archive_filter.grid_configure(pady=(0, 5))
        except Exception:
            pass

        ctk.CTkLabel(
            queue,
            text="Sorter",
            anchor="w",
            text_color=theme.TEXT_MUTED,
            font=theme.font(theme.SMALL_SIZE),
        ).grid(row=2, column=0, sticky="ew", padx=8, pady=(0, 3))

        self._archive_sort_var = ctk.StringVar(value=self.SORT_ORIGINAL)
        self._archive_sort = ctk.CTkSegmentedButton(
            queue,
            values=[
                self.SORT_ORIGINAL,
                self.SORT_MISSING,
                self.SORT_TITLE,
            ],
            variable=self._archive_sort_var,
            command=lambda _value: self._filter_archive_parts(),
            font=theme.font(theme.SMALL_SIZE),
        )
        self._archive_sort.grid(
            row=3, column=0, sticky="ew", padx=8, pady=(0, 8)
        )
        self._archive_sort.set(self.SORT_ORIGINAL)

        detail = getattr(self, "_health_frame", None)
        if detail is not None:
            self._queue_position_label = ctk.CTkLabel(
                detail,
                text="",
                anchor="e",
                text_color=theme.TEXT_MUTED,
                font=theme.font(theme.SMALL_SIZE),
            )
            self._queue_position_label.grid(
                row=1, column=0, columnspan=5,
                sticky="e", padx=10, pady=(0, 7)
            )

    def _sorted_archive_indices(self) -> list[int]:
        indices = list(range(len(getattr(self, "_archive_parts", []))))
        mode = (
            self._archive_sort_var.get()
            if hasattr(self, "_archive_sort_var")
            else self.SORT_ORIGINAL
        )

        if mode == self.SORT_MISSING and getattr(self, "_archive_health", None):
            indices.sort(
                key=lambda index: (
                    -self._archive_health[index]["missing"],
                    _identity(self._archive_parts[index], index)[1].casefold(),
                    index,
                )
            )
        elif mode == self.SORT_TITLE:
            indices.sort(
                key=lambda index: (
                    _identity(self._archive_parts[index], index)[1].casefold(),
                    index,
                )
            )
        return indices

    def _filter_archive_parts(self) -> None:
        """Apply search, availability filter and sorting as one queue operation."""
        if not getattr(self, "_archive_buttons", None):
            return

        needle = ""
        if hasattr(self, "_archive_search_var"):
            needle = self._archive_search_var.get().strip().casefold()

        ordered = self._sorted_archive_indices()
        visible: list[int] = []

        for index in ordered:
            searchable = self._archive_search_text[index]
            text_match = not needle or needle in searchable
            filter_match = self._matches_archive_filter(index)
            if text_match and filter_match:
                visible.append(index)

        self._visible_archive_indices = visible

        visible_set = set(visible)
        for index, button in enumerate(self._archive_buttons):
            if index not in visible_set:
                button.grid_remove()

        for row_no, index in enumerate(visible, start=1):
            button = self._archive_buttons[index]
            button.grid(
                row=row_no,
                column=0,
                sticky="ew",
                padx=4,
                pady=3,
            )

        no_match = getattr(self, "_archive_no_match", None)
        if no_match is not None:
            if visible:
                no_match.grid_remove()
            else:
                no_match.grid(
                    row=len(self._archive_buttons) + 4,
                    column=0,
                    sticky="ew",
                    padx=6,
                    pady=10,
                )

        mode = (
            self._archive_filter_var.get()
            if hasattr(self, "_archive_filter_var")
            else self.FILTER_ALL
        )

        # Keep current archive part if it remains in the queue. Only jump when
        # an active search/filter removes it.
        current = getattr(self, "_archive_index", 0)
        if visible and current not in visible and (
            needle or mode != self.FILTER_ALL
        ):
            self._show_archive_part(visible[0])

        self._update_a8_queue_position()

    def _clear_archive_filter(self) -> None:
        if hasattr(self, "_archive_search_var"):
            self._archive_search_var.set("")
        if hasattr(self, "_archive_filter_var"):
            self._archive_filter_var.set(self.FILTER_ALL)
            try:
                self._archive_filter.set(self.FILTER_ALL)
            except Exception:
                pass
        if hasattr(self, "_archive_sort_var"):
            self._archive_sort_var.set(self.SORT_ORIGINAL)
            try:
                self._archive_sort.set(self.SORT_ORIGINAL)
            except Exception:
                pass
        self._filter_archive_parts()

    def _show_archive_part(self, index: int) -> None:
        super()._show_archive_part(index)
        if hasattr(self, "_queue_position_label"):
            self._update_a8_queue_position()

    def _queue_position(self) -> tuple[int, int]:
        visible = getattr(self, "_visible_archive_indices", [])
        if not visible:
            return 0, 0
        try:
            position = visible.index(self._archive_index) + 1
        except ValueError:
            return 0, len(visible)
        return position, len(visible)

    def _update_a8_queue_position(self) -> None:
        label = getattr(self, "_queue_position_label", None)
        if label is None:
            return
        position, total = self._queue_position()
        if total == 0:
            label.configure(text="Ingen arkivdeler i gjeldende kø")
        elif position == 0:
            label.configure(text=f"{total} arkivdel(er) i gjeldende kø")
        else:
            label.configure(
                text=f"Køposisjon {position} av {total}"
            )

    def _previous_archive_part(self) -> None:
        visible = getattr(self, "_visible_archive_indices", [])
        if not visible:
            return
        try:
            position = visible.index(self._archive_index)
        except ValueError:
            self._show_archive_part(visible[0])
            return
        if position > 0:
            self._show_archive_part(visible[position - 1])

    def _next_archive_part(self) -> None:
        visible = getattr(self, "_visible_archive_indices", [])
        if not visible:
            return
        try:
            position = visible.index(self._archive_index)
        except ValueError:
            self._show_archive_part(visible[0])
            return
        if position < len(visible) - 1:
            self._show_archive_part(visible[position + 1])

    def _next_archive_part_with_missing_data(self) -> None:
        """Go to next visible queue item with missing data, wrapping once."""
        visible = getattr(self, "_visible_archive_indices", [])
        if not visible or not getattr(self, "_archive_health", None):
            return

        try:
            start_pos = visible.index(self._archive_index)
        except ValueError:
            start_pos = -1

        for step in range(1, len(visible) + 1):
            position = (start_pos + step) % len(visible)
            index = visible[position]
            if self._archive_health[index]["missing"] > 0:
                self._show_archive_part(index)
                return

    def _update_health_strip(self) -> None:
        super()._update_health_strip()
        if not hasattr(self, "_prev_button") or not hasattr(self, "_next_button"):
            return

        visible = getattr(self, "_visible_archive_indices", [])
        if not visible:
            self._prev_button.configure(state="disabled")
            self._next_button.configure(state="disabled")
            return

        try:
            position = visible.index(self._archive_index)
        except ValueError:
            self._prev_button.configure(state="disabled")
            self._next_button.configure(state="disabled")
            return

        self._prev_button.configure(
            state="normal" if position > 0 else "disabled"
        )
        self._next_button.configure(
            state="normal" if position < len(visible) - 1 else "disabled"
        )

    def _update_a7_queue_controls(self) -> None:
        button = getattr(self, "_next_missing_button", None)
        if button is None or not getattr(self, "_archive_health", None):
            return

        visible = getattr(self, "_visible_archive_indices", [])
        has_other_missing = any(
            index != getattr(self, "_archive_index", -1)
            and self._archive_health[index]["missing"] > 0
            for index in visible
        )
        button.configure(state="normal" if has_other_missing else "disabled")
        self._update_a8_queue_position()
