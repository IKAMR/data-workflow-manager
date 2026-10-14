"""Read-only Arkade 5 / Siegfried evidence viewer for Resultatvisninger."""
from __future__ import annotations

import json
from pathlib import Path
from tkinter import messagebox

import customtkinter as ctk

from noark5_workflow.external_evidence.arkade5 import infer_work_operations_from_depot_report
from noark5_workflow.external_evidence.arkade5_gui_data_a18 import build_arkade5_gui_snapshot


def _fmt(value):
    return '–' if value is None or value == '' else str(value)


def _display_import(run):
    return f"{run['import_id']} | Arkade {_fmt(run.get('source_version'))} | {_fmt(run.get('date'))}"


def _test_rows(run, search='', only_issues=False):
    q = search.casefold().strip()
    for test in run.get('tests') or []:
        if q and q not in (test['test_id'] + ' ' + test['test_name'] + ' ' + test['status']).casefold():
            continue
        if only_issues and test['status'].lower() not in ('error', 'warning', 'review', 'failed', 'feil', 'advarsel'):
            if not isinstance(test.get('errors'), int) or test['errors'] <= 0:
                continue
        yield test


class Arkade5SourcesDialog(ctk.CTkToplevel):
    def __init__(self, parent, work_operations, *, display_name='', mode='tests'):
        super().__init__(parent)
        self._snapshot = build_arkade5_gui_snapshot(work_operations)
        self._mode = mode
        self.title('Eksterne kilder – Arkade 5 og PRONOM' + (' – ' + display_name if display_name else ''))
        self.geometry('980x700')
        self.minsize(690, 480)
        self.transient(parent)
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(4, weight=1)
        ctk.CTkLabel(self, text='Arkade 5 – Noark 5-tester og Siegfried/PRONOM',
                     font=ctk.CTkFont(size=17, weight='bold'), anchor='w').grid(
                         row=0, column=0, sticky='ew', padx=16, pady=(14, 4))
        self._headline = ctk.CTkLabel(self, anchor='w', justify='left')
        self._headline.grid(row=1, column=0, sticky='ew', padx=16, pady=(0, 7))
        bar = ctk.CTkFrame(self)
        bar.grid(row=2, column=0, sticky='ew', padx=16, pady=5)
        bar.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(bar, text='Import:').grid(row=0, column=0, padx=(10, 4), pady=8)
        runs = self._snapshot['runs']
        self._run_labels = {_display_import(run): run for run in runs}
        self._choice = ctk.CTkOptionMenu(bar, values=list(self._run_labels) or ['Ingen importerte kjøringer'],
                                         command=lambda _value: self._refresh(), width=440)
        self._choice.grid(row=0, column=1, sticky='ew', padx=4, pady=8)
        self._mode_choice = ctk.CTkSegmentedButton(bar, values=['Tester', 'PRONOM'],
                            command=self._change_mode)
        self._mode_choice.grid(row=0, column=2, padx=10)
        self._mode_choice.set('PRONOM' if mode == 'pronom' else 'Tester')
        searchbar = ctk.CTkFrame(self, fg_color='transparent')
        searchbar.grid(row=3, column=0, sticky='ew', padx=16, pady=5)
        searchbar.grid_columnconfigure(0, weight=1)
        self._search = ctk.CTkEntry(searchbar, placeholder_text='Søk på test-ID, navn eller status')
        self._search.grid(row=0, column=0, sticky='ew', padx=(0, 10))
        self._search.bind('<KeyRelease>', lambda _: self._refresh())
        self._issues = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(searchbar, text='Bare avvik', variable=self._issues,
                        command=self._refresh).grid(row=0, column=1)
        self._content = ctk.CTkScrollableFrame(self)
        self._content.grid(row=4, column=0, sticky='nsew', padx=16, pady=6)
        self._content.grid_columnconfigure(0, weight=1)
        ctk.CTkButton(self, text='Lukk', width=100, command=self.destroy).grid(
            row=5, column=0, sticky='e', padx=16, pady=(4, 12))
        self._refresh()

    def _change_mode(self, mode):
        self._mode = 'pronom' if mode == 'PRONOM' else 'tests'
        self._refresh()

    def _selected_run(self):
        return self._run_labels.get(self._choice.get())

    def _refresh(self):
        for child in self._content.winfo_children():
            child.destroy()
        run = self._selected_run()
        s = self._snapshot
        self._headline.configure(text=(f"Importerte Arkade-kjøringer: {s['import_count']} | "
            f"Lesbare: {s['readable_imports']} | PRONOM-statistikk: {s['pronom_imports']}\n"
            'Kun lagret evidens. Ingen ny analyse eller oppdatering av depotrapporten.'))
        if not run:
            self._notice('Ingen importerte Arkade 5-resultater funnet for denne jobben.')
            return
        header = (f"Import-ID: {run['import_id']} | Arkade-versjon: {_fmt(run.get('source_version'))} | "
                  f"Testdato: {_fmt(run.get('date'))} | Importert: {_fmt(run.get('imported_at'))}\n"
                  f"Fil: {_fmt(run.get('source_file'))}\nSHA-256: {_fmt(run.get('source_sha256'))}")
        ctk.CTkLabel(self._content, text=header, justify='left', anchor='w', wraplength=880).grid(
            row=0, column=0, sticky='ew', padx=6, pady=(3, 12))
        if run.get('diagnostic'):
            self._notice('Kunne ikke lese importen: ' + run['diagnostic'], row=1)
            return
        if self._mode == 'pronom':
            self._render_pronom(run)
        else:
            self._render_tests(run)

    def _notice(self, text, row=0):
        ctk.CTkLabel(self._content, text=text, anchor='w', justify='left',
                     wraplength=880).grid(row=row, column=0, sticky='ew', padx=6, pady=8)

    def _render_tests(self, run):
        rows = list(_test_rows(run, self._search.get(), self._issues.get()))
        self._notice(f"Noark 5-tester: {len(run['tests'])} | Viste: {len(rows)}", row=1)
        for i, test in enumerate(rows, start=2):
            item = ctk.CTkFrame(self._content)
            item.grid(row=i, column=0, sticky='ew', pady=3)
            item.grid_columnconfigure(0, weight=1)
            label = (f"{_fmt(test['test_id'])} – {_fmt(test['test_name'])}\n"
                     f"Status: {_fmt(test['status'])} | Feil: {_fmt(test['errors'])}")
            ctk.CTkLabel(item, text=label, anchor='w', justify='left', wraplength=690).grid(
                row=0, column=0, sticky='ew', padx=10, pady=8)
            ctk.CTkButton(item, text='Detaljer', width=90,
                          command=lambda record=test: self._show_detail(record)).grid(
                              row=0, column=1, padx=10, pady=8)

    def _render_pronom(self, run):
        value = run.get('pronom') or {}
        if not value.get('available'):
            self._notice('Ingen importert Siegfried/PRONOM-statistikk for denne Arkade-kjøringen.', row=1)
            return
        stats = value.get('statistics') or {}
        self._notice((f"PRONOM-statistikk: {_fmt(stats.get('total_files'))} filobservasjoner | "
                      f"Uidentifiserte: {_fmt(stats.get('unidentified_files'))} | "
                      f"Format-ID-er: {_fmt(stats.get('unique_format_ids'))} | "
                      f"Statistikkrader: {_fmt(stats.get('row_count'))}"), row=1)
        q = self._search.get().casefold().strip()
        rows = stats.get('rows') or []
        for i, row in enumerate(rows, start=2):
            label = (f"{_fmt(row.get('format_id'))} | {_fmt(row.get('file_type'))} | "
                     f"{_fmt(row.get('format_version'))} | RAF-220301: {_fmt(row.get('raf_220301'))} | "
                     f"Antall: {_fmt(row.get('count'))}")
            if q and q not in label.casefold():
                continue
            if self._issues.get() and str(row.get('format_id') or '').casefold() not in (
                    '', '-', 'ukjent', 'unknown', 'unknown format', 'fmt/unknown'):
                continue
            ctk.CTkLabel(self._content, text=label, anchor='w', justify='left',
                         wraplength=880).grid(row=i, column=0, sticky='ew', padx=6, pady=4)
        detail = value.get('detailed_file_inventory') or {}
        if detail.get('found'):
            ctk.CTkLabel(self._content,
                text='Detaljert filinventar finnes som separat kilde; det er ikke lest inn i visningen.',
                anchor='w').grid(row=len(rows)+3, column=0, sticky='ew', padx=6, pady=8)

    def _show_detail(self, record):
        dialog = ctk.CTkToplevel(self)
        dialog.title(f"Arkade 5 – {_fmt(record.get('test_id'))}")
        dialog.geometry('850x560')
        dialog.transient(self)
        dialog.grid_columnconfigure(0, weight=1)
        dialog.grid_rowconfigure(1, weight=1)
        ctk.CTkLabel(dialog, text=f"{_fmt(record.get('test_id'))} – {_fmt(record.get('test_name'))}",
                     anchor='w').grid(row=0, column=0, sticky='ew', padx=10, pady=10)
        box = ctk.CTkTextbox(dialog, wrap='word')
        box.grid(row=1, column=0, sticky='nsew', padx=10, pady=6)
        box.insert('1.0', json.dumps(record.get('details') or {}, ensure_ascii=False, indent=2))
        box.configure(state='disabled')
        ctk.CTkButton(dialog, text='Lukk', command=dialog.destroy).grid(
            row=2, column=0, sticky='e', padx=10, pady=10)


def open_arkade5_sources(parent, *, report_path, display_name='', mode='tests'):
    path = Path(report_path) if report_path else None
    if path is None:
        messagebox.showwarning('Arkade 5', 'Mangler referanse til jobbens depotrapport.', parent=parent)
        return None
    try:
        work = infer_work_operations_from_depot_report(path)
        return Arkade5SourcesDialog(parent, work, display_name=display_name, mode=mode)
    except (OSError, ValueError, TypeError) as exc:
        messagebox.showerror('Arkade 5', f'Kunne ikke åpne importert evidens: {exc}', parent=parent)
        return None
