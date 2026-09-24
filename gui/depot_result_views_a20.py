
from __future__ import annotations

from tkinter import messagebox

import customtkinter as ctk

from noark5_workflow.external_evidence.arkade5 import (
    infer_work_operations_from_depot_report,
    list_arkade5_imports,
    load_arkade5_import,
)
from noark5_workflow.external_evidence.arkade5_coverage import build_arkade5_coverage
from noark5_workflow.external_evidence.arkade5_gap_analysis import build_gap_overlap_analysis
from version import APP_NAME
from . import theme
from .arkade5_metadata_a25 import (
    enrich_arkade5_imports,
    test_date_text,
    version_text,
)
from .depot_result_views_a17 import Arkade5CombinedCoverageDialogA17
from .depot_result_views_a19 import DepotResultViewsDialogA19


_CLASS_LABEL = {
    "equivalent": "Ekvivalent",
    "partial": "Delvis overlapp",
    "complementary": "Komplementær",
    "arkade_only": "Kun Arkade",
    "unmapped": "Ikke kartlagt",
}


def _source_name(item: dict) -> str:
    return str(
        item.get("display_source_file")
        or (item.get("source") or {}).get("original_name")
        or "–"
    )


class Arkade5CoverageDialogA25(ctk.CTkToplevel):
    """Coverage dialog aligned with the current relation-based mapping model."""

    def __init__(self, master, *, coverage: dict, source_label: str) -> None:
        super().__init__(master)
        self.title("Arkade 5 – DWM testdekning")
        self.geometry("1450x800")
        self.minsize(900, 600)
        self.transient(master)
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(3, weight=1)

        ctk.CTkLabel(
            self,
            text="ARKADE 5 – DWM TESTDEKNING",
            anchor="w",
            font=theme.font(theme.TITLE_SIZE),
        ).grid(row=0, column=0, sticky="ew", padx=18, pady=(18, 4))

        summary = coverage.get("summary") or {}
        ctk.CTkLabel(
            self,
            text=(
                f"{source_label}\n"
                f"Tester i Arkade-rapport: {coverage.get('arkade_tests_present', 0)}  |  "
                f"Ekvivalent: {summary.get('equivalent', 0)}  |  "
                f"Delvis overlapp: {summary.get('partial', 0)}  |  "
                f"Komplementær: {summary.get('complementary', 0)}  |  "
                f"Kun Arkade: {summary.get('arkade_only', 0)}  |  "
                f"Ikke kartlagt: {summary.get('unmapped', 0)}"
            ),
            anchor="w",
            justify="left",
            wraplength=1380,
            font=theme.font(theme.NORMAL_SIZE),
        ).grid(row=1, column=0, sticky="ew", padx=18, pady=(0, 6))

        ctk.CTkLabel(
            self,
            text=(
                "Testdekning beskriver dokumentert relasjon mellom Arkade 5-kontroller og "
                "DWM-kontroller. Den sier ikke at to tester er identiske bare fordi de peker "
                "mot samme Noark 5-område."
            ),
            anchor="w", justify="left", wraplength=1380,
            text_color=theme.TEXT_MUTED, font=theme.font(theme.SMALL_SIZE),
        ).grid(row=2, column=0, sticky="ew", padx=18, pady=(0, 10))

        frame = ctk.CTkScrollableFrame(self)
        frame.grid(row=3, column=0, sticky="nsew", padx=18, pady=(0, 10))
        for col, weight in enumerate((0, 2, 0, 2, 3)):
            frame.grid_columnconfigure(col, weight=weight)

        headers = ("Arkade", "Test", "Arkade-status", "Relasjon", "DWM / begrunnelse")
        for col, label in enumerate(headers):
            ctk.CTkLabel(
                frame, text=label, anchor="w", font=theme.font(theme.SMALL_SIZE)
            ).grid(row=0, column=col, sticky="ew", padx=6, pady=(4, 8))

        items = coverage.get("items") or []
        for row_no, item in enumerate(items, start=1):
            dwm = ", ".join(
                str(x.get("dwm_test_id") or "")
                for x in item.get("dwm_candidates") or []
                if x.get("dwm_test_id")
            )
            detail = dwm or item.get("reason") or "–"
            values = (
                item.get("arkade_test_id"),
                item.get("arkade_test_name"),
                item.get("arkade_status"),
                _CLASS_LABEL.get(item.get("classification"), item.get("classification")),
                detail,
            )
            for col, value in enumerate(values):
                ctk.CTkLabel(
                    frame,
                    text=str(value or "–"),
                    anchor="w", justify="left",
                    wraplength=(480 if col in (1, 4) else 230),
                    font=theme.font(theme.SMALL_SIZE),
                ).grid(row=row_no, column=col, sticky="new", padx=6, pady=5)

        if not items:
            ctk.CTkLabel(
                frame,
                text="Ingen testdekningsrader ble bygget for denne importen.",
                anchor="w",
            ).grid(row=1, column=0, columnspan=5, sticky="ew", padx=6, pady=10)

        bottom = ctk.CTkFrame(self, fg_color="transparent")
        bottom.grid(row=4, column=0, sticky="ew", padx=18, pady=(0, 18))
        bottom.grid_columnconfigure(0, weight=1)
        ctk.CTkButton(
            bottom, text="Lukk", width=90, command=self.destroy,
            fg_color=theme.BUTTON_BG, hover_color=theme.BUTTON_HOVER,
        ).grid(row=0, column=1)


