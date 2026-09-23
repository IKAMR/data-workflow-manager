from __future__ import annotations

import customtkinter as ctk
from tkinter import messagebox

from noark5_workflow.external_evidence.arkade5 import (
    infer_work_operations_from_depot_report,
    load_arkade5_import,
)
from version import APP_NAME
from . import theme
from .depot_result_views_a16 import DepotResultViewsDialogA16, _RELATION_LABELS, _STATUS_LABELS


def _display(value) -> str:
    return "–" if value in (None, "") else str(value)


def _find_normalized_test(normalized: dict, test_id: str) -> dict | None:
    wanted = str(test_id or "").strip().upper()
    for item in normalized.get("tests") or []:
        if str(item.get("test_id") or "").strip().upper() == wanted:
            return item
    return None


class Arkade5ControlDetailDialog(ctk.CTkToplevel):
    """Drill down from combined coverage to preserved normalized Arkade evidence."""

    def __init__(self, master, *, import_row: dict, control: dict, normalized_test: dict | None) -> None:
        super().__init__(master)
        self.title(f"Arkade 5 – {_display(control.get('arkade_test_id'))}")
        self.geometry("1280x820")
        self.minsize(900, 620)
        self.transient(master)
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(3, weight=1)

        arkade = control.get("arkade") or {}
        ctk.CTkLabel(
            self,
            text=f"{_display(control.get('arkade_test_id'))} – {_display(control.get('arkade_test_name'))}",
            anchor="w",
            font=theme.font(theme.TITLE_SIZE),
        ).grid(row=0, column=0, sticky="ew", padx=18, pady=(18, 4))

        ctk.CTkLabel(
            self,
            text=(
                f"Import-ID: {_display(import_row.get('import_id'))}  |  "
                f"Testdato: {_display(import_row.get('date_of_testing'))}  |  "
                f"Arkade-versjon: {_display(import_row.get('source_version'))}\n"
                f"Kildefil: {_display(import_row.get('source_file'))}  |  "
                f"SHA-256: {_display(import_row.get('source_sha256'))}"
            ),
            anchor="w", justify="left", wraplength=1220,
            text_color=theme.TEXT_MUTED, font=theme.font(theme.SMALL_SIZE),
        ).grid(row=1, column=0, sticky="ew", padx=18, pady=(0, 8))

        ctk.CTkLabel(
            self,
            text=(
                f"Relasjon: {_RELATION_LABELS.get(control.get('relation'), control.get('relation') or '–')}  |  "
                f"Dekning: {_STATUS_LABELS.get(control.get('combined_status'), control.get('combined_status') or '–')}  |  "
                f"Arkade-status: {_display(arkade.get('status'))}  |  "
                f"Feil: {arkade.get('number_of_errors', 0)}  |  "
                f"Resultater: {arkade.get('result_count', 0)}\n"
                f"DWM-test(er): {', '.join(control.get('dwm_test_ids') or []) or '–'}"
            ),
            anchor="w", justify="left", wraplength=1220,
            font=theme.font(theme.NORMAL_SIZE),
        ).grid(row=2, column=0, sticky="ew", padx=18, pady=(0, 10))

        box = ctk.CTkTextbox(self, wrap="word", font=theme.font(theme.SMALL_SIZE))
        box.grid(row=3, column=0, sticky="nsew", padx=18, pady=(0, 10))
        lines = []
        if normalized_test is None:
            lines.append("Ingen normalisert Arkade-test finnes for denne kontrollen i valgt kjøring.")
        else:
            lines.extend([
                f"Testtype: {_display(normalized_test.get('test_type'))}",
                f"Kildestatus: {_display(normalized_test.get('source_status'))}",
                f"Antall feil: {normalized_test.get('number_of_errors', 0)}",
                "",
                "FUNN / RESULTATER",
            ])
            results = normalized_test.get("results") or []
            if not results:
                lines.append("Ingen funn/resultater registrert.")
            for no, result in enumerate(results, start=1):
                lines.append(f"\n{no}. {_display(result.get('type') or result.get('result_type') or 'Resultat')}")
                message = result.get("message") or result.get("text") or result.get("description")
                if message:
                    lines.append(str(message))
                location = result.get("location") or {}
                if isinstance(location, dict):
                    where = []
                    for key in ("file", "path", "line", "line_number", "line_numbers", "system_id", "archive_part"):
                        value = location.get(key)
                        if value not in (None, "", []):
                            where.append(f"{key}: {value}")
                    if where:
                        lines.append("Plassering: " + " | ".join(where))
                for key in ("expected", "actual", "value"):
                    value = result.get(key)
                    if value not in (None, "", []):
                        lines.append(f"{key}: {value}")
                extra = result.get("source_extra")
                if extra:
                    lines.append(f"Kilde-ekstra: {extra}")
        box.insert("1.0", "\n".join(lines))
        box.configure(state="disabled")

        bottom = ctk.CTkFrame(self, fg_color="transparent")
        bottom.grid(row=4, column=0, sticky="ew", padx=18, pady=(0, 18))
        bottom.grid_columnconfigure(0, weight=1)
        ctk.CTkButton(
            bottom, text="Lukk", width=90, command=self.destroy,
            fg_color=theme.BUTTON_BG, hover_color=theme.BUTTON_HOVER,
        ).grid(row=0, column=1)
        self.after_idle(self.lift)
        self.after_idle(self.focus_force)


