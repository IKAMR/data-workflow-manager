from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class WindowGeometry:
    x: int
    y: int
    width: int
    height: int


@dataclass(frozen=True)
class ScreenBounds:
    x: int
    y: int
    width: int
    height: int


def _positive_int(value, fallback: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return fallback
    return parsed if parsed > 0 else fallback


def _optional_int(value) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def virtual_screen_bounds(window) -> ScreenBounds:
    """Return current virtual desktop bounds, with a portable primary-screen fallback."""
    if os.name == "nt":
        try:
            import ctypes

            user32 = ctypes.windll.user32
            # Windows virtual-screen metrics include all currently connected displays.
            x = int(user32.GetSystemMetrics(76))  # SM_XVIRTUALSCREEN
            y = int(user32.GetSystemMetrics(77))  # SM_YVIRTUALSCREEN
            width = int(user32.GetSystemMetrics(78))  # SM_CXVIRTUALSCREEN
            height = int(user32.GetSystemMetrics(79))  # SM_CYVIRTUALSCREEN
            if width > 0 and height > 0:
                return ScreenBounds(x, y, width, height)
        except Exception:
            pass

    return ScreenBounds(
        0,
        0,
        max(1, int(window.winfo_screenwidth())),
        max(1, int(window.winfo_screenheight())),
    )


def _has_visible_area(geometry: WindowGeometry, screen: ScreenBounds, minimum: int = 80) -> bool:
    left = max(geometry.x, screen.x)
    top = max(geometry.y, screen.y)
    right = min(geometry.x + geometry.width, screen.x + screen.width)
    bottom = min(geometry.y + geometry.height, screen.y + screen.height)
    return (right - left) >= minimum and (bottom - top) >= minimum


def startup_geometry(settings: dict, window) -> str | None:
    """Build a safe startup geometry string from independent position/size settings.

    A remembered position is accepted only when a useful part of the window is
    still inside the *current* virtual desktop. If an external monitor has been
    disconnected, the window is centred on the primary screen instead.
    """
    restore_position = bool(settings.get("restore_main_window_position", True))
    restore_size = bool(settings.get("restore_main_window_size", True))
    if not restore_position and not restore_size:
        return None

    window.update_idletasks()
    current_width = max(1180, int(window.winfo_width() or 1500))
    current_height = max(720, int(window.winfo_height() or 900))

    screen = virtual_screen_bounds(window)
    width = (
        _positive_int(settings.get("main_window_width"), current_width)
        if restore_size
        else current_width
    )
    height = (
        _positive_int(settings.get("main_window_height"), current_height)
        if restore_size
        else current_height
    )

    # Never restore a window larger than the currently available virtual desktop.
    width = min(width, max(1180, screen.width))
    height = min(height, max(720, screen.height))

    if not restore_position:
        return f"{width}x{height}" if restore_size else None

    x = _optional_int(settings.get("main_window_x"))
    y = _optional_int(settings.get("main_window_y"))
    if x is None or y is None:
        return f"{width}x{height}" if restore_size else None

    candidate = WindowGeometry(x, y, width, height)
    if not _has_visible_area(candidate, screen):
        # Safe fallback: centre on the primary display rather than on a missing monitor.
        primary_width = max(1, int(window.winfo_screenwidth()))
        primary_height = max(1, int(window.winfo_screenheight()))
        x = max(0, (primary_width - width) // 2)
        y = max(0, (primary_height - height) // 2)

    return f"{width}x{height}+{x}+{y}"


def capture_normal_geometry(window) -> WindowGeometry | None:
    """Capture only normal/restorable geometry, never minimized/maximized state."""
    try:
        if str(window.state()) != "normal":
            return None
        width = int(window.winfo_width())
        height = int(window.winfo_height())
        x = int(window.winfo_x())
        y = int(window.winfo_y())
    except Exception:
        return None
    if width <= 0 or height <= 0:
        return None
    return WindowGeometry(x, y, width, height)
