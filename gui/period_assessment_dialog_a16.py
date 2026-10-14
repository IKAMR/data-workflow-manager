"""Manual period review for selected jobs, without re-running XPath analyses."""
from __future__ import annotations
import tkinter as tk
from tkinter import messagebox
import customtkinter as ctk
from noark5_workflow.reporting.job_summary_a16 import _latest_report, _extraction_label
from noark5_workflow.reporting.period_assessment_a16 import load_assessment, review_candidate, save_assessment
from noark5_workflow.reporting.yearly_volume_a16 import METRICS, archive_part_volumes, combined_volumes, sparse_boundary_years, registration_years
from noark5_workflow.reporting.period_kdrs_evidence_a18 import (
    load_job_kdrs_period_evidence, format_kdrs_scope, summarize_kdrs_period_sources,
)


def open_period_assessment_dialog(parent, jobs):
    jobs = tuple(jobs)
    window = ctk.CTkToplevel(parent)
    window.title('Periodevurdering – valgte jobber')
    # The operator may resize the window as well as the internal year-volume pane.
    window.geometry(f'{min(1100, max(790, window.winfo_screenwidth() - 100))}x'
                    f'{min(840, max(560, window.winfo_screenheight() - 110))}')
    window.minsize(720, 510)
    window.transient(parent)
    window.grab_set()
    choices = [f'{j.job_id} – {_extraction_label(j, _latest_report(j)[0])}' for j in jobs]
    idx = ctk.IntVar(value=0)
    buttons = ctk.CTkFrame(window, fg_color='transparent')
    buttons.pack(side='bottom', fill='x', padx=18, pady=12)
    # Independent scrolling and a draggable divider. The yearly evidence pane
    # remains useful even when Standard/U1/U2 contains hundreds of yearly rows.
    panes = tk.PanedWindow(window, orient=tk.VERTICAL, sashwidth=10,
                           sashrelief='raised', showhandle=True, borderwidth=0,
                           background='#333333', opaqueresize=True)
    panes.pack(fill='both', expand=True, padx=8, pady=8)
    upper = ctk.CTkFrame(panes, fg_color='transparent')
    lower = ctk.CTkFrame(panes, fg_color='transparent')
    panes.add(upper, minsize=160, stretch='always')
    panes.add(lower, minsize=160, stretch='always')
    body = ctk.CTkScrollableFrame(upper)
    body.pack(fill='both', expand=True)
    # Bottom panel owns its own scrollbar; its height follows the drag handle.
    # No initial sash placement is forced after a user adjusts the divider.
    ctk.CTkLabel(body, text='Uttrekk').pack(anchor='w', padx=18, pady=(16, 3))
    dropdown = ctk.CTkOptionMenu(body, values=choices, width=635)
    dropdown.pack(anchor='w', padx=18)
    details = ctk.CTkTextbox(body, height=220, wrap='word')
    details.pack(fill='x', padx=18, pady=12)
    input_row = ctk.CTkFrame(body, fg_color='transparent')
    input_row.pack(fill='x', padx=18)
    ctk.CTkLabel(input_row, text='Vurdert fra år').pack(side='left')
    first = ctk.CTkEntry(input_row, width=75)
    first.pack(side='left', padx=10)
    ctk.CTkLabel(input_row, text='til år').pack(side='left')
    last = ctk.CTkEntry(input_row, width=75)
    last.pack(side='left', padx=10)
    status = ctk.StringVar(value='ikke_vurdert')
    ctk.CTkLabel(body, text='Vurderingsstatus').pack(anchor='w', padx=18, pady=(12, 3))
    ctk.CTkSegmentedButton(body, values=['ikke_vurdert', 'godkjent', 'undersokes'], variable=status).pack(fill='x', padx=18)
    ctk.CTkLabel(body, text='Begrunnelse').pack(anchor='w', padx=18, pady=(12, 3))
    comment = ctk.CTkTextbox(body, height=95)
    comment.pack(fill='x', padx=18)

    header = ctk.CTkFrame(lower, fg_color='transparent')
    header.pack(fill='x', padx=10, pady=(5, 0))
    ctk.CTkLabel(header, text='Årlig produksjonsvolum – DWM og KDRS Query (separate kilder)',
                 anchor='w').pack(side='left', padx=(8, 8))
    ctk.CTkLabel(header, text='Dra skillelinjen over for mer plass',
                 anchor='e').pack(side='right', padx=(8, 8))
    scope = ctk.CTkOptionMenu(lower, values=['Samlet uttrekk'], width=635)
    scope.pack(fill='x', padx=18, pady=(3, 0))
    volume = ctk.CTkTextbox(lower, height=280, wrap='none', font=('Consolas', 12))
    volume.pack(fill='both', expand=True, padx=18, pady=(5, 10))
    current_parts = []
    current_report = {}
    current_kdrs = {}
    kdrs_scopes = {}

    def show_scope(choice):
        lines = []
        if choice == 'Samlet uttrekk' or choice.startswith('DWM arkivdel '):
            if choice == 'Samlet uttrekk':
                totals = combined_volumes(current_parts)
                registration = registration_years(current_report.get('report'))
            else:
                selected_index = scope.cget('values').index(choice) - 1
                totals = current_parts[selected_index][2]
                entries = ((current_report.get('report') or {}).get('archive_parts') or [])
                yearly = (entries[selected_index].get('yearly_volume') or {}) if selected_index < len(entries) else {}
                raw = yearly.get('registration')
                registration = {}
                if isinstance(raw, dict):
                    for y, count in raw.items():
                        try:
                            year, number = int(y), int(count)
                        except (TypeError, ValueError):
                            continue
                        if 1000 <= year <= 9999 and number >= 0:
                            registration[year] = number
                else:
                    registration = None
            lines = ['DWM – lagret XPath-årsvolum',
                     'År     Saker      Reg.       JP     Dok.beskr.    Dok.obj.',
                     '------------------------------------------------------------']
            years = set(totals) | set(registration or {})
            for year in sorted(years):
                row = totals.get(year)
                reg = str(registration.get(year, '–')) if registration is not None else '–'
                # Other series are unknown for a registration-only year, not zero.
                folder = str(row['folder']) if row is not None else '–'
                journal = str(row['journal']) if row is not None else '–'
                description = str(row['document_description']) if row is not None else '–'
                obj = str(row['document_object']) if row is not None else '–'
                lines.append(f'{year:<6} {folder:>7} {reg:>9} {journal:>8} {description:>12} {obj:>11}')
            if not years:
                lines.append('Ikke tilgjengelig – betyr ikke null aktivitet.')
            if registration is None:
                lines.append('Registreringer per år: Ikke tilgjengelig (ikke 0).')
            sparse = sparse_boundary_years(totals)
            if sparse:
                lines += ['', 'Ytterår med få observasjoner – må vurderes: ' + ', '.join(str(y) for y, _ in sparse)]
            if choice == 'Samlet uttrekk':
                runs = current_kdrs.get('runs') or []
                if runs:
                    lines.extend(['', 'KDRS Query – egne kilder (ikke summert):'])
                    lines.extend(summarize_kdrs_period_sources(runs))
                    lines.append('Velg en bestemt KDRS-kilde i menyen for hele årsfordelingen.')
        elif choice in kdrs_scopes:
            run, part = kdrs_scopes[choice]
            lines.extend(format_kdrs_scope(run, part))
        if not lines:
            lines = ['Ingen årsvolum tilgjengelig i dette kildeutvalget.']
        lines += ['', 'Volum alene avgjør aldri arkivperioden.']
        volume.configure(state='normal')
        volume.delete('1.0', 'end')
        volume.insert('1.0', '\n'.join(lines))
        volume.configure(state='disabled')
    scope.configure(command=show_scope)

    def load_choice(choice):
        i = choices.index(choice)
        idx.set(i)
        job = jobs[i]
        data, _, diagnostic = _latest_report(job)
        saved = load_assessment(job)
        candidate = review_candidate(data)
        current_report['report'] = data
        current_kdrs.clear()
        current_kdrs.update(load_job_kdrs_period_evidence(job))
        current_parts.clear()
        current_parts.extend(archive_part_volumes(data))
        kdrs_scopes.clear()
        scopes = ['Samlet uttrekk'] + [f'DWM arkivdel {i+1}. {title} ({sysid[:8]})'
                                     for i,(sysid,title,_) in enumerate(current_parts)]
        for run in current_kdrs.get('runs') or []:
            for part in run.get('scopes') or []:
                # Include whole-extraction Standard/U1 too. Otherwise they
                # cannot be inspected separately from the long combined view.
                label = ('KDRS ' + str(run.get('report_type')) + ' / '
                         + str(run.get('import_id')) + ' / ' + str(part.get('label')))
                if label in kdrs_scopes:
                    label += ' [' + str(len(kdrs_scopes) + 1) + ']'
                kdrs_scopes[label] = (run, part)
                scopes.append(label)
        scope.configure(values=scopes)
        scope.set('Samlet uttrekk')
        show_scope('Samlet uttrekk')
        def readable_years(value):
            return str(value) if value else 'Ikke tilgjengelig'
        has_dwm = bool(candidate.get('observed_years'))
        lines = ['Oppgitt: ' + readable_years(candidate.get('declared_years')),
                 'DWM XPath samlet: ' + readable_years(candidate.get('observed_years')),
                 'DWM dokumentbeskrivelser/-objekter: ' + readable_years(candidate.get('document_years')),
                 'DWM-forslag: ' + readable_years(candidate.get('proposed_years')),
                 'Motstrid mellom DWM-kilder: ' + ('Ja' if candidate.get('conflicting_sources') else 'Nei'),
                 'Vurdering kreves: ' + ('Kan ikke vurderes – DWM XPath mangler' if not has_dwm
                                        else 'Ja' if candidate.get('needs_review') else 'Nei'),
                 '', 'KDRS Query – importert, uavhengig periodeevidens:']
        for run in current_kdrs.get('runs') or []:
            for part in run.get('scopes') or []:
                span = part.get('period_observed_years')
                text = f'{span[0]}–{span[1]}' if span else 'Ingen sikre årsdata'
                lines.append(f'  {run.get("report_type")} / {part.get("label")}: {text} (import {run.get("import_id")})')
        for diag in current_kdrs.get('diagnostics') or []:
            lines.append('KDRS: ' + str(diag))
        if not data:
            lines.append('DWM: ' + diagnostic)
        if not has_dwm:
            lines.append('KDRS-observasjoner gir ikke automatisk godkjent periode eller DWM-forslag.')
        details.configure(state='normal')
        details.delete('1.0', 'end')
        details.insert('1.0', '\n'.join(lines))
        details.configure(state='disabled')
        chosen = (saved or {}).get('selected_years') or candidate.get('proposed_years') or []
        for widget, value in ((first, chosen[0] if len(chosen) == 2 else ''),
                              (last, chosen[1] if len(chosen) == 2 else '')):
            widget.delete(0, 'end')
            widget.insert(0, str(value))
        status.set((saved or {}).get('status', 'ikke_vurdert'))
        comment.delete('1.0', 'end')
        comment.insert('1.0', (saved or {}).get('comment', ''))

    dropdown.configure(command=load_choice)
    def save():
        job = jobs[idx.get()]
        data, _, diagnostic = _latest_report(job)
        if not data:
            messagebox.showerror('Periodevurdering', diagnostic, parent=window)
            return
        entered = [first.get().strip(), last.get().strip()]
        years = entered if any(entered) else None
        try:
            path = save_assessment(job, data, status=status.get(), years=years,
                                   comment=comment.get('1.0', 'end').strip())
        except (ValueError, OSError) as exc:
            messagebox.showerror('Periodevurdering', str(exc), parent=window)
            return
        messagebox.showinfo('Periodevurdering', f'Lagret:\n{path}', parent=window)
    ctk.CTkButton(buttons, text='Lagre vurdering', command=save).pack(side='left')
    ctk.CTkButton(buttons, text='Lukk', command=window.destroy).pack(side='right')
    load_choice(choices[0])
    window.wait_window()
