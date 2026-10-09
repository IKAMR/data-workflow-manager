"""GUI for read-only imported KDRS Query results and report evidence."""
from __future__ import annotations

from pathlib import Path
import os
import webbrowser
import sys
from tkinter import messagebox
import customtkinter as ctk

from noark5_workflow.external_evidence.result_bank import build_external_result_bank
from noark5_workflow.external_evidence.kdrs_query_views import write_kdrs_query_views
from noark5_workflow.external_evidence.kdrs_query_selection import METRICS, candidates, set_choice, load_choices
from noark5_workflow.external_evidence.number_format import format_count


def _resources(bank):
    return [row for row in bank.get('resources', [])
            if isinstance(row, dict) and row.get('source_system') == 'KDRS Query']


def _format_resource(row):
    lines = [f"{row.get('test_point') or row.get('test_id') or 'Ukjent test'}  {row.get('test_name') or ''}",
             f"Rapporttype: {row.get('report_type') or '-'}  |  Arkivdel: {row.get('archive_part_title') or 'Hele uttrekket'}",
             f"Kilde: {row.get('source_file') or '-'}  |  SHA-256: {row.get('source_sha256') or '-'}", ""]
    from noark5_workflow.external_evidence.kdrs_query_views import presentation_text
    for item in row.get('results') or []:
        lines.append(presentation_text(str(item.get('text', '') if isinstance(item, dict) else item)))
    if not row.get('results'):
        lines.append('Ingen resultatlinjer')
    return '\n'.join(lines)


