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
        self._job_metadata = {}
        self._quantity_choices = []
        self._quantity_selected = set()
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
        self._prefix = ctk.StringVar(value=saved.get('report_prefix','') if 'saved' in locals() else '')
        self._report_profile = ctk.StringVar(value='Detaljert')
        self._report_layout = ctk.StringVar(value='Én samlet rapport')
        self._report_sections = None
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
        self._field('Filprefiks (valgfritt)', self._prefix)
        profile_bar=ctk.CTkFrame(self, fg_color='transparent')
        profile_bar.pack(fill='x', padx=18, pady=(4,0))
        ctk.CTkLabel(profile_bar,text='Rapportprofil',width=245,anchor='w').pack(side='left')
        ctk.CTkOptionMenu(profile_bar,variable=self._report_profile,values=['Oversikt','Standard','Detaljert'],command=self._profile_changed,width=185).pack(side='left',padx=8)
        ctk.CTkButton(profile_bar,text='Velg rapportinnhold',command=self._choose_report_content,width=190).pack(side='left',padx=10)
        layout_bar=ctk.CTkFrame(self, fg_color='transparent')
        layout_bar.pack(fill='x',padx=18,pady=(3,0))
        ctk.CTkLabel(layout_bar,text='Rapportstruktur',width=245,anchor='w').pack(side='left')
        ctk.CTkOptionMenu(layout_bar,variable=self._report_layout,values=['Én samlet rapport','Hovedrapport + vedlegg per uttrekk'],width=255).pack(side='left',padx=8)
        self._quantity_button = ctk.CTkButton(self, text='Velg Arkade 5-mengdetall (valgfritt)', command=self._choose_quantities, width=260)
        self._quantity_button.pack(anchor='w', padx=18, pady=(3, 0))
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
                json.dumps({'report_folder':self._output.get(),'report_prefix':self._prefix.get().strip()},ensure_ascii=False),encoding='utf-8')
        except OSError:
            pass

    def _field(self, label, variable, *, browse=False):
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
        self._job_metadata = {}
        self._quantity_choices = []
        self._quantity_selected = set()
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
        self._show_jobs(jobs, discover=True)

    def _search_folders(self):
        if self._running or self._mode.get() != 'folders':
            return
        source = Path(self._source.get())
        if not source.is_dir():
            self._clear_jobs(f'Mappen finnes ikke: {source}')
            return
        self._clear_jobs('Søker etter eksisterende depotrapporter ...')
        try:
            from gui.noark5_overview_evidence_a10 import extraction_root, report_candidates
            from tools.noark5_batch_overview_a6 import locate_reports, identity
            with contextlib.redirect_stdout(io.StringIO()):
                reports = locate_reports(source)
            selected = {}
            for report in reports:
                jid = identity(report, {})
                if jid == 'Ukjent jobb':
                    continue
                root = extraction_root(report)
                # A report file lives inside repository_operations; resolve from parents.
                for parent in report.parents:
                    if parent.name.lower() == 'repository_operations':
                        root = parent.parent
                        break
                key = (str(root), jid)
                selected[key] = (jid, root.name, str(root))
            jobs = [selected[key] for key in sorted(selected)]
        except (OSError, ValueError, TypeError) as exc:
            self._clear_jobs(f'Kunne ikke finne jobber: {exc}')
            return
        self._show_jobs(jobs, discover=True)

    def _show_jobs(self, jobs, *, discover=False):
        from gui.noark5_overview_evidence_a10 import extraction_root, evidence_status
        self._clear_jobs(f'Fant {len(jobs)} jobber. Velg en eller flere for rapportering.'
                         if jobs else 'Ingen jobber funnet.')
        if not jobs:
            return
        header = ctk.CTkFrame(self._job_frame, fg_color='transparent')
        header.pack(fill='x', pady=(0, 5))
        for text, width in [('Velg / jobb / uttrekk', 460), ('Depotrapport', 100),
                            ('Arkade 5', 95), ('KDRS Query', 105)]:
            ctk.CTkLabel(header, text=text, width=width, anchor='w',
                         font=ctk.CTkFont(weight='bold')).pack(side='left', padx=(0, 6))
        for job, name, location in jobs:
            root = extraction_root(location)
            status = evidence_status(root, job) if root else {
                'depot':'Ikke funnet', 'arkade':'Ikke påvist', 'kdrs':'Ikke påvist'}
            # Source folder and job id together prevent collisions across joblists.
            key = (str(root) if root else location, job)
            variable = ctk.BooleanVar(value=True)
            self._job_vars[key] = variable
            self._job_metadata[key] = (job, name, location)
            row = ctk.CTkFrame(self._job_frame, fg_color='transparent')
            row.pack(fill='x', pady=1)
            label = f'{job} | {name or (root.name if root else "Ukjent uttrekk")}'
            ctk.CTkCheckBox(row, text=label, variable=variable, width=460).pack(side='left',padx=(0,6))
            for field, width in [('depot',100),('arkade',95),('kdrs',105)]:
                ctk.CTkLabel(row, text=status[field], width=width, anchor='w').pack(side='left',padx=(0,6))

    def _choose_quantities(self):
        """Let the user explicitly select evidenced Arkade totals for reporting only."""
        if self._running:
            return
        selected_jobs = [self._job_metadata[key] for key, var in self._job_vars.items() if var.get()]
        if not selected_jobs:
            messagebox.showinfo('Arkade 5', 'Velg minst én jobb først.', parent=self)
            return
        from gui.noark5_quantity_choices_a116 import candidates_for_jobs, selection_key
        try:
            import contextlib
            import io
            with contextlib.redirect_stdout(io.StringIO()):
                candidates = candidates_for_jobs(
                    selected_jobs,
                    joblist=self._joblist_path if self._mode.get() == 'joblist' else None,
                    source=self._source.get() if self._mode.get() == 'folders' else None,
                )
        except (OSError, ValueError, TypeError) as exc:
            messagebox.showerror('Arkade 5-mengdetall', str(exc), parent=self)
            return
        if not candidates:
            messagebox.showinfo('Arkade 5', 'Ingen entydig dokumenterte uttrekkstotaler funnet for valgte jobber.', parent=self)
            return
        self._quantity_choices = candidates
        dialog = ctk.CTkToplevel(self)
        dialog.title('Velg Arkade 5-totaler – kun rapportgrunnlag')
        dialog.geometry('850x540')
        dialog.transient(self)
        dialog.grab_set()
        ctk.CTkLabel(dialog, text='Velg dokumenterte totaler for hele uttrekket. Ingen DWM- eller arkivdelverdier endres.',
                     anchor='w').pack(fill='x', padx=14, pady=12)
        frame = ctk.CTkScrollableFrame(dialog)
        frame.pack(fill='both', expand=True, padx=14, pady=6)
        vars_by_key = {}
        for choice in candidates:
            key = selection_key(choice)
            var = ctk.BooleanVar(value=key in self._quantity_selected)
            vars_by_key[key] = var
            dwm = 'ukjent' if choice['dwm_count'] is None else str(choice['dwm_count'])
            description = (f"{choice['job']} | {choice['extraction']} | {choice['label']} | "
                           f"Arkade 5: {choice['count']:,} | DWM: {dwm}")
            ctk.CTkCheckBox(frame, text=description.replace(',', ' '), variable=var).pack(anchor='w', padx=6, pady=4)
        shortcuts = ctk.CTkFrame(dialog, fg_color='transparent')
        shortcuts.pack(fill='x', padx=14, pady=(2, 6))
        def choose_by(condition):
            for choice in candidates:
                vars_by_key[selection_key(choice)].set(bool(condition(choice)))
        ctk.CTkButton(shortcuts, text='Velg der DWM mangler',
                      command=lambda: choose_by(lambda c: c.get('dwm_count') is None)).pack(side='left', padx=(0, 8))
        ctk.CTkButton(shortcuts, text='Velg alle',
                      command=lambda: choose_by(lambda c: True)).pack(side='left', padx=(0, 8))
        ctk.CTkButton(shortcuts, text='Fjern alle',
                      command=lambda: choose_by(lambda c: False)).pack(side='left')
        def save():
            self._quantity_selected = {key for key, var in vars_by_key.items() if var.get()}
            self._state_label.configure(text=f'{len(self._quantity_selected)} Arkade 5-total(er) valgt for rapportvisning.')
            dialog.destroy()
        ctk.CTkButton(dialog, text='Bruk valgene', command=save).pack(pady=(2, 12))

    _section_labels = {
        'coverage':'Datadekning', 'sources':'Kildesammenligning',
        'arkade_sources':'Arkade 5-kilder per import', 'archive_parts':'Arkivdeler',
        'arkade_tests':'Arkade 5-testresultater', 'pronom':'PRONOM / filformater',
        'deviations':'Registrerte avvik',
    }
    _profile_defaults = {
        'Oversikt':set(),
        'Standard':{'coverage','sources','archive_parts','arkade_tests','deviations'},
        'Detaljert':set(_section_labels),
    }

    def _profile_changed(self, *_):
        self._report_sections = None
        self._state_label.configure(text=f'Rapportprofil: {self._report_profile.get()} (standard seksjonsvalg).')

    def _choose_report_content(self):
        dialog=ctk.CTkToplevel(self)
        dialog.title('Velg rapportinnhold – Noark 5')
        dialog.geometry('530x510')
        dialog.transient(self)
        dialog.grab_set()
        ctk.CTkLabel(dialog,text='Velg seksjoner i HTML og PDF. JSON og CSV beholder alle data.',anchor='w').pack(fill='x',padx=16,pady=(16,10))
        initial=self._report_sections if self._report_sections is not None else self._profile_defaults[self._report_profile.get()]
        vars_={}
        for key,label in self._section_labels.items():
            var=ctk.BooleanVar(value=key in initial)
            vars_[key]=var
            ctk.CTkCheckBox(dialog,text=label,variable=var).pack(anchor='w',padx=20,pady=7)
        def confirm():
            self._report_sections={key for key,var in vars_.items() if var.get()}
            self._state_label.configure(text=f'{len(self._report_sections)} rapportseksjoner valgt for HTML/PDF.')
            dialog.destroy()
        ctk.CTkButton(dialog,text='Bruk valgene',command=confirm).pack(pady=13)

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
        selection = [self._job_metadata[key][0] for key, var in self._job_vars.items() if var.get()]
        if not selection:
            messagebox.showerror('Jobbvalg', 'Velg minst én jobb. Klikk Finn jobber etter endring av kildemappe.', parent=self)
            return
        prefix=self._prefix.get().strip()
        if prefix and (prefix in ('.','..') or len(prefix)>100 or any(c not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-.' for c in prefix)):
            messagebox.showerror('Filprefiks', 'Bruk bare A-Z, a-z, tall, bindestrek, understrek og punktum (maks 100 tegn).', parent=self)
            return
        basename=(prefix+'_' if prefix else '')+'noark5-uttrekksoversikt'
        existing=[target/(basename+ext) for ext in ('.html','.pdf','.json','.csv') if (target/(basename+ext)).exists()]
        if existing and not messagebox.askyesno('Overskrive rapportfiler', f'{len(existing)} rapportfil(er) finnes allerede med dette navnet. Vil du overskrive dem?', parent=self):
            return
        # Only explicitly checked rows are exported; CLI revalidates against source reports.
        from gui.noark5_quantity_choices_a116 import selected_payload
        quantity_payload = selected_payload(self._quantity_choices, self._quantity_selected)
        self._remember_output()
        self._running = True
        self._last_output = None
        self._open_button.configure(state='disabled')
        self._pdf_button.configure(state='disabled')
        self._start_button.configure(state='disabled')
        self._state_label.configure(text='Kjører – status oppdateres nedenfor')
        self._append(f'Starter {len(selection)} valgte jobber: {source}')
        threading.Thread(target=self._worker, args=(script, source, target, selection, self._joblist_path if use_joblist else None, prefix, quantity_payload, self._report_profile.get().lower(), self._report_sections, self._report_layout.get()), daemon=True).start()

    def _worker(self, script, source, target, selection, joblist=None, prefix='', quantity_payload=None, profile='detaljert', sections=None, layout='Én samlet rapport'):
        try:
            command = [sys.executable, '-u', str(script), '--source', str(source), '--output', str(target), '--select', *selection]
            if joblist: command += ['--joblist', str(joblist)]
            if prefix: command += ['--prefix', prefix]
            command += ['--report-profile', profile]
            if layout == 'Hovedrapport + vedlegg per uttrekk': command += ['--report-layout', 'attachments']
            if sections is not None: command += ['--report-sections', ','.join(sorted(sections))]
            import tempfile
            # Keep the temporary choice manifest alive until the generator has read it.
            with tempfile.TemporaryDirectory(prefix='dwm-quantity-choice-') as temp_dir:
                if quantity_payload and quantity_payload.get('choices'):
                    manifest = Path(temp_dir) / 'choices.json'
                    manifest.write_text(json.dumps(quantity_payload, ensure_ascii=False), encoding='utf-8')
                    command += ['--quantity-selections', str(manifest)]
                self._run_command(command, target, prefix)
        except Exception as exc:
            self._events.put(('failure', str(exc)))

    def _run_command(self, command, target, prefix):
            with subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                  text=True, encoding='utf-8', errors='replace', bufsize=1,
                                  env={**__import__('os').environ, 'PYTHONIOENCODING': 'utf-8'}) as process:
                for line in process.stdout:
                    self._events.put(('line', line.rstrip()))
                self._events.put(('done', process.wait(), target, prefix))

    def _poll(self):
        try:
            while True:
                event = self._events.get_nowait()
                if event[0] == 'line':
                    self._append(event[1])
                elif event[0] == 'done':
                    code, target, prefix = event[1], event[2], event[3]
                    basename=(prefix+'_' if prefix else '')+'noark5-uttrekksoversikt'
                    self._running = False
                    self._start_button.configure(state='normal')
                    expected = tuple(basename + ext for ext in ('.html','.json','.csv'))
                    core_ready = code == 0 and all((target / name).is_file() for name in expected)
                    pdf_ready = core_ready and (target / (basename+'.pdf')).is_file()
                    if core_ready:
                        self._last_output = target / (basename+'.html')
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
