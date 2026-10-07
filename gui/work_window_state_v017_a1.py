from __future__ import annotations

from hashlib import sha1
import sys

from settings import load_config, save_config


_STATE_KEY = "work_window_states_v017_a1"


def job_window_state_key(kind: str, identity: str = "") -> str:
    """Stable compact key for a major work window."""
    kind = str(kind or "window").strip() or "window"
    identity = str(identity or "").strip()
    if not identity:
        return kind
    digest = sha1(identity.encode("utf-8")).hexdigest()[:12]
    return f"{kind}:{digest}"


def _monitor_work_area(window, x: int, y: int, width: int, height: int) -> tuple[int, int, int, int]:
    """Return the nearest monitor work area as x, y, width, height.

    On Windows the work area excludes the taskbar and handles mixed multi-monitor
    layouts. Other platforms fall back to Tk's virtual-root dimensions.
    """
    if sys.platform.startswith("win"):
        try:
            import ctypes
            from ctypes import wintypes

            class RECT(ctypes.Structure):
                _fields_ = [
                    ("left", wintypes.LONG),
                    ("top", wintypes.LONG),
                    ("right", wintypes.LONG),
                    ("bottom", wintypes.LONG),
                ]

            class MONITORINFO(ctypes.Structure):
                _fields_ = [
                    ("cbSize", wintypes.DWORD),
                    ("rcMonitor", RECT),
                    ("rcWork", RECT),
                    ("dwFlags", wintypes.DWORD),
                ]

            rect = RECT(x, y, x + max(1, width), y + max(1, height))
            user32 = ctypes.windll.user32
            monitor = user32.MonitorFromRect(ctypes.byref(rect), 2)  # MONITOR_DEFAULTTONEAREST
            info = MONITORINFO()
            info.cbSize = ctypes.sizeof(MONITORINFO)
            if monitor and user32.GetMonitorInfoW(monitor, ctypes.byref(info)):
                work = info.rcWork
                return (
                    int(work.left),
                    int(work.top),
                    max(1, int(work.right - work.left)),
                    max(1, int(work.bottom - work.top)),
                )
        except Exception:
            pass

    try:
        return (
            int(window.winfo_vrootx()),
            int(window.winfo_vrooty()),
            max(1, int(window.winfo_vrootwidth())),
            max(1, int(window.winfo_vrootheight())),
        )
    except Exception:
        return (0, 0, max(1, int(window.winfo_screenwidth())), max(1, int(window.winfo_screenheight())))


def _fit_to_work_area(
    window, x: int, y: int, width: int, height: int,
    *, max_width_fraction: float = 1.0, max_height_fraction: float = 1.0,
) -> tuple[int, int, int, int]:
    """Keep a remembered/initial work window fully usable on its monitor."""
    wx, wy, ww, wh = _monitor_work_area(window, x, y, width, height)
    margin_x = 20
    margin_y = 24
    max_width = max(640, ww - margin_x * 2)
    max_height = max(520, wh - margin_y * 2)
    # Tk/CustomTkinter may report logical pixels while Win32 monitor APIs use
    # physical pixels under DPI scaling. Cap against Tk's own dimensions too.
    try:
        tk_width = max(1, int(window.winfo_screenwidth()))
        tk_height = max(1, int(window.winfo_screenheight()))
        max_width = min(max_width, max(640, int(tk_width * float(max_width_fraction))))
        max_height = min(max_height, max(520, int(tk_height * float(max_height_fraction))))
    except Exception:
        pass
    width = max(1, min(int(width), max_width))
    height = max(1, min(int(height), max_height))
    x = max(wx + margin_x, min(int(x), wx + ww - width - margin_x))
    y = max(wy + margin_y, min(int(y), wy + wh - height - margin_y))
    return x, y, width, height


def install_work_window_state(
    window, key: str, *, max_width_fraction: float = 1.0, max_height_fraction: float = 1.0
) -> None:
    """Restore and remember geometry for a major work window.

    This is deliberately opt-in. Small operation/configuration dialogs are not
    registered here and therefore keep their existing parent-relative behavior.
    """
    key = str(key or "").strip()
    if not key or getattr(window, "_v017_window_state_installed", False):
        return
    window._v017_window_state_installed = True
    # Major work windows own their persisted position. Prevent the generic
    # parent-centering hook from moving them on later maps/deiconify calls.
    window._n5wf_parent_positioned = True
    window._v017_window_state_key = key
    window._v017_window_state_after = None
    window._v017_window_state_restoring = True

    cfg = load_config()
    states = cfg.get(_STATE_KEY, {})
    state = states.get(key, {}) if isinstance(states, dict) else {}

    def restore() -> None:
        try:
            window.update_idletasks()
            current_width = max(1, int(window.winfo_width()), int(window.winfo_reqwidth()))
            current_height = max(1, int(window.winfo_height()), int(window.winfo_reqheight()))
            current_x = int(window.winfo_x())
            current_y = int(window.winfo_y())

            width = int(state.get("width") or current_width)
            height = int(state.get("height") or current_height)
            x = int(state.get("x")) if state.get("x") is not None else current_x
            y = int(state.get("y")) if state.get("y") is not None else current_y
            x, y, width, height = _fit_to_work_area(
                window, x, y, width, height,
                max_width_fraction=max_width_fraction,
                max_height_fraction=max_height_fraction,
            )
            window.geometry(f"{width}x{height}+{x}+{y}")

            if bool(state.get("maximized", False)):
                try:
                    window.state("zoomed")
                except Exception:
                    pass
        finally:
            window._v017_window_state_restoring = False

    def save_now() -> None:
        window._v017_window_state_after = None
        if getattr(window, "_v017_window_state_restoring", False):
            return
        try:
            maximized = str(window.state()).lower() == "zoomed"
            config = load_config()
            current = config.get(_STATE_KEY, {})
            current = dict(current) if isinstance(current, dict) else {}

            if maximized:
                # Keep the last normal geometry while preserving zoom state.
                item = dict(current.get(key, {}) or {})
                item["maximized"] = True
            else:
                width = int(window.winfo_width())
                height = int(window.winfo_height())
                x = int(window.winfo_x())
                y = int(window.winfo_y())
                if width < 200 or height < 150:
                    return
                x, y, width, height = _fit_to_work_area(
                    window, x, y, width, height,
                    max_width_fraction=max_width_fraction,
                    max_height_fraction=max_height_fraction,
                )
                item = {
                    "x": x,
                    "y": y,
                    "width": width,
                    "height": height,
                    "maximized": False,
                }
            current[key] = item
            save_config({_STATE_KEY: current})
        except Exception:
            pass

    def schedule_save(_event=None) -> None:
        if getattr(window, "_v017_window_state_restoring", False):
            return
        pending = getattr(window, "_v017_window_state_after", None)
        if pending is not None:
            try:
                window.after_cancel(pending)
            except Exception:
                pass
        try:
            window._v017_window_state_after = window.after(350, save_now)
        except Exception:
            pass

    try:
        window.bind("<Configure>", schedule_save, add="+")
        window.after_idle(restore)
    except Exception:
        window._v017_window_state_restoring = False