class KdrsQueryResultsDialog(ctk.CTkToplevel):
    def __init__(self, master, *, work_operations):
        super().__init__(master)
        self.work_operations = Path(work_operations)
        self.bank = build_external_result_bank(self.work_operations)
        self.resources = _resources(self.bank)
        self.title('KDRS Query – importerte resultater')
        self.geometry('1100x760')
        self.minsize(800, 560)
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(3, weight=1)
        ctk.CTkLabel(self, text=f'KDRS Query – {len(self.resources)} importerte resultatseksjoner',
                     font=ctk.CTkFont(size=17, weight='bold')).grid(row=0, column=0, sticky='w', padx=16, pady=10)
        filters = ctk.CTkFrame(self)
        filters.grid(row=1, column=0, sticky='ew', padx=16)
        self.kind = ctk.CTkOptionMenu(filters, values=['Alle', 'Standard', 'U1', 'U2'], command=lambda _: self._refresh())
        self.kind.pack(side='left', padx=6, pady=8)
        self.search = ctk.CTkEntry(filters, placeholder_text='Søk test, resultat, kilde eller arkivdel', width=340)
        self.search.pack(side='left', padx=6)
        self.search.bind('<KeyRelease>', lambda _: self._refresh())
        self.count = ctk.CTkLabel(filters, text='')
        self.count.pack(side='left', padx=6)
        # Report selections are explicit: no implicit equivalence between KDRS and DWM.
        self._candidate_rows = []
        self._choice_labels = []
        choices = ctk.CTkFrame(self)
        choices.grid(row=2, column=0, sticky='ew', padx=16, pady=(6, 0))
        ctk.CTkLabel(choices, text='Rapportverdi (hele uttrekket):').pack(side='left', padx=5)
        self._metric_menu = ctk.CTkOptionMenu(choices, values=list(METRICS.values()), width=155, command=lambda _: self._refresh_candidates())
        self._metric_menu.pack(side='left', padx=5)
        self._candidate_menu = ctk.CTkOptionMenu(choices, values=self._choice_labels or ['Ingen numeriske observasjoner'], width=450)
        self._candidate_menu.pack(side='left', padx=5, fill='x', expand=True)
        ctk.CTkButton(choices, text='Bruk som rapportgrunnlag', width=180,
                      command=self._use_selected).pack(side='left', padx=5)
        self.text = ctk.CTkTextbox(self, wrap='word')
        self.text.grid(row=3, column=0, sticky='nsew', padx=16, pady=10)
        footer = ctk.CTkFrame(self, fg_color='transparent')
        footer.grid(row=4, column=0, sticky='e', padx=16, pady=(0, 14))
        ctk.CTkButton(footer, text='Generer rapportgrunnlag (JSON + HTML)', width=260,
                      command=self._export).pack(side='left', padx=6)
        ctk.CTkButton(footer, text='Åpne rapporter', width=150, command=self._show_reports).pack(side='left', padx=6)
        ctk.CTkButton(footer, text='Lukk', width=100, command=self.destroy).pack(side='left', padx=6)
        self._refresh_candidates()
        self._refresh()

    def _refresh_candidates(self):
        metric = next((key for key, label in METRICS.items() if label == self._metric_menu.get()), None)
        self._candidate_rows = candidates(self.work_operations, metric) if metric else []
        self._choice_labels = [f"{r['label']} = {format_count(int(r['value']))} | {r['report_type']} | {r['source_file']}" for r in self._candidate_rows]
        self._candidate_menu.configure(values=self._choice_labels or ["Ingen entydig mappede verdier"])
        self._candidate_menu.set(self._choice_labels[0] if self._choice_labels else "Ingen entydig mappede verdier")

    def _use_selected(self):
        if not self._choice_labels:
            messagebox.showwarning('KDRS Query', 'Ingen numeriske observasjoner tilgjengelig.', parent=self)
            return
        metric = next((key for key, label in METRICS.items() if label == self._metric_menu.get()), None)
        selection = self._candidate_menu.get()
        if metric is None or selection not in self._choice_labels:
            return
        row = self._candidate_rows[self._choice_labels.index(selection)]
        if not messagebox.askyesno('Velg rapportgrunnlag',
            f"Bruke {format_count(int(row['value']))} fra KDRS Query for {METRICS[metric]}?\n\n"
            f"Kilde: {row['source_file']}\nTest: {row['test_id']}\n"
            f"Resultatlinje: {row['line']}\n\n"
            'Denne verdien blir valgt for visning/rapportgrunnlag, uten å endre DWM-testresultatet.',
            parent=self):
            return
        try:
            set_choice(self.work_operations, metric, row['observation_id'])
        except (OSError, ValueError) as exc:
            messagebox.showerror('KDRS Query', str(exc), parent=self)
            return
        messagebox.showinfo('KDRS Query',
            'Valget er lagret med kildeproveniens. Lukk og åpne Resultatvisninger på nytt '
            'for å oppdatere nøkkeltallene. Eksisterende depotrapport må genereres på nytt '
            'før dette valget kan inngå i dens hovedtall.', parent=self)

    def _filtered(self):
        kind = {'Alle': '', 'Standard': 'standard', 'U1': 'u01', 'U2': 'u02'}.get(self.kind.get(), '')
        query = self.search.get().casefold().strip()
        for row in self.resources:
            if kind and row.get('report_type') != kind:
                continue
            text = _format_resource(row)
            if query and query not in text.casefold():
                continue
            yield text

    def _refresh(self):
        records = list(self._filtered())
        self.count.configure(text=f'{len(records)} vises')
        self.text.configure(state='normal')
        self.text.delete('1.0', 'end')
        self.text.insert('1.0', ('\n\n' + '=' * 65 + '\n\n').join(records)
                         if records else 'Ingen importerte resultater samsvarer med filteret.')
        self.text.configure(state='disabled')

    def _report_file(self, kind):
        name = 'imported-results.html' if kind == 'html' else 'report-evidence.json'
        return self.work_operations / 'external_evidence' / 'kdrs_query_views' / name

    def _open_report(self, kind):
        path = self._report_file(kind)
        if not path.is_file():
            messagebox.showwarning('KDRS Query', 'Rapportfilen finnes ikke. Generer rapportgrunnlaget først.', parent=self)
            return
        try:
            if sys.platform == 'win32':
                os.startfile(str(path))
            else:
                if not webbrowser.open(path.resolve().as_uri()):
                    raise OSError('Ingen nettleser kunne åpne rapportfilen.')
        except (OSError, ValueError) as exc:
            messagebox.showerror('KDRS Query', f'Kunne ikke åpne rapporten:\n{exc}', parent=self)

    def _show_reports(self, *, generated=False):
        """Single viewer for existing reports; never creates or changes reports."""
        html_path = self._report_file('html')
        json_path = self._report_file('json')
        found_html = html_path.is_file()
        found_json = json_path.is_file()
        dialog = ctk.CTkToplevel(self)
        dialog.title('KDRS Query – rapporter')
        dialog.geometry('700x260')
        dialog.minsize(560, 235)
        dialog.transient(self)
        dialog.grid_columnconfigure(0, weight=1)
        state = 'Rapportgrunnlag lagret.' if generated else 'Eksisterende rapportgrunnlag:'
        if not (found_html or found_json):
            state = 'Ingen rapporter generert.'
        text = (f'{state}\n\n'
                f'HTML: {html_path if found_html else "Finnes ikke"}\n\n'
                f'JSON: {json_path if found_json else "Finnes ikke"}')
        ctk.CTkLabel(dialog, text=text, justify='left', anchor='w',
                     wraplength=650).grid(row=0, column=0, sticky='ew', padx=18, pady=18)
        buttons = ctk.CTkFrame(dialog, fg_color='transparent')
        buttons.grid(row=1, column=0, sticky='e', padx=14, pady=10)
        ctk.CTkButton(buttons, text='Åpne HTML', state='normal' if found_html else 'disabled',
                      command=lambda: self._open_report('html')).pack(side='left', padx=5)
        ctk.CTkButton(buttons, text='Åpne JSON', state='normal' if found_json else 'disabled',
                      command=lambda: self._open_report('json')).pack(side='left', padx=5)
        ctk.CTkButton(buttons, text='Lukk', command=dialog.destroy).pack(side='left', padx=5)
        dialog.lift()

    def _export(self):
        try:
            write_kdrs_query_views(self.work_operations)
        except Exception as exc:
            messagebox.showerror('KDRS Query', f'Kunne ikke generere rapportgrunnlag:\n{exc}', parent=self)
            return
        self._show_reports(generated=True)
