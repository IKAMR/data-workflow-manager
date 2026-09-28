from __future__ import annotations

import tkinter as tk

import customtkinter as ctk

from . import theme
from .depot_result_center_a19_2 import DepotResultCenterDialogA19_2


def _clean_year_series(values) -> dict[int, int]:
    cleaned: dict[int, int] = {}
    for year, count in (values or {}).items():
        try:
            y = int(year)
            n = max(0, int(count or 0))
        except (TypeError, ValueError):
            continue
        cleaned[y] = cleaned.get(y, 0) + n
    return cleaned


def _period_profile_layout(
    values,
    assessed_start: int | None,
    assessed_end: int | None,
    total_start: int | None = None,
    total_end: int | None = None,
    *,
    near_years: int = 2,
) -> dict[str, object]:
    """Presentation-only split between the readable main period and remote outliers.

    The readable range is anchored to the extraction-level assessed period and the
    selected archive part's assessed period. One or two neighbouring years remain
    visible so boundary effects (for example a technical closing year) are not hidden.
    Remote years such as 2099 are kept as explicit detached observations.
    """
    cleaned = _clean_year_series(values)
    observed = sorted(y for y, n in cleaned.items() if n > 0)
    if not observed:
        return {
            "values": cleaned,
            "main_start": None,
            "main_end": None,
            "left_outliers": [],
            "right_outliers": [],
            "observed_start": None,
            "observed_end": None,
            "assessed_start": assessed_start,
            "assessed_end": assessed_end,
        }

    core_candidates_start = [y for y in (total_start, assessed_start) if y is not None]
    core_candidates_end = [y for y in (total_end, assessed_end) if y is not None]
    core_start = min(core_candidates_start) if core_candidates_start else observed[0]
    core_end = max(core_candidates_end) if core_candidates_end else observed[-1]
    if core_start > core_end:
        core_start, core_end = core_end, core_start

    main_candidates = [
        y for y in observed
        if core_start - near_years <= y <= core_end + near_years
    ]
    # Always retain the assessed/core years on the readable axis, even if they
    # happen to have zero observations in the selected content series.
    main_start = min([core_start] + main_candidates)
    main_end = max([core_end] + main_candidates)

    return {
        "values": cleaned,
        "main_start": main_start,
        "main_end": main_end,
        "left_outliers": [y for y in observed if y < main_start],
        "right_outliers": [y for y in observed if y > main_end],
        "observed_start": observed[0],
        "observed_end": observed[-1],
        "assessed_start": assessed_start,
        "assessed_end": assessed_end,
    }


