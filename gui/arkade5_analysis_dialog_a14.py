from __future__ import annotations

import customtkinter as ctk

from . import theme


_LEVEL = {
    "error": "FEIL",
    "warning": "ADVARSEL",
    "review": "VURDER",
    "ok": "OK",
}
_COVERAGE = {
    "equivalent": "Direkte sammenlignbar",
    "candidate": "Kandidat",
    "known_non_equivalent": "Ikke direkte sammenlignbar",
    "unmapped": "Ikke kartlagt",
}


def _display(value) -> str:
    return "–" if value in (None, "") else str(value)


class Arkade5AnalysisDialog(ctk.CTkToplevel):
    def __init__(self, master, *, analysis: dict, source_label: str) -> None:
        super().__init__(master)
        self.title("Arkade 5 – rapportanalyse")
        self.geometry("1540x900")
        self.minsize(1100, 680)
        self.transient(master)
        self.analysis = analysis

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(3, weight=1)

        ctk.CTkLabel(
            self,
            text="ARKADE 5 – RAPPORTANALYSE",
            anchor="w",
            font=theme.font(theme.TITLE_SIZE),
        ).grid(row=0, column=0, sticky="ew", padx=18, pady=(18, 4))

        s = analysis.get("summary") or {}
        ctk.CTkLabel(
            self,
            text=(
                f"{source_label}\n"
                f"Tester: {s.get('tests', 0)}  |  "
                f"FEIL: {s.get('error', 0)}  |  "
                f"ADVARSEL: {s.get('warning', 0)}  |  "
                f"VURDER: {s.get('review', 0)}  |  "
                f"OK: {s.get('ok', 0)}  |  "
                f"Trenger oppfølging: {s.get('needs_attention', 0)}"
            ),
            anchor="w",
            justify="left",
            font=theme.font(theme.NORMAL_SIZE),
        ).grid(row=1, column=0, sticky="ew", padx=18, pady=(0, 4))

        ctk.CTkLabel(
            self,
            text=(
                "Visningen prioriterer Arkade-feil og advarsler, deretter punkter "
                "som bør vurderes fordi de ikke er direkte sammenlignbare eller "
                "ikke er kartlagt mot DWM. Dette er beslutningsstøtte – ikke en "
                "automatisk depotkonklusjon."
            ),
            anchor="w",
            justify="left",
            wraplength=1480,
            text_color=theme.TEXT_MUTED,
            font=theme.font(theme.SMALL_SIZE),
        ).grid(row=2, column=0, sticky="ew", padx=18, pady=(0, 10))

        outer = ctk.CTkScrollableFrame(self)
        outer.grid(row=3, column=0, sticky="nsew", padx=18, pady=(0, 10))
        outer.grid_columnconfigure(0, weight=1)

        for row_no, item in enumerate(analysis.get("items") or []):
            level = _LEVEL.get(item.get("attention_level"), str(item.get("attention_level") or "–"))
            coverage = _COVERAGE.get(
                item.get("coverage_classification"),
                item.get("coverage_classification") or "–",
            )
            candidates = ", ".join(
                f"{x.get('dwm_test_id')} ({x.get('legacy_job_id')})"
                for x in item.get("dwm_candidates") or []
            ) or "–"
            rec = item.get("reconciliation") or {}
            rec_text = rec.get("status") or "ikke tilgjengelig"

            card = ctk.CTkFrame(outer)
            card.grid(row=row_no, column=0, sticky="ew", padx=4, pady=6)
            card.grid_columnconfigure(0, weight=1)

            ctk.CTkLabel(
                card,
                text=f"{level}   {item.get('test_id') or '–'}   {item.get('test_name') or '–'}",
                anchor="w",
                justify="left",
                font=theme.font(theme.NORMAL_SIZE),
            ).grid(row=0, column=0, sticky="ew", padx=10, pady=(8, 2))

            ctk.CTkLabel(
                card,
                text=(
                    f"{item.get('explanation') or '–'}\n"
                    f"Arkade-status: {_display(item.get('arkade_status'))}  |  "
                    f"Feil: {item.get('number_of_errors', 0)}  |  "
                    f"DWM-dekning: {coverage}  |  "
                    f"Reconciliation: {rec_text}\n"
                    f"DWM-kandidater: {candidates}"
                ),
                anchor="w",
                justify="left",
                wraplength=1450,
                font=theme.font(theme.SMALL_SIZE),
            ).grid(row=1, column=0, sticky="ew", padx=10, pady=(0, 4))

            findings = item.get("findings") or []
            if findings:
                finding_text = []
                for finding in findings[:20]:
                    loc = finding.get("file") or ""
                    lines = finding.get("line_numbers")
                    where = ""
                    if loc:
                        where += f" [{loc}"
                        if lines:
                            where += f": {lines}"
                        where += "]"
                    finding_text.append(
                        f"- {finding.get('type') or 'Resultat'}: "
                        f"{finding.get('message') or '–'}{where}"
                    )
                if len(findings) > 20:
                    finding_text.append(f"- … {len(findings)-20} flere funn")
                ctk.CTkLabel(
                    card,
                    text="\n".join(finding_text),
                    anchor="w",
                    justify="left",
                    wraplength=1450,
                    text_color=theme.TEXT_MUTED,
                    font=theme.font(theme.SMALL_SIZE),
                ).grid(row=2, column=0, sticky="ew", padx=18, pady=(0, 8))

        bottom = ctk.CTkFrame(self, fg_color="transparent")
        bottom.grid(row=4, column=0, sticky="ew", padx=18, pady=(0, 18))
        bottom.grid_columnconfigure(0, weight=1)
        ctk.CTkButton(
            bottom,
            text="Lukk",
            width=90,
            command=self.destroy,
            fg_color=theme.BUTTON_BG,
            hover_color=theme.BUTTON_HOVER,
        ).grid(row=0, column=1)

        self.after_idle(self.lift)
        self.after_idle(self.focus_force)
