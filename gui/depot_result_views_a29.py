from __future__ import annotations

import customtkinter as ctk

from . import theme
from .depot_result_views_a28 import DepotResultViewsDialogA28
from .depot_result_views_a22 import _PRIMARY_FIELDS, _SECONDARY_FIELDS, _identity


_FIELD_LABELS = dict(_PRIMARY_FIELDS + _SECONDARY_FIELDS)


def _missing_archive_fields(row: dict) -> list[tuple[str, str]]:
    """Return only fields whose materialized value is absent.

    Numeric zero is a valid materialized value and must not be classified as
    missing.
    """
    missing = []
    for field_id, label in _PRIMARY_FIELDS + _SECONDARY_FIELDS:
        if row.get(field_id) is None:
            missing.append((field_id, label))
    return missing


class DepotResultViewsDialogA29(DepotResultViewsDialogA28):
    """v0.1.6-a9: explain exactly which archive-part data is missing."""

    FILTER_COMPLETE = "Alle nøkkelfelt"

    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        self._install_a9_missing_data_surface()
        self._refresh_a9_archive_cards()
        self._filter_archive_parts()
        if getattr(self, "_archive_parts", None):
            self._update_a9_missing_data(self._archive_index)

    def _install_a9_missing_data_surface(self) -> None:
        archive_filter = getattr(self, "_archive_filter", None)
        if archive_filter is not None:
            try:
                archive_filter.configure(values=[self.FILTER_ALL, self.FILTER_MISSING, self.FILTER_COMPLETE])
                self._archive_filter_var.set(self.FILTER_ALL)
                archive_filter.set(self.FILTER_ALL)
            except Exception:
                pass

        detail = getattr(self, "_detail", None)
        assessment = getattr(self, "_assessment_surface", None)
        if detail is None or assessment is None:
            return

        assessment.grid_configure(row=6)
        detail.grid_rowconfigure(5, weight=0)
        detail.grid_rowconfigure(6, weight=1)

        self._missing_data_frame = ctk.CTkFrame(detail)
        self._missing_data_frame.grid(row=5, column=0, sticky="ew", padx=16, pady=(0, 8))
        self._missing_data_frame.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            self._missing_data_frame,
            text="Manglende datagrunnlag",
            anchor="w",
            font=theme.font(theme.NORMAL_SIZE, weight="bold"),
        ).grid(row=0, column=0, sticky="ew", padx=12, pady=(10, 3))

        self._missing_data_label = ctk.CTkLabel(
            self._missing_data_frame,
            text="",
            anchor="w",
            justify="left",
            wraplength=900,
            text_color=theme.TEXT_SUB,
            font=theme.font(theme.SMALL_SIZE),
        )
        self._missing_data_label.grid(row=1, column=0, sticky="ew", padx=12, pady=(0, 4))

        ctk.CTkLabel(
            self._missing_data_frame,
            text=(
                "Manglende felt betyr at verdien ikke er materialisert i "
                "depotrapporten. Det er ikke i seg selv en testfeil eller et "
                "faglig avvik."
            ),
            anchor="w",
            justify="left",
            wraplength=900,
            text_color=theme.TEXT_MUTED,
            font=theme.font(theme.SMALL_SIZE),
        ).grid(row=2, column=0, sticky="ew", padx=12, pady=(0, 10))

    def _refresh_a9_archive_cards(self) -> None:
        for index, button in enumerate(getattr(self, "_archive_buttons", [])):
            row = self._archive_parts[index]
            system_id, title = _identity(row, index)
            missing = _missing_archive_fields(row)
            if missing:
                names = ", ".join(label for _field_id, label in missing)
                missing_text = f"Mangler: {names}"
            else:
                missing_text = "Alle nøkkelfelt tilgjengelig"
            health = self._archive_health[index]
            button.configure(
                text=(
                    f"{system_id}\n{title}\n"
                    f"{health['available']}/{health['total']} nøkkelfelt\n"
                    f"{missing_text}"
                ),
                height=88,
            )

    def _show_archive_part(self, index: int) -> None:
        super()._show_archive_part(index)
        if hasattr(self, "_missing_data_label"):
            self._update_a9_missing_data(index)

    def _update_a9_missing_data(self, index: int) -> None:
        if not getattr(self, "_archive_parts", None):
            return
        row = self._archive_parts[index]
        missing = _missing_archive_fields(row)
        if not missing:
            self._missing_data_label.configure(text="Alle ni nøkkelfelt er materialisert for denne arkivdelen.")
            return
        sources = row.get("sources") or {}
        lines = []
        for field_id, label in missing:
            source = sources.get(field_id) or {}
            test_id = source.get("test_id")
            source_path = source.get("path")
            if test_id or source_path:
                evidence = f"kilde: test {test_id or '–'} · sti {source_path or '–'}"
            else:
                evidence = "ingen feltspesifikk kildereferanse materialisert"
            lines.append(f"• {label} — {evidence}")
        self._missing_data_label.configure(text="\n".join(lines))

    def _matches_archive_filter(self, index: int) -> bool:
        if not hasattr(self, "_archive_filter_var"):
            return True
        mode = self._archive_filter_var.get()
        missing = len(_missing_archive_fields(self._archive_parts[index]))
        if mode == self.FILTER_MISSING:
            return missing > 0
        if mode == self.FILTER_COMPLETE:
            return missing == 0
        return True

    def _sorted_archive_indices(self) -> list[int]:
        indices = list(range(len(getattr(self, "_archive_parts", []))))
        mode = self._archive_sort_var.get() if hasattr(self, "_archive_sort_var") else self.SORT_ORIGINAL
        if mode == self.SORT_MISSING:
            indices.sort(key=lambda index: (-len(_missing_archive_fields(self._archive_parts[index])), _identity(self._archive_parts[index], index)[1].casefold(), index))
        elif mode == self.SORT_TITLE:
            indices.sort(key=lambda index: (_identity(self._archive_parts[index], index)[1].casefold(), index))
        return indices
