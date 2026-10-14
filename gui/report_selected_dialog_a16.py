"""Options UI for read-only selected-job reports."""
from __future__ import annotations
import webbrowser
from pathlib import Path
from tkinter import filedialog, messagebox
import customtkinter as ctk
from noark5_workflow.reporting.job_summary_a16 import SECTIONS, PRESETS, ReportOptions, write_selected_jobs_report
from noark5_workflow.reporting.depot_metadata import job_display_name


def open_selected_report_dialog(parent, jobs):
    jobs = tuple(jobs)
    dialog = ctk.CTkToplevel(parent)
    single = len(jobs) == 1
    dialog.title('Rapport for ett uttrekk' if single else 'Samlerapport for valgte jobber')
    
    # Scale to work area, leaving room for Windows taskbar and window decorations.
    screen_height = dialog.winfo_screenheight()
    dialog.geometry(f'800x{min(850, max(510, screen_height - 110))}')
    dialog.minsize(660, 430)
    dialog.transient(parent)
    dialog.grab_set()
    # Fixed footer is packed first; only the options content scrolls.
    buttons=ctk.CTkFrame(dialog,fg_color='transparent')
    buttons.pack(side='bottom',fill='x',padx=22,pady=(9,14))
    content=ctk.CTkScrollableFrame(dialog)
    content.pack(side='top',fill='both',expand=True,padx=8,pady=8)
    heading = (f'Rapport – {jobs[0].job_id} – {job_display_name(jobs[0])}'
               if single else f'Samlerapport – {len(jobs)} valgte jobber')
    ctk.CTkLabel(content, text=heading, wraplength=710, justify='left').pack(anchor='w', padx=22, pady=(10,8))
    level = ctk.StringVar(value='Medium')
    ctk.CTkLabel(content,text='Detaljnivå').pack(anchor='w', padx=22)
    ctk.CTkSegmentedButton(content,values=list(PRESETS),variable=level).pack(fill='x',padx=22,pady=(4,12))
    ctk.CTkLabel(content,text='Rapportdeler – åpne for å tilpasse').pack(anchor='w',padx=22)
    scroll = ctk.CTkFrame(content)
    scroll.pack(fill='x',padx=22,pady=(4,10))
    vars = {k: ctk.BooleanVar(value=k in PRESETS['Medium']) for k in SECTIONS}
    for k,label in SECTIONS.items():
        ctk.CTkCheckBox(scroll,text=label,variable=vars[k]).pack(anchor='w',padx=8,pady=5)
    applying=[False]
    def changed(*_):
        if applying[0]:return
        applying[0]=True
        for k,v in vars.items():v.set(k in PRESETS[level.get()])
        applying[0]=False
    level.trace_add('write',changed)
    ctk.CTkLabel(content,text='Valgfrie vedlegg').pack(anchor='w',padx=22)
    extraction=ctk.BooleanVar(value=False)
    archive_part=ctk.BooleanVar(value=False)
    ctk.CTkCheckBox(content,text='Vedlegg per uttrekk',variable=extraction).pack(anchor='w',padx=22,pady=5)
    ctk.CTkCheckBox(content,text='Vedlegg per arkivdel',variable=archive_part).pack(anchor='w',padx=22,pady=5)
    ctk.CTkLabel(content,text='Hovedrapport og valgte vedlegg lagres direkte i valgt mappe.').pack(anchor='w',padx=22,pady=5)
    ctk.CTkLabel(content,text='Filnavnprefiks (valgfritt)').pack(anchor='w',padx=22,pady=(7,2))
    prefix=ctk.StringVar(value='')
    ctk.CTkEntry(content,textvariable=prefix,placeholder_text='Eksempel: 1502_ephorte_hist').pack(fill='x',padx=22)
    ctk.CTkLabel(content,text='Eksportformater').pack(anchor='w',padx=22,pady=(7,2))
    format_vars={f:ctk.BooleanVar(value=f=='HTML') for f in ('HTML','PDF','JSON')}
    from importlib.util import find_spec
    if not (find_spec('reportlab') and find_spec('bs4')):
        ctk.CTkLabel(content,text='PDF-støtte mangler. Kjør install.bat (GUI eller alle) for å installere den.',
                     wraplength=590,text_color='#d3a354').pack(anchor='w',padx=22)
    format_row=ctk.CTkFrame(content,fg_color='transparent')
    format_row.pack(fill='x',padx=22)
    for fmt,var in format_vars.items():
        ctk.CTkCheckBox(format_row,text=fmt,variable=var).pack(side='left',padx=(0,20))
    ctk.CTkLabel(content,text='Kun lagrede resultater. Ingen ny analyse eller endring av jobbstatus.',wraplength=580).pack(anchor='w',padx=22,pady=(10,4))
    def generate():
        selected=tuple(k for k,v in vars.items() if v.get())
        if not selected:
            messagebox.showwarning('Samlerapport','Velg minst én rapportdel.',parent=dialog);return
        opts=ReportOptions(level.get(),selected,extraction.get(),archive_part.get())
        formats=tuple(fmt.lower() for fmt,var in format_vars.items() if var.get())
        if not formats:
            messagebox.showwarning('Samlerapport','Velg minst ett eksportformat.',parent=dialog);return
        target=filedialog.askdirectory(parent=dialog,title='Velg mappe for rapportfiler',mustexist=True)
        if not target:return
        warnings=[]
        try:
            from noark5_workflow.reporting.report_package_a16 import write_report_package, safe_prefix
            safe_prefix(prefix.get())
            path=write_report_package(Path(target), jobs, opts, prefix=prefix.get(),formats=formats,on_warning=warnings.append)
        except FileExistsError:
            if not messagebox.askyesno('Bekreft overskriving',
                    'En eller flere rapportfiler finnes allerede i valgt mappe. Overskrive kun filene med dette prefikset?',parent=dialog):
                return
            try:
                path=write_report_package(Path(target), jobs, opts, prefix=prefix.get(),formats=formats,overwrite=True,on_warning=warnings.append)
            except Exception as exc:
                messagebox.showerror('Samlerapport',f'Kunne ikke lage rapport:\n{exc}',parent=dialog);return
        except Exception as exc:
            messagebox.showerror('Samlerapport',f'Kunne ikke lage rapport:\n{exc}',parent=dialog);return
        dialog.destroy()
        if warnings:
            messagebox.showwarning('Rapporteksport – delvis fullført',
                '\n'.join(warnings)+'\nHTML/JSON er lagret der disse formatene var valgt.',parent=parent)
        if path.suffix.lower()=='.html':
            webbrowser.open(path.resolve().as_uri())
        else:
            messagebox.showinfo('Samlerapport',f'Rapport lagret: {path}',parent=parent)
    ctk.CTkButton(buttons,text='Lagre og åpne rapport',command=generate).pack(side='left')
    def assess():
        from gui.period_assessment_dialog_a16 import open_period_assessment_dialog
        open_period_assessment_dialog(dialog, jobs)
    ctk.CTkButton(buttons,text='Vurder ytterår',command=assess).pack(side='left',padx=8)
    ctk.CTkButton(buttons,text='Avbryt',command=dialog.destroy).pack(side='right')
    dialog.wait_window()
