"""Manual period reviews for whole extractions and individual native archive parts.

Never runs XPath or silently equates imported KDRS U2 indices to DWM system-IDs.
"""
from __future__ import annotations

import tkinter as tk
from tkinter import messagebox
import customtkinter as ctk

from noark5_workflow.reporting.job_summary_a16 import _latest_report, _extraction_label
from noark5_workflow.reporting.period_assessment_a16 import (
    load_assessment, load_part_assessment, part_review_candidate,
    review_candidate, save_assessment, save_part_assessment,
)
from noark5_workflow.reporting.yearly_volume_a16 import (
    archive_part_volumes, combined_volumes, sparse_boundary_years, registration_years,
)
from noark5_workflow.reporting.period_kdrs_evidence_a18 import (
    load_job_kdrs_period_evidence, format_kdrs_scope, summarize_kdrs_period_sources,
)
from noark5_workflow.reporting.period_year_profile_a18 import (
    format_year_profile, has_period_year_series, preferred_source_label,
)


def open_period_assessment_dialog(parent, jobs):
    jobs = tuple(jobs)
    if not jobs:
        return
    window = ctk.CTkToplevel(parent)
    window.title('Periodevurdering – uttrekk og arkivdeler')
    window.geometry(f'{min(1100, max(790, window.winfo_screenwidth() - 100))}x'
                    f'{min(840, max(560, window.winfo_screenheight() - 110))}')
    window.minsize(720, 510)
    window.transient(parent)
    window.grab_set()

    choices = [f'{j.job_id} – {_extraction_label(j, _latest_report(j)[0])}' for j in jobs]
    idx = ctk.IntVar(value=0)
    actions = ctk.CTkFrame(window, fg_color='transparent')
    actions.pack(side='bottom', fill='x', padx=18, pady=10)
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

    ctk.CTkLabel(body, text='Uttrekk').pack(anchor='w', padx=18, pady=(8, 2))
    dropdown = ctk.CTkOptionMenu(body, values=choices, width=635)
    dropdown.pack(anchor='w', padx=18)
    ctk.CTkLabel(body, text='Vurderingsnivå – velg hele uttrekket eller én arkivdel').pack(
        anchor='w', padx=18, pady=(10, 2))
    review_scope = ctk.CTkOptionMenu(body, values=['Hele uttrekket'], width=635)
    review_scope.pack(anchor='w', padx=18)
    ctk.CTkLabel(body, text='Vurderingen lagres separat for hvert nivå. KDRS U2-kilder er ikke automatisk koblet til DWM arkivdel-ID.',
                 anchor='w', wraplength=850).pack(anchor='w', padx=18, pady=(3, 3))
    details = ctk.CTkTextbox(body, height=160, wrap='word')
    details.pack(fill='x', padx=18, pady=7)
    input_row = ctk.CTkFrame(body, fg_color='transparent')
    input_row.pack(fill='x', padx=18)
    ctk.CTkLabel(input_row, text='Vurdert fra år').pack(side='left')
    first = ctk.CTkEntry(input_row, width=85)
    first.pack(side='left', padx=10)
    ctk.CTkLabel(input_row, text='til år').pack(side='left')
    last = ctk.CTkEntry(input_row, width=85)
    last.pack(side='left', padx=10)
    status = ctk.StringVar(value='ikke_vurdert')
    ctk.CTkLabel(body, text='Vurderingsstatus').pack(anchor='w', padx=18, pady=(10, 3))
    ctk.CTkSegmentedButton(body, values=['ikke_vurdert', 'godkjent', 'undersokes'],
                           variable=status).pack(fill='x', padx=18)
    ctk.CTkLabel(body, text='Faglig begrunnelse / kilder').pack(anchor='w', padx=18, pady=(10, 3))
    comment = ctk.CTkTextbox(body, height=80)
    comment.pack(fill='x', padx=18)

    header = ctk.CTkFrame(lower, fg_color='transparent')
    header.pack(fill='x', padx=10, pady=(5, 0))
    ctk.CTkLabel(header, text='Årlig produksjonsvolum – DWM og KDRS Query (separate kilder)',
                 anchor='w').pack(side='left', padx=(8, 8))
    open_large_button = ctk.CTkButton(header, text='Åpne i eget vindu', width=165)
    open_large_button.pack(side='right', padx=(8, 8))
    source_scope = ctk.CTkOptionMenu(lower, values=['Samlet uttrekk'], width=635)
    source_scope.pack(fill='x', padx=18, pady=(3, 0))
    volume = ctk.CTkTextbox(lower, height=280, wrap='none', font=('Consolas', 12))
    volume.pack(fill='both', expand=True, padx=18, pady=(5, 10))

    current = {'report': {}, 'kdrs': {}, 'parts': [], 'native_parts': [],
               'source_scopes': {}, 'review_ids': {}, 'part_source_labels': {}}
    # A detached view is a read-only snapshot. Different source runs and jobs
    # can be compared side by side without changing the assessment fields.
    large_views = {}

    def open_large_view():
        job_id = str(jobs[idx.get()].job_id)
        source_label = source_scope.get()
        key = (job_id, source_label)
        existing = large_views.get(key)
        if existing is not None and existing.winfo_exists():
            existing.deiconify()
            existing.lift()
            existing.focus_force()
            return

        # Copy exactly the displayed annual series, including provenance,
        # zero/missing/conflict markers and the full year-by-year table.
        snapshot = volume.get('1.0', 'end-1c')
        detached = ctk.CTkToplevel(window)
        large_views[key] = detached
        detached.title(f'Årsfordeling – {job_id} – {source_label}')
        detached.geometry(f'{max(780, detached.winfo_screenwidth() - 100)}x'
                          f'{max(500, detached.winfo_screenheight() - 125)}+30+30')
        detached.minsize(720, 450)

        # On Windows the detached evidence is maximized for an overview.
        # Other window managers retain the large resizable fallback geometry.
        try:
            detached.state('zoomed')
        except tk.TclError:
            pass

        footer = ctk.CTkFrame(detached, fg_color='transparent')
        footer.pack(side='bottom', fill='x', padx=16, pady=(0, 12))
        ctk.CTkLabel(detached, text=f'{job_id} – {source_label}',
                     anchor='w', justify='left', wraplength=1200).pack(
                         fill='x', padx=18, pady=(14, 4))
        expanded = ctk.CTkTextbox(detached, wrap='none', font=('Consolas', 13))
        expanded.pack(fill='both', expand=True, padx=16, pady=(4, 10))
        expanded.insert('1.0', snapshot)
        expanded.configure(state='disabled')

        def copy_all():
            detached.clipboard_clear()
            detached.clipboard_append(snapshot)

        def close_view():
            if large_views.get(key) is detached:
                large_views.pop(key, None)
            detached.destroy()

        ctk.CTkButton(footer, text='Kopier all tekst', command=copy_all).pack(side='left')
        ctk.CTkButton(footer, text='Lukk', command=close_view).pack(side='right')
        detached.protocol('WM_DELETE_WINDOW', close_view)
        detached.lift()
        detached.focus_force()

    open_large_button.configure(command=open_large_view)

    def _readable(years):
        return f'{years[0]}–{years[1]}' if years else 'Ikke tilgjengelig'

    def show_source(choice):
        report, parts = current['report'], current['parts']
        lines = []
        if choice == 'Samlet uttrekk' or choice.startswith('DWM arkivdel '):
            if choice == 'Samlet uttrekk':
                totals = combined_volumes(parts)
                registrations = registration_years(report)
            else:
                index = source_scope.cget('values').index(choice) - 1
                totals = parts[index][2]
                sid = parts[index][0]
                registrations = registration_years(report, archive_part_id=sid)
            lines = ['DWM – lagret XPath-årsvolum',
                     'År     Saker      Reg.       JP     Dok.beskr.    Dok.obj.',
                     '------------------------------------------------------------']
            years = set(totals) | set(registrations or {})
            for year in sorted(years):
                row = totals.get(year)
                reg = str(registrations.get(year, '–')) if registrations is not None else '–'
                fields = [str(row[k]) if row is not None else '–'
                          for k in ('folder', 'journal', 'document_description', 'document_object')]
                lines.append(f'{year:<6} {fields[0]:>7} {reg:>9} {fields[1]:>8} {fields[2]:>12} {fields[3]:>11}')
            if not years:
                lines.append('Ikke tilgjengelig – dette betyr ikke null aktivitet.')
            if registrations is None:
                lines.append('Registreringer per år: Ikke tilgjengelig (ikke 0).')
            sparse = sparse_boundary_years(totals)
            if sparse:
                lines.extend(['', 'Ytterår med få observasjoner: ' + ', '.join(str(y) for y, _ in sparse)])
            if choice == 'Samlet uttrekk' and (current['kdrs'].get('runs') or []):
                lines += ['', 'KDRS Query – separate kilder, ikke summert:']
                lines.extend(summarize_kdrs_period_sources(current['kdrs']['runs']))
        elif choice in current['source_scopes']:
            run, part = current['source_scopes'][choice]
            if has_period_year_series(part):
                lines.extend(format_year_profile(run, part))
            else:
                lines.extend(format_kdrs_scope(run, part))
                lines.append('Ingen entydige produksjonsårsserier i valgt KDRS-kilde. '
                             'Dette er ikke dokumentasjon på at arkivdelen mangler innhold.')
        lines += ['', 'Volum alene avgjør aldri arkivperioden.']
        volume.configure(state='normal')
        volume.delete('1.0', 'end')
        volume.insert('1.0', '\n'.join(lines))
        volume.configure(state='disabled')

    source_scope.configure(command=show_source)

    def load_review(choice):
        job = jobs[idx.get()]
        data, kdrs = current['report'], current['kdrs']
        system_id = current['review_ids'].get(choice)
        saved = (load_assessment(job) if system_id is None
                 else load_part_assessment(job, system_id)) or {}
        if system_id is None:
            candidate = review_candidate(data)
            lines = ['Nivå: HELE UTTREKKET',
                     'Oppgitt uttrekksperiode: ' + _readable(candidate.get('declared_years')),
                     'DWM XPath: ' + _readable(candidate.get('observed_years')),
                     'DWM dokumentgrunnlag: ' + _readable(candidate.get('document_years')),
                     'DWM-forslag: ' + _readable(candidate.get('proposed_years'))]
            whole_sources = [(run, s) for run in kdrs.get('runs') or []
                             for s in run.get('scopes') or [] if s.get('scope_id') == 'whole']
            if whole_sources:
                lines += ['KDRS Query tilgjengelig – faglig vurdering kan utføres uten DWM XPath:',
                          'ÅRSFORDELING OG ANTALL: Se det nedre feltet som nå automatisk viser KDRS Standard/U1.',
                          'Vurder mulige avvik i observerte ytterår; verken behold eller forkast blindt.']
                for run, row in whole_sources:
                    lines.append('  ' + str(run.get('report_type')) + ' / ' +
                                 str(run.get('import_id')) + ': ' + _readable(row.get('period_observed_years')))
            elif not candidate.get('observed_years'):
                lines.append('Ingen observerte ytterår i tilgjengelige DWM-/KDRS-kilder.')
        else:
            candidate = part_review_candidate(data, system_id)
            lines = ['Nivå: ARKIVDEL', 'System-ID: ' + system_id,
                     'Arkivdel: ' + str(candidate['archive_part'].get('title') or ''),
                     'DWM XPath ytterår: ' + _readable(candidate.get('dwm_observed_years')),
                     'KDRS U2 er kildeinformasjon og må kobles til riktig arkivdel før den legges til grunn.',
                     'Se årsseriene i kildemenyen nedenfor.']
        if saved.get('status') == 'godkjent':
            lines.append('Lagret faglig godkjent periode: ' + _readable(saved.get('selected_years')))
        lines.append('Ingen automatisk faglig godkjenning. Oppgi vurderte ytterår og begrunnelse.')
        details.configure(state='normal')
        details.delete('1.0', 'end')
        details.insert('1.0', '\n'.join(lines))
        details.configure(state='disabled')
        proposed = candidate.get('proposed_years') if system_id is None else candidate.get('dwm_observed_years')
        chosen = saved.get('selected_years') or proposed or []
        for widget, value in ((first, chosen[0] if len(chosen) == 2 else ''),
                              (last, chosen[1] if len(chosen) == 2 else '')):
            widget.delete(0, 'end')
            widget.insert(0, str(value))
        status.set(saved.get('status', 'ikke_vurdert'))
        comment.delete('1.0', 'end')
        comment.insert('1.0', saved.get('comment') or '')
        # A missing DWM annual series must not hide imported KDRS observations.
        # This changes only what is shown, never the proposed/saved period.
        native_years = combined_volumes(current['parts'])
        has_native = any(any(n > 0 for n in counts.values()) for counts in native_years.values())
        default_source = preferred_source_label(
            source_scope.cget('values'), current['source_scopes'],
            has_dwm_years=has_native, review_system_id=system_id,
            part_source_labels=current['part_source_labels'])
        source_scope.set(default_source)
        show_source(default_source)

    review_scope.configure(command=load_review)

    def load_job(choice):
        index = choices.index(choice)
        idx.set(index)
        job = jobs[index]
        data, _, diagnostic = _latest_report(job)
        current['report'] = data or {}
        current['kdrs'] = load_job_kdrs_period_evidence(job)
        current['parts'] = archive_part_volumes(data)
        current['native_parts'] = (data or {}).get('archive_parts') or []
        current['source_scopes'].clear()
        source_labels = ['Samlet uttrekk']
        current['part_source_labels'].clear()
        for i, (sid, title, _) in enumerate(current['parts']):
            label = f'DWM arkivdel {i+1}. {title} ({sid[:8]})'
            source_labels.append(label)
            if sid:
                current['part_source_labels'][sid] = label
        for run in current['kdrs'].get('runs') or []:
            for part in run.get('scopes') or []:
                label = ('KDRS ' + str(run.get('report_type')) + ' / ' +
                         str(run.get('import_id')) + ' / ' + str(part.get('label')))
                if label in current['source_scopes']:
                    label += ' [' + str(len(current['source_scopes']) + 1) + ']'
                current['source_scopes'][label] = run, part
                source_labels.append(label)
        source_scope.configure(values=source_labels)
        # Selection is done by load_review using the active assessment scope.
        # KDRS Standard is preferred when DWM has no native annual observations.
        current['review_ids'].clear()
        current['review_ids']['Hele uttrekket'] = None
        review_labels = ['Hele uttrekket']
        for number, row in enumerate(current['native_parts'], 1):
            meta = row.get('archive_part') or {}
            sid = str(meta.get('system_id') or '')
            if not sid:
                continue  # Do not save an ambiguous part under a guessed ID.
            label = f'Arkivdel {number}. {meta.get("title") or sid} ({sid})'
            if label in current['review_ids']:
                continue
            current['review_ids'][label] = sid
            review_labels.append(label)
        review_scope.configure(values=review_labels)
        review_scope.set('Hele uttrekket')
        load_review('Hele uttrekket')
        if not data and not current['kdrs'].get('runs'):
            details.configure(state='normal')
            details.insert('end', '\n' + diagnostic)
            details.configure(state='disabled')

    dropdown.configure(command=load_job)

    def save():
        job = jobs[idx.get()]
        system_id = current['review_ids'].get(review_scope.get())
        report = current['report']
        if not report and system_id is not None:
            messagebox.showerror('Periodevurdering', 'Arkivdel kan ikke identifiseres uten depotrapport.', parent=window)
            return
        entered = [first.get().strip(), last.get().strip()]
        years = entered if any(entered) else None
        try:
            if system_id is None:
                path = save_assessment(job, report, status=status.get(), years=years,
                                       comment=comment.get('1.0', 'end').strip())
            else:
                path = save_part_assessment(job, report, system_id, status=status.get(),
                                            years=years, comment=comment.get('1.0', 'end').strip())
        except (ValueError, OSError) as exc:
            messagebox.showerror('Periodevurdering', str(exc), parent=window)
            return
        messagebox.showinfo('Periodevurdering',
                            f'Lagret for {review_scope.get()}:\n{path}', parent=window)
        load_review(review_scope.get())

    ctk.CTkButton(actions, text='Lagre vurdering', command=save).pack(side='left')
    ctk.CTkButton(actions, text='Lukk', command=window.destroy).pack(side='right')
    load_job(choices[0])
    window.wait_window()
