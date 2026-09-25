from __future__ import annotations

import os
import sys
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


def current_monitor_work_area(window) -> ScreenBounds:
    """Return the work area of the monitor containing ``window``.

    Windows gets monitor-specific coordinates so a two-monitor desktop is not
    mistaken for one ultrawide display. Other platforms use Tk's screen bounds
    as a portable fallback.
    """
    if os.name == "nt":
        try:
            import ctypes
            from ctypes import wintypes

            class MONITORINFO(ctypes.Structure):
                _fields_ = [
                    ("cbSize", wintypes.DWORD),
                    ("rcMonitor", wintypes.RECT),
                    ("rcWork", wintypes.RECT),
                    ("dwFlags", wintypes.DWORD),
                ]

            hwnd = int(window.winfo_id())
            user32 = ctypes.windll.user32
            monitor = user32.MonitorFromWindow(
                wintypes.HWND(hwnd),
                2,  # MONITOR_DEFAULTTONEAREST
            )
            if monitor:
                info = MONITORINFO()
                info.cbSize = ctypes.sizeof(MONITORINFO)
                if user32.GetMonitorInfoW(monitor, ctypes.byref(info)):
                    rect = info.rcWork
                    width = int(rect.right - rect.left)
                    height = int(rect.bottom - rect.top)
                    if width > 0 and height > 0:
                        return ScreenBounds(
                            int(rect.left),
                            int(rect.top),
                            width,
                            height,
                        )
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
    """Build a safe startup geometry string from independent position/size settings."""
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
        primary_width = max(1, int(window.winfo_screenwidth()))
        primary_height = max(1, int(window.winfo_screenheight()))
        x = max(0, (primary_width - width) // 2)
        y = max(0, (primary_height - height) // 2)

    return f"{width}x{height}+{x}+{y}"


def should_restore_maximized(settings: dict) -> bool:
    """Return whether startup should restore the previous maximized state."""
    return bool(settings.get("restore_main_window_maximized", True)) and bool(
        settings.get("main_window_maximized", False)
    )


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


def result_review_window_geometry(
    screen: ScreenBounds,
    *,
    wide_ratio: float = 2.0,
) -> tuple[str, str | None]:
    """Return opening mode for the Noark 5 result-review work window.

    Normal displays are maximized. Displays with aspect ratio >= ``wide_ratio``
    are treated as ultrawide and get a large centred normal window instead.

    Return value:
      ("maximized", None)
      ("fitted", "<width>x<height>+<x>+<y>")
    """
    ratio = screen.width / max(1, screen.height)
    if ratio < wide_ratio:
        return "maximized", None

    width = min(2000, max(1320, int(screen.width * 0.62)))
    height = min(1200, max(760, int(screen.height * 0.88)))

    width = min(width, screen.width)
    height = min(height, screen.height)

    x = screen.x + max(0, (screen.width - width) // 2)
    y = screen.y + max(0, (screen.height - height) // 2)
    return "fitted", f"{width}x{height}+{x}+{y}"


def apply_result_review_opening_mode(window, *, wide_ratio: float = 2.0) -> None:
    """Apply the a6 opening rule after the native result window is mapped."""

    def apply() -> None:
        try:
            if not window.winfo_exists():
                return

            window.update_idletasks()
            screen = current_monitor_work_area(window)
            mode, geometry = result_review_window_geometry(
                screen,
                wide_ratio=wide_ratio,
            )

            if mode == "fitted":
                try:
                    window.state("normal")
                except Exception:
                    pass
                if geometry:
                    window.geometry(geometry)
                window._dwm_result_opening_mode = "fitted"
                return

            # Normal-aspect display: use native maximize where supported.
            maximized = False
            if os.name == "nt":
                try:
                    window.state("zoomed")
                    maximized = True
                except Exception:
                    pass
            elif sys.platform.startswith("linux"):
                try:
                    window.attributes("-zoomed", True)
                    maximized = True
                except Exception:
                    try:
                        window.state("zoomed")
                        maximized = True
                    except Exception:
                        pass
            else:
                try:
                    window.state("zoomed")
                    maximized = True
                except Exception:
                    pass

            if not maximized:
                # Portable fallback: occupy the monitor work area without
                # relying on a platform-specific maximize state.
                window.state("normal")
                window.geometry(
                    f"{screen.width}x{screen.height}+{screen.x}+{screen.y}"
                )

            window._dwm_result_opening_mode = "maximized"
        except Exception:
            # Opening mode is presentation only and must never block the dialog.
            return

    try:
        window.after_idle(apply)
        # Run once more after native focus/Z-order handling has settled.
        window.after(220, apply)
    except Exception:
        return
