from __future__ import annotations

import copy

import customtkinter as ctk

from noark5_workflow.analysis.archive_parts_summary import build_all_archive_parts_summary
from . import theme
from .depot_result_center_a16_11 import DepotResultCenterDialogA16_11


class DepotResultCenterDialogA16_12(DepotResultCenterDialogA16_11):
    """a16.12: aggregate archive-part workspace and reliably compact annual tab."""

    ALL_ID = "__ALL_ARCHIVE_PARTS__"

    def __init__(self, master, **kwargs) -> None:
        model = copy.deepcopy(kwargs.get("model") or {})
        all_summary = model.get("all_archive_parts_summary") or build_all_archive_parts_summary(model)
        model["all_archive_parts_summary"] = all_summary
        real_rows = list(model.get("archive_parts") or [])
        model["archive_parts"] = [self._aggregate_row(all_summary)] + real_rows
        self._a1612_real_archive_count = len(real_rows)
        kwargs["model"] = model

        super().__init__(master, **kwargs)
        self._reorder_archive_tabs()
        self._compact_per_year_surface()
        self._fix_archive_count_labels()
        self._refresh_all_archive_card()
        if getattr(self, "_archive_parts", None):
            self._show_archive_part(0)

    @classmethod
    def _aggregate_row(cls, summary: dict) -> dict:
        declared = summary.get("declared_period") or {}
        return {
            "archive_part": {
                "system_id": cls.ALL_ID,
                "title": "Alle arkivdeler",
                "name": "Alle arkivdeler",
                "archive_period_start_date": declared.get("start_date"),
                "archive_period_end_date": declared.get("end_date"),
                "aggregate": True,
            },
            "folder_count": summary.get("folder_count"),
            "registration_count": summary.get("registration_count"),
            "journalpost_count": summary.get("journalpost_count"),
            "document_description_count": summary.get("document_description_count"),
            "document_object_count": summary.get("document_object_count"),
            "screening_count": summary.get("screening_count"),
            "disposal_decision_count": summary.get("disposal_decision_count"),
            "performed_disposal_count": summary.get("performed_disposal_count"),
            "deletion_count": summary.get("deletion_count"),
            "yearly_volume": summary.get("yearly_volume") or {},
            "sources": {},
            "is_all_archive_parts": True,
        }

    def _reorder_archive_tabs(self) -> None:
        tabs = getattr(self, "_a10_tabs", None)
        if tabs is None:
            return
        wanted = ["Sammendrag", "Per år", "Kontroller", "Vurderingspunkter"]
        for index, name in enumerate(wanted):
            try:
                tabs.move(index, name)
            except Exception:
                pass
        try:
            current = list(getattr(tabs, "_name_list", []))
            ordered = [name for name in wanted if name in current]
            ordered.extend(name for name in current if name not in ordered)
            tabs._name_list = ordered
            tabs._segmented_button.configure(values=ordered)
        except Exception:
            pass

    def _compact_per_year_surface(self) -> None:
        tabs = getattr(self, "_a10_tabs", None)
        panel = getattr(self, "_a15_year_panel", None)
        table = getattr(self, "_a166_table", None)
        if tabs is None or panel is None:
            return
        try:
            tab = tabs.tab("Per år")
            tab.grid_columnconfigure(0, weight=0)
            tab.grid_columnconfigure(1, weight=1)
            tab.grid_rowconfigure(0, weight=0)
            panel.grid_configure(sticky="nw", padx=(4, 0), pady=4)
            panel.configure(width=760)
        except Exception:
            pass
        if table is not None:
            try:
                table.configure(width=720, height=410)
                table.grid_configure(sticky="nw")
            except Exception:
                pass

    def _fix_archive_count_labels(self) -> None:
        expected = f"{self._a1612_real_archive_count} arkivdel(er)"
        synthetic = f"{self._a1612_real_archive_count + 1} arkivdel(er)"

        def walk(widget):
            for child in widget.winfo_children():
                if isinstance(child, ctk.CTkLabel):
                    try:
                        if str(child.cget("text")) == synthetic:
                            child.configure(text=expected)
                    except Exception:
                        pass
                walk(child)
        walk(self)

    def _refresh_all_archive_card(self) -> None:
        buttons = getattr(self, "_archive_buttons", [])
        if not buttons:
            return
        summary = self.model.get("all_archive_parts_summary") or {}
        observed = summary.get("observed_period") or {}
        first = observed.get("first_year") or "–"
        last = observed.get("last_year") or "–"
        buttons[0].configure(
            text=(
                "Alle arkivdeler\n"
                f"{self._a1612_real_archive_count} arkivdeler · samlet uttrekk\n"
                f"Sum alle tall  |  obs. {first}–{last}"
            ),
            height=72,
        )
        search = getattr(self, "_archive_search_text", None)
        if isinstance(search, list) and search:
            search[0] = "alle arkivdeler samlet uttrekk total sum"

    def _show_archive_part(self, index: int) -> None:
        super()._show_archive_part(index)
        if not getattr(self, "_archive_parts", None):
            return
        row = self._archive_parts[index]
        if not row.get("is_all_archive_parts"):
            return
        summary = self.model.get("all_archive_parts_summary") or {}
        declared = summary.get("declared_period") or {}
        observed = summary.get("observed_period") or {}
        declared_text = f"{declared.get('start_date') or '–'} → {declared.get('end_date') or '–'}"
        observed_text = f"{observed.get('first_year') or '–'}–{observed.get('last_year') or '–'}"
        try:
            self._archive_title.configure(text="Alle arkivdeler")
            self._archive_subtitle.configure(
                text=(
                    f"Samlet for {self._a1612_real_archive_count} arkivdeler   |   "
                    f"Oppgitt uttrekksperiode: {declared_text}   |   Observert: {observed_text}"
                )
            )
        except Exception:
            pass
        period_text = getattr(self, "_a164_period_text", None)
        if period_text is not None:
            period_text.configure(text=(
                f"Hele uttrekket oppgitt: {declared_text}   |   Observert aktivitet: {observed_text}\n"
                "Årsgrensene er summert fra alle arkivdeler. Eksakte observerte første/siste datoer "
                "vises når dette er materialisert eksplisitt i kildetestene."
            ))

    def _render_a166(self, index: int) -> None:
        table = getattr(self, "_a166_table", None)
        if table is None:
            return
        for child in table.winfo_children():
            child.destroy()

        row = self._archive_parts[index]
        values = {key: self._series(row, key) for key, _label in self._SERIES}
        years = sorted({y for data in values.values() for y, n in data.items() if n > 0})
        headers = ("År", "Mapper/saker", "Registrering/JP", "Dok.beskr.", "Dok.objekter")
        widths = (52, 106, 118, 108, 108)
        for col, (label, width) in enumerate(zip(headers, widths)):
            table.grid_columnconfigure(col, weight=0, minsize=width)
            ctk.CTkLabel(table, text=label, anchor="e" if col else "w",
                         font=theme.font(theme.SMALL_SIZE, weight="bold")).grid(
                row=0, column=col, sticky="ew", padx=4, pady=(1, 3))
        if not years:
            ctk.CTkLabel(table, text="Ingen årsfordeling materialisert.", anchor="w",
                         text_color=theme.TEXT_MUTED, font=theme.font(theme.SMALL_SIZE)).grid(
                row=1, column=0, columnspan=5, sticky="w", padx=4, pady=5)
            return

        keys = ("folder", "journal", "document_description", "document_object")
        totals = {key: 0 for key in keys}
        for r, year in enumerate(years, start=1):
            ctk.CTkLabel(table, text=str(year), anchor="w",
                         font=theme.font(theme.SMALL_SIZE, weight="bold")).grid(
                row=r, column=0, sticky="ew", padx=4, pady=0)
            for col, key in enumerate(keys, start=1):
                n = int(values[key].get(year, 0) or 0)
                totals[key] += n
                ctk.CTkLabel(table, text=f"{n:,}".replace(",", " "), anchor="e",
                             font=theme.font(theme.SMALL_SIZE)).grid(
                    row=r, column=col, sticky="ew", padx=4, pady=0)
        total_row = len(years) + 1
        ctk.CTkLabel(table, text="Sum", anchor="w",
                     font=theme.font(theme.SMALL_SIZE, weight="bold")).grid(
            row=total_row, column=0, sticky="ew", padx=4, pady=(3, 1))
        for col, key in enumerate(keys, start=1):
            ctk.CTkLabel(table, text=f"{totals[key]:,}".replace(",", " "), anchor="e",
                         font=theme.font(theme.SMALL_SIZE, weight="bold")).grid(
                row=total_row, column=col, sticky="ew", padx=4, pady=(3, 1))

    def _render_a169_controls(self, index: int) -> None:
        if self._archive_parts[index].get("is_all_archive_parts"):
            table = getattr(self, "_a168_controls_table", None)
            if table is None:
                return
            for child in table.winfo_children():
                child.destroy()
            s = self.model.get("all_archive_parts_summary") or {}
            items = (
                ("Arkivdeler", s.get("archive_part_count")),
                ("Mapper/saker", s.get("folder_count")),
                ("Registreringer", s.get("registration_count")),
                ("Journalposter", s.get("journalpost_count")),
                ("Dokumentbeskrivelser", s.get("document_description_count")),
                ("Dokumentobjekter", s.get("document_object_count")),
            )
            for col in range(4):
                table.grid_columnconfigure(col, weight=0, minsize=(170 if col % 2 == 0 else 130))
            ctk.CTkLabel(table, text="Samlet kontrollgrunnlag", anchor="w",
                         font=theme.font(theme.NORMAL_SIZE, weight="bold")).grid(
                row=0, column=0, columnspan=4, sticky="w", padx=7, pady=(6, 4))
            for i, (label, value) in enumerate(items):
                r, base = 1 + i // 2, (i % 2) * 2
                ctk.CTkLabel(table, text=label, anchor="w", font=theme.font(theme.SMALL_SIZE)).grid(
                    row=r, column=base, sticky="w", padx=7, pady=2)
                ctk.CTkLabel(table, text=f"{int(value or 0):,}".replace(",", " "), anchor="e",
                             font=theme.font(theme.SMALL_SIZE, weight="bold")).grid(
                    row=r, column=base + 1, sticky="e", padx=7, pady=2)
            return
        super()._render_a169_controls(index)
