"""Qt-free height policy for DWM Basic's four workflow steps.

The main window may grow/shrink only within its *current screen's usable
geometry*.  When the content is taller than that screen, the established
QScrollArea remains responsible for scrolling; never move to another monitor.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FitResult:
    window_height: int
    frame_top: int
    requires_scrolling: bool


def fit_basic_height(*, content_height: int, viewport_height: int,
                     window_height: int, minimum_height: int,
                     screen_top: int, screen_height: int, frame_top: int,
                     frame_extra: int = 0, margin: int = 8,
                     padding: int = 20) -> FitResult:
    """Return a client height and frame Y, preserving the existing X/width.

    All dimensions are Qt logical pixels.  viewport_height is the height of
    the Basic scroll area's *viewport*, excluding fixed QMainWindow chrome.
    frame_extra is titlebar/borders: frameGeometry.height - QWidget.height.
    """
    content = max(0, int(content_height))
    viewport = max(1, int(viewport_height))
    existing = max(1, int(window_height))
    minimum = max(1, int(minimum_height))
    available = max(1, int(screen_height))
    frame_extra = max(0, int(frame_extra))
    margin = max(0, int(margin))
    padding = max(0, int(padding))

    # The scroll area occupies only part of the main window.  Keep toolbar,
    # window header, status strip and frame in the calculation.
    fixed_chrome = max(0, existing - viewport)
    required = max(minimum, fixed_chrome + content + padding)
    screen_cap = max(1, available - frame_extra - 2 * margin)
    # If an unusually short screen cannot even fit Qt's fixed minimum, Qt
    # will enforce that minimum; we must not invent a larger monitor.
    target = max(minimum, min(required, screen_cap))

    upper = int(screen_top) + margin
    lower = int(screen_top) + available - margin - frame_extra - target
    top = max(upper, min(int(frame_top), lower))
    return FitResult(target, top, required > screen_cap)


def should_auto_fit(*, ready: bool, basic: bool, page_visible: bool,
                    window_visible: bool, maximized: bool, fullscreen: bool,
                    minimized: bool, manual_override: bool) -> bool:
    """Respect full-screen/maximized windows and an explicit manual resize."""
    return all((ready, basic, page_visible, window_visible,
                not maximized, not fullscreen, not minimized,
                not manual_override))


def visible_basic_layout_height(layout, available_width: int) -> int:
    """Measure a Basic step from *visible* layout items, not stretched geometry.

    QScrollArea(widgetResizable=True) expands its body to the viewport. After
    visiting the taller Run step, both body.geometry() and nested layout cache
    may still reflect the old height on the first event-loop turn. A body-wide
    sizeHint is therefore an unsafe basis for *shrinking* to Source/Work.

    This helper intentionally uses QLayoutItem duck typing (no Qt import) and
    includes vertical margins and spacing only between contributing items.
    """
    margins = layout.contentsMargins()
    inner_width = max(1, int(available_width) - margins.left() - margins.right())
    heights: list[int] = []
    for index in range(layout.count()):
        item = layout.itemAt(index)
        if item is None:
            continue
        if item.spacerItem() is not None:
            # The final expanding stretch belongs to the viewport, not to the
            # natural requested window height.
            continue
        widget = item.widget()
        if widget is not None and widget.isHidden():
            continue
        if item.isEmpty():
            continue
        height = max(0, item.sizeHint().height())
        if item.hasHeightForWidth():
            height = max(height, item.heightForWidth(inner_width))
        heights.append(height)
    spacing = max(0, layout.spacing())
    return max(0, margins.top() + margins.bottom()
               + sum(heights) + spacing * max(0, len(heights) - 1))