class Arkade5CombinedCoverageDialogA17(ctk.CTkToplevel):
    """Combined coverage with filters and drill-down to one Arkade control."""

    FILTERS = {
        "Alle": None,
        "DWM + Arkade": "covered_by_both",
        "Arkade dekker": "covered_by_arkade",
        "DWM dekker": "covered_by_dwm",
        "Ikke dekket": "not_covered_in_run",
        "Arkade-feil": "arkade_error",
    }

    def __init__(self, master, *, report_model: dict, report_path) -> None:
        super().__init__(master)
        self.title("Samlet DWM / Arkade 5-dekning")
        self.geometry("1640x920")
        self.minsize(1120, 680)
        self.transient(master)
        self.report_model = report_model
        self.report_path = report_path
        self.external = (report_model.get("external_validation") or {}).get("arkade5") or {}
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(3, weight=1)

        ctk.CTkLabel(self, text="SAMLET DWM / ARKADE 5-DEKNING", anchor="w", font=theme.font(theme.TITLE_SIZE)).grid(
            row=0, column=0, sticky="ew", padx=18, pady=(18, 4)
        )
        summary = self.external.get("summary") or {}
        ctk.CTkLabel(
            self,
            text=(f"Arkade-kjøringer: {summary.get('imports', 0)}  |  Dekket av Arkade: {summary.get('covered_by_arkade', 0)}  |  "
                  f"Arkade-feil: {summary.get('arkade_errors', 0)}  |  Arkade-advarsler: {summary.get('arkade_warnings', 0)}"),
            anchor="w", text_color=theme.TEXT_MUTED, font=theme.font(theme.SMALL_SIZE),
        ).grid(row=1, column=0, sticky="ew", padx=18, pady=(0, 8))

        filters = ctk.CTkFrame(self, fg_color="transparent")
        filters.grid(row=2, column=0, sticky="ew", padx=18, pady=(0, 8))
        filters.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(filters, text="Filter:", anchor="w").grid(row=0, column=0, padx=(0, 8))
        self.filter_var = ctk.StringVar(value="Alle")
        ctk.CTkOptionMenu(filters, variable=self.filter_var, values=list(self.FILTERS), command=lambda _v: self._render()).grid(row=0, column=1, sticky="w")

        self.outer = ctk.CTkScrollableFrame(self)
        self.outer.grid(row=3, column=0, sticky="nsew", padx=18, pady=(0, 10))
        self.outer.grid_columnconfigure(0, weight=1)
        self._render()

        bottom = ctk.CTkFrame(self, fg_color="transparent")
        bottom.grid(row=4, column=0, sticky="ew", padx=18, pady=(0, 18))
        bottom.grid_columnconfigure(0, weight=1)
        ctk.CTkButton(bottom, text="Lukk", width=90, command=self.destroy, fg_color=theme.BUTTON_BG, hover_color=theme.BUTTON_HOVER).grid(row=0, column=1)
        self.after_idle(self.lift)
        self.after_idle(self.focus_force)

    def _matches(self, control: dict) -> bool:
        selected = self.FILTERS.get(self.filter_var.get())
        if selected is None:
            return True
        if selected == "arkade_error":
            return (control.get("arkade") or {}).get("status") == "error"
        return control.get("combined_status") == selected

    def _render(self) -> None:
        for widget in self.outer.winfo_children():
            widget.destroy()
        row_cursor = 0
        for import_no, import_row in enumerate(self.external.get("imports") or [], start=1):
            coverage = import_row.get("coverage") or {}
            controls = [c for c in coverage.get("arkade_control_areas") or [] if self._matches(c)]
            if not controls:
                continue
            ctk.CTkLabel(
                self.outer,
                text=(f"{import_no}. Arkade 5 | versjon {_display(import_row.get('source_version'))} | "
                      f"testdato {_display(import_row.get('date_of_testing'))} | import-ID {_display(import_row.get('import_id'))}\n"
                      f"Kildefil: {_display(import_row.get('source_file'))} | SHA-256: {_display(import_row.get('source_sha256'))}"),
                anchor="w", justify="left", font=theme.font(theme.SECTION_SIZE, "bold"),
            ).grid(row=row_cursor, column=0, sticky="ew", padx=6, pady=(10 if row_cursor else 4, 6))
            row_cursor += 1
            for control in controls:
                arkade = control.get("arkade") or {}
                card = ctk.CTkFrame(self.outer)
                card.grid(row=row_cursor, column=0, sticky="ew", padx=6, pady=4)
                card.grid_columnconfigure(0, weight=1)
                ctk.CTkLabel(
                    card,
                    text=(f"{_display(control.get('arkade_test_id'))} – {_display(control.get('arkade_test_name'))}\n"
                          f"{_RELATION_LABELS.get(control.get('relation'), control.get('relation') or '–')} | "
                          f"{_STATUS_LABELS.get(control.get('combined_status'), control.get('combined_status') or '–')} | "
                          f"Arkade-status: {_display(arkade.get('status'))} | DWM: {', '.join(control.get('dwm_test_ids_present') or control.get('dwm_test_ids') or []) or '–'}"),
                    anchor="w", justify="left", wraplength=1360, font=theme.font(theme.SMALL_SIZE),
                ).grid(row=0, column=0, sticky="ew", padx=10, pady=8)
                ctk.CTkButton(
                    card, text="Detaljer...", width=100,
                    command=lambda i=import_row, c=control: self._open_detail(i, c),
                    fg_color=theme.BUTTON_BG, hover_color=theme.BUTTON_HOVER,
                ).grid(row=0, column=1, padx=10, pady=8)
                row_cursor += 1
        if row_cursor == 0:
            ctk.CTkLabel(self.outer, text="Ingen kontrollområder matcher valgt filter.", anchor="w").grid(row=0, column=0, sticky="ew", padx=8, pady=8)

    def _open_detail(self, import_row: dict, control: dict) -> None:
        if self.report_path is None:
            return
        try:
            work = infer_work_operations_from_depot_report(self.report_path)
            loaded = load_arkade5_import(work, str(import_row.get("import_id") or ""))
            normalized_test = _find_normalized_test(loaded.get("normalized") or {}, str(control.get("arkade_test_id") or ""))
        except Exception as exc:
            messagebox.showerror(APP_NAME, str(exc), parent=self)
            return
        Arkade5ControlDetailDialog(self, import_row=import_row, control=control, normalized_test=normalized_test)


class DepotResultViewsDialogA17(DepotResultViewsDialogA16):
    """v0.1.5-a7: filter and drill down in combined DWM/Arkade coverage."""

    def _open_combined_arkade5_coverage(self) -> None:
        Arkade5CombinedCoverageDialogA17(self, report_model=self.model, report_path=self.report_path)