def _display(value) -> str:
    return "–" if value in (None, "") else str(value)


class Arkade5CombinedCoverageDialogA25(Arkade5CombinedCoverageDialogA17):
    """a25: compact rows with the action next to the row it belongs to."""

    def _render(self) -> None:
        for widget in self.outer.winfo_children():
            widget.destroy()

        row_cursor = 0
        for import_no, import_row in enumerate(self.external.get("imports") or [], start=1):
            coverage = import_row.get("coverage") or {}
            controls = [
                control
                for control in coverage.get("arkade_control_areas") or []
                if self._matches(control)
            ]
            if not controls:
                continue

            ctk.CTkLabel(
                self.outer,
                text=(
                    f"{import_no}. Arkade 5 | versjon {_display(import_row.get('source_version'))} | "
                    f"testdato {_display(import_row.get('date_of_testing'))} | "
                    f"import-ID {_display(import_row.get('import_id'))}\n"
                    f"Kildefil: {_display(import_row.get('source_file'))} | "
                    f"SHA-256: {_display(import_row.get('source_sha256'))}"
                ),
                anchor="w",
                justify="left",
                font=theme.font(theme.SECTION_SIZE, "bold"),
            ).grid(
                row=row_cursor,
                column=0,
                sticky="ew",
                padx=6,
                pady=(8 if row_cursor else 3, 4),
            )
            row_cursor += 1

            for control in controls:
                arkade = control.get("arkade") or {}
                relation = _CLASS_LABEL.get(
                    control.get("relation"),
                    control.get("relation") or "–",
                )
                dwm_ids = (
                    control.get("dwm_test_ids_present")
                    or control.get("dwm_test_ids")
                    or []
                )
                dwm_text = ", ".join(dwm_ids) or "–"

                card = ctk.CTkFrame(self.outer)
                card.grid(row=row_cursor, column=0, sticky="ew", padx=6, pady=2)
                card.grid_columnconfigure(1, weight=1)

                ctk.CTkButton(
                    card,
                    text="Detaljer...",
                    width=92,
                    height=28,
                    command=lambda i=import_row, c=control: self._open_detail(i, c),
                    fg_color=theme.BUTTON_BG,
                    hover_color=theme.BUTTON_HOVER,
                ).grid(row=0, column=0, padx=(8, 7), pady=5, sticky="nw")

                ctk.CTkLabel(
                    card,
                    text=(
                        f"{_display(control.get('arkade_test_id'))} – "
                        f"{_display(control.get('arkade_test_name'))}\n"
                        f"{relation} | "
                        f"Arkade-status: {_display(arkade.get('status'))} | "
                        f"DWM: {dwm_text}"
                    ),
                    anchor="w",
                    justify="left",
                    wraplength=1360,
                    font=theme.font(theme.SMALL_SIZE),
                ).grid(row=0, column=1, sticky="ew", padx=(0, 8), pady=5)

                row_cursor += 1

        if row_cursor == 0:
            ctk.CTkLabel(
                self.outer,
                text="Ingen kontrollområder matcher valgt filter.",
                anchor="w",
            ).grid(row=0, column=0, sticky="ew", padx=8, pady=8)


