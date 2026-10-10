"""Read-only multi-extraction report launcher for Noark 5 Resultatvisninger.

Only explicit user action starts a report. Scans the known DWM report paths,
never the archive content. The existing a6.4 generator remains the authority.
"""
from __future__ import annotations

import queue
import subprocess
import sys
import threading
from pathlib import Path
from tkinter import filedialog, messagebox
import webbrowser

import customtkinter as ctk

REPORT_NAME = 'noark5-uttrekksoversikt.html'
PDF_NAME = 'noark5-uttrekksoversikt.pdf'


def extraction_group_root(report_path: str | Path) -> Path:
    """Find sibling extraction root from a DWM report file; fail closed."""
    path = Path(report_path).resolve()
    for parent in path.parents:
        if parent.name.lower() == 'repository_operations':
            return parent.parent.parent
    raise ValueError('Kan ikke finne repository_operations i rapportstien')


def generator_path() -> Path:
    return Path(__file__).resolve().parent.parent / 'tools' / 'noark5_batch_overview_a6.py'


def available_jobs(source: Path) -> list[str]:
    """List jobs by known report paths only; never walk document trees."""
    from tools.noark5_batch_overview_a6 import locate_reports
    from tools.noark5_batch_overview_a6 import identity
    return sorted({identity(path, {}) for path in locate_reports(source) if identity(path, {}) != 'Ukjent jobb'})


