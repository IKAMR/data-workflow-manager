from __future__ import annotations

import customtkinter as ctk
from tkinter import messagebox

from . import theme
from .depot_result_center_a23_1 import DepotResultCenterDialogA23_1


class DepotResultCenterDialogA23_2(DepotResultCenterDialogA23_1):
    """a23.2: structured visual evidence for the Arkivdel control.

    a23.1 introduced control-specific evidence. a23.2 starts the visual
    treatment of that evidence without changing the underlying materialized
    values or running new analysis.
    """

    def _a232_clear(self, frame) -> None:
        for child in frame.winfo_children():
            child.destroy()

    def _a232_card(self, parent, row: int, title: str, values: list[tuple[str, str]], *, columns: int = 2) -> None:
        card = ctk.CTkFrame(parent, fg_color=theme.CARD_BG, border_width=1, border_color=theme.CARD_BORDER)
        card.grid(row=row, column=0, sticky="ew", padx=2, pady=(0, 8))
        for col in range(columns * 2):
            card.grid_columnconfigure(col, weight=1 if col % 2 else 0)
        ctk.CTkLabel(
            card,
            text=title,
            anchor="w",
            font=theme.font(theme.SMALL_SIZE, weight="bold"),
        ).grid(row=0, column=0, columnspan=columns * 2, sticky="ew", padx=10, pady=(8, 5))
        for idx, (label, value) in enumerate(values):
            rr = 1 + idx // columns
            cc = (idx % columns) * 2
            ctk.CTkLabel(
                card,
                text=label,
                anchor="w",
                text_color=theme.TEXT_MUTED,
                font=theme.font(theme.SMALL_SIZE),
            ).grid(row=rr, column=cc, sticky="w", padx=(10, 5), pady=3)
            ctk.CTkLabel(
                card,
                text=value,
                anchor="w",
                justify="left",
                font=theme.font(theme.SMALL_SIZE, weight="bold"),
            ).grid(row=rr, column=cc + 1, sticky="ew", padx=(0, 14), pady=3)
        bottom = 1 + ((len(values) - 1) // columns if values else 0)
        card.grid_rowconfigure(bottom + 1, minsize=5)

    def _a232_render_archive_part(self, parent, index: int, row: dict, item: dict) -> None:
        identity = row.get("archive_part") or {}
        try:
            period = self._effective_period(row, index)
            if isinstance(period, (tuple, list)) and len(period) >= 2:
                observed = f"{period[0] or '–'}–{period[1] or '–'}"
            else:
                observed = str(period or "–")
        except Exception:
            observed = "–"

        self._a232_card(parent, 0, "Identitet", [
            ("Navn", self._a231_value(identity.get("title"))),
            ("Kortnavn", self._a231_value(identity.get("short_name") or identity.get("shortName"))),
            ("systemID", self._a231_value(identity.get("system_id"))),
            ("Observert periode", observed),
        ], columns=1)

        self._a232_card(parent, 1, "Omfang", [
            ("Mapper", self._fmt_count(row.get("folder_count"))),
            ("Registreringer", self._fmt_count(row.get("registration_count"))),
            ("Journalposter", self._fmt_count(row.get("journalpost_count"))),
            ("Dokumentbeskrivelser", self._fmt_count(row.get("document_description_count"))),
            ("Dokumentobjekter", self._fmt_count(row.get("document_object_count"))),
        ], columns=2)

        self._a232_card(parent, 2, "Kontrollgrunnlag", [
            ("Kontrollstatus", str(item.get("control_status") or "–")),
            ("Kilde", str(item.get("source") or "–")),
            ("Resultat / verdi", str(item.get("value") or "–")),
        ], columns=1)

        note = ctk.CTkFrame(parent, fg_color="transparent")
        note.grid(row=3, column=0, sticky="ew", padx=2, pady=(2, 8))
        ctk.CTkLabel(
            note,
            text="Visningen bruker det allerede materialiserte kontrollgrunnlaget. Faglig behandling endrer ikke kildeverdiene.",
            anchor="w",
            justify="left",
            wraplength=650,
            text_color=theme.TEXT_MUTED,
            font=theme.font(theme.SMALL_SIZE),
        ).grid(row=0, column=0, sticky="ew")

    def _a232_render_evidence(self, parent, index: int, item: dict) -> None:
        self._a232_clear(parent)
        parts = getattr(self, "_archive_parts", None) or []
        label = str(item.get("label") or "")
        if label == "Arkivdel" and 0 <= index < len(parts):
            self._a232_render_archive_part(parent, index, parts[index], item)
            return

        # Other controls keep the a23.1 control-specific text for now. This is
        # deliberate: a23.2 establishes the visual pattern with one complete
        # representative control before the same pattern is expanded further.
        text = ctk.CTkTextbox(parent, wrap="word", font=theme.font(theme.SMALL_SIZE))
        text.grid(row=0, column=0, sticky="nsew", padx=0, pady=0)
        parent.grid_rowconfigure(0, weight=1)
        parent.grid_columnconfigure(0, weight=1)
        text.insert("1.0", self._a223_context_text(index, item))
        text.configure(state="disabled")

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
        evidence = ctk.CTkScrollableFrame(evidence_frame, fg_color="transparent")
        evidence.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 10))
        evidence.grid_columnconfigure(0, weight=1)

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
            for _pos, (button, item) in enumerate(buttons):
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
            # Circular navigation: Neste from the last control returns to
            # the first control, and Forrige from the first returns to the last.
            pos = pos % len(items)
            item = items[pos]
            selected["pos"] = pos
            selected["item"] = item
            title.configure(text=item["label"])
            meta.configure(text=f"Seksjon: {item['section']}   ·   Kilde: {item['source']}   ·   Kontrollstatus: {item['control_status']}   ·   Kontroll {pos + 1} av {len(items)}")
            self._a232_render_evidence(evidence, index, item)
            review = self._a222_review_for(index, item["section"], item["label"], item["source"])
            status_var.set(str(review.get("review_status") or "Ikke vurdert"))
            comment.delete("1.0", "end")
            comment.insert("1.0", str(review.get("comment") or ""))
            for button_pos, (button, _button_item) in enumerate(buttons):
                if button_pos == pos:
                    button.configure(fg_color=theme.BLUE, hover_color=theme.BLUE, border_width=0)
                else:
                    button.configure(fg_color=theme.BUTTON_BG, hover_color=theme.BUTTON_HOVER, border_width=0)
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
