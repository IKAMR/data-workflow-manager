from __future__ import annotations

import customtkinter as ctk

from . import theme
from .depot_result_center_a16_13 import DepotResultCenterDialogA16_13


class DepotResultCenterDialogA16_15(DepotResultCenterDialogA16_13):
    """a16.15: fix hidden legacy controls sink placement."""

    def __init__(self, master, **kwargs) -> None:
        self._a1614_legacy_controls_sink = None
        self._a1614_year_context = None
        super().__init__(master, **kwargs)
        self._compact_summary_surface()
        self._install_year_context_panel()
        if getattr(self, "_archive_parts", None):
            self._show_archive_part(getattr(self, "_archive_index", 0))

    def _ensure_legacy_controls_sink(self) -> None:
        """Keep inherited a30 rendering harmless after a16.8 replaced its textbox."""
        old = getattr(self, "_a10_controls", None)
        if old is not None:
            try:
                if old.winfo_exists():
                    return
            except Exception:
                pass

        tabs = getattr(self, "_a10_tabs", None)
        if tabs is None:
            return
        try:
            tab = tabs.tab("Kontroller")
        except Exception:
            return

        sink = ctk.CTkTextbox(tab, width=1, height=1)
        # The legacy layer still writes its text while newer layers render the
        # visible structured table. Keep the compatibility widget off-screen.
        sink.place(x=-10000, y=-10000)
        self._a1614_legacy_controls_sink = sink
        self._a10_controls = sink

    def _show_archive_part(self, index: int) -> None:
        self._ensure_legacy_controls_sink()
        super()._show_archive_part(index)
        self._render_year_context(index)

    def _compact_summary_surface(self) -> None:
        period_panel = getattr(self, "_a164_period_panel", None)
        if period_panel is not None:
            try:
                period_panel.grid_configure(pady=(0, 4))
                for child in period_panel.winfo_children():
                    info = child.grid_info()
                    row = int(info.get("row", -1))
                    child.grid_configure(pady=(4, 1) if row == 0 else (0, 5))
            except Exception:
                pass

        doc_text = getattr(self, "_a166_doc_text", None)
        if doc_text is not None:
            try:
                panel = doc_text.master
                panel.grid_configure(pady=(0, 4))
                for child in panel.winfo_children():
                    info = child.grid_info()
                    row = int(info.get("row", -1))
                    child.grid_configure(pady=(4, 1) if row == 0 else (0, 5))
            except Exception:
                pass

        # The summary's inherited scroll area should receive the remaining height.
        tabs = getattr(self, "_a10_tabs", None)
        if tabs is not None:
            try:
                tab = tabs.tab("Sammendrag")
                for row in range(0, 8):
                    tab.grid_rowconfigure(row, weight=0)
                tab.grid_rowconfigure(6, weight=1)
            except Exception:
                pass

    def _install_year_context_panel(self) -> None:
        tabs = getattr(self, "_a10_tabs", None)
        if tabs is None:
            return
        try:
            tab = tabs.tab("Per år")
        except Exception:
            return

        tab.grid_columnconfigure(0, weight=0)
        tab.grid_columnconfigure(1, weight=1)
        panel = ctk.CTkFrame(tab)
        panel.grid(row=0, column=1, sticky="new", padx=(10, 4), pady=4)
        panel.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            panel,
            text="Ytterår og kilder",
            anchor="w",
            font=theme.font(theme.NORMAL_SIZE, weight="bold"),
        ).grid(row=0, column=0, sticky="ew", padx=12, pady=(10, 4))
        self._a1614_year_context = ctk.CTkLabel(
            panel,
            text="",
            anchor="nw",
            justify="left",
            wraplength=620,
            text_color=theme.TEXT_SUB,
            font=theme.font(theme.SMALL_SIZE),
        )
        self._a1614_year_context.grid(row=1, column=0, sticky="ew", padx=12, pady=(0, 12))

    @staticmethod
    def _fmt_span(value: dict | None) -> str:
        value = value or {}
        first = value.get("first_year")
        last = value.get("last_year")
        if not first and not last:
            return "–"
        return f"{first or '–'}–{last or '–'}"

    def _render_year_context(self, index: int) -> None:
        label = self._a1614_year_context
        if label is None or not getattr(self, "_archive_parts", None):
            return
        row = self._archive_parts[index]
        summary = self.model.get("all_archive_parts_summary") or {}
        declared = summary.get("declared_period") or {}
        whole_declared = f"{declared.get('start_year') or '–'}–{declared.get('end_year') or '–'}"

        if row.get("is_all_archive_parts"):
            periods = summary.get("observed_period_by_series") or {}
            real_rows = [r for r in self._archive_parts if not r.get("is_all_archive_parts")]
            with_declared = 0
            for real in real_rows:
                identity = real.get("archive_part") or {}
                if identity.get("archive_period_start_date") or identity.get("archive_period_end_date"):
                    with_declared += 1

            findings = summary.get("cross_source_year_findings") or []
            lines = [
                f"Arkivuttrekk.xml oppgitt: {whole_declared}",
                f"Arkivdeler med egne oppgitte ytterår: {with_declared} av {len(real_rows)}",
                "",
                f"Mapper/saker observert: {self._fmt_span(periods.get('folder'))}",
                f"Journalposter observert: {self._fmt_span(periods.get('journal'))}",
                f"Dokumentbeskrivelser observert: {self._fmt_span(periods.get('document_description'))}",
                f"Dokumentobjekter observert: {self._fmt_span(periods.get('document_object'))}",
            ]
            if findings:
                lines.extend(["", "År som krever vurdering:"])
                for item in findings[:8]:
                    counts = item.get("counts") or {}
                    lines.append(
                        f"• {item.get('year')}: dok.beskr. {int(counts.get('document_description') or 0):,}, "
                        f"dok.obj. {int(counts.get('document_object') or 0):,}, "
                        "uten mappe/journal"
                    )
            label.configure(text="\n".join(lines).replace(",", " "))
            return

        reported, observed = self._periods(row)
        lines = [
            f"Valgt arkivdel oppgitt: {self._period_text(reported)}",
            f"Valgt arkivdel observert: {self._period_text(observed)}",
            f"Hele uttrekket oppgitt: {whole_declared}",
        ]
        if reported == (None, None):
            lines.extend(["", "Merk: Arkivdelen mangler egne oppgitte ytterår. Observert periode er derfor kontrollgrunnlaget."])
        elif observed != (None, None) and reported != observed:
            lines.extend(["", "Merk: Oppgitte og observerte ytterår avviker."])
        label.configure(text="\n".join(lines))
