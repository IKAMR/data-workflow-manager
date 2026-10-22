"""Present saved DWM XPath type/status distributions in a20 HTML/PDF/CSV.

All views receive the same a20 snapshot. No XPath code or KDRS mapping here.
"""
from __future__ import annotations

import csv
from html import escape
from io import StringIO

from .report_content_a201 import DISTRIBUTIONS, SCALARS


def _h(value):
    return escape('–' if value is None else str(value), quote=True)


def _table(columns, rows, css=''):
    cls = ' class="' + _h(css) + '"' if css else ''
    head = '<tr>' + ''.join('<th>' + _h(v) + '</th>' for v in columns) + '</tr>'
    body = ''.join('<tr>' + ''.join('<td>' + _h(v) + '</td>' for v in row) + '</tr>' for row in rows)
    return '<table' + cls + '><thead>' + head + '</thead><tbody>' + body + '</tbody></table>'


def _code(key):
    return '(tom verdi)' if key == '' else key


def _compact_distribution(fact, limit=0):
    if not fact:
        return 'Ikke tilgjengelig'
    rows = list((fact.get('value') or {}).items())
    if not rows:
        return 'Tilgjengelig, ingen observerte verdier'
    shown = rows if not limit else rows[:limit]
    result = ', '.join(_code(key) + ': ' + str(value) for key,value in shown)
    if limit and len(rows) > limit:
        result += f' (+{len(rows)-limit} flere i Full/vedlegg A)'
    return result


def _summary(snapshot):
    out=[]
    for job in snapshot['jobs']:
        profile=job.get('content_profile') or {}
        data=profile.get('distributions') or {}
        jp = data.get('journalpost_type')
        out.append((job['job_id'],job['extraction'],
                    _compact_distribution(jp),
                    _compact_distribution(data.get('folder_type'),5),
                    _compact_distribution(data.get('registration_type'),5),
                    _compact_distribution(data.get('variant_format'),5),
                    'DWM XPath' if profile.get('status')=='available' else
                    (profile.get('diagnostic') or 'Ikke tilgjengelig')))
    return ('<h2>Innholdsprofil – saker, journalposter og dokumenter</h2>'
            '<p>Fordelingene er hentet fra tidligere lagrede normale DWM XPath-tester. '
            'Hver type/kode vises slik den er observert, inkludert inngående, utgående '
            'og notattyper der disse forekommer. KDRS Query og Arkade 5 vises '
            'som separate kilder, ikke lagt sammen med DWM. Ukjent er ikke 0.</p>'
            + _table(('Jobb','Uttrekk','Journalposter etter type','Saker etter type',
                      'Registreringstype','Variantformat','Kilde/status'),out,'a201-content-overview'))


def _other_volume(snapshot):
    """Compact auxiliary quantities, not substitutes for primary counts."""
    selected=(('main_document_links','Hoveddok. (tilknytninger)'),
              ('notes','Merknader'),('correspondence_parties','Korrespondanseparter'),
              ('writeoffs','Avskrivningsmåter'),('screenings','Skjerminger'))
    rows=[]
    for job in snapshot['jobs']:
        values=(job.get('content_profile') or {}).get('scalars') or {}
        rows.append((job['job_id'], job['extraction'],
                     *(values[key]['value'] if key in values else 'Ukjent'
                       for key,_label in selected)))
    return ('<h3>Supplerende omfangsmål – DWM XPath</h3>'
            '<p>Hoveddokument er antall dokumentbeskrivelser tilknyttet som hoveddokument, '
            'ikke automatisk antall journalposter med hoveddokument. '
            'Ukjente måltall vises ikke som 0.</p>'
            + _table(('Jobb','Uttrekk',*(label for _key,label in selected)),rows))

def _coverage(snapshot):
    total=len(snapshot['jobs'])
    rows=[]
    for key,info in DISTRIBUTIONS.items():
        n=sum(key in (j.get('content_profile') or {}).get('distributions',{}) for j in snapshot['jobs'])
        rows.append((info[2],f'{n}/{total}',info[0]))
    return ('<h3>Datadekning for type- og statusfordelinger</h3>'+
            _table(('Område','Uttrekk med DWM-tall','XPath-test'),rows))


def _aggregate_journal(snapshot):
    totals={}
    available=0
    for job in snapshot['jobs']:
        fact=((job.get('content_profile') or {}).get('distributions') or {}).get('journalpost_type')
        if not fact:
            continue
        available+=1
        for key, count in fact.get('value',{}).items():
            totals[key]=totals.get(key,0)+count
    if not totals:
        return '<p>Samlet journalpostfordeling: Ingen tilgjengelige DWM-typefordelinger.</p>'
    rows=[(_code(key),count) for key,count in sorted(totals.items(),key=lambda x:(-x[1],x[0]))]
    return ('<h3>Samlet fordeling – journalposttyper</h3>'+
            f'<p>Sum av kjente DWM XPath-kilder for {available}/{len(snapshot["jobs"])} uttrekk. '
            'Ikke sammenlign denne delsummen med et fullstendig JP-hovedtall når noe mangler. '
            'Flere versjoner/kilder for samme jobb summeres ikke.</p>'+
            _table(('Type/verdi i kilden','Antall (kjent delsum)'),rows))


def _facts(scope, *, full=True, include_source=True):
    out=[]
    for key,spec in DISTRIBUTIONS.items():
        fact=(scope.get('distributions') or {}).get(key)
        if not fact or (not full and not spec[3]):
            continue
        values=fact.get('value') or {}
        if not values:
            out.append((fact['label'],'(ingen observerte verdier)',0,
                        fact['test_id'] if include_source else ''))
        else:
            out.extend((fact['label'],_code(code),value,
                        fact['test_id'] if include_source else '') for code,value in values.items())
    for key,spec in SCALARS.items():
        fact=(scope.get('scalars') or {}).get(key)
        if fact and (full or spec[3]):
            out.append((fact['label'],'Antall',fact['value'],
                        fact['test_id'] if include_source else ''))
    return out


