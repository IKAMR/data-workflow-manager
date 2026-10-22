from __future__ import annotations

import queue
import re
import threading
from pathlib import Path
from tkinter import filedialog, messagebox

import customtkinter as ctk

from . import theme
from .jobs_window_v017_a1 import V017A1JobsWindow


def _recovery_preview_text(plan):
    """Operator preview: distinguish DWM reports from partial report jobs."""
    jobs = list(plan.jobs)
    with_report = sum(bool(getattr(job, 'has_report', False)) for job in jobs)
    # Legacy a20.6 preview fakes and report-only plans expose old attributes.
    if not any(hasattr(job, 'has_report') for job in jobs):
        with_report = len(jobs)
    lines = [
        f'Funnet: {len(plan.extraction_folders)} uttrekksmapper, '
        f'{len(jobs)} rapportjobber (med DWM-depotrapport: {with_report}; '
        f'uten depotrapport: {len(jobs) - with_report}).',
        '',
        'Rapportjobbene opprettes UTEN kjørbar workflow. Manglende tall er ukjent, ikke null.',
        'Tidligere DWM-arkiver, KDRS Query og Arkade 5 markeres som kilder, men '
        'ikke som verifiserte DWM-depotrapporter.',
        '',
    ]
    for job in jobs:
        verified = bool(getattr(job, 'manifest_verified', False))
        has_report = bool(getattr(job, 'has_report', False)) if hasattr(job, 'has_report') else True
        role = ('DWM-DEPOTRAPPORT' if has_report else 'DELVIS / IKKE ANALYSERT')
        lines.append(f'{job.job_id} | {job.name} | {role}')
        evidence = tuple(getattr(job, 'evidence', ()) or ())
        if evidence:
            lines.append('    Tilgjengelige kilder: ' + '; '.join(evidence))
        if has_report:
            lines.append('    Rapportkilde: ' + ('manifest verifisert' if verified else
                         'manifest/kildeidentitet ikke verifisert'))
    if not jobs:
        lines.append('Ingen identifiserbare uttrekk eller rapportjobber ble funnet.')
    lines.extend(['', 'Lagre en NY .n5jobs på en stabil disk (for eksempel C:), '
                  'og velg deretter «Åpne lagret jobbliste».'])
    if plan.missing_report_extractions:
        lines.extend(['', f'{len(plan.missing_report_extractions)} uttrekksmapper uten lagret '
                      'DWM-depotrapport (ikke feilaktig merket som ferdige):'])
        lines.extend('  ' + path.name for path in plan.missing_report_extractions)
    if plan.existing_job_lists:
        lines.extend(['', 'Eksisterende jobblister (ikke endret):'])
        lines.extend('  ' + str(path) for path in plan.existing_job_lists)
    if plan.archived_dwm_zips:
        lines.extend(['', f'{len(plan.archived_dwm_zips)} eldre DWM ZIP-arkiv(er) '
                      '(ikke pakket ut eller tolket som komplette depotrapporter):'])
        lines.extend('  ' + str(path) for path in plan.archived_dwm_zips)
    if plan.warnings:
        lines.extend(['', f'{len(plan.warnings)} kilde-/lesemerknad(er):'])
        lines.extend('  ' + note for note in plan.warnings)
    return '\n'.join(lines)