class ArkadeGapOverlapDialogA25(ctk.CTkToplevel):
    """a25: focus immediately and show progress before static analysis is built."""

    def __init__(self, master) -> None:
        super().__init__(master)
        self.title("DWM / Arkade 5 – gap og overlapp")
        self.geometry("980x700")
        self.minsize(760, 520)
        self.transient(master)
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        ctk.CTkLabel(
            self,
            text="DWM / Arkade 5 – gap og overlapp",
            anchor="w",
            font=theme.font(theme.HEADER_SIZE, weight="bold"),
        ).grid(row=0, column=0, sticky="ew", padx=16, pady=(16, 6))

        self.loading = ctk.CTkLabel(
            self,
            text="Laster gap- og overlappoversikt …",
            anchor="center",
            justify="center",
            text_color=theme.TEXT_MUTED,
            font=theme.font(theme.NORMAL_SIZE),
        )
        self.loading.grid(row=1, column=0, sticky="nsew", padx=16, pady=16)

        self.update_idletasks()
        try:
            self.lift()
            self.focus_force()
            self.grab_set()
        except Exception:
            pass

        # Let Tk paint the window and loading text before analysis/rendering.
        self.after(75, self._build_content)

    def _build_content(self) -> None:
        try:
            model = build_gap_overlap_analysis()
        except Exception as exc:
            self.loading.configure(
                text=f"Kunne ikke bygge gap- og overlappoversikten:\n{exc}"
            )
            return

        summary = model["summary"]
        self.loading.destroy()

        body = ctk.CTkScrollableFrame(self)
        body.grid(row=1, column=0, sticky="nsew", padx=12, pady=(0, 12))
        body.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            body,
            text=(
                "Statisk kunnskapsmodell – ikke dokumentasjon på at en kontroll er kjørt. "
                "Arkade-, DWM- og historiske KDRS-identifikatorer holdes adskilt."
            ),
            anchor="w",
            justify="left",
            wraplength=900,
            text_color=theme.TEXT_MUTED,
        ).grid(row=0, column=0, sticky="ew", pady=(0, 10))

        ctk.CTkLabel(
            body,
            text=(
                f"Arkade-kontroller: {summary['arkade_test_count']}   |   "
                f"Kun Arkade: {summary['dwm_gaps_covered_by_arkade']}   |   "
                f"Overlapp: {summary['overlap_control_areas']}   |   "
                f"Kun DWM: {summary['dwm_only']}"
            ),
            anchor="w",
        ).grid(row=1, column=0, sticky="ew", pady=(0, 12))

        only_arkade = ctk.CTkFrame(body)
        only_arkade.grid(row=2, column=0, sticky="ew", pady=(0, 12))
        only_arkade.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            only_arkade,
            text="Kontroller kun i Arkade 5",
            anchor="w",
            font=theme.font(theme.BODY_SIZE, weight="bold"),
        ).grid(row=0, column=0, sticky="ew", padx=10, pady=(8, 4))

        for idx, area in enumerate(
            [
                item
                for item in model["arkade_control_areas"]
                if item["relation"] == "arkade_only"
            ],
            start=1,
        ):
            ctk.CTkLabel(
                only_arkade,
                text=f"{area['arkade_test_id']}  {area.get('arkade_test_name') or ''}",
                anchor="w",
                justify="left",
            ).grid(row=idx, column=0, sticky="ew", padx=14, pady=1)

        overlap = ctk.CTkFrame(body)
        overlap.grid(row=3, column=0, sticky="ew")
        overlap.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            overlap,
            text="Overlapp mellom DWM og Arkade 5",
            anchor="w",
            font=theme.font(theme.BODY_SIZE, weight="bold"),
        ).grid(row=0, column=0, sticky="ew", padx=10, pady=(8, 4))

        for idx, area in enumerate(
            [
                item
                for item in model["arkade_control_areas"]
                if item["relation"] != "arkade_only"
            ],
            start=1,
        ):
            dwm_ids = ", ".join(item["dwm_test_id"] for item in area["dwm"]) or "–"
            label = _CLASS_LABEL.get(area["relation"], area["relation"])
            ctk.CTkLabel(
                overlap,
                text=f"{area['arkade_test_id']}  {label}  |  DWM: {dwm_ids}",
                anchor="w",
                justify="left",
            ).grid(row=idx, column=0, sticky="ew", padx=14, pady=1)

        try:
            self.lift()
            self.focus_force()
        except Exception:
            pass


