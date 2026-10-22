"""Options UI for read-only selected-job reports (shared a20 report service)."""
from __future__ import annotations
import webbrowser
import queue
import threading
from pathlib import Path
from tkinter import filedialog, messagebox
import customtkinter as ctk
from noark5_workflow.reporting.job_summary_a16 import SECTIONS, PRESETS, ReportOptions
from noark5_workflow.reporting.depot_metadata import job_display_name


def open_selected_report_dialog(parent, jobs):
    jobs = tuple(jobs)
    dialog = ctk.CTkToplevel(parent)
    single = len(jobs) == 1
    dialog.title('Rapport for ett uttrekk' if single else 'Samlerapport for valgte jobber')

    # Scale to work area, leaving room for Windows taskbar and decorations.
    screen_height = dialog.winfo_screenheight()
    dialog.geometry(f'800x{min(850, max(510, screen_height - 110))}')
    dialog.minsize(660, 430)
    dialog.transient(parent)
    dialog.grab_set()
    buttons = ctk.CTkFrame(dialog, fg_color='transparent')
    buttons.pack(side='bottom', fill='x', padx=22, pady=(9,14))
    content = ctk.CTkScrollableFrame(dialog)
    content.pack(side='top', fill='both', expand=True, padx=8, pady=8)
    heading = (f'Rapport – {jobs[0].job_id} – {job_display_name(jobs[0])}'
               if single else f'Samlerapport – {len(jobs)} valgte jobber')
    ctk.CTkLabel(content, text=heading, wraplength=710, justify='left').pack(
        anchor='w', padx=22, pady=(10,8))
    level = ctk.StringVar(value='Medium')
    ctk.CTkLabel(content, text='Detaljnivå').pack(anchor='w', padx=22)
    ctk.CTkSegmentedButton(content, values=list(PRESETS), variable=level).pack(
        fill='x', padx=22, pady=(4,12))
    ctk.CTkLabel(content,
        text='Medium: journalposttyper og sentrale kategorier. Full: alle lagrede kategorier, med detaljer i vedlegg A/B når de velges.',
        justify='left',wraplength=710).pack(anchor='w',padx=22,pady=(0,8))
    ctk.CTkLabel(content, text='Rapportdeler – åpne for å tilpasse').pack(anchor='w', padx=22)
    scroll = ctk.CTkFrame(content)
    scroll.pack(fill='x', padx=22, pady=(4,10))
    vars = {k: ctk.BooleanVar(value=k in PRESETS['Medium']) for k in SECTIONS}
    for key,label in SECTIONS.items():
        ctk.CTkCheckBox(scroll, text=label, variable=vars[key]).pack(anchor='w', padx=8, pady=5)
    applying = [False]
    def changed(*_):
        if applying[0]:
            return
        applying[0] = True
        for key,value in vars.items():
            value.set(key in PRESETS[level.get()])
        applying[0] = False
    level.trace_add('write',changed)
    ctk.CTkLabel(content, text='Valgfrie vedlegg').pack(anchor='w', padx=22)
    extraction = ctk.BooleanVar(value=False)
    archive_part = ctk.BooleanVar(value=False)
    ctk.CTkCheckBox(content, text='Vedlegg per uttrekk', variable=extraction).pack(
        anchor='w', padx=22, pady=5)
    ctk.CTkCheckBox(content, text='Vedlegg per arkivdel', variable=archive_part).pack(
        anchor='w', padx=22, pady=5)
    ctk.CTkLabel(content, text='Rapporten bygges først lokalt, og kopieres deretter til valgt mappe. Ved diskbrudd venter eksporten på ny tilkobling.').pack(
        anchor='w', padx=22, pady=5)
    ctk.CTkLabel(content, text='Filnavnprefiks (valgfritt)').pack(
        anchor='w', padx=22, pady=(7,2))
    prefix = ctk.StringVar(value='')
    ctk.CTkEntry(content, textvariable=prefix,
                 placeholder_text='Eksempel: 1502_ephorte_hist').pack(fill='x', padx=22)
    ctk.CTkLabel(content, text='Eksportformater').pack(anchor='w', padx=22, pady=(7,2))
    format_vars = {fmt:ctk.BooleanVar(value=fmt=='HTML') for fmt in ('HTML','PDF','JSON','CSV')}
    from importlib.util import find_spec
    if not (find_spec('reportlab') and find_spec('bs4')):
        ctk.CTkLabel(content,
                     text='PDF-støtte mangler. Kjør install.bat for å installere den.',
                     wraplength=590, text_color='#d3a354').pack(anchor='w', padx=22)
    format_row = ctk.CTkFrame(content, fg_color='transparent')
    format_row.pack(fill='x', padx=22)
    for fmt,var in format_vars.items():
        ctk.CTkCheckBox(format_row, text=fmt, variable=var).pack(side='left', padx=(0,20))
    ctk.CTkLabel(content,
                 text='Én felles rapporttjeneste. Kun lagrede resultater; ingen analyse eller endring av jobbstatus.',
                 wraplength=580).pack(anchor='w', padx=22, pady=(10,4))

    # The exporter works on a background thread. Tk variables, dialogs and
    # windows are accessed ONLY on the Tk thread via this local event queue.
    events = queue.Queue()
    state = {'running':False, 'cancel':None, 'thread':None, 'log':''}
    pending_decision = queue.Queue(maxsize=1)
    warnings = []
    status_label = ctk.CTkLabel(buttons, text='', wraplength=660,
                                font=('Segoe UI', 11), anchor='w', justify='left')
    status_label.pack(side='bottom', fill='x', pady=(8,0))

    def close_or_cancel():
        if state['running']:
            state['cancel'].set()
            status_label.configure(text='Stopper etter pågående filoperasjon. Ingen kilde- eller jobbdata endres.')
            return
        dialog.destroy()

    def finish():
        state['running'] = False
        start_button.configure(state='normal')
        assess_button.configure(state='normal')
        cancel_button.configure(text='Avbryt')

    def poll_worker():
        while True:
            try:
                kind, payload = events.get_nowait()
            except queue.Empty:
                break
            if kind == 'progress':
                stage, msg, done, total, log_path = payload
                state['log'] = log_path
                status_label.configure(text=msg)
            elif kind == 'overwrite':
                filenames = payload
                approved = messagebox.askyesno('Bekreft overskriving',
                    'Rapportfiler finnes i målmappen. Overskrive eksisterende filer '
                    'med dette filnavnprefikset?\n\n' +
                    '\n'.join(filenames[:3]) +
                    ('\n…' if len(filenames) > 3 else ''), parent=dialog)
                pending_decision.put(approved)
            elif kind == 'warning':
                warnings.append(payload)
            elif kind == 'completed':
                path = Path(payload)
                finish()
                dialog.destroy()
                if warnings:
                    summary = '\n'.join(warnings[:12])
                    if len(warnings)>12:
                        summary += f'\n… {len(warnings)-12} flere merknader.'
                    messagebox.showwarning('Rapporteksport – kontrollmerknader',
                        summary + ('\nLogg: '+state['log'] if state['log'] else ''),parent=parent)
                if path.suffix.lower() == '.html':
                    webbrowser.open(path.resolve().as_uri())
                else:
                    messagebox.showinfo('Samlerapport', 'Rapport lagret: '+str(path),parent=parent)
                return
            elif kind == 'cancelled':
                finish()
                status_label.configure(text='Eksporten er stoppet. Logg: '+str(payload))
            elif kind == 'failed':
                finish()
                reason, log_path = payload
                status_label.configure(text='Eksport mislyktes. Se lokal rapportlogg: '+log_path)
                messagebox.showerror('Samlerapport',
                    'Kunne ikke lage rapport:\n'+reason+'\n\nDetaljer i: '+log_path,
                    parent=dialog)
        if state['running']:
            dialog.after(250, poll_worker)

    def generate():
        if state['running']:
            return
        selected = tuple(k for k,v in vars.items() if v.get())
        if not selected:
            messagebox.showwarning('Samlerapport','Velg minst én rapportdel.',parent=dialog)
            return
        opts = ReportOptions(level.get(),selected,extraction.get(),archive_part.get())
        formats = tuple(fmt.lower() for fmt,var in format_vars.items() if var.get())
        if not formats:
            messagebox.showwarning('Samlerapport','Velg minst ett eksportformat.',parent=dialog)
            return
        target = filedialog.askdirectory(parent=dialog,title='Velg mappe for rapportfiler',mustexist=True)
        if not target:
            return
        stop = threading.Event()
        state['running'] = True
        state['cancel'] = stop
        state['log'] = ''
        warnings.clear()
        while not pending_decision.empty():
            try:
                pending_decision.get_nowait()
            except queue.Empty:
                break
        start_button.configure(state='disabled')
        assess_button.configure(state='disabled')
        cancel_button.configure(text='Stopp eksport')
        status_label.configure(text='Starter rapporteksport i bakgrunnen …')
        export_prefix = prefix.get()

        def worker():
            from noark5_workflow.reporting.report_recovery_a203 import (
                write_reconnectable_report, ExportStopped)
            from noark5_workflow.reporting.report_service_a20 import write_report_package

            def notify(stage, msg, done, total, logfile):
                events.put(('progress',(stage,msg,done,total,logfile)))

            def confirm(paths):
                events.put(('overwrite',paths))
                while not stop.is_set():
                    try:
                        return pending_decision.get(timeout=0.25)
                    except queue.Empty:
                        continue
                return False

            try:
                path = write_reconnectable_report(Path(target), jobs, opts,
                       prefix=export_prefix, formats=formats, cancelled=stop,
                       on_progress=notify,
                       on_warning=lambda msg: events.put(('warning',str(msg))),
                       confirm_overwrite=confirm, writer=write_report_package)
                events.put(('completed',str(path)))
            except ExportStopped:
                events.put(('cancelled',state['log']))
            except Exception as exc:
                # Error detail + traceback are preserved by the local session.
                # Errno 22 is intentionally NOT reported as a verified disk loss.
                if stop.is_set():
                    events.put(('cancelled',state['log']))
                else:
                    events.put(('failed',(str(exc),state['log'] or '(logg ikke opprettet)')))

        state['thread'] = threading.Thread(target=worker, daemon=True,
                                           name='dwm-selected-report-export')
        state['thread'].start()
        dialog.after(250, poll_worker)

    start_button = ctk.CTkButton(buttons,text='Lagre og åpne rapport',command=generate)
    start_button.pack(side='left')
    def assess():
        from gui.period_assessment_dialog_a16 import open_period_assessment_dialog
        open_period_assessment_dialog(dialog,jobs)
    assess_button = ctk.CTkButton(buttons,text='Vurder ytterår',command=assess)
    assess_button.pack(side='left',padx=8)
    cancel_button = ctk.CTkButton(buttons,text='Avbryt',command=close_or_cancel)
    cancel_button.pack(side='right')
    dialog.protocol('WM_DELETE_WINDOW', close_or_cancel)
    dialog.wait_window()
