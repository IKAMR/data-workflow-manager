from __future__ import annotations

import sys
import tkinter as tk


def enable_native_work_window(window) -> None:
    """Make one explicitly selected work window a normal native OS window.

    Call this from the window's own constructor after CustomTkinter has created
    the Toplevel. Do not apply it from the global <Map> hook: changing transient
    window-manager state while a Toplevel is being mapped can cause remapping
    loops/flicker on Windows.

    Windows gets normal minimize/maximize/close controls. Other platforms keep
    the window manager's native decorations. Intentional popup/tooltips that use
    overrideredirect are not changed.
    """
    try:
        if bool(window.overrideredirect()):
            return
    except (tk.TclError, AttributeError):
        return

    try:
        window.resizable(True, True)
        window.tk.call("wm", "transient", window._w, "")
        if sys.platform.startswith("win"):
            try:
                window.attributes("-toolwindow", False)
            except (tk.TclError, AttributeError):
                pass
        window._dwm_native_work_window = True
    except (tk.TclError, AttributeError):
        # Window styling must never prevent a window from opening.
        return


def present_native_work_window(window) -> None:
    """Bring one native work window to the foreground without keeping it topmost.

    Each presentation gets a generation token. If another work window opens and
    releases this window as its parent, the parent's pending delayed callbacks
    become stale and are ignored. This prevents an older parent presentation
    callback from stealing foreground focus back from a newly opened child.
    """
    generation = int(getattr(window, "_dwm_present_generation", 0)) + 1
    window._dwm_present_generation = generation

    def is_current() -> bool:
        try:
            return (
                window.winfo_exists()
                and int(getattr(window, "_dwm_present_generation", 0))
                == generation
            )
        except (tk.TclError, AttributeError):
            return False

    def final_focus() -> None:
        if not is_current():
            return
        try:
            if sys.platform.startswith("win"):
                try:
                    window.attributes("-topmost", False)
                except (tk.TclError, AttributeError):
                    pass
            window.lift()
            try:
                window.focus_force()
            except (tk.TclError, AttributeError):
                try:
                    window.focus_set()
                except (tk.TclError, AttributeError):
                    pass
        except (tk.TclError, AttributeError):
            return

    def activate() -> None:
        if not is_current():
            return
        try:
            window.deiconify()
            window.update_idletasks()
            window.lift()

            if sys.platform.startswith("win"):
                try:
                    window.attributes("-topmost", True)
                except (tk.TclError, AttributeError):
                    pass

            try:
                window.focus_force()
            except (tk.TclError, AttributeError):
                pass

            window.after(90, final_focus)
        except (tk.TclError, AttributeError):
            return

    try:
        window.after_idle(activate)
        window.after(180, final_focus)
    except (tk.TclError, AttributeError):
        return


def release_parent_work_window(parent) -> None:
    """Release parent Z-order and invalidate its pending presentation callbacks.

    The generation bump is the key part: any delayed focus/lift callbacks created
    earlier by ``present_native_work_window(parent)`` immediately become stale.
    """
    if parent is None:
        return
    try:
        if not parent.winfo_exists():
            return
    except Exception:
        return

    try:
        parent._dwm_present_generation = (
            int(getattr(parent, "_dwm_present_generation", 0)) + 1
        )

        if sys.platform.startswith("win"):
            try:
                parent.attributes("-topmost", False)
            except (tk.TclError, AttributeError):
                pass
        try:
            parent.lower()
        except (tk.TclError, AttributeError):
            pass
    except (tk.TclError, AttributeError):
        return


