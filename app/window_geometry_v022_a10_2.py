"""Pure calculations for safe Qt main-window restoration on mixed-DPI screens.

The saved client rectangle must fit inside the available *decorated* screen.
No Qt import, monitor switch, or user settings mutation is performed here.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ScreenArea:
    x: int
    y: int
    width: int
    height: int
    name: str = ''

    @property
    def right(self) -> int:
        return self.x + self.width

    @property
    def bottom(self) -> int:
        return self.y + self.height


@dataclass(frozen=True)
class WindowRect:
    x: int
    y: int
    width: int
    height: int


def bounded_window_rect(
    saved: WindowRect, screens: tuple[ScreenArea, ...] | list[ScreenArea],
    *, preferred_screen: str = '', fallback_width: int = 1180,
    fallback_height: int = 780,
) -> WindowRect:
    """Choose a monitor and reserve Windows frame/title-bar/scale margins.

    Values are *logical Qt pixels* from QScreen.availableGeometry. This is
    deliberately conservative: even if requested client size fits, a native
    window's title bar and frame may extend beyond the available rectangle.
    """
    if not screens:
        return saved
    target = next((s for s in screens if s.name == preferred_screen and preferred_screen), None)
    if target is None:
        def overlap(s: ScreenArea) -> int:
            width = max(0, min(saved.x + saved.width, s.right) - max(saved.x, s.x))
            height = max(0, min(saved.y + saved.height, s.bottom) - max(saved.y, s.y))
            return width * height
        target = max(screens, key=overlap)
        if overlap(target) == 0:
            target = screens[0]
    # Insets account for the negative frame Y commonly seen in Qt/Windows
    # warnings. Reserve rather than use all available client pixels.
    left, top, right, bottom = 20, 64, 28, 36
    max_w = max(1, target.width - left - right)
    max_h = max(1, target.height - top - bottom)
    width = min(max(1, saved.width or fallback_width), max_w)
    height = min(max(1, saved.height or fallback_height), max_h)
    x = min(max(saved.x, target.x + left), target.right - right - width)
    y = min(max(saved.y, target.y + top), target.bottom - bottom - height)
    return WindowRect(int(x), int(y), int(width), int(height))


def bounded_dialog_size(
    requested_width: int, requested_height: int,
    screen_width: int, screen_height: int,
) -> tuple[int, int]:
    """Dialog dimensions within screen bounds, preserving user resizing."""
    ceiling_w = max(1, int(screen_width) - 80)
    ceiling_h = max(1, int(screen_height) - 110)
    width = min(max(1, int(requested_width)), ceiling_w)
    height = min(max(1, int(requested_height)), ceiling_h)
    return width, height
