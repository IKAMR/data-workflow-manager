"""Shared presentation adapters for DWM selected-job report snapshots (a20).

All presentation formats receive the same read-only snapshot. This is an
adapter over existing report_package_a16/period_report_a18, not a second XPath
or evidence implementation.
"""
from __future__ import annotations

import csv
from html import escape
from io import StringIO
import re

from .report_model_a20 import METRICS


def _h(value):
    return escape('–' if value is None else str(value), quote=True)


def _table(headers, rows, css=''):
    heading = ''.join('<th>' + _h(v) + '</th>' for v in headers)
    body = ''.join('<tr>' + ''.join('<td>' + _h(v) + '</td>' for v in row) + '</tr>' for row in rows)
    return '<table' + (f' class="{css}"' if css else '') + '><thead><tr>' + heading + '</tr></thead><tbody>' + body + '</tbody></table>'


def _period(years):
    return f'{years[0]}–{years[1]}' if years else 'Ikke faglig godkjent'


def _sources(record):
    items = []
    for source in record['kdrs_sources']:
        name = str(source.get('report_type') or '').upper()
        if source.get('whole_years'):
            items.append(name + ' (årsfordeling)')
        elif source.get('part_scope_count'):
            items.append(name + ' (arkivdeler)')
        else:
            items.append(name + ' (uten årsgrunnlag)')
    return ', '.join(items) or 'Ikke dokumentert'


def render_period_index(snapshot):
    rows = []
    for record in snapshot['jobs']:
        rows.append((record['job_id'], record['extraction'],
                     'Funnet' if record['has_depot_report'] else 'Mangler',
                     _period(record['dwm_observed_years']) if record['dwm_observed_years'] else 'Mangler',
                     _sources(record),
                     _period(record['approved_years']),
                     record['professional_period_status']))
    html = ('<p>DWM XPath, KDRS Query og faglig fastsatt periode holdes atskilt. '
            'Etter en fullført analyse kan periodevurderingen fortsatt kreve faglig avklaring. '
            'Få enkeltforekomster i ytterkant fastsetter ikke automatisk produksjonsperioden.</p>')
    html += _table(('Jobb','Uttrekk','Depotrapport','DWM XPath-år','KDRS-grunnlag',
                    'Faglig godkjent periode','Faglig vurderingsstatus'), rows,
                   'a20-period-index')
    if snapshot['warnings']:
        html += '<p><strong>Kontrollmerknader:</strong> ' + _h('; '.join(snapshot['warnings'])) + '</p>'
    return html


def render_part_index(snapshot):
    rows = []
    for record in snapshot['jobs']:
        for part in record['archive_parts']:
            rows.append((record['job_id'],record['extraction'],part['number'],
                         part['title'],part['system_id'] or 'Mangler',
                         *('Ukjent' if part['counts'][m] is None else part['counts'][m]
                           for m, _label in METRICS if m != 'archive_part_count'),
                         _period(part['approved_years']) if part['approved_years'] else '–',
                         part['professional_status']))
    if not rows:
        return '<p>Ingen arkivdelrader i de tilgjengelige depotrapportene.</p>'
    return ('<p>Én rad per dokumentert arkivdel. Mengdetallene nedenfor er DWM-verdier; '
            'KDRS U2-observasjoner og verifiserte rapportvalg vises separat i detaljene '
            'lenger ned. Manglende tall er ukjent, ikke null.</p>' +
            _table(('Jobb','Uttrekk','#','Arkivdel','System-ID',
                    *(name for metric,name in METRICS if metric != 'archive_part_count'),
                    'Faglig periode','Vurderingsstatus'), rows, 'a20-part-index'))


def _patch_overview_status(html_text, snapshot):
    """Retire the misleading XPath-only status *in the job overview only*."""
    match = re.search(r'<table class="job-overview">.*?</table>', html_text, re.S)
    if not match:
        return html_text
    original = match.group()
    lines = list(re.finditer(r'<tr>.*?</tr>',original,re.S))
    if len(lines) != len(snapshot['jobs']) + 1:
        return html_text   # Do not blindly pair rows with a changed report layout.
    replacements = {}
    for idx, record in enumerate(snapshot['jobs'], 1):
        row = lines[idx].group()
        cells = list(re.finditer(r'<td>.*?</td>',row,re.S))
        if len(cells) < 4:
            return html_text
        cell = cells[3]
        replacements[idx] = (row[:cell.start()] + '<td>' + _h(record['professional_period_status']) + '</td>' + row[cell.end():])
    out = []
    last = 0
    for idx,line in enumerate(lines):
        out.append(original[last:line.start()])
        out.append(replacements.get(idx,line.group()))
        last = line.end()
    out.append(original[last:])
    edited = ''.join(out)
    return html_text[:match.start()] + edited + html_text[match.end():]


