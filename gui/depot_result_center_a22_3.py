from __future__ import annotations

import customtkinter as ctk
from tkinter import messagebox
import sys

from . import theme
from .depot_result_center_a22_2 import DepotResultCenterDialogA22_2


class DepotResultCenterDialogA22_3(DepotResultCenterDialogA22_2):
    """a22.3: maximized control workspace with visible evidence and navigation."""

    def _a223_maximize(self, win) -> None:
        try:
            win.state("zoomed")
        except Exception:
            try:
                win.attributes("-zoomed", True)
            except Exception:
                pass

    def _a223_present_work_window(self, win) -> None:
        """Bring the workspace to the foreground once, without permanent topmost."""
        try:
            win.deiconify()
            win.update_idletasks()
        except Exception:
            pass
        self._a223_maximize(win)
        try:
            win.lift()
        except Exception:
            pass

        # Windows is stricter than Tk about foreground activation.  Resolve the
        # native top-level HWND and use a short TOPMOST -> NOTOPMOST pulse so the
        # workspace is placed above the Resultatvisninger window that opened it,
        # while immediately returning to ordinary z-order afterwards.
        if sys.platform.startswith("win"):
            try:
                import ctypes

                user32 = ctypes.windll.user32
                hwnd = int(win.winfo_id())
                GA_ROOT = 2
                root_hwnd = int(user32.GetAncestor(hwnd, GA_ROOT) or hwnd)
                SW_RESTORE = 9
                HWND_TOPMOST = -1
                HWND_NOTOPMOST = -2
                SWP_NOMOVE = 0x0002
                SWP_NOSIZE = 0x0001
                SWP_SHOWWINDOW = 0x0040
                flags = SWP_NOMOVE | SWP_NOSIZE | SWP_SHOWWINDOW

                user32.ShowWindow(root_hwnd, SW_RESTORE)
                user32.SetWindowPos(root_hwnd, HWND_TOPMOST, 0, 0, 0, 0, flags)
                user32.SetWindowPos(root_hwnd, HWND_NOTOPMOST, 0, 0, 0, 0, flags)
                user32.BringWindowToTop(root_hwnd)
                user32.SetForegroundWindow(root_hwnd)
                user32.SetFocus(root_hwnd)
            except Exception:
                pass
        else:
            try:
                win.attributes("-topmost", True)
                win.update_idletasks()
                win.attributes("-topmost", False)
            except Exception:
                pass

        try:
            win.lift()
            win.focus_force()
        except Exception:
            pass

    def _a223_context_text(self, index: int, item: dict) -> str:
        parts = getattr(self, "_archive_parts", None) or []
        if not (0 <= index < len(parts)):
            return item.get("value") or "–"
        row = parts[index]
        identity = row.get("archive_part") or {}
        lines = [
            f"Kontroll: {item.get('label') or '–'}",
            f"Resultat / verdi: {item.get('value') or '–'}",
            f"Kontrollstatus: {item.get('control_status') or '–'}",
            f"Kilde: {item.get('source') or '–'}",
            "",
            "Kontekst for valgt arkivdel",
            f"Arkivdel: {identity.get('title') or 'Alle arkivdeler'}",
            f"systemID: {identity.get('system_id') or '–'}",
        ]
        try:
            period = self._effective_period(row, index)
            if period:
                if isinstance(period, (tuple, list)) and len(period) >= 2:
                    lines.append(f"Observert periode: {period[0]}–{period[1]}")
                else:
                    lines.append(f"Observert periode: {period}")
        except Exception:
            pass
        for label, key in (
            ("Mapper", "folder_count"),
            ("Registreringer", "registration_count"),
            ("Dokumentbeskrivelser", "document_description_count"),
            ("Dokumentobjekter", "document_object_count"),
        ):
            value = row.get(key)
            if value is not None:
                lines.append(f"{label}: {self._fmt_count(value)}")
        lines.extend(("", "Kontrollen vurderes mot det materialiserte resultatgrunnlaget. Kildeverdien over endres ikke av den faglige behandlingen."))
        return "\n".join(lines)

    def _a222_open_control_window(self) -> None:
        existing = getattr(self, "_a222_control_window", None)
        if existing is not None:
            try:
                if existing.winfo_exists():
                    self._a223_present_work_window(existing)
                    return
            except Exception:
                pass

        index = int(getattr(self, "_archive_index", 0) or 0)
        items = self._a222_control_items(index)
        win = ctk.CTkToplevel(self)
        self._a222_control_window = win
        win.title("Kontrollbehandling – Noark 5")
        win.geometry("1400x850")
        win.minsize(1050, 650)
        win.resizable(True, True)
        win.protocol("WM_DELETE_WINDOW", win.destroy)
        win.grid_columnconfigure(1, weight=1)
        win.grid_rowconfigure(1, weight=1)
        # Present after Tk has mapped the native Windows frame. This keeps the
        # workspace in front on first open, but does not make it permanently topmost.
        win.after(40, lambda: self._a223_present_work_window(win))
        win.after(220, lambda: self._a223_present_work_window(win))
        win.after(650, lambda: self._a223_present_work_window(win))

        header = ctk.CTkFrame(win, fg_color="transparent")
        header.grid(row=0, column=0, columnspan=2, sticky="ew", padx=14, pady=(10, 6))
        header.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(header, text="Kontrollbehandling", anchor="w", font=theme.font(theme.HEADER_SIZE, weight="bold")).grid(row=0, column=0, sticky="w")
        parts = getattr(self, "_archive_parts", None) or []
        selected_row = parts[index] if 0 <= index < len(parts) else {}
        identity = selected_row.get("archive_part") or {}
        archive_title = identity.get("title") or "Alle arkivdeler"
        ctk.CTkLabel(header, text=f"Valgt arkivdel: {archive_title}   ·   {len(items)} kontroller", anchor="e", text_color=theme.TEXT_MUTED, font=theme.font(theme.SMALL_SIZE)).grid(row=0, column=1, sticky="e")

        left = ctk.CTkScrollableFrame(win, width=330)
        left.grid(row=1, column=0, sticky="nsew", padx=(14, 7), pady=(0, 14))
        left.grid_columnconfigure(0, weight=1)
        work = ctk.CTkFrame(win)
        work.grid(row=1, column=1, sticky="nsew", padx=(7, 14), pady=(0, 14))
        work.grid_columnconfigure(0, weight=3)
        work.grid_columnconfigure(1, weight=2)
        work.grid_rowconfigure(3, weight=1)

        title = ctk.CTkLabel(work, text="Velg en kontroll", anchor="w", font=theme.font(theme.TITLE_SIZE, weight="bold"))
        title.grid(row=0, column=0, columnspan=2, sticky="ew", padx=14, pady=(14, 2))
        meta = ctk.CTkLabel(work, text="", anchor="w", justify="left", text_color=theme.TEXT_MUTED, font=theme.font(theme.SMALL_SIZE))
        meta.grid(row=1, column=0, columnspan=2, sticky="ew", padx=14, pady=(0, 4))

        overview = ctk.CTkFrame(work, fg_color=theme.CARD_BG, border_width=1, border_color=theme.CARD_BORDER)
        overview.grid(row=2, column=0, columnspan=2, sticky="ew", padx=14, pady=(0, 8))
        overview.grid_columnconfigure(1, weight=1)
        overview_text = ctk.CTkLabel(overview, text="", anchor="w", justify="left", font=theme.font(theme.SMALL_SIZE, weight="bold"))
        overview_text.grid(row=0, column=0, sticky="w", padx=(10, 12), pady=7)
        overview_progress = ctk.CTkProgressBar(overview, height=10)
        overview_progress.grid(row=0, column=1, sticky="ew", padx=(0, 10), pady=7)
        overview_progress.set(0)

        evidence_frame = ctk.CTkFrame(work)
        evidence_frame.grid(row=3, column=0, sticky="nsew", padx=(14, 7), pady=(0, 10))
        evidence_frame.grid_columnconfigure(0, weight=1)
        evidence_frame.grid_rowconfigure(1, weight=1)
        ctk.CTkLabel(evidence_frame, text="Resultat og evidens", anchor="w", font=theme.font(theme.NORMAL_SIZE, weight="bold")).grid(row=0, column=0, sticky="ew", padx=12, pady=(10, 4))
        evidence = ctk.CTkTextbox(evidence_frame, wrap="word", font=theme.font(theme.SMALL_SIZE))
        evidence.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 10))
        evidence.configure(state="disabled")

        review_frame = ctk.CTkFrame(work)
        review_frame.grid(row=3, column=1, sticky="nsew", padx=(7, 14), pady=(0, 10))
        review_frame.grid_columnconfigure(0, weight=1)
        review_frame.grid_rowconfigure(4, weight=1)
        ctk.CTkLabel(review_frame, text="Faglig vurdering", anchor="w", font=theme.font(theme.NORMAL_SIZE, weight="bold")).grid(row=0, column=0, sticky="ew", padx=12, pady=(10, 6))
        ctk.CTkLabel(review_frame, text="Vurderingsstatus", anchor="w", font=theme.font(theme.SMALL_SIZE, weight="bold")).grid(row=1, column=0, sticky="ew", padx=12)
        status_var = ctk.StringVar(value="Ikke vurdert")
        status = ctk.CTkOptionMenu(review_frame, variable=status_var, values=list(self.REVIEW_STATUSES))
        status.grid(row=2, column=0, sticky="ew", padx=12, pady=(3, 10))
        ctk.CTkLabel(review_frame, text="Kommentar / faglig behandling", anchor="w", font=theme.font(theme.SMALL_SIZE, weight="bold")).grid(row=3, column=0, sticky="ew", padx=12)
        comment = ctk.CTkTextbox(review_frame, wrap="word", font=theme.font(theme.SMALL_SIZE))
        comment.grid(row=4, column=0, sticky="nsew", padx=12, pady=(3, 10))

        selected = {"pos": -1, "item": None}
        buttons = []

        def refresh_buttons():
            treated = 0
            for pos, (button, item) in enumerate(buttons):
                review = self._a222_review_for(index, item["section"], item["label"], item["source"])
                suffix = str(review.get("review_status") or "")
                if suffix and suffix != "Ikke vurdert":
                    treated += 1
                marker = "✓ " if suffix and suffix != "Ikke vurdert" else ""
                button.configure(text=marker + item["label"] + (f"  ·  {suffix}" if suffix and suffix != "Ikke vurdert" else ""))
            total = max(1, len(items))
            overview_progress.set(treated / total)
            current = selected.get("pos", -1) + 1 if selected.get("pos", -1) >= 0 else 0
            overview_text.configure(text=f"Fremdrift: {treated}/{len(items)} vurdert   ·   Valgt kontroll: {current}/{len(items)}")

        def choose_pos(pos: int):
            if not items:
                return
            pos = max(0, min(pos, len(items) - 1))
            item = items[pos]
            selected["pos"] = pos
            selected["item"] = item
            title.configure(text=item["label"])
            meta.configure(text=f"Seksjon: {item['section']}   ·   Kilde: {item['source']}   ·   Kontrollstatus: {item['control_status']}   ·   Kontroll {pos + 1} av {len(items)}")
            evidence.configure(state="normal")
            evidence.delete("1.0", "end")
            evidence.insert("1.0", self._a223_context_text(index, item))
            evidence.configure(state="disabled")
            review = self._a222_review_for(index, item["section"], item["label"], item["source"])
            status_var.set(str(review.get("review_status") or "Ikke vurdert"))
            comment.delete("1.0", "end")
            comment.insert("1.0", str(review.get("comment") or ""))
            for button_pos, (button, _button_item) in enumerate(buttons):
                if button_pos == pos:
                    # Same selection language as Arkivdeler: full light-blue
                    # selected row, dark-blue inactive rows.
                    button.configure(
                        fg_color=theme.BLUE,
                        hover_color=theme.BLUE,
                        border_width=0,
                    )
                else:
                    button.configure(
                        fg_color=theme.BUTTON_BG,
                        hover_color=theme.BUTTON_HOVER,
                        border_width=0,
                    )
            refresh_buttons()

        current_section = None
        rr = 0
        for pos, item in enumerate(items):
            if item["section"] != current_section:
                current_section = item["section"]
                ctk.CTkLabel(left, text=current_section, anchor="w", font=theme.font(theme.SMALL_SIZE, weight="bold")).grid(row=rr, column=0, sticky="ew", padx=6, pady=(10, 3))
                rr += 1
            button = ctk.CTkButton(left, text=item["label"], anchor="w", height=30, command=lambda p=pos: choose_pos(p))
            button.grid(row=rr, column=0, sticky="ew", padx=4, pady=2)
            buttons.append((button, item))
            rr += 1
        refresh_buttons()

        def save_current(show_message=False):
            item = selected.get("item")
            if item is None:
                messagebox.showinfo("Data Workflow Manager", "Velg en kontroll først.", parent=win)
                return False
            try:
                self._a222_set_review(index, item, status_var.get(), comment.get("1.0", "end"))
            except Exception as exc:
                messagebox.showerror("Data Workflow Manager", str(exc), parent=win)
                return False
            self._render_structured_controls(index)
            self._a222_render_review_points(index)
            refresh_buttons()
            if show_message:
                messagebox.showinfo("Data Workflow Manager", "Vurderingen er lagret.", parent=win)
            return True

        nav = ctk.CTkFrame(work, fg_color="transparent")
        nav.grid(row=4, column=0, columnspan=2, sticky="ew", padx=14, pady=(0, 12))
        nav.grid_columnconfigure(2, weight=1)
        ctk.CTkButton(nav, text="← Forrige kontroll", width=150, command=lambda: choose_pos(selected["pos"] - 1)).grid(row=0, column=0, padx=(0, 6))
        ctk.CTkButton(nav, text="Neste kontroll →", width=150, command=lambda: choose_pos(selected["pos"] + 1)).grid(row=0, column=1, padx=(0, 10))
        ctk.CTkButton(nav, text="Lagre vurdering", width=140, command=lambda: save_current(True)).grid(row=0, column=3, padx=5)
        ctk.CTkButton(nav, text="Lagre og neste →", width=150, command=lambda: save_current(False) and choose_pos(selected["pos"] + 1)).grid(row=0, column=4, padx=5)
        ctk.CTkButton(nav, text="Lukk", width=90, command=win.destroy).grid(row=0, column=5, padx=(5, 0))

        if items:
            choose_pos(0)


    @staticmethod
    def _set_text(widget, text: str) -> None:
        """Ignore writes to presentation widgets replaced by newer GUI layers."""
        if widget is None:
            return
        try:
            if not widget.winfo_exists():
                return
        except Exception:
            return
        try:
            widget.configure(state="normal")
            widget.delete("1.0", "end")
            widget.insert("1.0", text)
            widget.configure(state="disabled")
        except Exception:
            # A layered result view may destroy a legacy textbox during the same
            # archive-part refresh.  That textbox is no longer visible or authoritative.
            return

    def _a223_sync_open_control_window(self) -> None:
        """Rebuild an open workspace so it follows the current archive selection."""
        win = getattr(self, "_a222_control_window", None)
        if win is None:
            return
        try:
            if not win.winfo_exists():
                self._a222_control_window = None
                return
        except Exception:
            self._a222_control_window = None
            return

        try:
            win.destroy()
        except Exception:
            pass
        self._a222_control_window = None

        def reopen():
            try:
                self._a222_open_control_window()
            except Exception:
                pass

        try:
            self.after_idle(reopen)
        except Exception:
            reopen()

    def _a171_archive_click(self, index: int, *, ctrl: bool = False, shift: bool = False) -> None:
        """Follow a17.3 selection changes and synchronize Kontrollbehandling."""
        super()._a171_archive_click(index, ctrl=ctrl, shift=shift)
        self._a223_sync_open_control_window()

    def _show_archive_part(self, index: int) -> None:
        """Synchronize programmatic archive-part changes with Kontrollbehandling."""
        super()._show_archive_part(index)
        self._a223_sync_open_control_window()
