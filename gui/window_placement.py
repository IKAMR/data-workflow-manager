from __future__ import annotations

import sys
import tkinter as tk

import customtkinter as ctk


_NATIVE_DIALOG_POLICY_INSTALLED = False
_ORIGINAL_CTK_TOPLEVEL_TRANSIENT = None
_ORIGINAL_CTK_TOPLEVEL_RESIZABLE = None


def install_native_dialog_policy() -> None:
    """Give every application CTkToplevel a normal native desktop title bar.

    Windows:
      - app dialogs are ordinary resizable windows with minimize/maximize/close
      - calls to transient(master) are intentionally ignored, because a
        transient window normally loses minimize/maximize controls
      - modal behaviour may still be provided by grab_set() where needed

    Other platforms keep their existing native Tk/CustomTkinter behaviour.
    """
    global _NATIVE_DIALOG_POLICY_INSTALLED
    global _ORIGINAL_CTK_TOPLEVEL_TRANSIENT
    global _ORIGINAL_CTK_TOPLEVEL_RESIZABLE

    if _NATIVE_DIALOG_POLICY_INSTALLED:
        return
    _NATIVE_DIALOG_POLICY_INSTALLED = True

    if not sys.platform.startswith("win"):
        return

    _ORIGINAL_CTK_TOPLEVEL_TRANSIENT = ctk.CTkToplevel.transient
    _ORIGINAL_CTK_TOPLEVEL_RESIZABLE = ctk.CTkToplevel.resizable

    def native_transient(window, master=None):
        if master is None:
            return _ORIGINAL_CTK_TOPLEVEL_TRANSIENT(window)
        window._dwm_logical_parent = master
        try:
            _ORIGINAL_CTK_TOPLEVEL_RESIZABLE(window, True, True)
        except (tk.TclError, AttributeError):
            pass
        try:
            window.attributes("-toolwindow", False)
        except (tk.TclError, AttributeError):
            pass
        return None

    def native_resizable(window, width=None, height=None):
        if width is None and height is None:
            return _ORIGINAL_CTK_TOPLEVEL_RESIZABLE(window)
        return _ORIGINAL_CTK_TOPLEVEL_RESIZABLE(window, True, True)

    ctk.CTkToplevel.transient = native_transient
    ctk.CTkToplevel.resizable = native_resizable


def enable_native_work_window(window) -> None:
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
        return


def present_native_work_window(window) -> None:
    generation = int(getattr(window, "_dwm_present_generation", 0)) + 1
    window._dwm_present_generation = generation

    def is_current() -> bool:
        try:
            return window.winfo_exists() and int(getattr(window, "_dwm_present_generation", 0)) == generation
        except (tk.TclError, AttributeError):
            return False

    def final_focus() -> None:
        if not is_current(): return
        try:
            if sys.platform.startswith("win"):
                try: window.attributes("-topmost", False)
                except (tk.TclError, AttributeError): pass
            window.lift()
            try: window.focus_force()
            except (tk.TclError, AttributeError):
                try: window.focus_set()
                except (tk.TclError, AttributeError): pass
        except (tk.TclError, AttributeError):
            return

    def activate() -> None:
        if not is_current(): return
        try:
            window.deiconify(); window.update_idletasks(); window.lift()
            if sys.platform.startswith("win"):
                try: window.attributes("-topmost", True)
                except (tk.TclError, AttributeError): pass
            try: window.focus_force()
            except (tk.TclError, AttributeError): pass
            window.after(90, final_focus)
        except (tk.TclError, AttributeError):
            return
    try:
        window.after_idle(activate); window.after(180, final_focus)
    except (tk.TclError, AttributeError):
        return


def release_parent_work_window(parent) -> None:
    if parent is None: return
    try:
        if not parent.winfo_exists(): return
    except Exception:
        return
    try:
        parent._dwm_present_generation = int(getattr(parent, "_dwm_present_generation", 0)) + 1
        if sys.platform.startswith("win"):
            try: parent.attributes("-topmost", False)
            except (tk.TclError, AttributeError): pass
        try: parent.lower()
        except (tk.TclError, AttributeError): pass
    except (tk.TclError, AttributeError):
        return


def present_child_over_parent(window, parent) -> None:
    def activate_native() -> None:
        try:
            if not window.winfo_exists(): return
        except (tk.TclError, AttributeError):
            return
        if sys.platform.startswith("win"):
            try:
                import ctypes
                user32=ctypes.windll.user32
                SWP_NOMOVE=0x0002; SWP_NOSIZE=0x0001; SWP_NOACTIVATE=0x0010
                flags_parent=SWP_NOMOVE|SWP_NOSIZE|SWP_NOACTIVATE
                flags_child=SWP_NOMOVE|SWP_NOSIZE
                HWND_NOTOPMOST=-2; HWND_TOPMOST=-1; HWND_TOP=0
                if parent is not None and parent.winfo_exists():
                    try: parent.attributes("-topmost", False)
                    except (tk.TclError, AttributeError): pass
                    user32.SetWindowPos(int(parent.winfo_id()), HWND_NOTOPMOST,0,0,0,0,flags_parent)
                child_hwnd=int(window.winfo_id())
                user32.SetWindowPos(child_hwnd, HWND_TOPMOST,0,0,0,0,flags_child)
                user32.SetWindowPos(child_hwnd, HWND_NOTOPMOST,0,0,0,0,flags_child)
                user32.SetWindowPos(child_hwnd, HWND_TOP,0,0,0,0,flags_child)
            except Exception:
                try: window.lift()
                except (tk.TclError, AttributeError): pass
        else:
            try:
                if parent is not None: parent.lower()
                window.lift()
            except (tk.TclError, AttributeError): pass
        try: window.focus_force()
        except (tk.TclError, AttributeError): pass
    try:
        window.after_idle(activate_native); window.after(280, activate_native); window.after(480, activate_native)
    except (tk.TclError, AttributeError):
        return


def _visible_toplevel(widget):
    master=getattr(widget,"master",None)
    while master is not None:
        try:
            top=master.winfo_toplevel()
            if top is not widget and top.winfo_exists() and top.winfo_viewable(): return top
        except tk.TclError: pass
        master=getattr(master,"master",None)
    return None


def place_near_parent(window, root) -> None:
    try:
        if getattr(window,"_n5wf_parent_positioned",False): return
        parent=_visible_toplevel(window) or root
        if parent is window or not parent.winfo_exists(): return
        parent.update_idletasks(); window.update_idletasks()
        pw=max(1,parent.winfo_width()); ph=max(1,parent.winfo_height())
        px=parent.winfo_rootx(); py=parent.winfo_rooty()
        ww=max(1,window.winfo_width(),window.winfo_reqwidth()); wh=max(1,window.winfo_height(),window.winfo_reqheight())
        x=px+max(0,(pw-ww)//2); y=py+max(0,(ph-wh)//2)
        window.geometry(f"+{x}+{y}"); window._n5wf_parent_positioned=True
    except (tk.TclError, AttributeError): return


def install_child_window_placement(root) -> None:
    if getattr(root,"_n5wf_child_placement_installed",False): return
    root._n5wf_child_placement_installed=True
    def on_map(event):
        widget=getattr(event,"widget",None)
        if widget is None or widget is root: return
        try:
            if isinstance(widget,tk.Toplevel): root.after_idle(lambda w=widget: place_near_parent(w,root))
        except tk.TclError: return
    root.bind_all("<Map>",on_map,add="+")