def enrich_html(text, filename, snapshot, *, include_period=True):
    """Extend the *existing* report package without changing raw observations.

    Main and part annex receive a compact professional navigation layer. DWM
    source details, U2 provenance and all original tables remain in place.
    """
    if filename == 'index.html':
        text = _patch_overview_status(text,snapshot)
        status_section = '<h2>Faglig periodevurdering – hele uttrekket</h2>' + render_period_index(snapshot)
        # Replace the obsolete XPath-only pending table, not the source facts.
        begin = text.find('<h2>Åpne periodevurderinger</h2>')
        end = text.find('<h2>Grupperte vurderingspunkter</h2>', begin+1) if begin >= 0 else -1
        if begin >= 0 and end > begin:
            text = text[:begin] + (status_section if include_period else '') + text[end:]
        elif include_period:
            text = text.replace('</body>',status_section+'</body>',1)
    elif filename == 'vedlegg-a-uttrekk.html':
        # Legacy text describes XPath-only assessment. Its wording must not
        # contradict the complete professional source status in a20.
        text = text.replace(' · Vurdering: Kan ikke vurderes',
                            ' · DWM XPath-avstemming: årsgrunnlag mangler')
        if include_period:
            text = text.replace('</h1>','</h1><h2>Faglig periodevurdering – uttrekk</h2>'+
                                render_period_index(snapshot),1)
    elif filename == 'vedlegg-b-arkivdeler.html':
        section = ('<h2>Arkivdeler – kompakt indeks</h2>' + render_part_index(snapshot))
        text = text.replace('</h1>','</h1>'+section,1)
    elif filename == 'vedlegg-d-periodevurdering.html':
        text = text.replace('</h1>','</h1><h2>Faglige vurderinger – alle uttrekk</h2>'+
                            render_period_index(snapshot),1)
    return text


def _csv_cell(value):
    if value is None:
        return ''
    if type(value) is int:
        return str(value)
    value = str(value)
    # A LABEL, archive title or comment may come from untrusted metadata.
    if value.lstrip().startswith(('=','+','-','@')):
        return "'" + value
    return value


def _csv_payload(headers, rows):
    out = StringIO(newline='')
    writer = csv.writer(out,delimiter=';',lineterminator='\r\n')
    writer.writerow(headers)
    for row in rows:
        writer.writerow([_csv_cell(v) for v in row])
    # UTF-8 BOM improves Norwegian Excel import with semicolon separators.
    return out.getvalue().encode('utf-8-sig')


def csv_for_page(filename, snapshot, legacy_payload):
    """Tabular exports from exactly the same snapshot as HTML/JSON/PDF."""
    if filename == 'vedlegg-b-arkivdeler.html':
        headers=('JOB','Uttrekk','Arkivdelnr','System-ID','Arkivdeltittel',
                 *(metric for metric,_ in METRICS if metric != 'archive_part_count'),
                 'Faglig status','Godkjent fra','Godkjent til','Vurderte fra','Vurderte til',
                 'Begrunnelse','Kildegrunnlag')
        rows=[]
        for record in snapshot['jobs']:
            for part in record['archive_parts']:
                a=part['approved_years'] or (None,None)
                b=part['selected_years'] or (None,None)
                rows.append((record['job_id'],record['extraction'],part['number'],part['system_id'],part['title'],
                             *(part['counts'][key] for key,_ in METRICS if key != 'archive_part_count'),
                             part['professional_status'],*a,*b,part['comment'],part['source_note']))
        return _csv_payload(headers,rows)
    headers = ('JOB','Uttrekk','Depotrapport','Periodevurdering','Godkjent fra','Godkjent til',
               'Oppgitt fra','Oppgitt til', *(key for key,_label in METRICS),
               'Antall arkivdelrader','KDRS-kilder','Rapportkilde','Merknad')
    rows=[]
    for record in snapshot['jobs']:
        approved=record['approved_years'] or (None,None)
        declared=record['dwm_declared_years'] or (None,None)
        rows.append((record['job_id'],record['extraction'],
                     'Funnet' if record['has_depot_report'] else 'Mangler',
                     record['professional_period_status'],*approved,*declared,
                     *(record['counts'][key] for key,_label in METRICS),
                     record['reported_archive_parts'],_sources(record),
                     record['source_file'],record['diagnostic']))
    return _csv_payload(headers,rows)
