from __future__ import annotations

import sys
import threading
import traceback
from datetime import datetime
from tkinter import messagebox

import customtkinter as ctk

from version import APP_NAME
from gui import theme


class AppExceptionMonitor:
    """Surface otherwise console-only exceptions inside the application.

    The monitor does not suppress console tracebacks. It mirrors them into a
    persistent, clearly visible GUI warning and keeps a short in-memory history.
    """

    def __init__(self, app) -> None:
        self.app = app
        self.errors: list[str] = []
        self._previous_threading_hook = threading.excepthook
        self._previous_sys_hook = sys.excepthook

        self._install_indicator()
        self._install_hooks()

    def _install_indicator(self) -> None:
        bar = self.app.status_bar

        self.button = ctk.CTkButton(
            bar,
            text="⚠ FEIL",
            width=88,
            height=20,
            font=theme.font(theme.SMALL_SIZE, "bold"),
            fg_color=theme.DANGER_TEXT,
            hover_color=theme.DANGER_BG,
            text_color="#ffffff",
            command=self.show_errors,
        )
        self.button.grid(row=0, column=3, padx=(2, 10), pady=2, sticky="e")
        self.button.grid_remove()

    def _install_hooks(self) -> None:
        # Tkinter calls this for exceptions raised by button/menu/widget
        # callbacks. Overriding it is the canonical way to surface callback
        # exceptions without losing the traceback.
        self.app.report_callback_exception = self._tk_exception

        # Worker/background thread exceptions otherwise only go to stderr.
        threading.excepthook = self._thread_exception

        # Keep a final process-level hook as well. It primarily preserves
        # visibility in the console; if Tk is still alive we also mirror it.
        sys.excepthook = self._sys_exception

    @staticmethod
    def _format(exc_type, exc_value, exc_tb, *, prefix: str) -> str:
        stamp = datetime.now().astimezone().isoformat(timespec="seconds")
        body = "".join(
            traceback.format_exception(exc_type, exc_value, exc_tb)
        ).rstrip()
        return f"[{stamp}] {prefix}\n{body}"

    def _record(self, text: str) -> None:
        self.errors.append(text)
        self.errors = self.errors[-20:]

        try:
            self.button.configure(text=f"⚠ FEIL ({len(self.errors)})")
            self.button.grid()
        except Exception:
            pass

        try:
            self.app.status_bar.set_status(
                "⚠ Programfeil oppdaget – klikk FEIL for detaljer"
            )
        except Exception:
            pass

        try:
            self.app.log_panel.append(
                "PROGRAMFEIL: Se rød FEIL-indikator for traceback."
            )
        except Exception:
            pass

    def _record_from_any_thread(self, text: str) -> None:
        try:
            self.app.after(0, lambda t=text: self._record(t))
        except Exception:
            pass

    def _tk_exception(self, exc_type, exc_value, exc_tb) -> None:
        text = self._format(
            exc_type,
            exc_value,
            exc_tb,
            prefix="Tkinter callback exception",
        )
        # Preserve the console traceback as before.
        traceback.print_exception(exc_type, exc_value, exc_tb)
        self._record(text)

    def _thread_exception(self, args) -> None:
        text = self._format(
            args.exc_type,
            args.exc_value,
            args.exc_traceback,
            prefix=f"Thread exception: {getattr(args.thread, 'name', 'unknown')}",
        )
        try:
            self._previous_threading_hook(args)
        finally:
            self._record_from_any_thread(text)

    def _sys_exception(self, exc_type, exc_value, exc_tb) -> None:
        text = self._format(
            exc_type,
            exc_value,
            exc_tb,
            prefix="Unhandled application exception",
        )
        try:
            self._previous_sys_hook(exc_type, exc_value, exc_tb)
        finally:
            self._record_from_any_thread(text)

    def show_errors(self) -> None:
        if not self.errors:
            messagebox.showinfo(APP_NAME, "Ingen registrerte programfeil.")
            return

        window = ctk.CTkToplevel(self.app)
        window.title(f"Programfeil – {APP_NAME}")
        window.geometry("1100x650")
        window.minsize(760, 420)
        window.configure(fg_color=theme.APP_BG)
        window.grid_columnconfigure(0, weight=1)
        window.grid_rowconfigure(1, weight=1)

        ctk.CTkLabel(
            window,
            text=(
                f"⚠ PROGRAMFEIL – {len(self.errors)} registrert"
                + ("e" if len(self.errors) != 1 else "")
            ),
            font=theme.font(theme.SECTION_SIZE, "bold"),
            text_color=theme.DANGER_TEXT,
            anchor="w",
        ).grid(row=0, column=0, padx=16, pady=(14, 8), sticky="ew")

        box = ctk.CTkTextbox(
            window,
            font=theme.font(theme.SMALL_SIZE),
            fg_color=theme.PANEL_BG_DARK,
            text_color=theme.TEXT,
            wrap="none",
        )
        box.grid(row=1, column=0, padx=16, pady=(0, 10), sticky="nsew")
        box.insert("1.0", "\n\n" + ("\n\n" + ("-" * 90) + "\n\n").join(self.errors))
        box.configure(state="disabled")
        box.see("end")

        buttons = ctk.CTkFrame(window, fg_color="transparent")
        buttons.grid(row=2, column=0, padx=16, pady=(0, 14), sticky="e")

        ctk.CTkButton(
            buttons,
            text="Kvitter",
            width=90,
            command=self.clear_indicator,
            fg_color=theme.BUTTON_BG,
            hover_color=theme.BUTTON_HOVER,
        ).pack(side="left", padx=(0, 8))

        ctk.CTkButton(
            buttons,
            text="Lukk",
            width=90,
            command=window.destroy,
            fg_color=theme.BLUE_DIM,
            hover_color=theme.BLUE,
        ).pack(side="left")

    def clear_indicator(self) -> None:
        # Keep the actual error history for this application session but remove
        # the visual alarm after the user has acknowledged it.
        try:
            self.button.grid_remove()
            self.app.status_bar.set_status(
                "Programfeil kvittert – detaljer beholdes i denne appøkten"
            )
        except Exception:
            pass
