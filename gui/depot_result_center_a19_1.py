from __future__ import annotations

import customtkinter as ctk

from . import theme
from .depot_result_center_a18_9 import DepotResultCenterDialogA18_9


_BLOCKS = "▁▂▃▄▅▆▇█"


def _sparkline(values: dict[int, int] | dict[str, int], max_points: int = 24) -> str:
    """Render a compact, presentation-only year distribution from materialized counts."""
    cleaned: dict[int, int] = {}
    for year, count in (values or {}).items():
        try:
            y = int(year)
            n = max(0, int(count or 0))
        except (TypeError, ValueError):
            continue
        cleaned[y] = cleaned.get(y, 0) + n
    if not cleaned:
        return "–"

    start, end = min(cleaned), max(cleaned)
    series = [cleaned.get(year, 0) for year in range(start, end + 1)]
    if len(series) > max_points:
        bucketed: list[int] = []
        for index in range(max_points):
            lo = round(index * len(series) / max_points)
            hi = round((index + 1) * len(series) / max_points)
            hi = max(hi, lo + 1)
            bucketed.append(sum(series[lo:hi]))
        series = bucketed

    peak = max(series) if series else 0
    if peak <= 0:
        bars = _BLOCKS[0] * len(series)
    else:
        bars = "".join(
            _BLOCKS[min(len(_BLOCKS) - 1, round((value / peak) * (len(_BLOCKS) - 1)))]
            if value > 0 else "·"
            for value in series
        )
    if start == end:
        return f"{start}  {bars}"
    return f"{start}  {bars}  {end}"


def _correspondence_profile(model: dict) -> dict[str, int]:
    raw = model.get("_a19_correspondence_counts") or {}
    return {
        "incoming": int(raw.get("incoming") or 0),
        "outgoing": int(raw.get("outgoing") or 0),
        "note": int(raw.get("note") or 0),
        "other": int(raw.get("other") or 0),
    }


class DepotResultCenterDialogA19_1(DepotResultCenterDialogA18_9):
    """a19.1: compact period activity and correspondence profiles."""

    def __init__(self, master, **kwargs) -> None:
        self._a191_period_spark_labels = []
        super().__init__(master, **kwargs)
        self._a191_install_period_profiles()
        if getattr(self, "_archive_parts", None):
            self._a191_refresh_period_profiles(getattr(self, "_archive_index", 0))

    def _build_overview_tab(self, tab) -> None:
        super()._build_overview_tab(tab)

        # Insert one additive row between the DWM result distribution and the
        # existing status cards. Existing a18 layout and actions remain intact.
        for child in tab.winfo_children():
            try:
                info = child.grid_info()
                row = int(info.get("row", -1))
            except Exception:
                continue
            if row >= 3:
                try:
                    child.grid_configure(row=row + 1)
                except Exception:
                    pass
        tab.grid_rowconfigure(5, weight=1)

        profile = _correspondence_profile(self.model)
        total = sum(profile.values())
        panel = ctk.CTkFrame(tab)
        panel.grid(row=3, column=0, sticky="ew", padx=12, pady=(0, 8))
        panel.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            panel,
            text="Korrespondanseprofil – journalposter",
            anchor="w",
            font=theme.font(theme.NORMAL_SIZE, weight="bold"),
        ).grid(row=0, column=0, sticky="ew", padx=14, pady=(9, 5))

        if not total:
            ctk.CTkLabel(
                panel,
                text="Ikke tilgjengelig i materialisert kdrs.c15-kontrollgrunnlag.",
                anchor="w",
                text_color=theme.TEXT_MUTED,
                font=theme.font(theme.SMALL_SIZE),
            ).grid(row=1, column=0, sticky="ew", padx=14, pady=(0, 9))
            return

        bar = ctk.CTkFrame(panel, height=18, fg_color=theme.PANEL_BG_DARK)
        bar.grid(row=1, column=0, sticky="ew", padx=14, pady=(0, 6))
        bar.grid_propagate(False)
        bar.grid_rowconfigure(0, weight=1)
        specs = (
            ("incoming", "Inngående", theme.BLUE),
            ("outgoing", "Utgående", theme.CATEGORY_COLORS["Innhold"]),
            ("note", "Notat", theme.CATEGORY_COLORS["Metadata"]),
            ("other", "Andre", theme.TEXT_MUTED),
        )
        visible_col = 0
        for key, _label, color in specs:
            value = profile[key]
            if value <= 0:
                continue
            bar.grid_columnconfigure(visible_col, weight=value)
            segment = ctk.CTkFrame(bar, fg_color=color, corner_radius=0)
            segment.grid(row=0, column=visible_col, sticky="nsew")
            visible_col += 1

        labels = ctk.CTkFrame(panel, fg_color="transparent")
        labels.grid(row=2, column=0, sticky="ew", padx=10, pady=(0, 8))
        for col, (key, label, _color) in enumerate(specs):
            labels.grid_columnconfigure(col, weight=1, uniform="a191corrlabels")
            value = profile[key]
            percent = round((value / total) * 100) if total else 0
            ctk.CTkLabel(
                labels,
                text=f"{label}: {percent}%  ·  {self._fmt_count(value)}",
                anchor="w",
                text_color=theme.TEXT_SUB,
                font=theme.font(theme.SMALL_SIZE),
            ).grid(row=0, column=col, sticky="ew", padx=4)

    def _a191_install_period_profiles(self) -> None:
        frame = getattr(self, "_a1621_period_frame", None)
        review = getattr(self, "_a1621_period_review", None)
        if frame is None:
            return
        try:
            if review is not None:
                review.grid_configure(row=2)
        except Exception:
            pass

        profile = ctk.CTkFrame(frame, fg_color="transparent")
        profile.grid(row=1, column=0, columnspan=3, sticky="ew", pady=(2, 1))
        self._a191_period_spark_labels = []
        for col in range(3):
            profile.grid_columnconfigure(col, weight=1, uniform="a191period")
            label = ctk.CTkLabel(
                profile,
                text="–",
                anchor="w",
                text_color=theme.TEXT_SUB,
                font=theme.font(theme.SMALL_SIZE),
            )
            label.grid(row=0, column=col, sticky="ew", padx=(0 if col == 0 else 8, 8))
            self._a191_period_spark_labels.append(label)

    def _a191_refresh_period_profiles(self, index: int) -> None:
        if len(self._a191_period_spark_labels) != 3:
            return
        parts = getattr(self, "_archive_parts", None) or []
        if not (0 <= index < len(parts)):
            return
        row = parts[index]
        series = (
            self._series(row, "folder"),
            self._series(row, "journal"),
            self._series(row, "document_description"),
        )
        for widget, values in zip(self._a191_period_spark_labels, series):
            widget.configure(text=_sparkline(values))

    def _show_archive_part(self, index: int) -> None:
        super()._show_archive_part(index)
        self._a191_refresh_period_profiles(index)