class Arkade5RunsDialogA25(ctk.CTkToplevel):
    """Simple run-oriented entry point for imported Arkade evidence."""

    def __init__(self, master, *, work, imports: list[dict], open_analysis) -> None:
        super().__init__(master)
        self.title("Arkade 5 – importerte kjøringer")
        self.geometry("1180x680")
        self.minsize(850, 520)
        self.transient(master)
        self.work = work
        self.imports = imports
        self.open_analysis = open_analysis

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        ctk.CTkLabel(
            self,
            text=(
                f"Importerte Arkade 5-kjøringer: {len(imports)}. "
                "Hver kjøring beholdes separat med kilde og sporbarhet."
            ),
            anchor="w", justify="left", wraplength=1120,
            font=theme.font(theme.NORMAL_SIZE),
        ).grid(row=0, column=0, sticky="ew", padx=18, pady=(18, 10))

        frame = ctk.CTkScrollableFrame(self)
        frame.grid(row=1, column=0, sticky="nsew", padx=18, pady=(0, 10))
        frame.grid_columnconfigure(0, weight=1)

        for row_no, item in enumerate(imports):
            summary = item.get("source_summary") or {}
            ctk.CTkLabel(
                frame,
                text=(
                    f"Arkade-versjon: {version_text(item)}  |  "
                    f"Testdato: {test_date_text(item)}\n"
                    f"Tester: {summary.get('number_of_tests_run') or '–'}  |  "
                    f"Feil: {summary.get('number_of_errors') or 0}  |  "
                    f"Advarsler: {summary.get('number_of_warnings') or 0}\n"
                    f"Kilde: {_source_name(item)}\n"
                    f"Import-ID: {item.get('import_id') or '–'}"
                ),
                anchor="w", justify="left", wraplength=900,
                font=theme.font(theme.SMALL_SIZE),
            ).grid(row=row_no, column=0, sticky="ew", padx=6, pady=8)
            ctk.CTkButton(
                frame,
                text="Analyser...",
                width=110,
                command=lambda selected=item: self._open(selected),
            ).grid(row=row_no, column=1, padx=6, pady=8)

        ctk.CTkButton(
            self, text="Lukk", width=90, command=self.destroy,
            fg_color=theme.BUTTON_BG, hover_color=theme.BUTTON_HOVER,
        ).grid(row=2, column=0, sticky="e", padx=18, pady=(0, 18))

    def _open(self, selected: dict) -> None:
        self.open_analysis(self.work, selected)


