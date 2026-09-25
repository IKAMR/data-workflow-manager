from __future__ import annotations

import customtkinter as ctk

from . import theme
from .depot_result_views_a24 import DepotResultViewsDialogA24
from .depot_result_views_a22 import _PRIMARY_FIELDS, _SECONDARY_FIELDS, _identity


_EXPECTED_FIELDS = tuple(field_id for field_id, _label in (_PRIMARY_FIELDS + _SECONDARY_FIELDS))


def _archive_part_health(row: dict) -> dict:
    """Describe availability only; this is not a faglig status."""
    available = sum(1 for field_id in _EXPECTED_FIELDS if row.get(field_id) is not None)
    total = len(_EXPECTED_FIELDS)
    missing = total - available

    if available == total:
        label = "Alle nøkkelfelt materialisert"
        level = "complete"
    elif available == 0:
        label = "Ingen nøkkelfelt materialisert"
        level = "missing"
    else:
        label = f"{available} av {total} nøkkelfelt materialisert"
        level = "partial"

    return {
        "available": available,
        "missing": missing,
        "total": total,
        "label": label,
        "level": level,
    }


class DepotResultViewsDialogA25(DepotResultViewsDialogA24):
    """v0.1.6-a5: archive-part review optimized for fast sequential review."""

    def __init__(self, master, **kwargs):
        # Let the full a4 constructor finish first. In particular, a4 must
        # create _assessment_surface, set the Arkivdeler default tab and apply
        # native work-window chrome before a5 augments the layout.
        super().__init__(master, **kwargs)
        self._install_a5_archive_part_controls()

    def _build_archive_parts_tab(self, tab) -> None:
        # During a4/base construction only build the inherited archive-part
        # surface. a5-specific controls are installed after super().__init__()
        # has completed, avoiding partial-window construction.
        super()._build_archive_parts_tab(tab)

    def _install_a5_archive_part_controls(self) -> None:
        self._archive_health = [
            _archive_part_health(row)
            for row in getattr(self, "_archive_parts", [])
        ]

        # Enrich the existing left-hand archive-part cards from a3/a4 rather
        # than rebuilding navigation again.
        for index, button in enumerate(getattr(self, "_archive_buttons", [])):
            row = self._archive_parts[index]
            system_id, title = _identity(row, index)
            health = self._archive_health[index]
            button.configure(
                text=(
                    f"{system_id}\n"
                    f"{title}\n"
                    f"{health['available']}/{health['total']} nøkkelfelt  |  "
                    f"Mangler {health['missing']}"
                )
            )

        detail = getattr(self, "_detail", None)
        assessment = getattr(self, "_assessment_surface", None)
        if (
            detail is None
            or assessment is None
            or not getattr(self, "_archive_parts", None)
        ):
            return

        # Move the a4 assessment surface one row down and insert an explicit
        # availability/status strip. This describes data availability, not
        # acceptance of the archive part.
        assessment.grid_configure(row=5)

        self._health_frame = ctk.CTkFrame(detail)
        self._health_frame.grid(
            row=4, column=0, sticky="ew", padx=16, pady=(0, 8)
        )
        self._health_frame.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            self._health_frame,
            text="Datagrunnlag",
            anchor="w",
            font=theme.font(theme.SMALL_SIZE, weight="bold"),
        ).grid(row=0, column=0, sticky="w", padx=(12, 8), pady=9)

        self._health_label = ctk.CTkLabel(
            self._health_frame,
            text="",
            anchor="w",
            justify="left",
            text_color=theme.TEXT_SUB,
            font=theme.font(theme.SMALL_SIZE),
        )
        self._health_label.grid(row=0, column=1, sticky="ew", padx=8, pady=9)

        self._prev_button = ctk.CTkButton(
            self._health_frame,
            text="← Forrige",
            width=90,
            command=self._previous_archive_part,
            fg_color=theme.BUTTON_BG,
            hover_color=theme.BUTTON_HOVER,
        )
        self._prev_button.grid(row=0, column=2, padx=(8, 4), pady=7)

        self._next_button = ctk.CTkButton(
            self._health_frame,
            text="Neste →",
            width=90,
            command=self._next_archive_part,
            fg_color=theme.BUTTON_BG,
            hover_color=theme.BUTTON_HOVER,
        )
        self._next_button.grid(row=0, column=3, padx=(4, 10), pady=7)

        # The inherited bottom annotation row was row 5. Move it one step down
        # so both the health strip and assessment surface get proper vertical
        # space without overlap.
        for child in detail.winfo_children():
            try:
                info = child.grid_info()
            except Exception:
                continue
            if child is self._health_frame or child is assessment:
                continue
            if str(info.get("row")) == "5":
                child.grid_configure(row=6)

        detail.grid_rowconfigure(5, weight=1)
        self._update_health_strip()

    def _show_archive_part(self, index: int) -> None:
        super()._show_archive_part(index)
        if hasattr(self, "_health_label"):
            self._update_health_strip()

    def _update_health_strip(self) -> None:
        if not getattr(self, "_archive_health", None):
            return

        index = self._archive_index
        health = self._archive_health[index]
        self._health_label.configure(
            text=(
                f"{health['label']}  |  "
                f"Mangler {health['missing']}  |  "
                "Dette beskriver datatilgjengelighet, ikke faglig godkjenning."
            )
        )

        self._prev_button.configure(
            state="normal" if index > 0 else "disabled"
        )
        self._next_button.configure(
            state="normal"
            if index < len(self._archive_parts) - 1
            else "disabled"
        )

    def _previous_archive_part(self) -> None:
        if self._archive_index > 0:
            self._show_archive_part(self._archive_index - 1)

    def _next_archive_part(self) -> None:
        if self._archive_index < len(self._archive_parts) - 1:
            self._show_archive_part(self._archive_index + 1)
