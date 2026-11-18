"""Qt-free, bounded sizing decisions for Advanced-mode desktop panels.

Values are logical Qt pixels, not physical monitor pixels. The controller may
request dock sizes within the existing window; it must never resize the native
main window to satisfy contents or alter Source/Work/job data.
"""
from __future__ import annotations

from dataclasses import dataclass
import json


@dataclass(frozen=True)
class AdvancedLayout:
    left_width: int
    activity_height: int
    system_width: int
    activity_width: int
    job_name_width: int
    workflow_name_width: int
    history_name_width: int
    history_upper_height: int
    job_upper_height: int


def _bounded(value: int, minimum: int, maximum: int) -> int:
    return max(minimum, min(int(value), max(minimum, int(maximum))))


def plan_advanced_layout(
    width: int, height: int, *, job_name_px: int = 240,
    operation_name_px: int = 230, history_name_px: int = 230,
    job_count: int = 0, history_count: int = 0,
    system_visible: bool = True,
) -> AdvancedLayout:
    """Propose readable columns without consuming the whole content area.

    The layout remains usable on a smaller monitor by allowing table scrolling.
    A window is NEVER enlarged to fit longer strings.
    """
    w = max(1, int(width))
    h = max(1, int(height))
    job_name = _bounded(job_name_px + 26, 245, 510)
    workflow_name = _bounded(operation_name_px + 25, 270, 500)
    history_name = _bounded(history_name_px + 26, 220, 460)
    # Other job columns (ID, status, Work, percent) and internal margins
    # require about 195 logical pixels beside the name column.
    wanted_left = max(355, job_name + 195, workflow_name + 145)
    min_right = min(w - 260, max(385, round(w * 0.50)))
    max_left = max(250, w - max(300, min_right))
    left = _bounded(wanted_left, 250, min(580, max_left))
    usable_right = max(1, w - left - 26)
    if system_visible:
        system = _bounded(round(usable_right * 0.28), 150, 325)
        if usable_right - system < 305:
            system = max(110, usable_right - 305)
    else:
        system = 0
    activity_width = max(1, usable_right - system)
    bottom = _bounded(round(h * 0.61), 200, max(200, h - 305))
    # Upper part of the activity splitter contains chronological deljobbs;
    # lower part contains stored job status/log text. Both must stay usable.
    desired_history = min(max(190, history_count * 18 + 46), round(bottom * 0.55))
    history_upper = _bounded(desired_history, 160, max(160, bottom - 170))
    upper_jobs = _bounded(max(245, 180 + job_count * 25), 225, max(225, round(h * 0.47)))
    return AdvancedLayout(left, bottom, system, activity_width, job_name,
                          workflow_name, history_name, history_upper, upper_jobs)


def severe_panel_clipping(*, left_width: int, activity_height: int,
                          activity_width: int, system_width: int = 0,
                          system_visible: bool = False) -> bool:
    """Repair obviously unusable saved panes, even with user preferences."""
    return (left_width < 260 or activity_height < 190 or activity_width < 260
            or (system_visible and system_width < 95))


def restored_splitter_sizes(text: str, available: int) -> tuple[int, int] | None:
    """Reapply a user-set ratio within current screen/DPI limits.

    Reject empty/invalid ratios, and keep both panes readable on a short screen.
    """
    try:
        parts = json.loads(str(text))
        if not isinstance(parts, list) or len(parts) != 2:
            return None
        a, b = int(parts[0]), int(parts[1])
        if a <= 0 or b <= 0:
            return None
    except (TypeError, ValueError, OverflowError):
        return None
    space = int(available)
    if space < 320:
        return None
    first = _bounded(round(space * a / (a + b)), 140, space - 140)
    return (first, space - first)