class Arkade5AdvancedDialogA25(ctk.CTkToplevel):
    """Keep expert/maintenance actions available without dominating normal review."""

    def __init__(self, master, *, actions: list[tuple[str, callable]]) -> None:
        super().__init__(master)
        self.title("Arkade 5 – avanserte verktøy")
        self.geometry("720x620")
        self.minsize(620, 520)
        self.transient(master)
        self.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            self,
            text=(
                "Avanserte verktøy for import, kartlegging, eksport og vedlikehold. "
                "Normal resultatgjennomgang gjøres fra Samlet oversikt og Arkade-kjøringer."
            ),
            anchor="w", justify="left", wraplength=660,
            font=theme.font(theme.NORMAL_SIZE),
        ).grid(row=0, column=0, sticky="ew", padx=18, pady=(18, 12))

        for row, (label, callback) in enumerate(actions, start=1):
            ctk.CTkButton(
                self,
                text=label,
                command=lambda cb=callback: self._run(cb),
                fg_color=theme.BUTTON_BG,
                hover_color=theme.BUTTON_HOVER,
            ).grid(row=row, column=0, sticky="ew", padx=18, pady=4)

        ctk.CTkButton(
            self, text="Lukk", width=90, command=self.destroy,
            fg_color=theme.BUTTON_BG, hover_color=theme.BUTTON_HOVER,
        ).grid(row=len(actions) + 1, column=0, sticky="e", padx=18, pady=(16, 18))

    def _run(self, callback) -> None:
        parent = self.master
        try:
            self.grab_release()
        except Exception:
            pass
        self.destroy()
        try:
            parent.after_idle(callback)
        except Exception:
            callback()


