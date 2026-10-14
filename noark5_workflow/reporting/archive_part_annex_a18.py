"""Compact, source-separated archive-part appendix for 1..N DWM jobs.

This consumes the same SHA-bound U2 projection / exact observation model used in
index and appendix C. It does not parse KDRS text or promote imported counts.
"""
from __future__ import annotations
from html import escape

METRICS = (
    ('folder_count','Mapper'),('registration_count','Registreringer'),
    ('journalpost_count','Journalposter'),
    ('document_description_count','Dokumentbeskrivelser'),
    ('document_object_count','Dokumentobjekter'),
)


def _h(value):
    return escape(str(value), quote=True)


def _v(value):
    return (f'{value:,}'.replace(',',' ') if type(value) is int and value >= 0
            else 'Ukjent')


def _table(headings, rows):
    return ('<table><thead><tr>' + ''.join('<th>'+_h(h)+'</th>' for h in headings) +
            '</tr></thead><tbody>' + ''.join('<tr>' + ''.join('<td>'+_h(v)+'</td>' for v in row) +
            '</tr>' for row in rows) + '</tbody></table>')


def render_archive_part_annex(rows, u2_model, *, volume_chart=None, year_registration=None,
                               volumes_by_part=None, extraction_label=None, part_period_html=None):
    """One section per native part; never assign U2 across jobs or system IDs."""
    source = {(str(p.get('job_id')), str(p.get('system_id'))): p
              for p in u2_model.get('archive_parts') or [] if p.get('system_id')}
    out = [('<p>Hver arkivdel viser DWM XPath, observerte KDRS Query U2-tall og '
            'rapportverdi separat. Et importert tall er ikke automatisk godkjent. '
            'Ukjent er ikke null. Full kildehistorikk og kontrollfunn finnes i vedlegg C og JSON.</p>')]
    for job, data, _report_path, _diagnostic in rows:
        if not data:
            continue
        jid = str(job.job_id)
        label = extraction_label(job, data) if extraction_label else jid
        volumes = {}
        if volumes_by_part is not None:
            volumes = {str(ident): volume for ident, _title, volume in volumes_by_part(data)}
        for number, part in enumerate(data.get('archive_parts') or [], 1):
            info = part.get('archive_part') or {}
            sid = str(info.get('system_id') or '')
            title = str(info.get('title') or sid or 'Uten navn')
            evidence = source.get((jid,sid))
            out.append('<section class="appendix"><h2>Vedlegg – arkivdel: '+_h(label)+' / '+_h(title)+'</h2>')
            # Keep the complete available scalar metadata without displaying
            # dozens of blank count fields or empty synthetic year tables.
            metas = []
            for field, value in info.items():
                if field in ('title','description') or value is None or value == '':
                    continue
                if isinstance(value,(dict,list)):
                    continue
                metas.append((field,value))
            if metas:
                out.append('<p><strong>Arkivdelmetadata</strong></p>'+_table(('Egenskap','Verdi'),metas))
            description = info.get('description')
            if description:
                out.append('<p><strong>Beskrivelse:</strong> '+_h(description).replace('\n','<br>')+'</p>')
            if evidence is None:
                out.append('<p>KDRS U2 er ikke tilordnet denne arkivdelen. '
                           'DWM-tall beholdes separat; manglende er ukjent.</p>')
            else:
                out.append('<p>KDRS Query U2: '+_h(evidence.get('u2_status') or 'Ukjent tilordning')+'</p>')
            table_rows = []
            dwm = []
            kdrs = []
            report = []
            selected=[]
            for metric, name in METRICS:
                item = ((evidence or {}).get('metrics') or {}).get(metric) or {}
                original = item.get('dwm') if evidence is not None else part.get(metric)
                observed = (((evidence or {}).get('kdrs_u2_observations') or {}).get(metric) or {})
                selected_value = item.get('report') if evidence is not None else original
                dwm.append(_v(original))
                kdrs.append('Motstrid' if observed.get('status')=='motstrid' else _v(observed.get('value')))
                report.append(_v(selected_value))
                if item.get('source') == 'KDRS Query (verifisert)' and type(selected_value) is int:
                    selected.append(name)
            out.append(_table(('Kilde / status',*(name for _metric,name in METRICS)), [
                ('DWM XPath',*dwm), ('KDRS Query U2 (observert)',*kdrs),
                ('Rapportverdi',*report)]))
            if selected:
                out.append('<p>Verifisert, arkivdelavgrenset KDRS-valg: '+_h(', '.join(selected))+
                           ' (KDRS). Andre importerte tall er kun observasjoner.</p>')
            if evidence and evidence.get('u2'):
                imports = sorted({str((s or {}).get('source_import_id')) for s in evidence['u2']
                                  if (s or {}).get('source_import_id')})
                files = sorted({str((s or {}).get('source_file')) for s in evidence['u2']
                                if (s or {}).get('source_file')})
                tests = sorted({str((s or {}).get('test')) for s in evidence['u2']
                                if (s or {}).get('test')})
                out.append('<p class="note">KDRS U2-kilde: '+_h(', '.join(files) or 'Ukjent')+
                           '; import: '+_h(', '.join(imports) or 'Ukjent')+
                           '; test: '+_h(', '.join(tests) or 'Ukjent')+
                           '. Detaljert SHA-256 og testkobling: vedlegg C / JSON.</p>')
            # Other real non-empty native scalar counters remain accessible;
            # do not add duplicate DWM counts already in the comparison table.
            extra = [(k,_v(v) if type(v) is int else v) for k,v in part.items()
                     if k not in ('archive_part','yearly_volume') and k not in dict(METRICS)
                     and v is not None and v != '' and not isinstance(v,(list,dict))]
            if extra:
                out.append('<p><strong>Øvrige DWM-måltall</strong></p>'+_table(('Måltall','DWM'),extra))
            if part_period_html is not None and sid:
                periods=((data.get('period_reconciliation') or {}).get('archive_parts') or [])
                if any(str(((record or {}).get('archive_part') or {}).get('system_id') or '') == sid
                       for record in periods):
                    out.append(part_period_html(data, info))
            # Per-part dates/year volumes exist for some extractions; keep them
            # when present, but never manufacture a zero chart for empty data.
            year_data = volumes.get(sid) or {}
            if year_data and volume_chart:
                regs = year_registration(data, archive_part_id=sid) if year_registration else None
                out.append('<h3>Årsvolum – DWM XPath</h3>'+volume_chart(year_data, registrations=regs))
            out.append('</section>')
    unmatched=u2_model.get('unmatched_u2') or []
    if unmatched:
        out.append('<h2>U2-kilder uten entydig arkivdelkobling</h2><p>Disse funnene er ikke '
                   'tildelt en annen arkivdel.</p>')
        out.append(_table(('Jobb','Kildetittel','Årsak','Import','Kilde'), [
            (r.get('job_id'),r.get('title'),r.get('reason'),r.get('source_import_id'),r.get('source_file'))
            for r in unmatched]))
    for warning in u2_model.get('diagnostics') or []:
        out.append('<p>'+_h(warning)+'</p>')
    return ''.join(out)
