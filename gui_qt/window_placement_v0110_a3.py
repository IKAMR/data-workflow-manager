"""v0.1.10-a3: screen-safe, preference-driven popup placement.

The geometry planner is pure Python for tests on systems without Qt. A window
may appear beside the DWM main window on the same or an adjacent monitor, if
there is room for its minimum size. Otherwise it is centered over the main
window and clamped to a visible screen. Main-window geometry is never changed.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Sequence

PLACEMENT_CHOICES = {
    'auto': 'Automatisk (anbefalt)',
    'over': 'Over hovedvinduet',
    'beside': 'Ved siden av hovedvinduet',
}


def placement_mode(settings: Mapping | None, *, kind: str) -> str:
    choice = str((settings or {}).get('qt_popup_placement') or 'auto').strip().lower()
    if choice not in PLACEMENT_CHOICES:
        choice = 'auto'
    if choice == 'auto':
        return 'beside' if kind in {'report', 'results'} else 'over'
    return choice


@dataclass(frozen=True)
class Rect:
    x: int
    y: int
    width: int
    height: int

    @property
    def right(self) -> int:
        return self.x + self.width

    @property
    def bottom(self) -> int:
        return self.y + self.height

    @property
    def cx(self) -> int:
        return self.x + self.width // 2

    @property
    def cy(self) -> int:
        return self.y + self.height // 2


def _clamp(number: int, low: int, high: int) -> int:
    return max(low, min(int(number), max(low, high)))


def plan_popup(
    parent: Rect,
    wanted: tuple[int, int],
    minimum: tuple[int, int],
    screens: Sequence[Rect],
    *,
    mode: str,
    gap: int = 8,
) -> tuple[Rect, str]:
    if not screens:
        raise ValueError('Ingen tilgjengelige skjermer')
    if mode not in ('over', 'beside'):
        raise ValueError('Ukjent popup-plassering')
    width = max(int(wanted[0]), int(minimum[0]), 1)
    height = max(int(wanted[1]), int(minimum[1]), 1)
    min_width = max(int(minimum[0]), 1)
    min_height = max(int(minimum[1]), 1)
    # Use the display containing the center of the main window; if the main
    # window straddles screens, prefer the display with greatest overlap.
    def overlap(screen: Rect) -> int:
        w = max(0, min(parent.right, screen.right) - max(parent.x, screen.x))
        h = max(0, min(parent.bottom, screen.bottom) - max(parent.y, screen.y))
        return w * h
    screen = max(screens, key=lambda s: (overlap(s), -(abs(s.cx-parent.cx)+abs(s.cy-parent.cy))))

    if mode == 'beside':
        # Try the free area on the main monitor first. If no space remains,
        # try an adjacent monitor without crossing the main window.
        other = [s for s in screens if s is not screen and s != screen]
        ordered = [(screen, 'right'), (screen, 'left')]
        ordered += [(s, 'right') for s in other if s.x >= parent.right - gap]
        ordered += [(s, 'left') for s in other if s.right <= parent.x + gap]
        # Prefer right on another monitor before left on same monitor if both
        # directions are possible after a same-screen right attempt.
        if len(ordered) > 2:
            ordered = [ordered[0], *ordered[2:], ordered[1]]
        for target, side in ordered:
            if side == 'right':
                start_x = max(parent.right + gap, target.x + gap)
                available_width = target.right - gap - start_x
            else:
                end_x = min(parent.x - gap, target.right - gap)
                available_width = end_x - (target.x + gap)
            available_height = target.height - 2 * gap
            if available_width < min_width or available_height < min_height:
                continue
            w = min(width, available_width)
            h = min(height, available_height)
            x = start_x if side == 'right' else end_x - w
            y = _clamp(parent.cy - h // 2, target.y + gap, target.bottom - gap - h)
            return Rect(x, y, w, h), 'beside'

    # No side position is safe: center over the parent, use the current
    # display and preserve the window's minimum size whenever possible.
    w = min(width, max(min_width, screen.width - 2*gap))
    h = min(height, max(min_height, screen.height - 2*gap))
    x = _clamp(parent.cx - w // 2, screen.x + gap, screen.right - gap - w)
    y = _clamp(parent.cy - h // 2, screen.y + gap, screen.bottom - gap - h)
    return Rect(x, y, w, h), 'over'


def place_popup(popup, main_window, *, settings: Mapping | None, kind: str):
    """Use real Qt window/screen geometry. Safe before show() or exec()."""
    from PySide6.QtWidgets import QApplication

    def rect(qrect) -> Rect:
        return Rect(qrect.x(), qrect.y(), qrect.width(), qrect.height())

    parent = rect(main_window.frameGeometry())
    screens = [rect(item.availableGeometry()) for item in QApplication.screens()]
    size = popup.size()
    minimum = popup.minimumSize()
    geometry, actual = plan_popup(
        parent, (size.width(), size.height()),
        (minimum.width(), minimum.height()), screens,
        mode=placement_mode(settings, kind=kind),
    )
    if popup.width() != geometry.width or popup.height() != geometry.height:
        popup.resize(geometry.width, geometry.height)
    popup.move(geometry.x, geometry.y)
    return actual