class V017A2JobsWindow(V017A1JobsWindow):
    """Selected-job reports, external evidence and read-only DWM recovery."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        parent = self.report_selected_button.master
        self.evidence_status_button = ctk.CTkButton(
            parent, text='Evidensstatus', width=112,
            fg_color=theme.BUTTON_BG,
            hover_color=theme.BUTTON_HOVER,
            command=self._open_evidence_status,
        )
        self.evidence_status_button.pack(
            side='left', padx=(0, 6), before=self.report_selected_button,
        )
        self.recover_reports_button = ctk.CTkButton(
            parent, text='Gjenfinn DWM-jobber', width=138,
            fg_color=theme.BUTTON_BG,
            hover_color=theme.BUTTON_HOVER,
            command=self._recover_report_jobs,
        )
        self.recover_reports_button.pack(
            side='left', padx=(0, 6), before=self.evidence_status_button,
        )

    def _open_evidence_status(self):
        """Read-only: no implicit source migration, import or XPath rerun."""
        from .external_evidence_status_a18 import open_evidence_status_dialog
        selected = tuple(self._selected_for_action())
        chosen = selected if selected else tuple(self.batch.jobs())
        if chosen:
            open_evidence_status_dialog(self, chosen, all_jobs=not bool(selected))

    def _recover_report_jobs(self):
        """Inspect saved DWM reports and let the user explicitly save a list.

        The same dialog holds the scan, final preview and save action. A result
        is NEVER shown as final before the worker has posted its 'ok' event.
        Worker code never accesses Tk; closing while scanning is safe.
        """
        existing = getattr(self, '_dwm_recovery_window', None)
        if existing is not None:
            try:
                if existing.winfo_exists():
                    existing.deiconify()
                    existing.lift()
                    existing.focus_force()
                    return
            except Exception:
                pass

        if self._batch_running:
            messagebox.showinfo('Gjenfinn DWM-jobber',
                                'Stopp kjørende jobber før jobblistegjenfinning.', parent=self)
            return
        chosen = filedialog.askdirectory(
            parent=self,
            title='Velg arkiv-noark5, kommune, uttrekk eller dwm-mappe',
            mustexist=True)
        if not chosen:
            return
        directory = Path(chosen)
        window = ctk.CTkToplevel(self)
        self._dwm_recovery_window = window
        window.title('Gjenfinn DWM-rapportjobber')
        screen_h = window.winfo_screenheight()
        window.geometry(f'880x{min(660, max(430, screen_h - 140))}')
        window.minsize(650, 370)
        window.transient(self)

        title = ctk.CTkLabel(window, text='Gjenfinn alle uttrekk som rapportjobber fra arkiv- og DWM-data',
                             font=('Segoe UI', 11, 'bold'), anchor='w')
        title.pack(fill='x', padx=20, pady=(17, 6))
        status = ctk.CTkLabel(window, text=f'Søker i {directory}',
                              wraplength=820, justify='left', anchor='w',
                              font=('Segoe UI', 11))
        status.pack(fill='x', padx=20, pady=(0, 5))
        progress_text = ctk.CTkLabel(window,
                                     text='Søker etter uttrekk og lagrede depotrapporter. '
                                          'Ingen XPath, Arkade 5 eller nye analyser kjøres.',
                                     wraplength=820, justify='left', anchor='w',
                                     font=('Segoe UI', 11))
        progress_text.pack(fill='x', padx=20, pady=(0, 7))
        progress_bar = ctk.CTkProgressBar(window, mode='indeterminate')
        progress_bar.pack(fill='x', padx=20, pady=(0, 10))
        progress_bar.start()

        details = ctk.CTkTextbox(window, wrap='word', font=('Segoe UI', 11))
        details.pack(fill='both', expand=True, padx=20, pady=(0, 8))

        def show_details(content):
            details.configure(state='normal')
            details.delete('1.0', 'end')
            details.insert('1.0', content)
            details.configure(state='disabled')

        show_details('Søket pågår. Resultater vises her når skanningen er avsluttet.\n'
                     'Eksisterende rapportfiler, jobblister og kildeuttrekk endres ikke.')

        actions = ctk.CTkFrame(window, fg_color='transparent')
        actions.pack(fill='x', padx=20, pady=(2, 15))
        stop = threading.Event()
        results = queue.Queue()
        state = {'phase': 'searching', 'plan': None, 'saved': None}

        def close():
            state['phase'] = 'closed'
            stop.set()
            self._dwm_recovery_window = None
            window.destroy()

        close_button = ctk.CTkButton(actions, text='Avbryt', command=close, width=110)
        close_button.pack(side='right')

        def save_found():
            if state['phase'] != 'ready' or state['plan'] is None:
                return
            safe_name = re.sub(r'[^A-Za-z0-9_-]', '-', directory.name or 'dwm')
            filename = filedialog.asksaveasfilename(
                parent=window, title='Lagre rekonstruert jobbliste på en stabil disk',
                initialfile=f'gjenfunnet-{safe_name}.n5jobs',
                defaultextension='.n5jobs',
                filetypes=[('DWM-jobbliste', '*.n5jobs'), ('Alle filer', '*.*')])
            if not filename:
                return
            try:
                from noark5_workflow.reporting.report_job_discovery_a207 import save_available_report_jobs
                output = save_available_report_jobs(state['plan'], filename)
            except (OSError, ValueError) as exc:
                status.configure(text='Kunne ikke lagre jobblisten.')
                messagebox.showerror('Gjenfinn DWM-jobber', str(exc), parent=window)
                return
            state['saved'] = output
            status.configure(text=f'Ny rapportjobbliste lagret: {output}')
            progress_text.configure(text='Rapportjobbene kan åpnes nå eller senere via Jobbliste → Åpne.')
            open_button.configure(state='normal')

        save_button = ctk.CTkButton(actions, text='Lagre ny jobbliste ...',
                                    command=save_found, state='disabled', width=173)
        save_button.pack(side='left', padx=(0, 8))

        def open_saved():
            output = state['saved']
            if output is None or state['phase'] != 'ready':
                return
            opener = getattr(self.master, '_load_job_list_file', None)
            if opener is None:
                messagebox.showinfo('Gjenfinn DWM-jobber',
                                    'Åpne den lagrede .n5jobs via Jobbliste → Åpne.', parent=window)
                return
            if not messagebox.askyesno('Åpne gjenfunnet jobbliste',
                        'Åpne ny rapportjobbliste nå?\n\n'
                        'Gjeldende jobbliste erstattes i minnet. Ulagrede endringer i '
                        'den gamle listen kan gå tapt. Gjenfunne jobber har ingen '
                        'workflow og skal kun brukes til rapport.', parent=window):
                return
            try:
                loaded = opener(output, show_error=True)
            except Exception as exc:
                messagebox.showerror('Gjenfinn DWM-jobber',
                                     f'Kunne ikke åpne jobblisten: {exc}', parent=window)
                return
            if loaded:
                close()
                self.refresh()

        open_button = ctk.CTkButton(actions, text='Åpne lagret jobbliste',
                                    command=open_saved, state='disabled', width=170)
        open_button.pack(side='left')
        window.protocol('WM_DELETE_WINDOW', close)

        def worker():
            try:
                from noark5_workflow.reporting.report_job_discovery_a207 import discover_available_report_jobs
                plan = discover_available_report_jobs(
                    directory, cancelled=stop,
                    on_progress=lambda message: results.put(('progress', message)))
                results.put(('ok', plan))
            except Exception as exc:
                results.put(('error', str(exc)))

        threading.Thread(target=worker, daemon=True,
                         name='dwm-report-job-discovery').start()

        def poll():
            if state['phase'] != 'searching':
                return
            try:
                if not window.winfo_exists():
                    return
            except Exception:
                return
            completed = None
            # Process the whole queue: never let a stale progress message
            # overwrite the final result when both arrive in one Tk tick.
            while True:
                try:
                    kind, payload = results.get_nowait()
                except queue.Empty:
                    break
                if kind == 'progress' and completed is None:
                    progress_text.configure(text=str(payload))
                elif kind in ('ok', 'error'):
                    completed = (kind, payload)
            if completed is None:
                window.after(150, poll)
                return
            progress_bar.stop()
            progress_bar.pack_forget()
            close_button.configure(text='Lukk')
            kind, payload = completed
            if kind == 'error':
                state['phase'] = 'error'
                status.configure(text='Søket kunne ikke fullføres. Ingen jobbliste er opprettet.')
                progress_text.configure(text='Kontroller disktilkobling og valgt mappe før nytt søk.')
                show_details(str(payload))
                return
            plan = payload
            state['phase'] = 'ready'
            state['plan'] = plan
            with_report = sum(bool(getattr(job, 'has_report', True)) for job in plan.jobs)
            count_word = 'rapportjobb' if len(plan.jobs) == 1 else 'rapportjobber'
            status.configure(text=f'Ferdig: {len(plan.extraction_folders)} uttrekksmapper, '
                                  f'{len(plan.jobs)} {count_word} funnet ('
                                  f'{with_report} med komplett DWM-depotrapport).')
            progress_text.configure(text='Kontroller funnene nedenfor, og velg selv om '
                                         'du vil lagre en ny jobbliste.')
            show_details(_recovery_preview_text(plan))
            if plan.jobs:
                save_button.configure(state='normal')

        window.after(150, poll)
