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

    Removing Tk's transient relationship gives the window normal OS chrome, but
    Windows may then activate the parent again after creation. A short, explicit
    activation pulse after the window has been mapped fixes the Z-order without
    turning the window into a permanent always-on-top window.

    On non-Windows platforms the helper only performs the normal deiconify/lift/
    focus sequence.
    """

    def final_focus() -> None:
        try:
            if not window.winfo_exists():
                return
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
        try:
            if not window.winfo_exists():
                return
            window.deiconify()
            window.update_idletasks()
            window.lift()

            if sys.platform.startswith("win"):
                try:
                    # Temporary activation pulse only. It is cleared again below.
                    window.attributes("-topmost", True)
                except (tk.TclError, AttributeError):
                    pass

            try:
                window.focus_force()
            except (tk.TclError, AttributeError):
                pass

            # Let the native window manager finish activation, then return the
            # window to ordinary non-topmost behaviour.
            window.after(90, final_focus)
        except (tk.TclError, AttributeError):
            return

    try:
        window.after_idle(activate)
        # A second delayed pass covers Windows cases where the caller's button
        # command regains focus after the first idle callback.
        window.after(180, final_focus)
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