class DepotResultViewsDialogA20(DepotResultViewsDialogA19):
    """v0.1.5-a25: simplify Arkade review and fix coverage/metadata presentation."""

    def _build_external_evidence_tab(self, tab) -> None:
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_rowconfigure(0, weight=1)

        self.external_evidence_text = ctk.CTkTextbox(
            tab, wrap="word", font=theme.font(theme.SMALL_SIZE)
        )
        self.external_evidence_text.grid(
            row=0, column=0, sticky="nsew", padx=8, pady=(8, 6)
        )

        primary = ctk.CTkFrame(tab, fg_color="transparent")
        primary.grid(row=1, column=0, sticky="ew", padx=8, pady=(2, 8))
        primary.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            primary,
            text=(
                "Normal gjennomgang: start med samlet DWM/Arkade-oversikt. "
                "Åpne deretter en konkret Arkade-kjøring når du trenger kildefunnene."
            ),
            anchor="w", justify="left", wraplength=720,
            text_color=theme.TEXT_MUTED, font=theme.font(theme.SMALL_SIZE),
        ).grid(row=0, column=0, sticky="ew", padx=(0, 8))

        has_external = bool(
            ((self.model.get("external_validation") or {}).get("arkade5") or {}).get("imports")
        )
        ctk.CTkButton(
            primary, text="Samlet oversikt...", width=150,
            state="normal" if has_external else "disabled",
            command=self._open_combined_arkade5_coverage,
        ).grid(row=0, column=1, padx=4)

        ctk.CTkButton(
            primary, text="Arkade-kjøringer...", width=155,
            state="normal" if self.report_path else "disabled",
            command=self._open_arkade5_runs,
            fg_color=theme.BUTTON_BG, hover_color=theme.BUTTON_HOVER,
        ).grid(row=0, column=2, padx=4)

        ctk.CTkButton(
            primary, text="Avansert...", width=105,
            state="normal" if self.report_path else "disabled",
            command=self._open_arkade5_advanced,
            fg_color=theme.BUTTON_BG, hover_color=theme.BUTTON_HOVER,
        ).grid(row=0, column=3, padx=(4, 0))

        self._refresh_external_evidence()

    def _live_imports(self):
        if self.report_path is None:
            return None, []
        work = infer_work_operations_from_depot_report(self.report_path)
        imports = enrich_arkade5_imports(work, list_arkade5_imports(work))
        return work, imports

    def _refresh_external_evidence(self) -> None:
        if not hasattr(self, "external_evidence_text"):
            return
        lines = ["ARKADE 5 – EKSTERN EVIDENS", ""]
        try:
            _work, imports = self._live_imports()
        except Exception as exc:
            imports = []
            lines.append(f"Kunne ikke lese ekstern evidens: {exc}")

        if not imports and len(lines) == 2:
            lines.extend([
                "Ingen Arkade 5-rapporter er importert for dette arbeidsområdet.",
                "",
                "Bruk Avansert... for manuell import eller søk etter eksisterende rapporter.",
            ])
        else:
            lines.append(f"Importerte kjøringer: {len(imports)}")
            lines.append("")
            for no, item in enumerate(imports, start=1):
                summary = item.get("source_summary") or {}
                lines.extend([
                    f"{no}. Arkade 5 | versjon {version_text(item)} | testdato {test_date_text(item)}",
                    f"   Tester: {summary.get('number_of_tests_run') or '–'} | "
                    f"Feil: {summary.get('number_of_errors') or 0} | "
                    f"Advarsler: {summary.get('number_of_warnings') or 0}",
                    f"   Kilde: {_source_name(item)}",
                    f"   Import-ID: {item.get('import_id') or '–'}",
                    "",
                ])
            lines.append(
                "Arkade-resultater er ekstern evidens og endrer ikke automatisk "
                "DWM-status eller depotets faglige konklusjon."
            )

        self.external_evidence_text.configure(state="normal")
        self.external_evidence_text.delete("1.0", "end")
        self.external_evidence_text.insert("1.0", "\n".join(lines))
        self.external_evidence_text.configure(state="disabled")

    def _open_arkade5_runs(self) -> None:
        try:
            work, imports = self._live_imports()
        except Exception as exc:
            messagebox.showerror(APP_NAME, str(exc), parent=self)
            return
        if not imports:
            messagebox.showinfo(APP_NAME, "Ingen Arkade 5-kjøringer er importert.", parent=self)
            return
        Arkade5RunsDialogA25(
            self,
            work=work,
            imports=imports,
            open_analysis=self._open_arkade5_analysis_for_import,
        )

    def _open_arkade5_coverage_for_import(self, work, selected) -> None:
        try:
            loaded = load_arkade5_import(work, str(selected.get("import_id")))
            coverage = build_arkade5_coverage(loaded["normalized"])
            enriched = enrich_arkade5_imports(work, [selected])[0]
        except Exception as exc:
            messagebox.showerror(APP_NAME, str(exc), parent=self)
            return

        label = (
            f"Arkade 5 | versjon {version_text(enriched)} | "
            f"Testdato: {test_date_text(enriched)} | "
            f"Import-ID: {enriched.get('import_id') or '–'}"
        )
        Arkade5CoverageDialogA25(self, coverage=coverage, source_label=label)

    def _open_combined_arkade5_coverage(self) -> None:
        dialog = Arkade5CombinedCoverageDialogA25(
            self,
            report_model=self.model,
            report_path=self.report_path,
        )
        try:
            dialog.update_idletasks()
            dialog.lift()
            dialog.focus_force()
        except Exception:
            pass

    def _open_gap_overlap(self) -> None:
        ArkadeGapOverlapDialogA25(self)

    def _open_arkade5_advanced(self) -> None:
        actions = [
            ("Importer Arkade 5 JSON...", self._import_arkade5_evidence),
            ("Finn Arkade 5-rapporter...", self._discover_arkade5_evidence),
            ("Testdekning...", self._open_arkade5_coverage),
            ("Ressursbank...", self._open_external_result_bank),
            ("Generer Arkade-analyser...", self._generate_all_arkade_reports),
            ("Eksporter Arkade-evidenspakke...", self._export_arkade5_evidence_package),
            ("Gap og overlapp...", self._open_gap_overlap),
        ]
        Arkade5AdvancedDialogA25(self, actions=actions)