def _extraction_details(snapshot, *, full=True):
    out=['<h2>Type-/statusfordelinger per uttrekk</h2>']
    for job in snapshot['jobs']:
        profile=job.get('content_profile') or {}
        out.append('<h3>'+_h(job['job_id'])+' – '+_h(job['extraction'])+'</h3>')
        rows=_facts(profile,full=full)
        if rows:
            out.append('<p>Datagrunnlag: normal DWM XPath-kjøring. '
                       'Kildens test-ID fremgår per kategori; ingen nye analyser utført.</p>')
            out.append(_table(('Kategori','Verdi/kode','Antall','Kildetest'),rows))
        else:
            out.append('<p>'+_h(profile.get('diagnostic') or 'Ingen lagret typefordeling tilgjengelig.')+'</p>')
    return ''.join(out)


def _part_details(snapshot, *, full=True):
    out=['<h2>Innholdsprofil per arkivdel – DWM XPath</h2>',
         '<p>Arkivdeler kobles utelukkende via native system-ID. '
         'Fordelinger kan mangle selv om antall arkivdeler og hovedtall er kjent. '
         'KDRS Query U2-observasjoner beholdes separat i den eksisterende delen av vedlegg B.</p>']
    available=0
    for job in snapshot['jobs']:
        profile=job.get('content_profile') or {}
        source=(profile.get('archive_parts') or {})
        for part in job.get('archive_parts') or []:
            sid=part.get('system_id')
            if not sid:
                continue
            facts=_facts(source.get(sid) or {},full=full)
            if not facts:
                continue
            available+=1
            out.append('<h3>'+_h(job['job_id'])+' – '+_h(part.get('title'))+' ('+_h(sid)+')</h3>')
            out.append(_table(('Kategori','Verdi/kode','Antall','Kildetest'),facts))
    if not available:
        out.append('<p>Ingen arkivdelvise type-/statusfordelinger funnet i lagrede DWM XPath-resultater.</p>')
    return ''.join(out)


def augment_content_html(html: str, filename: str, snapshot: dict, *,
                         level='Medium', enabled=(), extraction_appendix=False):
    """Extend current report pages; never delete or substitute source facts."""
    if level == 'Enkel' or 'totals' not in enabled:
        return html
    if not any(j.get('content_profile') for j in snapshot.get('jobs') or []):
        return html
    if filename == 'index.html':
        content=_summary(snapshot)+_aggregate_journal(snapshot)+_other_volume(snapshot)
        if level=='Full':
            content+=_coverage(snapshot)
            if not extraction_appendix:
                content+=_extraction_details(snapshot,full=True)
        # Keep the main report readable: place the content profile between
        # volume/evidence material and the existing technical assessment.
        anchor='<h2>Teknisk kontroll</h2>'
        return html.replace(anchor,content+anchor,1) if anchor in html else html.replace('</body>',content+'</body>',1)
    if filename == 'vedlegg-a-uttrekk.html':
        return html.replace('</body>',_extraction_details(snapshot,full=True)+'</body>',1)
    if filename == 'vedlegg-b-arkivdeler.html':
        return html.replace('</body>',_part_details(snapshot,full=(level=='Full'))+'</body>',1)
    return html


def _cell(v):
    if v is None:
        return ''
    value=str(v)
    if value.lstrip().startswith(('=','+','-','@')):
        return "'"+value
    return value


def content_csv(snapshot, *, level='Full') -> bytes:
    """Long-form Excel-friendly CSV with provenance and independently scoped rows."""
    target=StringIO(newline='')
    writer=csv.writer(target,delimiter=';',lineterminator='\r\n')
    writer.writerow(('JOB','Uttrekk','Nivå','System-ID','Kategori-ID','Kategori',
                     'Verdi/kode','Antall','XPath-test','Kildeløp','Status'))
    for job in snapshot['jobs']:
        profile=job.get('content_profile') or {}
        root=profile.get('source_run') or ''
        def add_rows(scope,scope_name,system_id):
            for key,spec in DISTRIBUTIONS.items():
                fact=(scope.get('distributions') or {}).get(key)
                if not fact:
                    continue
                for value,count in fact.get('value',{}).items():
                    writer.writerow(tuple(_cell(v) for v in
                        (job['job_id'],job['extraction'],scope_name,system_id,key,fact['label'],
                         _code(value),count,fact['test_id'],root,'Tilgjengelig')))
            for key,spec in SCALARS.items():
                fact=(scope.get('scalars') or {}).get(key)
                if fact:
                    writer.writerow(tuple(_cell(v) for v in
                        (job['job_id'],job['extraction'],scope_name,system_id,key,fact['label'],
                         'Antall',fact['value'],fact['test_id'],root,'Tilgjengelig')))
        add_rows(profile,'Uttrekk','')
        part_data=profile.get('archive_parts') or {}
        for part in job.get('archive_parts') or []:
            sid=part.get('system_id')
            if sid and sid in part_data:
                add_rows(part_data[sid],'Arkivdel',sid)
        if profile.get('status') != 'available':
            writer.writerow(tuple(_cell(v) for v in
                (job['job_id'],job['extraction'],'Uttrekk','','','',
                 '',None,'',root,profile.get('diagnostic') or 'Ikke tilgjengelig')))
    return target.getvalue().encode('utf-8-sig')
