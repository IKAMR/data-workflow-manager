from __future__ import annotations

import json
import webbrowser
from pathlib import Path
from tkinter import messagebox

import customtkinter as ctk

from noark5_workflow.analysis.depot_assessment import (
    ASSESSMENT_STATUSES,
    load_depot_assessment,
    record_depot_assessment,
)
from noark5_workflow.core.identity import UserIdentity
from version import APP_NAME
from . import theme
from .depot_assessment_dialog import STATUS_LABELS, LABEL_TO_STATUS
from .depot_result_views_a31 import DepotResultViewsDialogA31


class DepotResultCenterDialogA14_1(DepotResultViewsDialogA31):
    """v0.1.6-a14.1: one primary window for Noark 5 result review.

    The existing a11 dashboard remains authoritative.  This increment only
    simplifies navigation by bringing depot assessment, PRONOM statistics and
    report access into the same Resultatvisninger window.
    """

    def __init__(
        self,
        master,
        *,
        model: dict,
        report_path: str | Path | None = None,
        user_identity: dict[str, str] | None = None,
    ) -> None:
        super().__init__(
            master,
            model=model,
            report_path=report_path,
            user_identity=user_identity,
        )
        self.title("Resultatvisninger – Noark 5")
        self.geometry("1320x860")
        self.minsize(1020, 700)
        self.user = UserIdentity.from_mapping(user_identity)

        tabs = self._root_tabview()
        if tabs is None:
            return

        tabs.add("Filformater")
        tabs.add("Depotvurdering")
        tabs.add("Rapport")

        self._build_pronom_tab(tabs.tab("Filformater"))
        self._build_assessment_tab(tabs.tab("Depotvurdering"))
        self._build_report_tab(tabs.tab("Rapport"))

        # Keep the user's starting point predictable.  Existing result views
        # are not removed or re-analysed; they are simply collected here.
        try:
            tabs.set("Totalt")
        except Exception:
            pass

    def _root_tabview(self):
        """Return the top-level result tabview, not nested archive-part tabs."""
        for child in self.winfo_children():
            if isinstance(child, ctk.CTkTabview):
                return child
        return None

    # ------------------------------------------------------------------
    # Filformater / PRONOM
    # ------------------------------------------------------------------
    def _build_pronom_tab(self, tab) -> None:
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_rowconfigure(1, weight=1)

        ctk.CTkLabel(
            tab,
            text="Filformater / PRONOM",
            anchor="w",
            font=theme.font(theme.NORMAL_SIZE, weight="bold"),
        ).grid(row=0, column=0, sticky="ew", padx=12, pady=(12, 6))

        box = ctk.CTkTextbox(
            tab,
            wrap="none",
            font=theme.font(theme.SMALL_SIZE),
        )
        box.grid(row=1, column=0, sticky="nsew", padx=12, pady=(0, 12))
        box.insert("1.0", self._pronom_text())
        box.configure(state="disabled")
        self._a14_pronom_text = box

    def _pronom_text(self) -> str:
        arkade = ((self.model.get("external_validation") or {}).get("arkade5") or {})
        summary = arkade.get("pronom_summary") or {}
        imports = list(arkade.get("imports") or [])

        lines = [
            "PRONOM-STATISTIKK FRA ARKADE 5 / SIEGFRIED",
            "",
            "Statistikken er importert evidens. Ingen ny filidentifikasjon kjøres i denne visningen.",
            "Detaljert filinventar vises ikke på filnivå i dette inkrementet.",
            "",
        ]

        if not summary and not any((item.get("pronom") or {}).get("available") for item in imports):
            lines.append("Ingen PRONOM-statistikk er materialisert i depotrapporten.")
            return "\n".join(lines)

        lines.extend(
            [
                f"Importerte statistikksett: {summary.get('statistics_imports', 0)}",
                f"Statistikkrader: {summary.get('statistics_rows', 0)}",
                f"Filer totalt: {summary.get('total_files', 0)}",
                f"Unike Format-ID: {summary.get('unique_format_ids', 0)}",
                f"Detaljert inventar tilgjengelig: {summary.get('detailed_inventory_available', 0)}",
                "",
            ]
        )

        for import_no, item in enumerate(imports, start=1):
            pronom = item.get("pronom") or {}
            if not pronom.get("available"):
                continue
            stats = pronom.get("statistics") or {}
            detailed = pronom.get("detailed_file_inventory") or {}
            lines.extend(
                [
                    f"IMPORT {import_no}: {item.get('import_id') or '–'}",
                    f"Identifikasjonsmotor: {pronom.get('identification_engine') or 'Siegfried / PRONOM'}",
                    f"Rader: {stats.get('row_count', 0)} | Filer: {stats.get('total_files', 0)} | "
                    f"Unike Format-ID: {stats.get('unique_format_ids', 0)} | "
                    f"Uidentifiserte filer: {stats.get('unidentified_files', 0)}",
                ]
            )
            if detailed.get("found"):
                state = "importert" if detailed.get("imported") else "funnet, men ikke importert"
                lines.append(
                    f"Detaljert filinventar: {detailed.get('original_name') or '–'} ({state})"
                )
            lines.extend(
                [
                    "",
                    "Format-ID | Filtype | Formatversjon | RAF-220301 | Antall",
                    "-" * 78,
                ]
            )
            rows = list(stats.get("rows") or [])
            if not rows:
                lines.append("Ingen statistikkrader.")
            else:
                for row in rows:
                    lines.append(
                        " | ".join(
                            [
                                str(row.get("format_id") or "–"),
                                str(row.get("file_type") or "–"),
                                str(row.get("format_version") or "–"),
                                str(row.get("raf_220301") or "–"),
                                str(row.get("count") if row.get("count") is not None else "–"),
                            ]
                        )
                    )
            lines.extend(["", ""])

        return "\n".join(lines).rstrip()

    # ------------------------------------------------------------------
    # Depotvurdering in the same window
    # ------------------------------------------------------------------
    def _build_assessment_tab(self, tab) -> None:
        tab.grid_columnconfigure(1, weight=1)
        tab.grid_rowconfigure(4, weight=1)

        ctk.CTkLabel(
            tab,
            text=(
                "Depotets faglige vurdering lagres ved siden av originalrapporten. "
                "Tekniske resultater og rapportgrunnlag endres ikke."
            ),
            anchor="w",
            justify="left",
            wraplength=980,
            font=theme.font(theme.SMALL_SIZE),
            text_color=theme.TEXT_SUB,
        ).grid(row=0, column=0, columnspan=2, sticky="ew", padx=12, pady=(12, 10))

        ctk.CTkLabel(tab, text="Status", anchor="w").grid(
            row=1, column=0, sticky="w", padx=(12, 8), pady=6
        )
        self._a14_status_var = ctk.StringVar(value=STATUS_LABELS["requires_clarification"])
        ctk.CTkOptionMenu(
            tab,
            variable=self._a14_status_var,
            values=[STATUS_LABELS[s] for s in ASSESSMENT_STATUSES],
        ).grid(row=1, column=1, sticky="ew", padx=(0, 12), pady=6)

        ctk.CTkLabel(tab, text="Bruker", anchor="w").grid(
            row=2, column=0, sticky="w", padx=(12, 8), pady=6
        )
        username = self.user.username if self.user else "Ingen aktiv brukerprofil"
        ctk.CTkLabel(tab, text=username, anchor="w").grid(
            row=2, column=1, sticky="ew", padx=(0, 12), pady=6
        )

        self._a14_current = ctk.CTkLabel(
            tab,
            text="",
            anchor="w",
            justify="left",
            wraplength=980,
            text_color=theme.TEXT_MUTED,
            font=theme.font(theme.SMALL_SIZE),
        )
        self._a14_current.grid(
            row=3, column=0, columnspan=2, sticky="ew", padx=12, pady=(8, 6)
        )

        self._a14_reason = ctk.CTkTextbox(
            tab,
            wrap="word",
            height=210,
            font=theme.font(theme.SMALL_SIZE),
        )
        self._a14_reason.grid(
            row=4, column=0, columnspan=2, sticky="nsew", padx=12, pady=(0, 8)
        )

        buttons = ctk.CTkFrame(tab, fg_color="transparent")
        buttons.grid(row=5, column=0, columnspan=2, sticky="ew", padx=12, pady=(0, 12))
        buttons.grid_columnconfigure(0, weight=1)
        self._a14_save_button = ctk.CTkButton(
            buttons,
            text="Lagre depotvurdering",
            width=160,
            command=self._save_assessment,
        )
        self._a14_save_button.grid(row=0, column=1)

        if self.user is None or self.report_path is None:
            self._a14_save_button.configure(state="disabled")

        self._refresh_assessment()

    def _refresh_assessment(self) -> None:
        if not hasattr(self, "_a14_current"):
            return
        if self.report_path is None:
            self._a14_current.configure(text="Ingen konkret depotrapport er koblet til visningen.")
            return
        try:
            stored = load_depot_assessment(self.report_path)
        except Exception as exc:
            self._a14_current.configure(text=f"Kunne ikke lese depotvurdering: {exc}")
            return

        current = (stored or {}).get("current")
        if not current:
            self._a14_current.configure(text="Ingen tidligere depotvurdering er registrert.")
            return

        status = str(current.get("status") or "")
        label = STATUS_LABELS.get(status, status or "Ukjent")
        user = current.get("user") or {}
        username = user.get("username") or user.get("user_id") or "ukjent bruker"
        assessed_at = current.get("assessed_at") or ""
        reason = str(current.get("reason") or "")
        history_count = len((stored or {}).get("history") or [])

        self._a14_current.configure(
            text=(
                f"Gjeldende vurdering: {label} · {username} · {assessed_at} · "
                f"historikk {history_count}"
            )
        )
        if status in STATUS_LABELS:
            self._a14_status_var.set(STATUS_LABELS[status])
        self._a14_reason.delete("1.0", "end")
        self._a14_reason.insert("1.0", reason)

    def _save_assessment(self) -> None:
        if self.report_path is None:
            messagebox.showinfo(APP_NAME, "Ingen depotrapport er valgt.", parent=self)
            return
        if self.user is None:
            messagebox.showerror(APP_NAME, "Depotvurdering krever aktiv brukerprofil.", parent=self)
            return

        status = LABEL_TO_STATUS.get(self._a14_status_var.get())
        reason = self._a14_reason.get("1.0", "end").strip()
        if not status:
            messagebox.showerror(APP_NAME, "Velg en gyldig vurderingsstatus.", parent=self)
            return
        if not reason:
            messagebox.showerror(APP_NAME, "Skriv en faglig begrunnelse.", parent=self)
            return

        try:
            result = record_depot_assessment(
                self.report_path,
                status=status,
                reason=reason,
                user=self.user,
                render_html=True,
            )
        except Exception as exc:
            messagebox.showerror(APP_NAME, str(exc), parent=self)
            return

        self._refresh_assessment()
        messagebox.showinfo(
            APP_NAME,
            f"Depotvurderingen er lagret. Historikk: {result['history_count']} vurdering(er).",
            parent=self,
        )

    # ------------------------------------------------------------------
    # Rapport access in the same window
    # ------------------------------------------------------------------
    def _build_report_tab(self, tab) -> None:
        tab.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            tab,
            text="Rapport",
            anchor="w",
            font=theme.font(theme.NORMAL_SIZE, weight="bold"),
        ).grid(row=0, column=0, sticky="ew", padx=12, pady=(12, 6))

        report_text = str(self.report_path) if self.report_path else "Ingen rapport valgt"
        ctk.CTkLabel(
            tab,
            text=report_text,
            anchor="w",
            justify="left",
            wraplength=980,
            text_color=theme.TEXT_SUB,
            font=theme.font(theme.SMALL_SIZE),
        ).grid(row=1, column=0, sticky="ew", padx=12, pady=(0, 10))

        html_path = self.report_path.with_suffix(".html") if self.report_path else None
        ctk.CTkButton(
            tab,
            text="Åpne full HTML-rapport",
            width=180,
            state="normal" if html_path and html_path.is_file() else "disabled",
            command=self._open_full_report,
            fg_color=theme.BUTTON_BG,
            hover_color=theme.BUTTON_HOVER,
        ).grid(row=2, column=0, sticky="w", padx=12, pady=(0, 8))

        ctk.CTkLabel(
            tab,
            text=(
                "Fullrapporten er et rapportprodukt. Resultatgjennomgang, filformatstatistikk "
                "og depotvurdering gjøres nå fra samme Resultatvisninger-vindu."
            ),
            anchor="w",
            justify="left",
            wraplength=980,
            text_color=theme.TEXT_MUTED,
            font=theme.font(theme.SMALL_SIZE),
        ).grid(row=3, column=0, sticky="ew", padx=12, pady=(8, 12))

    def _open_full_report(self) -> None:
        if self.report_path is None:
            return
        html_path = self.report_path.with_suffix(".html")
        if not html_path.is_file():
            messagebox.showinfo(
                APP_NAME,
                "HTML-rapporten finnes ikke ved siden av JSON-rapporten.",
                parent=self,
            )
            return
        try:
            webbrowser.open(html_path.resolve().as_uri())
        except Exception as exc:
            messagebox.showerror(APP_NAME, f"Kunne ikke åpne rapporten: {exc}", parent=self)
