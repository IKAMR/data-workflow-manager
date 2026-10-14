"""Manual period review for selected jobs, without re-running XPath analyses."""
from __future__ import annotations
from tkinter import messagebox
import customtkinter as ctk
from noark5_workflow.reporting.job_summary_a16 import _latest_report, _extraction_label
from noark5_workflow.reporting.period_assessment_a16 import load_assessment, review_candidate, save_assessment
from noark5_workflow.reporting.yearly_volume_a16 import METRICS, archive_part_volumes, combined_volumes, sparse_boundary_years


def open_period_assessment_dialog(parent, jobs):
    jobs = tuple(jobs)
    window = ctk.CTkToplevel(parent)
    window.title('Periodevurdering – valgte jobber')
    window.geometry(f'900x{min(780, max(540, window.winfo_screenheight() - 110))}')
    window.minsize(690, 470)
    window.transient(parent)
    window.grab_set()
    choices = [f'{j.job_id} – {_extraction_label(j, _latest_report(j)[0])}' for j in jobs]
    idx = ctk.IntVar(value=0)
    buttons = ctk.CTkFrame(window, fg_color='transparent')
    buttons.pack(side='bottom', fill='x', padx=18, pady=12)
    body = ctk.CTkScrollableFrame(window)
    body.pack(fill='both', expand=True, padx=8, pady=8)
    ctk.CTkLabel(body, text='Uttrekk').pack(anchor='w', padx=18, pady=(16, 3))
    dropdown = ctk.CTkOptionMenu(body, values=choices, width=635)
    dropdown.pack(anchor='w', padx=18)
    details = ctk.CTkTextbox(body, height=185, wrap='word')
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

    ctk.CTkLabel(body, text='Årlig produksjonsvolum (lagret XPath-grunnlag)').pack(anchor='w', padx=18, pady=(13, 3))
    scope = ctk.CTkOptionMenu(body, values=['Samlet uttrekk'], width=635)
    scope.pack(anchor='w', padx=18)
    volume = ctk.CTkTextbox(body, height=200, wrap='none', font=('Consolas', 12))
    volume.pack(fill='x', padx=18, pady=(5, 12))
    current_parts = []

    def show_scope(choice):
        parts = current_parts[:]
        if choice == 'Samlet uttrekk':
            totals = combined_volumes(parts)
        else:
            selected_index = scope.cget('values').index(choice) - 1
            totals = parts[selected_index][2]
        lines = ['År     Saker      JP     Dok.beskr.    Dok.obj.', '--------------------------------------------------']
        for year, row in sorted(totals.items()):
            lines.append(f'{year:<6} {row["folder"]:>7} {row["journal"]:>7} {row["document_description"]:>12} {row["document_object"]:>11}')
        sparse = sparse_boundary_years(totals)
        if sparse:
            lines += ['', 'Mulige slengere i ytterår – må vurderes: ' + ', '.join(str(y) for y, _ in sparse)]
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
        candidate = review_candidate(data) if data else {}
        current_parts.clear()
        current_parts.extend(archive_part_volumes(data))
        scopes = ['Samlet uttrekk'] + [f'{i+1}. {title} ({sysid[:8]})' for i,(sysid,title,_) in enumerate(current_parts)]
        scope.configure(values=scopes)
        scope.set('Samlet uttrekk')
        show_scope('Samlet uttrekk')
        lines = ['Oppgitt: ' + str(candidate.get('declared_years')),
                 'XPath samlet: ' + str(candidate.get('observed_years')),
                 'Dokumentbeskrivelser/-objekter: ' + str(candidate.get('document_years')),
                 'Forslag: ' + str(candidate.get('proposed_years')),
                 'Motstrid mellom kilder: ' + ('Ja' if candidate.get('conflicting_sources') else 'Nei'),
                 'Vurdering kreves: ' + ('Ja' if candidate.get('needs_review') else 'Nei')]
        if not data:
            lines.append(diagnostic)
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
