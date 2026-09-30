from __future__ import annotations

import ctypes
import sys
from collections import defaultdict

import customtkinter as ctk
from tkinter import messagebox

from . import theme
from .depot_result_center_a22_3 import DepotResultCenterDialogA22_3


class DepotResultCenterDialogA22_4(DepotResultCenterDialogA22_3):
    """a22.4: control analysis workspace based on the documented target images.

    The workspace is primarily for orientation and evidence review. A professional
    review is optional, and only meaningful findings need to become review points.
    Canonical report facts are never rewritten here.
    """

    @staticmethod
    def _set_text(widget, text: str) -> None:
        """Safely update inherited text surfaces that may have been replaced.

        a22.2 replaces the old Vurderingspunkter contents.  The inherited a30
        archive renderer can still hold a reference to that now-destroyed textbox.
        Archive-part changes must therefore ignore stale widgets instead of letting
        Tk abort the selection callback.
        """
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
            # The widget may have been destroyed between winfo_exists() and update.
            return

    def _a224_force_foreground(self, win) -> None:
        """Bring the work window to the foreground once, without permanent topmost."""
        try:
            win.deiconify()
            win.update_idletasks()
            self._a223_maximize(win)
            # The work window is owned by Resultatvisninger, but must be placed above it.
            try:
                win.transient(self)
                self.attributes("-topmost", False)
            except Exception:
                pass
            win.lift(self)
            win.focus_force()
            win.attributes("-topmost", True)
        except Exception:
            pass

        if sys.platform.startswith("win"):
            try:
                user32 = ctypes.windll.user32
                kernel32 = ctypes.windll.kernel32
                hwnd = int(win.winfo_id())
                SW_MAXIMIZE = 3
                HWND_TOPMOST = -1
                HWND_NOTOPMOST = -2
                HWND_TOP = 0
                SWP_NOMOVE = 0x0002
                SWP_NOSIZE = 0x0001
                SWP_SHOWWINDOW = 0x0040
                ASFW_ANY = -1

                user32.AllowSetForegroundWindow(ASFW_ANY)
                user32.ShowWindow(hwnd, SW_MAXIMIZE)

                # Resultatvisninger can itself have been raised/topmost. Demote the
                # caller first, otherwise Windows may keep the new child behind it.
                try:
                    parent_hwnd = int(self.winfo_id())
                    user32.SetWindowPos(
                        parent_hwnd, HWND_NOTOPMOST, 0, 0, 0, 0,
                        SWP_NOMOVE | SWP_NOSIZE | SWP_SHOWWINDOW,
                    )
                except Exception:
                    parent_hwnd = 0

                fg = user32.GetForegroundWindow()
                current_tid = kernel32.GetCurrentThreadId()
                fg_tid = user32.GetWindowThreadProcessId(fg, None) if fg else 0
                attached = False
                if fg_tid and fg_tid != current_tid:
                    attached = bool(user32.AttachThreadInput(current_tid, fg_tid, True))
                try:
                    user32.BringWindowToTop(hwnd)
                    user32.SetWindowPos(
                        hwnd, HWND_TOPMOST, 0, 0, 0, 0,
                        SWP_NOMOVE | SWP_NOSIZE | SWP_SHOWWINDOW,
                    )
                    user32.SetForegroundWindow(hwnd)
                    user32.SetActiveWindow(hwnd)
                    user32.SetFocus(hwnd)
                finally:
                    if attached:
                        user32.AttachThreadInput(current_tid, fg_tid, False)
            except Exception:
                pass

        def release_topmost():
            try:
                win.attributes("-topmost", False)
                win.lift(self)
                win.focus_force()
                if sys.platform.startswith("win"):
                    try:
                        user32 = ctypes.windll.user32
                        hwnd = int(win.winfo_id())
                        HWND_TOP = 0
                        SWP_NOMOVE = 0x0002
                        SWP_NOSIZE = 0x0001
                        SWP_SHOWWINDOW = 0x0040
                        user32.SetWindowPos(hwnd, HWND_TOP, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE | SWP_SHOWWINDOW)
                        user32.BringWindowToTop(hwnd)
                        user32.SetForegroundWindow(hwnd)
                    except Exception:
                        pass
            except Exception:
                pass

        try:
            win.after(700, release_topmost)
        except Exception:
            release_topmost()

    def _a224_keep_above_caller(self, win) -> None:
        """Keep Kontrollbehandling above Resultatvisninger, but not globally topmost."""
        try:
            if not win.winfo_exists():
                return
            # Re-assert the owner relationship after the native window is mapped.
            win.transient(self)
            win.lift(self)
            self.lower(win)
            win.focus_force()
        except Exception:
            pass

        if sys.platform.startswith("win"):
            try:
                user32 = ctypes.windll.user32
                child = int(win.winfo_id())
                parent = int(self.winfo_id())
                SWP_NOMOVE = 0x0002
                SWP_NOSIZE = 0x0001
                SWP_SHOWWINDOW = 0x0040
                # Child first, then place caller directly behind child.
                user32.SetWindowPos(child, 0, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE | SWP_SHOWWINDOW)
                user32.SetWindowPos(parent, child, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE | SWP_SHOWWINDOW)
                user32.BringWindowToTop(child)
                user32.SetForegroundWindow(child)
            except Exception:
                pass

    @staticmethod
    def _a224_status_marker(item: dict, review: dict) -> tuple[str, str]:
        rs = str(review.get("review_status") or "Ikke vurdert")
        cs = str(item.get("control_status") or "OK")
        if rs == "Krever avklaring":
            return "●", "Krever avklaring"
        if rs == "Akseptert avvik" or cs == "OBS":
            return "●", "Avvik"
        if rs == "OK":
            return "●", "OK"
        if rs == "Ikke relevant":
            return "○", "Ikke relevant"
        return "○", "Ikke vurdert"

    def _a224_summary_counts(self, index: int, items: list[dict]) -> dict[str, int]:
        counts = defaultdict(int)
        for item in items:
            review = self._a222_review_for(index, item["section"], item["label"], item["source"])
            _marker, label = self._a224_status_marker(item, review)
            counts[label] += 1
        return counts

    def _a224_description(self, item: dict) -> str:
        descriptions = {
            "Arkivdel": "Kontroll av arkivdelinformasjon i arkivstruktur.xml. Viser identitet og sentrale metadata for valgt arkivdel.",
            "systemID": "Kontroll av stabil systemidentifikator for valgt arkivdel.",
            "Mapper": "Antall mapper i valgt arkivdel.",
            "Saker (saksmappe)": "Antall mapper klassifisert som saksmappe. Sammenholdes med totalt antall mapper og mappetyper.",
            "Mappetyper": "Fordeling av mappetyper. Brukes til å forstå struktur og eventuelle uventede eller manglende typer.",
            "Registreringer": "Antall registreringer i valgt arkivdel.",
            "Journalposter": "Antall journalposter i valgt arkivdel.",
            "Registreringstyper": "Fordeling av registreringstyper.",
            "Journalposttyper": "Fordeling av journalposttyper, blant annet inngående, utgående og notat.",
            "Journalstatus": "Fordeling av journalstatus. Viktig ved vurdering av historisk arkivdanning og uferdige elementer.",
            "Dokumentbeskrivelser": "Antall dokumentbeskrivelser.",
            "Dokumentobjekter": "Antall dokumentobjekter og forholdet til dokumentbeskrivelser.",
            "Tilknytning til registrering": "Fordeling av dokumentenes tilknytning til registreringer.",
            "Dokumenttype": "Fordeling av dokumenttyper.",
            "Variantformat": "Fordeling av variantformat i dokumentobjektene.",
            "Versjonsnummer": "Fordeling av versjonsnummer i dokumentobjektene.",
            "Format (metadata)": "Rå formatmetadata fra Noark-uttrekket. Holdes atskilt fra faktisk filformat/PUID.",
            "Skjerminger": "Antall skjerminger i valgt arkivdel.",
            "Kassasjonsvedtak": "Antall kassasjonsvedtak.",
            "Utført kassasjon": "Antall registrerte utførte kassasjoner.",
            "Slettinger": "Antall registrerte slettinger.",
        }
        return descriptions.get(item.get("label"), "Kontroll fra det materialiserte Noark 5-resultatgrunnlaget.")

    def _a224_result_rows(self, index: int, item: dict) -> list[tuple[str, str]]:
        rows = [
            ("Kontrollstatus", str(item.get("control_status") or "–")),
            ("Resultat / verdi", str(item.get("value") or "–")),
            ("Kilde", str(item.get("source") or "–")),
        ]
        parts = getattr(self, "_archive_parts", None) or []
        if 0 <= index < len(parts):
            row = parts[index]
            ident = row.get("archive_part") or {}
            rows.extend([
                ("Arkivdel", str(ident.get("title") or "Alle arkivdeler")),
                ("systemID", str(ident.get("system_id") or "–")),
            ])
            try:
                period = self._effective_period(row, index)
                if isinstance(period, (tuple, list)) and len(period) >= 2:
                    rows.append(("Periode (observert)", f"{period[0]} – {period[1]}"))
            except Exception:
                pass
        return rows

    def _a224_related_rows(self, index: int) -> list[tuple[str, str, str]]:
        parts = getattr(self, "_archive_parts", None) or []
        if not (0 <= index < len(parts)):
            return []
        row = parts[index]
        ident = row.get("archive_part") or {}
        out = [
            ("arkivstruktur.xml", "arkivdel", str(ident.get("title") or "Alle arkivdeler")),
            ("arkivstruktur.xml", "systemID", str(ident.get("system_id") or "–")),
            ("mappe.xml", "Antall mapper", self._fmt_count(row.get("folder_count"))),
            ("registrering.xml", "Antall registreringer", self._fmt_count(row.get("registration_count"))),
            ("dokumentbeskrivelse.xml", "Antall dokumentbeskrivelser", self._fmt_count(row.get("document_description_count"))),
            ("dokumentobjekt.xml", "Antall dokumentobjekter", self._fmt_count(row.get("document_object_count"))),
        ]
        return out

    def _a224_review_point_count(self, index: int) -> int:
        archive = self._a222_archive_key(index)
        bucket = self._a222_reviews.get(archive) or {}
        return sum(1 for review in bucket.values()
                   if str(review.get("review_status") or "Ikke vurdert") not in ("", "Ikke vurdert", "OK", "Ikke relevant"))

    def _build_controls_tab(self, tab) -> None:
        """Controls tab with an explicit open-window state indicator."""
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_rowconfigure(2, weight=1)

        header = ctk.CTkFrame(tab, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=12, pady=(10, 3))
        header.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            header,
            text="Kontroller for valgt arkivdel",
            anchor="w",
            font=theme.font(theme.NORMAL_SIZE, weight="bold"),
        ).grid(row=0, column=0, sticky="ew")
        self._a224_open_button = ctk.CTkButton(
            header,
            text="Åpne behandlingsvindu",
            width=190,
            command=self._a222_open_control_window,
        )
        self._a224_open_button.grid(row=0, column=1, padx=(10, 0))

        self._a224_open_status = ctk.CTkLabel(
            tab,
            text="",
            anchor="w",
            justify="left",
            text_color=theme.TEXT_MUTED,
            font=theme.font(theme.SMALL_SIZE),
        )
        self._a224_open_status.grid(row=1, column=0, sticky="ew", padx=14, pady=(0, 4))

        self._a1625_control_body = ctk.CTkScrollableFrame(tab)
        self._a1625_control_body.grid(row=2, column=0, sticky="nsew", padx=12, pady=(0, 12))
        self._a1625_control_body.grid_columnconfigure(0, weight=1)
        self._a10_controls = ctk.CTkTextbox(tab, width=1, height=1)

    def _a224_set_control_window_state(self, is_open: bool) -> None:
        button = getattr(self, "_a224_open_button", None)
        label = getattr(self, "_a224_open_status", None)
        try:
            if button is not None:
                button.configure(text="Hent frem behandlingsvindu" if is_open else "Åpne behandlingsvindu")
        except Exception:
            pass
        try:
            if label is not None:
                label.configure(text=(
                    "Kontrollbehandling er åpent. Valg av arkivdel synkroniseres automatisk."
                    if is_open else ""
                ))
        except Exception:
            pass

    def _show_archive_part(self, index: int) -> None:
        super()._show_archive_part(index)
        sync = getattr(self, "_a224_control_sync", None)
        win = getattr(self, "_a222_control_window", None)
        if sync is not None and win is not None:
            try:
                if win.winfo_exists():
                    sync(int(index))
            except Exception:
                pass

    def _a171_archive_click(self, index: int) -> None:
        """Keep the open control workspace synchronized with archive-part clicks.

        a17 intentionally calls super()._show_archive_part() directly, which bypasses
        later _show_archive_part overrides.  Therefore synchronization must hook the
        actual archive click path rather than polling only _archive_index.
        """
        super()._a171_archive_click(index)

        sync = getattr(self, "_a224_control_sync", None)
        win = getattr(self, "_a222_control_window", None)
        if sync is None or win is None:
            return
        try:
            if not win.winfo_exists():
                return
        except Exception:
            return

        parts = getattr(self, "_archive_parts", None) or []
        target = None
        selected = set(getattr(self, "_a171_selected", set()) or set())
        virtual_index = getattr(self, "_a171_virtual_index", None)
        if len(selected) > 1 and virtual_index is not None:
            target = int(virtual_index)
        elif len(selected) == 1:
            target = int(next(iter(selected)))
        else:
            # All archive parts / empty selection.
            target = next(
                (i for i, row in enumerate(parts) if row.get("is_all_archive_parts")),
                int(getattr(self, "_archive_index", 0) or 0),
            )
        try:
            sync(target)
        except Exception:
            pass

    def _a222_open_control_window(self) -> None:
        existing = getattr(self, "_a222_control_window", None)
        if existing is not None:
            try:
                if existing.winfo_exists():
                    self._a224_force_foreground(existing)
                    self.after(120, lambda: self._a224_keep_above_caller(existing))
                    return
            except Exception:
                pass

        index = int(getattr(self, "_archive_index", 0) or 0)
        items = self._a222_control_items(index)
        win = ctk.CTkToplevel(self)
        self._a222_control_window = win
        win.title("Kontrollbehandling – Noark 5")
        win.geometry("1500x900")
        win.minsize(1100, 700)
        win.resizable(True, True)
        def close_control_window():
            self._a224_control_sync = None
            self._a222_control_window = None
            self._a224_set_control_window_state(False)
            try:
                win.destroy()
            except Exception:
                pass

        win.protocol("WM_DELETE_WINDOW", close_control_window)
        win.bind("<Destroy>", lambda event: self._a224_set_control_window_state(False) if event.widget is win else None, add="+")
        self._a224_set_control_window_state(True)
        win.grid_columnconfigure(1, weight=1)
        win.grid_rowconfigure(1, weight=1)
        win.after(60, lambda: self._a224_force_foreground(win))
        win.after(180, lambda: self._a224_keep_above_caller(win))
        win.after(350, lambda: self._a224_force_foreground(win))
        win.after(550, lambda: self._a224_keep_above_caller(win))
        win.after(900, lambda: self._a224_force_foreground(win))
        win.after(1200, lambda: self._a224_keep_above_caller(win))

        # ----- Context header -------------------------------------------------
        top = ctk.CTkFrame(win)
        top.grid(row=0, column=0, columnspan=2, sticky="ew", padx=10, pady=(8, 6))
        for c in range(3):
            top.grid_columnconfigure(c, weight=1)
        parts = getattr(self, "_archive_parts", None) or []
        selected_row = parts[index] if 0 <= index < len(parts) else {}
        ident = selected_row.get("archive_part") or {}
        title_text = ident.get("title") or "Alle arkivdeler"
        ctk.CTkLabel(top, text=f"Uttrekk: {getattr(self, '_extraction_label', '') or ''}   |   Arkivdeler: {max(0, len(parts)-1)}",
                     anchor="w", font=theme.font(theme.SMALL_SIZE, weight="bold")).grid(row=0, column=0, sticky="ew", padx=12, pady=8)
        selected_archive_label = ctk.CTkLabel(
            top, text=f"Valgt arkivdel:\n{title_text}", anchor="w", justify="left",
            font=theme.font(theme.SMALL_SIZE, weight="bold"),
        )
        selected_archive_label.grid(row=0, column=1, sticky="ew", padx=12, pady=8)
        summary_label = ctk.CTkLabel(top, text="", anchor="e", justify="right", font=theme.font(theme.SMALL_SIZE, weight="bold"))
        summary_label.grid(row=0, column=2, sticky="ew", padx=12, pady=8)

        # ----- Left control navigator ---------------------------------------
        nav = ctk.CTkFrame(win, width=330)
        nav.grid(row=1, column=0, sticky="nsew", padx=(10, 5), pady=(0, 10))
        nav.grid_columnconfigure(0, weight=1)
        nav.grid_rowconfigure(3, weight=1)
        ctk.CTkLabel(nav, text="Kontroller", anchor="w", font=theme.font(theme.TITLE_SIZE, weight="bold")).grid(row=0, column=0, sticky="ew", padx=12, pady=(10, 4))
        filter_var = ctk.StringVar(value="")
        filter_entry = ctk.CTkEntry(nav, textvariable=filter_var, placeholder_text="Filtrer kontroller...")
        filter_entry.grid(row=1, column=0, sticky="ew", padx=10, pady=(0, 6))
        filter_actions = ctk.CTkFrame(nav, fg_color="transparent")
        filter_actions.grid(row=2, column=0, sticky="ew", padx=10, pady=(0, 4))
        filter_actions.grid_columnconfigure((0, 1), weight=1)
        tree = ctk.CTkScrollableFrame(nav)
        tree.grid(row=3, column=0, sticky="nsew", padx=6, pady=(0, 8))
        tree.grid_columnconfigure(0, weight=1)

        # ----- Main workspace ------------------------------------------------
        work = ctk.CTkFrame(win)
        work.grid(row=1, column=1, sticky="nsew", padx=(5, 10), pady=(0, 10))
        work.grid_columnconfigure(0, weight=1)
        work.grid_rowconfigure(2, weight=1)

        control_header = ctk.CTkFrame(work, fg_color="transparent")
        control_header.grid(row=0, column=0, sticky="ew", padx=12, pady=(10, 4))
        control_header.grid_columnconfigure(0, weight=1)
        control_title = ctk.CTkLabel(control_header, text="Velg en kontroll", anchor="w", font=theme.font(theme.HEADER_SIZE, weight="bold"))
        control_title.grid(row=0, column=0, sticky="ew")
        control_meta = ctk.CTkLabel(control_header, text="", anchor="e", text_color=theme.TEXT_MUTED, font=theme.font(theme.SMALL_SIZE))
        control_meta.grid(row=0, column=1, sticky="e", padx=(10, 0))
        control_description = ctk.CTkLabel(work, text="", anchor="w", justify="left", text_color=theme.TEXT_SUB, font=theme.font(theme.SMALL_SIZE))
        control_description.grid(row=1, column=0, sticky="ew", padx=12, pady=(0, 4))

        tabs = ctk.CTkTabview(work)
        tabs.grid(row=2, column=0, sticky="nsew", padx=10, pady=(0, 8))
        for name in ("Resultat og evidens", "Beskrivelse", "Relaterte kontroller", "Vurderingspunkter"):
            tabs.add(name)

        # Result/evidence: 2-column top + lower evidence/data
        result_tab = tabs.tab("Resultat og evidens")
        result_tab.grid_columnconfigure(0, weight=3)
        result_tab.grid_columnconfigure(1, weight=2)
        result_tab.grid_rowconfigure(1, weight=1)
        result_box = ctk.CTkFrame(result_tab)
        result_box.grid(row=0, column=0, sticky="nsew", padx=(5, 4), pady=5)
        result_box.grid_columnconfigure(1, weight=1)
        result_chart = ctk.CTkFrame(result_tab)
        result_chart.grid(row=0, column=1, sticky="nsew", padx=(4, 5), pady=5)
        result_chart.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(result_chart, text="Kontrollkontekst", anchor="w", font=theme.font(theme.NORMAL_SIZE, weight="bold")).grid(row=0, column=0, sticky="ew", padx=10, pady=(8, 4))
        context_text = ctk.CTkLabel(result_chart, text="", anchor="nw", justify="left", wraplength=430, font=theme.font(theme.SMALL_SIZE))
        context_text.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 8))

        lower = ctk.CTkFrame(result_tab)
        lower.grid(row=1, column=0, columnspan=2, sticky="nsew", padx=5, pady=(0, 5))
        lower.grid_columnconfigure(0, weight=1)
        lower.grid_rowconfigure(1, weight=1)
        ctk.CTkLabel(lower, text="Evidens og relaterte data", anchor="w", font=theme.font(theme.NORMAL_SIZE, weight="bold")).grid(row=0, column=0, sticky="ew", padx=10, pady=(8, 4))
        related = ctk.CTkTextbox(lower, wrap="none", font=theme.font(theme.SMALL_SIZE))
        related.grid(row=1, column=0, sticky="nsew", padx=8, pady=(0, 8))
        related.configure(state="disabled")

        desc_tab = tabs.tab("Beskrivelse")
        desc_tab.grid_columnconfigure(0, weight=1)
        desc_text = ctk.CTkTextbox(desc_tab, wrap="word", font=theme.font(theme.NORMAL_SIZE))
        desc_text.grid(row=0, column=0, sticky="nsew", padx=8, pady=8)
        desc_text.configure(state="disabled")

        rel_tab = tabs.tab("Relaterte kontroller")
        rel_tab.grid_columnconfigure(0, weight=1)
        rel_text = ctk.CTkTextbox(rel_tab, wrap="word", font=theme.font(theme.SMALL_SIZE))
        rel_text.grid(row=0, column=0, sticky="nsew", padx=8, pady=8)
        rel_text.configure(state="disabled")

        vp_tab = tabs.tab("Vurderingspunkter")
        vp_tab.grid_columnconfigure(0, weight=1)
        vp_text = ctk.CTkTextbox(vp_tab, wrap="word", font=theme.font(theme.SMALL_SIZE))
        vp_text.grid(row=0, column=0, sticky="nsew", padx=8, pady=8)
        vp_text.configure(state="disabled")

        # Review strip below tabs, optional not mandatory
        review = ctk.CTkFrame(work)
        review.grid(row=3, column=0, sticky="ew", padx=10, pady=(0, 6))
        review.grid_columnconfigure(2, weight=1)
        ctk.CTkLabel(review, text="Faglig vurdering (valgfri)", anchor="w", font=theme.font(theme.NORMAL_SIZE, weight="bold")).grid(row=0, column=0, columnspan=4, sticky="ew", padx=10, pady=(8, 4))
        ctk.CTkLabel(review, text="Status", anchor="w", font=theme.font(theme.SMALL_SIZE, weight="bold")).grid(row=1, column=0, sticky="w", padx=(10, 4), pady=(0, 8))
        status_var = ctk.StringVar(value="Ikke vurdert")
        status_menu = ctk.CTkOptionMenu(review, variable=status_var, values=list(self.REVIEW_STATUSES), width=180)
        status_menu.grid(row=1, column=1, sticky="w", padx=(0, 8), pady=(0, 8))
        comment = ctk.CTkEntry(review, placeholder_text="Kommentar bare når det er behov for faglig behandling")
        comment.grid(row=1, column=2, sticky="ew", padx=(0, 8), pady=(0, 8))

        selected = {"pos": -1, "item": None}
        groups: dict[str, list[tuple[int, dict]]] = defaultdict(list)
        for pos, item in enumerate(items):
            groups[item["section"]].append((pos, item))
        expanded = {name: True for name in groups}
        tree_buttons: list[tuple[ctk.CTkButton, int, dict]] = []

        def set_text(widget, value: str):
            widget.configure(state="normal")
            widget.delete("1.0", "end")
            widget.insert("1.0", value)
            widget.configure(state="disabled")

        def refresh_summary():
            counts = self._a224_summary_counts(index, items)
            summary_label.configure(text=(
                f"Kontroller totalt: {len(items)}\n"
                f"OK: {counts['OK']}   ·   Avvik: {counts['Avvik']}   ·   "
                f"Krever avklaring: {counts['Krever avklaring']}   ·   Ikke vurdert: {counts['Ikke vurdert']}"
            ))

        def render_result_rows(item):
            for child in result_box.winfo_children():
                child.destroy()
            ctk.CTkLabel(result_box, text=f"Kontrollresultat – {item['label']}", anchor="w", font=theme.font(theme.NORMAL_SIZE, weight="bold")).grid(row=0, column=0, columnspan=2, sticky="ew", padx=10, pady=(8, 4))
            for rr, (label, value) in enumerate(self._a224_result_rows(index, item), start=1):
                ctk.CTkLabel(result_box, text=label, anchor="w", font=theme.font(theme.SMALL_SIZE)).grid(row=rr, column=0, sticky="ew", padx=(10, 6), pady=2)
                ctk.CTkLabel(result_box, text=value, anchor="w", justify="left", wraplength=420, font=theme.font(theme.SMALL_SIZE, weight="bold")).grid(row=rr, column=1, sticky="ew", padx=(6, 10), pady=2)

        def refresh_related_text(item):
            rows = self._a224_related_rows(index)
            lines = [f"Valgt kontroll: {item['label']}", f"Kilde: {item['source']}", "", "Kilde                     Element                         Verdi", "-" * 92]
            for source, element, value in rows:
                lines.append(f"{source:<25} {element:<30} {value}")
            lines.extend(["", "Kontrollverdi:", str(item.get("value") or "–")])
            set_text(related, "\n".join(lines))

        def refresh_related_controls(item):
            same_section = [x for x in items if x["section"] == item["section"] and x is not item]
            lines = [f"Samme seksjon: {item['section']}", ""]
            for x in same_section:
                review_data = self._a222_review_for(index, x["section"], x["label"], x["source"])
                _m, lab = self._a224_status_marker(x, review_data)
                lines.append(f"• {x['label']}   [{lab}]   {x['value']}")
            set_text(rel_text, "\n".join(lines) if same_section else "Ingen relaterte kontroller i samme seksjon.")

        def refresh_vp(item):
            review_data = self._a222_review_for(index, item["section"], item["label"], item["source"])
            lines = [f"Kontroll: {item['label']}", f"Vurderingsstatus: {review_data.get('review_status') or 'Ikke vurdert'}"]
            if review_data.get("comment"):
                lines.extend(["", "Kommentar:", str(review_data.get("comment"))])
            lines.extend(["", f"Samlet antall vurderingspunkter/avvik for valgt arkivdel: {self._a224_review_point_count(index)}"])
            set_text(vp_text, "\n".join(lines))

        def choose_pos(pos: int):
            if not items:
                return
            pos = max(0, min(pos, len(items) - 1))
            item = items[pos]
            selected["pos"] = pos
            selected["item"] = item
            review_data = self._a222_review_for(index, item["section"], item["label"], item["source"])
            _marker, status_label = self._a224_status_marker(item, review_data)
            control_title.configure(text=f"{item['label']}   ·   {status_label}")
            control_meta.configure(text=f"Seksjon: {item['section']}   |   Kilde: {item['source']}   |   Kontroll {pos + 1} av {len(items)}")
            control_description.configure(text=self._a224_description(item))
            status_var.set(str(review_data.get("review_status") or "Ikke vurdert"))
            comment.delete(0, "end")
            comment.insert(0, str(review_data.get("comment") or ""))
            render_result_rows(item)
            context_text.configure(text=self._a223_context_text(index, item))
            refresh_related_text(item)
            set_text(desc_text, self._a224_description(item) + "\n\nKilde: " + str(item.get("source") or "–") + "\nKontrollverdi: " + str(item.get("value") or "–"))
            refresh_related_controls(item)
            refresh_vp(item)
            for button, bpos, _ in tree_buttons:
                button.configure(
                    border_width=0,
                    fg_color=theme.BLUE if bpos == pos else theme.BUTTON_BG,
                    hover_color=theme.BLUE_HOVER if bpos == pos else theme.BUTTON_HOVER,
                    text_color=theme.BUTTON_TEXT,
                )

        def save_current(show_message=False):
            item = selected.get("item")
            if item is None:
                return False
            self._a222_set_review(index, item, status_var.get(), comment.get())
            self._render_structured_controls(index)
            self._a222_render_review_points(index)
            refresh_summary()
            render_tree()
            choose_pos(selected["pos"])
            if show_message:
                messagebox.showinfo("Data Workflow Manager", "Vurderingen er lagret.", parent=win)
            return True

        ctk.CTkButton(review, text="Lagre vurdering", width=130, command=lambda: save_current(True)).grid(row=1, column=3, sticky="e", padx=(0, 10), pady=(0, 8))

        # Bottom orientation/navigation
        bottom = ctk.CTkFrame(work, fg_color="transparent")
        bottom.grid(row=4, column=0, sticky="ew", padx=10, pady=(0, 10))
        bottom.grid_columnconfigure(2, weight=1)
        ctk.CTkButton(bottom, text="← Forrige kontroll", width=145, command=lambda: choose_pos(selected["pos"] - 1)).grid(row=0, column=0, padx=(0, 6))
        ctk.CTkButton(bottom, text="Neste kontroll →", width=145, command=lambda: choose_pos(selected["pos"] + 1)).grid(row=0, column=1, padx=(0, 10))
        progress_label = ctk.CTkLabel(bottom, text="", anchor="w", text_color=theme.TEXT_MUTED, font=theme.font(theme.SMALL_SIZE))
        progress_label.grid(row=0, column=2, sticky="ew")
        ctk.CTkButton(bottom, text="Lukk", width=90, command=close_control_window).grid(row=0, column=3, padx=(8, 0))

        def render_tree(*_args):
            for child in tree.winfo_children():
                child.destroy()
            tree_buttons.clear()
            needle = filter_var.get().strip().casefold()
            rr = 0
            for section, group_items in groups.items():
                visible = [(pos, item) for pos, item in group_items if not needle or needle in item["label"].casefold() or needle in item["value"].casefold()]
                if not visible:
                    continue
                section_button = ctk.CTkButton(
                    tree, text=("▼ " if expanded[section] else "▶ ") + f"{section}  ({len(visible)})",
                    anchor="w", fg_color="transparent", hover_color=theme.CARD_BG,
                    command=lambda s=section: (expanded.__setitem__(s, not expanded[s]), render_tree()),
                )
                section_button.grid(row=rr, column=0, sticky="ew", padx=2, pady=(5, 1))
                rr += 1
                if not expanded[section]:
                    continue
                for pos, item in visible:
                    review_data = self._a222_review_for(index, item["section"], item["label"], item["source"])
                    marker, lab = self._a224_status_marker(item, review_data)
                    text = f"  {marker}  {item['label']}   ·   {lab}"
                    b = ctk.CTkButton(
                        tree, text=text, anchor="w", height=29,
                        fg_color=theme.BUTTON_BG, hover_color=theme.BUTTON_HOVER,
                        text_color=theme.BUTTON_TEXT,
                        command=lambda p=pos: choose_pos(p),
                    )
                    b.grid(row=rr, column=0, sticky="ew", padx=2, pady=1)
                    tree_buttons.append((b, pos, item))
                    rr += 1
            if selected["pos"] >= 0:
                for b, bpos, _ in tree_buttons:
                    b.configure(
                        border_width=0,
                        fg_color=theme.BLUE if bpos == selected["pos"] else theme.BUTTON_BG,
                        hover_color=theme.BLUE_HOVER if bpos == selected["pos"] else theme.BUTTON_HOVER,
                        text_color=theme.BUTTON_TEXT,
                    )
            review_counts = self._a224_summary_counts(index, items)
            progress_label.configure(text=f"Kontroll {max(0, selected['pos'] + 1)} av {len(items)}   |   Vurdert: {len(items) - review_counts['Ikke vurdert']}   |   Ikke vurdert: {review_counts['Ikke vurdert']}")

        def sync_context(new_index: int):
            nonlocal index, items, groups, expanded
            parts_now = getattr(self, "_archive_parts", None) or []
            if not (0 <= int(new_index) < len(parts_now)):
                return
            index = int(new_index)
            items = self._a222_control_items(index)
            groups = defaultdict(list)
            for pos, item in enumerate(items):
                groups[item["section"]].append((pos, item))
            expanded = {name: True for name in groups}
            selected["pos"] = -1
            selected["item"] = None

            row_now = parts_now[index]
            ident_now = row_now.get("archive_part") or {}
            archive_title = ident_now.get("title") or "Alle arkivdeler"
            selected_archive_label.configure(text=f"Valgt arkivdel:\\n{archive_title}")
            refresh_summary()
            render_tree()
            if items:
                choose_pos(0)

        self._a224_control_sync = sync_context

        # Keep the work window tied to the archive-part selection even when the
        # caller changes selection through a rendering path that bypasses
        # _show_archive_part().
        last_archive_index = {"value": index}

        def poll_archive_selection():
            try:
                if not win.winfo_exists():
                    return
                current = int(getattr(self, "_archive_index", 0) or 0)
                if current != last_archive_index["value"]:
                    last_archive_index["value"] = current
                    sync_context(current)
                win.after(200, poll_archive_selection)
            except Exception:
                pass

        win.after(200, poll_archive_selection)

        def set_all(value: bool):
            for section in expanded:
                expanded[section] = value
            render_tree()

        ctk.CTkButton(filter_actions, text="Utvid alle", height=28, command=lambda: set_all(True)).grid(row=0, column=0, sticky="ew", padx=(0, 3))
        ctk.CTkButton(filter_actions, text="Skjul alle", height=28, command=lambda: set_all(False)).grid(row=0, column=1, sticky="ew", padx=(3, 0))
        filter_var.trace_add("write", render_tree)

        refresh_summary()
        render_tree()
        if items:
            choose_pos(0)
