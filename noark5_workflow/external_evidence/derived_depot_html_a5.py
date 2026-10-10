"""Render a clearly identified derived depot report, never the native HTML path."""
from __future__ import annotations

import json
from html import escape
from pathlib import Path


def write_derived_depot_html(derived_json: str | Path) -> Path:
    """Render accepted values via the native renderer with explicit provenance notice."""
    derived_json = Path(derived_json)
    report = json.loads(derived_json.read_text(encoding='utf-8-sig'))
    application = report.get('external_evidence_application')
    if not isinstance(application, dict) or not application.get('derived_report'):
        raise ValueError('Filen er ikke en avledet depotrapport')
    entries = application.get('applied')
    if not isinstance(entries, list):
        raise ValueError('Avledet rapport mangler oversikt over kildevalg')

    from noark5_workflow.analysis.depot_report_builder import write_depot_report_html

    destination = derived_json.with_name('depot-derived-evidence-report.html')
    temporary = destination.with_name(destination.name + '.tmp')
    try:
        write_depot_report_html(report, temporary)
        html = temporary.read_text(encoding='utf-8')
        rows = []
        for entry in entries:
            evidence = entry.get('evidence') or {}
            old = entry.get('dwm_value')
            new = entry.get('effective_value')
            def display(x):
                return f'{x:,}'.replace(',', ' ') if type(x) is int else 'Ukjent' if x is None else str(x)
            rows.append('<tr>' + ''.join('<td>' + escape(str(x)) + '</td>' for x in (
                entry.get('scope') or '', entry.get('metric') or '',
                display(old), display(new), evidence.get('source_file') or '',
                evidence.get('test_id') or '', evidence.get('line') or '',
            )) + '</tr>')
        table = ('<table style="width:100%;border-collapse:collapse" border="1" cellpadding="6">'
                 '<thead><tr><th>Omfang</th><th>Felt</th><th>DWM</th><th>Valgt</th><th>Kildefil</th>'
                 '<th>Test</th><th>Linje</th></tr></thead><tbody>' + ''.join(rows) + '</tbody></table>') if rows else '<p>Ingen eksterne verdier er valgt.</p>'
        # Compact human-facing index appears at the top, with the same approved
        # source data as the complete provenance table below.
        metric_labels = {'folder_count': 'Mapper', 'case_folder_count': 'Saksmapper',
                         'registration_count': 'Registreringer', 'journalpost_count': 'Journalposter',
                         'document_description_count': 'Dokumentbeskrivelser',
                         'document_object_count': 'Dokumentobjekter'}
        summary_items = []
        for entry in entries:
            scope = str(entry.get('scope') or '')
            part = ('Arkivdel ' + scope.split(':', 1)[1]) if scope.startswith('part:') else 'Hele uttrekket'
            ev = entry.get('evidence') or {}
            label = metric_labels.get(entry.get('metric'), entry.get('metric') or '')
            summary_items.append('<li><strong>' + escape(part + ' – ' + str(label)) + ': '
                                 + escape(display(entry.get('effective_value'))) + '</strong> '
                                 + '<span>(Godkjent ekstern verdi: KDRS Query '
                                 + escape(str(ev.get('source_file') or '')) + ')</span></li>')
        summary = '<ul>' + ''.join(summary_items) + '</ul>' if summary_items else '<p>Ingen godkjente eksterne verdier.</p>'
        banner = ('<section id="dwm-derived-evidence-notice" style="background:#fff3d6;color:#352c15;'
                  'border:2px solid #b37a16;padding:18px;margin:16px auto;max-width:1440px">'
                  '<h2>Avledet depotrapport – eksternt evidensgrunnlag</h2>'
                  '<p>Dette er ikke den opprinnelige DWM-depotrapporten. Tall fra KDRS Query er brukt '
                  'bare der et eksplisitt, godkjent kildevalg foreligger. Originalrapport og '
                  'originale analyser er bevart.</p>'
                  '<p>SHA-256 for originalrapport: <code>' + escape(str(application.get('native_report_sha256') or 'Ukjent')) + '</code></p>'
                  '<h3>Godkjente verdier og kilde</h3>' + summary + '<h3>Full kildesporbarhet</h3>' + table + '</section>')
        if '<body' not in html.lower():
            raise ValueError('Uventet HTML-struktur fra depotrapportgenerator')
        import re
        html, count = re.subn(r'(<body[^>]*>)', lambda m: m.group(1) + banner, html, count=1, flags=re.I)
        if count != 1:
            raise ValueError('Kunne ikke markere avledet depotrapport')
        temporary.write_text(html, encoding='utf-8')
        temporary.replace(destination)
    finally:
        if temporary.exists():
            temporary.unlink()
    return destination
