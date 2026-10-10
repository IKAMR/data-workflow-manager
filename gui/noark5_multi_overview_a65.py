"""Read-only multi-extraction report launcher for Noark 5 Resultatvisninger.

Only explicit user action starts a report. Scans the known DWM report paths,
never the archive content. The existing a6.4 generator remains the authority.
"""
from __future__ import annotations

import queue
import contextlib
import io
import json
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
    # GUI owns progress. A discovery click must not flood the console.
    with contextlib.redirect_stdout(io.StringIO()):
        paths = locate_reports(source)
    return sorted({identity(path, {}) for path in paths if identity(path, {}) != 'Ukjent jobb'})


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
        self._joblist_path = self._find_active_joblist()
        self._mode = ctk.StringVar(value='joblist' if self._joblist_path else 'folders')
        self._source = ctk.StringVar(value=str(root))
        self._preferences_path = Path.home() / '.dwm_multi_overview_preferences.json'
        try:
            saved=json.loads(self._preferences_path.read_text(encoding='utf-8'))
            initial_output=saved.get('report_folder') or str(Path.home() / 'Documents' / 'DWM-uttrekksoversikt')
        except (OSError, ValueError, TypeError):
            initial_output=str(Path.home() / 'Documents' / 'DWM-uttrekksoversikt')
        self._output = ctk.StringVar(value=initial_output)
        ctk.CTkLabel(self, text='Samlet uttrekksoversikt – eksisterende depotrapporter',
                     font=ctk.CTkFont(size=13, weight='bold'), anchor='w').pack(fill='x', padx=18, pady=(18, 7))
        ctk.CTkLabel(self, text='Ingen nye Noark 5-tester. Ingen søk i DOKUMENT/content. Ingen automatisk depotgodkjenning.',
                     anchor='w').pack(fill='x', padx=18, pady=(0, 12))
        modebar=ctk.CTkFrame(self, fg_color='transparent')
        modebar.pack(fill='x',padx=18,pady=4)
        ctk.CTkRadioButton(modebar,text='Aktiv jobbliste',variable=self._mode,value='joblist',
            command=self._set_mode, state='normal' if self._joblist_path else 'disabled').pack(side='left',padx=(0,20))
        ctk.CTkRadioButton(modebar,text='Søk i mapper',variable=self._mode,value='folders',
            command=self._set_mode).pack(side='left')
        self._source_container = ctk.CTkFrame(self, fg_color='transparent')
        self._source_container.pack(fill='x', padx=18)
        source_bar = ctk.CTkFrame(self._source_container, fg_color='transparent')
        source_bar.pack(fill='x', pady=5)
        ctk.CTkLabel(source_bar, text='Kilde (overordnet mappe med uttrekk)', width=245, anchor='w').pack(side='left')
        ctk.CTkEntry(source_bar, textvariable=self._source).pack(side='left', fill='x', expand=True, padx=8)
        ctk.CTkButton(self._source_container, text='Finn jobber i kildemappen',
                      command=self._search_folders, width=210).pack(anchor='w', pady=(0, 4))
        self._source.trace_add('write', self._source_changed)
        self._job_info = ctk.CTkLabel(self, text='Alle oppdagede jobber velges som standard', anchor='w')
        self._job_info.pack(fill='x', padx=18)
        self._job_frame = ctk.CTkScrollableFrame(self, height=125)
        self._job_frame.pack(fill='x', padx=18, pady=4)
        self._set_mode()
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

    def _find_active_joblist(self):
        # The result center is a child of the main DWM window. Read its existing
        # job-list path; do not create or change any job-list parameters.
        node=self.master
        while node is not None:
            value=getattr(node,'job_list_path',None)
            if value and Path(value).is_file(): return Path(value)
            node=getattr(node,'master',None)
        return None

    def _remember_output(self):
        try:
            self._preferences_path.write_text(
                json.dumps({'report_folder':self._output.get()},ensure_ascii=False),encoding='utf-8')
        except OSError:
            pass

    def _field(self, label, variable, *, browse):
        bar = ctk.CTkFrame(self, fg_color='transparent')
        bar.pack(fill='x', padx=18, pady=5)
        ctk.CTkLabel(bar, text=label, width=245, anchor='w').pack(side='left')
        ctk.CTkEntry(bar, textvariable=variable).pack(side='left', fill='x', expand=True, padx=8)
        if browse:
            ctk.CTkButton(bar, text='Velg mappe', width=106, command=self._choose_output).pack(side='left')

    def _clear_jobs(self, message):
        for widget in self._job_frame.winfo_children():
            widget.destroy()
        self._job_vars = {}
        self._job_info.configure(text=message)

    def _set_mode(self):
        """Switch data source without starting any filesystem discovery."""
        if self._running:
            return
        if self._mode.get() == 'joblist' and self._joblist_path:
            self._source_container.pack_forget()
            self._load_joblist()
        else:
            self._source_container.pack(fill='x', padx=18, before=self._job_info)
            self._clear_jobs('Velg kildemappe og klikk Finn jobber i kildemappen.')

    def _source_changed(self, *_):
        if not self._running and self._mode.get() == 'folders':
            self._clear_jobs('Kildemappen er endret. Klikk Finn jobber for nytt søk.')

    def _load_joblist(self):
        """Read metadata from the current joblist; no report discovery."""
        try:
            data = json.loads(self._joblist_path.read_text(encoding='utf-8-sig'))
            jobs = [(j.get('job_id'), j.get('name') or Path(j.get('source_root') or '').name,
                     j.get('source_root') or '') for j in data.get('jobs', [])
                    if isinstance(j, dict) and j.get('job_id')]
        except (OSError, ValueError, TypeError) as exc:
            self._clear_jobs(f'Kunne ikke lese aktiv jobbliste: {exc}')
            return
        self._show_jobs(jobs)

    def _search_folders(self):
        if self._running or self._mode.get() != 'folders':
            return
        source = Path(self._source.get())
        if not source.is_dir():
            self._clear_jobs(f'Mappen finnes ikke: {source}')
            return
        self._clear_jobs('Søker etter eksisterende depotrapporter ...')
        try:
            jobs = [(jid, '', '') for jid in available_jobs(source)]
        except (OSError, ValueError, TypeError) as exc:
            self._clear_jobs(f'Kunne ikke finne jobber: {exc}')
            return
        self._show_jobs(jobs)

    def _show_jobs(self, jobs):
        self._clear_jobs(f'Fant {len(jobs)} jobber. Fjern avkrysning for jobber som ikke skal med.'
                         if jobs else 'Ingen jobber funnet.')
        for job, name, location in jobs:
            variable = ctk.BooleanVar(value=True)
            self._job_vars[job] = variable
            text = f'{job} | {name} | {Path(location).name}' if name else job
            ctk.CTkCheckBox(self._job_frame, text=text, variable=variable, width=110).pack(
                side='top', anchor='w', pady=1)

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
        use_joblist=self._mode.get()=='joblist' and self._joblist_path is not None
        script = generator_path()
        if not use_joblist and not source.is_dir():
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
        self._remember_output()
        self._running = True
        self._last_output = None
        self._open_button.configure(state='disabled')
        self._pdf_button.configure(state='disabled')
        self._start_button.configure(state='disabled')
        self._state_label.configure(text='Kjører – status oppdateres nedenfor')
        self._append(f'Starter {len(selection)} valgte jobber: {source}')
        threading.Thread(target=self._worker, args=(script, source, target, selection, self._joblist_path if use_joblist else None), daemon=True).start()

    def _worker(self, script, source, target, selection, joblist=None):
        try:
            command = [sys.executable, '-u', str(script), '--source', str(source), '--output', str(target), '--select', *selection]
            if joblist: command += ['--joblist', str(joblist)]
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
                    expected = ('noark5-uttrekksoversikt.html',
                                'noark5-uttrekksoversikt.json', 'noark5-uttrekksoversikt.csv')
                    core_ready = code == 0 and all((target / name).is_file() for name in expected)
                    pdf_ready = core_ready and (target / PDF_NAME).is_file()
                    if core_ready:
                        self._last_output = target / REPORT_NAME
                        self._open_button.configure(state='normal')
                        if pdf_ready:
                            self._pdf_button.configure(state='normal')
                        self._state_label.configure(
                            text='Fullført – HTML, JSON, CSV og PDF klare' if pdf_ready
                            else 'Delvis fullført – HTML, JSON og CSV klare; PDF mangler')
                    else:
                        self._state_label.configure(text=f'Feil under rapportgenerering (kode {code})')
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
