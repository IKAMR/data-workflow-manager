"""Combined read-only inventory of KDRS Query, Arkade 5 and PRONOM imports."""
from __future__ import annotations

import customtkinter as ctk
from noark5_workflow.external_evidence.batch_status_a18 import inspect_jobs

_FONT = ('Segoe UI', 11)


def _count_text(row, key):
    group = row[key]
    count = group['count']
    if not count:
        return 'Ingen import'
    if key == 'kdrs':
        types = '/'.join(group['types'])
        return f'{count}  ({types or "ukjent type"})'
    if key == 'pronom':
        return f'{count} statistikksett'
    return f'{count} importer'


def _detail_text(row):
    lines = [row['job_id'] + ' - ' + row['label'], 'Work: ' + (row['work'] or 'Ikke angitt'), '']
    for key, name in [('kdrs', 'KDRS Query'), ('arkade', 'Arkade 5'), ('pronom', 'PRONOM/Siegfried')]:
        lines.append(name + ': ' + _count_text(row, key))
        for imp in row[key]['imports']:
            lines.append('  Import-ID: ' + str(imp.get('import_id') or '?'))
            lines.append('  Importdato: ' + str(imp.get('date') or 'Ikke angitt'))
            if imp.get('types'):
                lines.append('  Rapporttyper: ' + ', '.join(imp['types']))
            if imp.get('version'):
                lines.append('  Versjon: ' + str(imp['version']))
            if imp.get('test_date'):
                lines.append('  Testdato: ' + str(imp['test_date']))
            if imp.get('files') is not None and key == 'pronom':
                lines.append('  Filer i statistikk: ' + str(imp['files']))
                lines.append('  Uidentifisert: ' + str(imp.get('unidentified')))
            elif imp.get('files'):
                lines.append('  Kildefiler: ' + ', '.join(str(x) for x in imp['files'] if x))
            if imp.get('source_sha256'):
                lines.append('  SHA-256: ' + str(imp['source_sha256']))
        lines.append('')
    lines.append('DWM-depotrapport: ' + ('Funnet' if row['depot_report'] else 'Ingen funnet'))
    lines.append('Kontroll av refererte filer: ' + ('MERKNADER' if row['issues'] else 'Ingen mangler påvist'))
    lines.extend('  - ' + str(issue) for issue in row['issues'])
    lines.extend(['', 'Importstatus dokumenterer tilgjengelig evidens, ikke faglig godkjenning.'])
    return '\n'.join(lines)


def open_evidence_status_dialog(parent, jobs, *, all_jobs=False):
    """Open one scrollable window for selected or all jobs; no source files change."""
    jobs = tuple(jobs)
    data = inspect_jobs(jobs)
    window = ctk.CTkToplevel(parent)
    window.title('Evidensstatus – ' + ('alle jobber' if all_jobs else 'valgte jobber'))
    screen_h = window.winfo_screenheight()
    screen_w = window.winfo_screenwidth()
    window.geometry(f'{min(1120, max(680, screen_w - 100))}x{min(770, max(440, screen_h - 130))}')
    window.minsize(680, 410)
    window.transient(parent)
    window.grid_columnconfigure(0, weight=1)
    window.grid_rowconfigure(2, weight=1)
    headline = f'{data["count"]} jobber  |  KDRS Query: {data["with_kdrs"]}  |  Arkade 5: {data["with_arkade"]}  |  PRONOM: {data["with_pronom"]}  |  Depotrapport: {data["with_report"]}'
    ctk.CTkLabel(window, text=headline, anchor='w', font=_FONT, wraplength=1030).grid(
        row=0, column=0, sticky='ew', padx=16, pady=(15, 5))
    ctk.CTkLabel(window, text=data['note'], anchor='w', font=_FONT, wraplength=1030, justify='left').grid(
        row=1, column=0, sticky='ew', padx=16, pady=(0, 9))
    scroll = ctk.CTkScrollableFrame(window)
    scroll.grid(row=2, column=0, sticky='nsew', padx=12, pady=(0, 10))
    for col, label, w in [(0, 'JOBB', 74), (1, 'Uttrekk', 235), (2, 'KDRS Query', 160),
                          (3, 'Arkade 5', 100), (4, 'PRONOM', 116), (5, 'Depot', 70),
                          (6, 'Merknader', 82), (7, '', 70)]:
        ctk.CTkLabel(scroll, text=label, width=w, anchor='w', font=_FONT).grid(
            row=0, column=col, padx=4, pady=(2, 8), sticky='w')
    scroll.grid_columnconfigure(1, weight=1)

    def show_details(row):
        popup = ctk.CTkToplevel(window)
        popup.title('Importdetaljer – ' + row['job_id'])
        popup.geometry(f'{min(820, max(580, screen_w - 180))}x{min(650, max(410, screen_h - 180))}')
        popup.transient(window)
        popup.grid_columnconfigure(0, weight=1)
        popup.grid_rowconfigure(0, weight=1)
        body = ctk.CTkTextbox(popup, font=_FONT, wrap='word')
        body.grid(row=0, column=0, sticky='nsew', padx=12, pady=12)
        body.insert('1.0', _detail_text(row))
        body.configure(state='disabled')
        ctk.CTkButton(popup, text='Lukk', command=popup.destroy, width=85).grid(
            row=1, column=0, sticky='e', padx=12, pady=(0, 12))
        popup.lift()

    for i, row in enumerate(data['jobs'], 1):
        values = [row['job_id'], row['label'], _count_text(row, 'kdrs'),
                  _count_text(row, 'arkade'), _count_text(row, 'pronom'),
                  'Funnet' if row['depot_report'] else 'Mangler',
                  str(len(row['issues'])) if row['issues'] else '–']
        widths = (74, 235, 160, 100, 116, 70, 82)
        for col, (value, width) in enumerate(zip(values, widths)):
            ctk.CTkLabel(scroll, text=str(value), width=width,
                         anchor='w', font=_FONT,
                         wraplength=width if col == 1 else 0).grid(
                row=i, column=col, sticky='ew' if col == 1 else 'w', padx=4, pady=3)
        ctk.CTkButton(scroll, text='Detaljer', width=72,
                      command=lambda current=row: show_details(current)).grid(
            row=i, column=7, padx=4, pady=3)
    footer = ctk.CTkFrame(window, fg_color='transparent')
    footer.grid(row=3, column=0, sticky='ew', padx=16, pady=(0, 12))

    def reload_data():
        window.destroy()
        open_evidence_status_dialog(parent, jobs, all_jobs=all_jobs)

    ctk.CTkButton(footer, text='Oppdater', width=90, command=reload_data).pack(side='left')
    ctk.CTkButton(footer, text='Lukk', width=90, command=window.destroy).pack(side='right')
    window.lift()
    return window