class MultiExtractionOverview(ctk.CTkToplevel):
    def __init__(self, master, *, report_path: str | Path):
        super().__init__(master)
        self.title('Samlet uttrekksoversikt – Noark 5')
        self.geometry('950x710')
        self.minsize(700, 430)
        self._events: queue.Queue = queue.Queue()
        self._running = False
        self._job_vars = {}
        self._last_output: Path | None = None
        try:
            root = extraction_group_root(report_path)
        except ValueError as exc:
            messagebox.showerror('Rapportsti', str(exc), parent=self)
            self.destroy()
            return
        self._source = ctk.StringVar(value=str(root))
        self._output = ctk.StringVar(value=str(Path.home() / 'Documents' / 'DWM-uttrekksoversikt'))
        ctk.CTkLabel(self, text='Samlet uttrekksoversikt – eksisterende depotrapporter',
                     font=ctk.CTkFont(size=13, weight='bold'), anchor='w').pack(fill='x', padx=18, pady=(18, 7))
        ctk.CTkLabel(self, text='Ingen nye Noark 5-tester. Ingen søk i DOKUMENT/content. Ingen automatisk depotgodkjenning.',
                     anchor='w').pack(fill='x', padx=18, pady=(0, 12))
        self._field('Kilde (overordnet mappe med uttrekk)', self._source, browse=False)
        ctk.CTkButton(self, text='Finn jobber i kildemappen', command=self._refresh_jobs, width=210).pack(anchor='w', padx=18, pady=(0, 4))
        self._job_info = ctk.CTkLabel(self, text='Alle oppdagede jobber velges som standard', anchor='w')
        self._job_info.pack(fill='x', padx=18)
        self._job_frame = ctk.CTkScrollableFrame(self, height=125)
        self._job_frame.pack(fill='x', padx=18, pady=4)
        self._refresh_jobs()
        self._field('Rapportmappe', self._output, browse=True)
        actions = ctk.CTkFrame(self, fg_color='transparent')
        actions.pack(fill='x', padx=18, pady=(10, 8))
        self._start_button = ctk.CTkButton(actions, text='Lag rapport – valgte jobber',
                                           command=self._start, width=250)
        self._start_button.pack(side='left', padx=(0, 8))
        self._open_button = ctk.CTkButton(actions, text='Åpne HTML', command=self._open, state='disabled')
        self._open_button.pack(side='left')
        self._pdf_button = ctk.CTkButton(actions, text='Åpne PDF', command=self._open_pdf, state='disabled')
        self._pdf_button.pack(side='left', padx=(8, 0))
        self._state_label = ctk.CTkLabel(self, text='Klar. Velg jobbene som skal inngå.', anchor='w')
        self._state_label.pack(fill='x', padx=18, pady=5)
        self._log = ctk.CTkTextbox(self, font=ctk.CTkFont(size=11), wrap='word')
        self._log.pack(fill='both', expand=True, padx=18, pady=(5, 18))
        self._log.configure(state='disabled')
        self.after(120, self._poll)

    def _field(self, label, variable, *, browse):
        bar = ctk.CTkFrame(self, fg_color='transparent')
        bar.pack(fill='x', padx=18, pady=5)
        ctk.CTkLabel(bar, text=label, width=245, anchor='w').pack(side='left')
        ctk.CTkEntry(bar, textvariable=variable).pack(side='left', fill='x', expand=True, padx=8)
        if browse:
            ctk.CTkButton(bar, text='Velg mappe', width=106, command=self._choose_output).pack(side='left')

    def _refresh_jobs(self):
        if self._running:
            return
        try:
            source = Path(self._source.get())
            jobs = available_jobs(source)
        except (OSError, ValueError) as exc:
            self._job_info.configure(text=f'Kunne ikke finne jobber: {exc}')
            return
        for widget in self._job_frame.winfo_children():
            widget.destroy()
        self._job_vars = {}
        for job in jobs:
            variable = ctk.BooleanVar(value=True)
            self._job_vars[job] = variable
            ctk.CTkCheckBox(self._job_frame, text=job, variable=variable, width=110).pack(side='top', anchor='w', pady=1)
        self._job_info.configure(text=f'Fant {len(jobs)} jobber. Fjern avkrysning for jobber som ikke skal med.')

    def _choose_output(self):
        path = filedialog.askdirectory(parent=self, title='Velg rapportmappe')
        if path:
            self._output.set(path)

    def _append(self, message):
        self._log.configure(state='normal')
        self._log.insert('end', message + '\n')
        self._log.see('end')
        self._log.configure(state='disabled')

    def _start(self):
        if self._running:
            return
        source, target = Path(self._source.get()), Path(self._output.get())
        script = generator_path()
        if not source.is_dir():
            messagebox.showerror('Kilde', f'Mappen finnes ikke: {source}', parent=self)
            return
        if not script.is_file():
            messagebox.showerror('Kode mangler', f'Kan ikke finne {script}', parent=self)
            return
        if not self._output.get().strip():
            messagebox.showerror('Rapportmappe', 'Oppgi en rapportmappe.', parent=self)
            return
        selection = [job for job, var in self._job_vars.items() if var.get()]
        if not selection:
            messagebox.showerror('Jobbvalg', 'Velg minst én jobb. Klikk Finn jobber etter endring av kildemappe.', parent=self)
            return
        self._running = True
        self._last_output = None
        self._open_button.configure(state='disabled')
        self._pdf_button.configure(state='disabled')
        self._start_button.configure(state='disabled')
        self._state_label.configure(text='Kjører – status oppdateres nedenfor')
        self._append(f'Starter {len(selection)} valgte jobber: {source}')
        threading.Thread(target=self._worker, args=(script, source, target, selection), daemon=True).start()

    def _worker(self, script, source, target, selection):
        try:
            command = [sys.executable, '-u', str(script), '--source', str(source), '--output', str(target), '--select', *selection]
            with subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                  text=True, encoding='utf-8', errors='replace', bufsize=1,
                                  env={**__import__('os').environ, 'PYTHONIOENCODING': 'utf-8'}) as process:
                for line in process.stdout:
                    self._events.put(('line', line.rstrip()))
                self._events.put(('done', process.wait(), target))
        except Exception as exc:
            self._events.put(('failure', str(exc)))

    def _poll(self):
        try:
            while True:
                event = self._events.get_nowait()
                if event[0] == 'line':
                    self._append(event[1])
                elif event[0] == 'done':
                    code, target = event[1], event[2]
                    self._running = False
                    self._start_button.configure(state='normal')
                    success = code == 0 and (target / REPORT_NAME).is_file() and (target / PDF_NAME).is_file()
                    self._state_label.configure(text='Fullført – rapport klar' if success else f'Feil under rapportgenerering (kode {code})')
                    if success:
                        self._last_output = target / REPORT_NAME
                        self._open_button.configure(state='normal')
                        self._pdf_button.configure(state='normal')
                elif event[0] == 'failure':
                    self._running = False
                    self._start_button.configure(state='normal')
                    self._state_label.configure(text='Feil under rapportgenerering')
                    self._append('FEIL: ' + event[1])
        except queue.Empty:
            pass
        try:
            if self.winfo_exists():
                self.after(120, self._poll)
        except Exception:
            pass

    def _open(self):
        if self._last_output and self._last_output.is_file():
            webbrowser.open(self._last_output.resolve().as_uri())

    def _open_pdf(self):
        if self._last_output and self._last_output.with_suffix('.pdf').is_file():
            webbrowser.open(self._last_output.with_suffix('.pdf').resolve().as_uri())