class DepotResultCenterDialogA19_4(DepotResultCenterDialogA19_2):
    """a19.4: assessed-period markers and detached remote year observations."""

    def __init__(self, master, **kwargs) -> None:
        self._a194_period_canvases: list[tk.Canvas] = []
        self._a194_period_payloads: list[dict[str, object]] = []
        super().__init__(master, **kwargs)
        self._a194_replace_period_sparklines()
        if getattr(self, "_archive_parts", None):
            self._a194_refresh_period_profiles(getattr(self, "_archive_index", 0))

    def _a194_replace_period_sparklines(self) -> None:
        old_labels = getattr(self, "_a191_period_spark_labels", None) or []
        if len(old_labels) != 3:
            return
        parents = []
        for label in old_labels:
            try:
                parents.append(label.master)
                label.grid_remove()
            except Exception:
                parents.append(None)

        self._a194_period_canvases = []
        self._a194_period_payloads = [{}, {}, {}]
        for index, parent in enumerate(parents):
            if parent is None:
                continue
            canvas = tk.Canvas(
                parent,
                height=42,
                background=theme.PANEL_BG,
                highlightthickness=0,
                bd=0,
            )
            canvas.grid(row=0, column=0, sticky="ew", padx=(0, 8), pady=(0, 0))
            canvas.bind("<Configure>", lambda _event, i=index: self._a194_draw_period_profile(i), add="+")
            self._a194_period_canvases.append(canvas)

    def _a194_total_period(self) -> tuple[int | None, int | None]:
        parts = getattr(self, "_archive_parts", None) or []
        for index, row in enumerate(parts):
            if row.get("is_all_archive_parts"):
                start, end, _source = self._effective_period(row, index)
                return start, end
        return None, None

    def _a194_refresh_period_profiles(self, index: int) -> None:
        if len(self._a194_period_canvases) != 3:
            return
        parts = getattr(self, "_archive_parts", None) or []
        if not (0 <= index < len(parts)):
            return
        row = parts[index]
        assessed_start, assessed_end, _source = self._effective_period(row, index)
        total_start, total_end = self._a194_total_period()
        series = (
            self._series(row, "folder"),
            self._series(row, "journal"),
            self._series(row, "document_description"),
        )
        self._a194_period_payloads = [
            _period_profile_layout(values, assessed_start, assessed_end, total_start, total_end)
            for values in series
        ]
        for profile_index in range(3):
            try:
                self.after_idle(lambda i=profile_index: self._a194_draw_period_profile(i))
            except Exception:
                self._a194_draw_period_profile(profile_index)

    def _a194_draw_period_profile(self, index: int) -> None:
        if not (0 <= index < len(self._a194_period_canvases)):
            return
        if not (0 <= index < len(self._a194_period_payloads)):
            return
        canvas = self._a194_period_canvases[index]
        payload = self._a194_period_payloads[index] or {}
        try:
            canvas.delete("all")
            width = max(180, int(canvas.winfo_width()))
            height = max(38, int(canvas.winfo_height()))
        except Exception:
            return

        main_start = payload.get("main_start")
        main_end = payload.get("main_end")
        if main_start is None or main_end is None:
            canvas.create_text(4, height // 2, text="–", anchor="w", fill=theme.TEXT_MUTED)
            return

        values = payload.get("values") or {}
        left_outliers = list(payload.get("left_outliers") or [])
        right_outliers = list(payload.get("right_outliers") or [])
        assessed_start = payload.get("assessed_start")
        assessed_end = payload.get("assessed_end")

        left_zone = 34 if left_outliers else 0
        right_zone = 54 if right_outliers else 0
        gap = 12 if (left_outliers or right_outliers) else 0
        x0 = 4 + left_zone + (gap if left_outliers else 0)
        x1 = width - 4 - right_zone - (gap if right_outliers else 0)
        if x1 <= x0 + 20:
            x0, x1 = 4, width - 4

        baseline = height - 12
        top = 4
        main_years = list(range(int(main_start), int(main_end) + 1))
        all_years = main_years + left_outliers + right_outliers
        peak = max((int(values.get(y, 0) or 0) for y in all_years), default=0)
        peak = max(1, peak)

        canvas.create_line(x0, baseline, x1, baseline, fill=theme.CARD_BORDER, width=1)
        slot = max(1.0, (x1 - x0) / max(1, len(main_years)))
        bar_width = max(1.0, min(10.0, slot * 0.72))
        for pos, year in enumerate(main_years):
            value = int(values.get(year, 0) or 0)
            if value <= 0:
                continue
            cx = x0 + (pos + 0.5) * slot
            bar_h = max(2.0, (value / peak) * (baseline - top))
            canvas.create_rectangle(
                cx - bar_width / 2,
                baseline - bar_h,
                cx + bar_width / 2,
                baseline,
                fill=theme.TEXT_SUB,
                outline="",
            )

        # Thin assessed-period markers are independent of the observed bars.
        def marker_x(year):
            if year is None or year < main_start or year > main_end:
                return None
            return x0 + (int(year) - int(main_start) + 0.5) * slot

        for year in (assessed_start, assessed_end):
            mx = marker_x(year)
            if mx is not None:
                canvas.create_line(mx, top, mx, baseline + 2, fill=theme.BLUE, width=2)

        # Remote observations remain visible without compressing the useful axis.
        if left_outliers:
            canvas.create_text(2, baseline - 13, text="…", anchor="w", fill=theme.TEXT_MUTED)
            year = min(left_outliers)
            value = int(values.get(year, 0) or 0)
            bar_h = max(2.0, (value / peak) * (baseline - top))
            canvas.create_rectangle(18, baseline - bar_h, 24, baseline, fill=theme.TEXT_MUTED, outline="")
            canvas.create_text(2, baseline + 1, text=str(year), anchor="nw", fill=theme.TEXT_MUTED)
        if right_outliers:
            canvas.create_text(x1 + 3, baseline - 13, text="…", anchor="w", fill=theme.TEXT_MUTED)
            # Prefer the strongest remote year as the representative narrow bar,
            # while retaining the actual year label rather than hiding the outlier.
            year = max(right_outliers, key=lambda y: int(values.get(y, 0) or 0))
            value = int(values.get(year, 0) or 0)
            bar_h = max(2.0, (value / peak) * (baseline - top))
            ox = min(width - 18, x1 + 24)
            canvas.create_rectangle(ox, baseline - bar_h, ox + 6, baseline, fill=theme.TEXT_MUTED, outline="")
            canvas.create_text(x1 + 3, baseline + 1, text=str(year), anchor="nw", fill=theme.TEXT_MUTED)

        canvas.create_text(x0, baseline + 1, text=str(main_start), anchor="nw", fill=theme.TEXT_MUTED)
        canvas.create_text(x1, baseline + 1, text=str(main_end), anchor="ne", fill=theme.TEXT_MUTED)

    def _show_archive_part(self, index: int) -> None:
        super()._show_archive_part(index)
        if getattr(self, "_a194_period_canvases", None):
            self._a194_refresh_period_profiles(index)

    def _save_reviewed_period(self) -> None:
        super()._save_reviewed_period()
        # The blue boundary markers are a live presentation of the saved depot
        # assessment, so they must move immediately when the assessed years move.
        if getattr(self, "_a194_period_canvases", None) and getattr(self, "_archive_parts", None):
            self._a194_refresh_period_profiles(getattr(self, "_archive_index", 0))