def present_child_over_parent(window, parent) -> None:
    """Present a native child work window above its caller, then return both
    windows to normal non-topmost behaviour.

    On Windows this uses native SetWindowPos for deterministic Z-order. Tk's
    temporary ``-topmost`` pulse alone is not sufficient when a maximization
    callback and the caller's earlier activation callback overlap.
    """

    def activate_native() -> None:
        try:
            if not window.winfo_exists():
                return
        except (tk.TclError, AttributeError):
            return

        if sys.platform.startswith("win"):
            try:
                import ctypes

                user32 = ctypes.windll.user32
                SWP_NOMOVE = 0x0002
                SWP_NOSIZE = 0x0001
                SWP_NOACTIVATE = 0x0010
                flags_parent = SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE
                flags_child = SWP_NOMOVE | SWP_NOSIZE

                HWND_NOTOPMOST = -2
                HWND_TOPMOST = -1
                HWND_TOP = 0

                if parent is not None and parent.winfo_exists():
                    try:
                        parent.attributes("-topmost", False)
                    except (tk.TclError, AttributeError):
                        pass
                    parent_hwnd = int(parent.winfo_id())
                    user32.SetWindowPos(
                        parent_hwnd,
                        HWND_NOTOPMOST,
                        0, 0, 0, 0,
                        flags_parent,
                    )

                child_hwnd = int(window.winfo_id())
                # Put the result view deterministically above the caller.
                user32.SetWindowPos(
                    child_hwnd,
                    HWND_TOPMOST,
                    0, 0, 0, 0,
                    flags_child,
                )
                # Immediately return it to ordinary non-topmost ordering while
                # retaining its position at the front.
                user32.SetWindowPos(
                    child_hwnd,
                    HWND_NOTOPMOST,
                    0, 0, 0, 0,
                    flags_child,
                )
                user32.SetWindowPos(
                    child_hwnd,
                    HWND_TOP,
                    0, 0, 0, 0,
                    flags_child,
                )
            except Exception:
                try:
                    window.lift()
                except (tk.TclError, AttributeError):
                    pass
        else:
            try:
                if parent is not None:
                    parent.lower()
                window.lift()
            except (tk.TclError, AttributeError):
                pass

        try:
            window.focus_force()
        except (tk.TclError, AttributeError):
            pass

    try:
        # First pass after mapping, second after the a6 maximize callback
        # (220 ms), and a final pass after all activation pulses have settled.
        window.after_idle(activate_native)
        window.after(280, activate_native)
        window.after(480, activate_native)
    except (tk.TclError, AttributeError):
        return

def _visible_toplevel(widget):
    """Return the nearest visible toplevel that should act as parent."""
    master = getattr(widget, "master", None)
    while master is not None:
        try:
            top = master.winfo_toplevel()
            if top is not widget and top.winfo_exists() and top.winfo_viewable():
                return top
        except tk.TclError:
            pass
        master = getattr(master, "master", None)
    return None


def place_near_parent(window, root) -> None:
    """Center a custom Tk/CTk dialog over its owning application window.

    Uses virtual desktop coordinates, so a parent on monitor 2/3 keeps its
    child dialog on that same monitor in normal multi-monitor layouts.
    """
    try:
        if getattr(window, "_n5wf_parent_positioned", False):
            return
        parent = _visible_toplevel(window) or root
        if parent is window or not parent.winfo_exists():
            return

        parent.update_idletasks()
        window.update_idletasks()

        pw = max(1, parent.winfo_width())
        ph = max(1, parent.winfo_height())
        px = parent.winfo_rootx()
        py = parent.winfo_rooty()

        ww = max(1, window.winfo_width(), window.winfo_reqwidth())
        wh = max(1, window.winfo_height(), window.winfo_reqheight())

        x = px + max(0, (pw - ww) // 2)
        y = py + max(0, (ph - wh) // 2)

        window.geometry(f"+{x}+{y}")
        window._n5wf_parent_positioned = True
    except (tk.TclError, AttributeError):
        # Placement must never prevent a dialog from opening.
        return


def install_child_window_placement(root) -> None:
    """Position every later custom Toplevel relative to its current parent.

    Important: this global <Map> hook performs placement only. Window-manager
    style/transient/focus changes must be explicit in selected work-window
    classes.
    """
    if getattr(root, "_n5wf_child_placement_installed", False):
        return
    root._n5wf_child_placement_installed = True

    def on_map(event):
        widget = getattr(event, "widget", None)
        if widget is None or widget is root:
            return
        try:
            if isinstance(widget, tk.Toplevel):
                root.after_idle(lambda w=widget: place_near_parent(w, root))
        except tk.TclError:
            return

    root.bind_all("<Map>", on_map, add="+")
