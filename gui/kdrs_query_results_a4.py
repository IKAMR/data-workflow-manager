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
from noark5_workflow.external_evidence.kdrs_query_mapping import build_mapped_pool
from noark5_workflow.external_evidence.evidence_decisions_a5 import (
    exact_candidates, select_evidence, load_decisions)



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
    def __init__(self, master, *, work_operations, on_evidence_saved=None, report_path=None):
        super().__init__(master)
        self.work_operations = Path(work_operations)
        self._on_evidence_saved = on_evidence_saved
        self._native_report_path = Path(report_path) if report_path else None
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
        ctk.CTkButton(footer, text='Velg dokumentert evidens', width=185,
                      command=self._show_evidence_dialog).pack(side='left', padx=6)
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

    def _dwm_count_for_evidence(self, metric_label, scope_label, metrics, scopes):
        """Read original DWM count for preview; never assume missing is zero."""
        if self._native_report_path is None or not self._native_report_path.is_file():
            return None
        import json
        from noark5_workflow.external_evidence.evidence_report_bridge_a5 import read_dwm_values
        metric = next((key for key, label in metrics.items() if label == metric_label), None)
        scope = scopes.get(scope_label)
        if metric is None:
            return None
        if metric == 'case_folder_count':
            metric = 'case_count'  # No native canonical count in report bridge yet.
        key = f"{'whole' if scope is None else 'part:' + str(scope)}:{metric}"
        try:
            report = json.loads(self._native_report_path.read_text(encoding='utf-8-sig'))
            values, _ = read_dwm_values(report)
            return values.get(key)
        except (OSError, ValueError, TypeError, KeyError):
            return None

    def _show_evidence_dialog(self, *, initial_metric=None, initial_part=None):
        """Select only exact semantic facts, with explicit scope and reason."""
        try:
            pool = build_mapped_pool(self.work_operations)
            decisions = load_decisions(self.work_operations)
        except (OSError, ValueError, KeyError) as exc:
            messagebox.showerror('Evidens', str(exc), parent=self)
            return
        parent = getattr(self, '_evidence_parent', self)
        dialog = ctk.CTkToplevel(parent)
        dialog.title('Velg dokumentert evidens')
        dialog.geometry('950x540')
        dialog.transient(parent)
        dialog.grid_columnconfigure(1, weight=1)
        metrics = {**METRICS, 'case_folder_count': 'Saksmapper'}
        # Existing public case_count is a report alias for exact case_folder_count.
        metrics.pop('case_count', None)
        ctk.CTkLabel(dialog, text='Måltall').grid(row=0, column=0, padx=12, pady=10, sticky='w')
        metric_menu = ctk.CTkOptionMenu(dialog, values=list(metrics.values()))
        metric_menu.grid(row=0, column=1, padx=12, pady=10, sticky='ew')
        parts = sorted({f['archive_part_index'] for res in pool.get('resources', [])
                        for line in res.get('semantic_lines', [])
                        for f in line.get('facts', [])
                        if f.get('mapping_status') == 'exact' and
                           isinstance(f.get('archive_part_index'), int) and
                           not isinstance(f.get('archive_part_index'), bool)})
        scopes = {'Hele uttrekket': None, **{f'Arkivdel {p}': p for p in parts}}
        ctk.CTkLabel(dialog, text='Omfang').grid(row=1, column=0, padx=12, pady=10, sticky='w')
        scope_menu = ctk.CTkOptionMenu(dialog, values=list(scopes))
        scope_menu.grid(row=1, column=1, padx=12, pady=10, sticky='ew')
        if initial_metric in metrics:
            metric_menu.set(metrics[initial_metric])
        if initial_part is not None and f'Arkivdel {initial_part}' in scopes:
            scope_menu.set(f'Arkivdel {initial_part}')
        ctk.CTkLabel(dialog, text='Kildeobservasjon').grid(row=2, column=0, padx=12, pady=10, sticky='w')
        source_menu = ctk.CTkOptionMenu(dialog, values=['Ingen entydige observasjoner'])
        source_menu.grid(row=2, column=1, padx=12, pady=10, sticky='ew')
        labels = {}
        status = ctk.CTkLabel(dialog, text='', anchor='w')
        status.grid(row=3, column=1, padx=12, pady=6, sticky='ew')
        preview = ctk.CTkLabel(dialog, text='', anchor='w', justify='left', wraplength=720)
        preview.grid(row=4, column=1, padx=12, pady=6, sticky='ew')
        reasons = {'DWM-test mangler': 'missing_dwm_test',
                   'DWM-resultat er feil': 'invalid_dwm_result',
                   'Ekstern kilde er kontrollert': 'verified_external_source'}
        ctk.CTkLabel(dialog, text='Begrunnelse').grid(row=5, column=0, padx=12, pady=10, sticky='w')
        reason_menu = ctk.CTkOptionMenu(dialog, values=list(reasons))
        reason_menu.grid(row=5, column=1, padx=12, pady=10, sticky='ew')
        ctk.CTkLabel(dialog, text='Merknad').grid(row=6, column=0, padx=12, pady=10, sticky='w')
        note = ctk.CTkEntry(dialog, placeholder_text='Dokumenter vurderingen (obligatorisk)')
        note.grid(row=6, column=1, padx=12, pady=10, sticky='ew')

        def refresh(_=None):
            metric = next((k for k, v in metrics.items() if v == metric_menu.get()), None)
            scope = scopes[scope_menu.get()]
            found = exact_candidates(pool, metric, part_index=scope) if metric else []
            labels.clear()
            for i, row in enumerate(found, 1):
                label = (f"{i}: {format_count(row['value'])} | {row.get('report_type') or '-'} | "
                         f"{row.get('source_file') or '-'} | linje {row['source_line_number']}")
                labels[label] = row
            source_menu.configure(values=list(labels) or ['Ingen entydige observasjoner'])
            source_menu.set(next(iter(labels), 'Ingen entydige observasjoner'))
            decision_key = f"{'whole' if scope is None else 'part:'+str(scope)}:{metric}"
            decision = decisions.get(decision_key)
            status.configure(text=('Valgt evidens: ' + format_count(decision.get('value')) if decision else
                                  'Ingen dokumentert evidens valgt for dette måltallet'))
            refresh_preview()

        def refresh_preview(_=None):
            row = labels.get(source_menu.get())
            if not row:
                preview.configure(text='Ingen entydig ekstern observasjon for dette måltallet og omfanget.')
                return
            available = list(labels.values())
            distinct = sorted({r['value'] for r in available})
            agreement = ('Kildene er enige om tallverdien.' if len(distinct) == 1 else
                         'KILDEKONFLIKT: tilgjengelige observasjoner har ulike tallverdier.')
            dwm_value = self._dwm_count_for_evidence(metric_menu.get(), scope_menu.get(), metrics, scopes)
            dwm_text = ('DWM-verdi: ' + (format_count(dwm_value) if dwm_value is not None else 'Ukjent / ikke tilgjengelig') + '\n')
            preview.configure(text=(
                'Foreslått ekstern rapportverdi: ' + format_count(row['value']) + '\n'
                + dwm_text
                + 'Kilde: ' + str(row.get('source_file') or '-') + '\n'
                + agreement + '\n'
                'Originale DWM-tall beholdes. Valget påvirker kun dokumentert evidensgrunnlag '
                'og avledede depotrapporter etter oppdatering.'
            ))

        metric_menu.configure(command=refresh)
        scope_menu.configure(command=refresh)
        source_menu.configure(command=refresh_preview)
        refresh()

        def save(*, advance=False):
            row = labels.get(source_menu.get())
            if row is None:
                messagebox.showwarning('Evidens', 'Ingen entydig kildeobservasjon valgt.', parent=dialog)
                return
            if not note.get().strip():
                messagebox.showwarning('Evidens', 'Skriv en merknad som dokumenterer kildevalget.', parent=dialog)
                return
            metric = next(k for k, v in metrics.items() if v == metric_menu.get())
            try:
                select_evidence(self.work_operations, pool, metric=metric, evidence_id=row['id'],
                                part_index=scopes[scope_menu.get()],
                                reason=reasons[reason_menu.get()], note=note.get())
            except (OSError, ValueError, KeyError) as exc:
                messagebox.showerror('Evidens', str(exc), parent=dialog)
                return
            decisions.clear()
            decisions.update(load_decisions(self.work_operations))
            refresh()
            if callable(self._on_evidence_saved):
                try:
                    updated = self._on_evidence_saved()
                except Exception as exc:
                    messagebox.showwarning('Evidens',
                        f'Evidensvalget er lagret, men oppdatering av rapportgrunnlaget feilet: {exc}\n'
                        'Bruk Oppdater evidensgrunnlag i Resultatvisninger før rapporten brukes.', parent=dialog)
                    return
                if updated is False:
                    messagebox.showwarning('Evidens',
                        'Evidensvalget er lagret, men rapportgrunnlaget ble ikke oppdatert. '
                        'Se feilmeldingen i Resultatvisninger, og oppdater før rapporten brukes.', parent=dialog)
                    return
            if advance:
                # Stay on the same archive part; advance the metric only after
                # a successful save/refresh. Every new value still needs an
                # explicit source, reason and operator note.
                keys = list(metrics)
                next_index = (keys.index(metric) + 1) % len(keys)
                metric_menu.set(metrics[keys[next_index]])
                note.delete(0, 'end')
                refresh()
                return
            messagebox.showinfo('Evidens', 'Valget er lagret med sporbar kilde. Originale DWM-resultater er uendret. '
                                'Evidensgrunnlaget er oppdatert dersom depotrapport er tilgjengelig.', parent=dialog)

        buttons = ctk.CTkFrame(dialog, fg_color='transparent')
        buttons.grid(row=7, column=1, sticky='e', padx=12, pady=14)
        ctk.CTkButton(buttons, text='Lagre evidensvalg', command=save).pack(side='left', padx=5)
        ctk.CTkButton(buttons, text='Lagre og neste måltall', command=lambda: save(advance=True)).pack(side='left', padx=5)
        ctk.CTkButton(buttons, text='Lukk', command=dialog.destroy).pack(side='left', padx=5)

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
            from noark5_workflow.external_evidence.evidence_report_a5 import write_evidence_annex
            write_evidence_annex(self.work_operations)
        except Exception as exc:
            messagebox.showerror('KDRS Query', f'Kunne ikke generere rapportgrunnlag:\n{exc}', parent=self)
            return
        self._show_reports(generated=True)


class DirectEvidenceSelector:
    """Open the audited evidence form directly from Resultatvisninger.

    Unlike KdrsQueryResultsDialog, no heavyweight result-browser window or
    result-bank rendering is created. The shared decision form stays intact.
    """

    _dwm_count_for_evidence = KdrsQueryResultsDialog._dwm_count_for_evidence
    _show_evidence_dialog = KdrsQueryResultsDialog._show_evidence_dialog

    def __init__(self, master, *, work_operations, on_evidence_saved=None, report_path=None):
        self._evidence_parent = master
        self.work_operations = Path(work_operations)
        self._on_evidence_saved = on_evidence_saved
        self._native_report_path = Path(report_path) if report_path else None
