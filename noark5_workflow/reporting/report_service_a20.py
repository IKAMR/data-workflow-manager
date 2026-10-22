"""One public entrypoint for selected-job report exports in Data Workflow Manager.

DWM GUI, single-job views and later CLI/portal callers can call
``write_report_package`` with the same job sequence and ReportOptions.
The underlying a19 renderer remains authoritative for sources, archive U2,
comparison, charts and PDF layout. This layer adds the a20 canonical snapshot,
professional period status, compact part index and CSV; no new XPath/Arkade work.
"""
from __future__ import annotations

import json
from copy import copy
from html import escape
from pathlib import Path
import tempfile
from typing import Callable

from .report_model_a20 import build_snapshot
from .report_views_a20 import enrich_html, csv_for_page
from .report_content_a201 import attach_content_profiles
from .report_content_views_a201 import augment_content_html, content_csv
from .report_layout_a202 import improve_report_html

SUPPORTED_FORMATS = ('html','pdf','json','csv')
REPORT_NAMES = (
    'index.html', 'vedlegg-a-uttrekk.html', 'vedlegg-b-arkivdeler.html',
    'vedlegg-c-teknisk-evidens.html', 'vedlegg-d-periodevurdering.html',
)


def _prefix(value):
    value = str(value or '').strip()
    if value:
        if value in ('.','..') or any(c in value for c in '/\\<>:"|?*') or any(ord(c)<32 for c in value):
            raise ValueError('Ugyldig filnavnprefiks')
        if value.endswith(('.', ' ')):
            raise ValueError('Ugyldig filnavnprefiks')
        if not value.endswith(('_','-')):
            value += '_'
    return value


def _recovered_source_rows(jobs):
    """Display the source grade of recovered report-only jobs, not invented counts."""
    out=[]
    for job in jobs:
        try:
            state=job.get_operation_params('__dwm_report_recovery__')
        except (AttributeError,TypeError,ValueError):
            state=(getattr(job,'operation_params',{}) or {}).get('__dwm_report_recovery__')
        if not isinstance(state,dict) or not state.get('report_only'):
            continue
        sources=list(map(str,state.get('evidence') or []))
        cache=state.get('report_cache') or ''
        status=('Gjenfunnet fra eldre rapport/ZIP (lokal kopi)' if cache else
                'Lagret DWM-depotrapport' if state.get('report_file') else
                'Uten komplett DWM-depotrapport – antall ukjent')
        out.append({'job_id':str(job.job_id),
                    'extraction':str(job.name or job.job_id),
                    'basis':status,
                    'evidence':sources,
                    'original_job_id':str(state.get('source_job_id') or ''),
                    'recovery_cache':str(cache),
                    'source_extraction':str(state.get('extraction_path') or '')})
    return out


def _recovered_source_html(rows):
    if not rows:
        return ''
    markup=['<section class="report-recovery-sources"><h2>Gjenfunne rapportjobber – '
            'kildegrunnlag</h2><p>Eksisterende DWM-rapportering og eldre kildeartefakter '
            'holdes atskilt. Uten en komplett depotrapport er antall ukjent, ikke null. '
            'Gjenfinning kjører ingen nye analyser og er ikke faglig godkjenning.</p>',
            '<table><thead><tr><th>Jobb</th><th>Uttrekk</th><th>Rapportstatus</th>'
            '<th>Tilgjengelig evidens</th></tr></thead><tbody>']
    for row in rows:
        parts=(row['job_id'],row['extraction'],row['basis'],
               '; '.join(row['evidence']) or 'Ingen')
        markup.append('<tr>'+''.join('<td>'+escape(str(x),quote=True)+'</td>'
                                     for x in parts)+'</tr>')
    markup.append('</tbody></table></section>')
    return ''.join(markup)


def _available(options):
    enabled = set(options.enabled)
    names = ['index.html']
    if options.extraction_appendix:
        names.append('vedlegg-a-uttrekk.html')
    if options.archive_part_appendix:
        names.append('vedlegg-b-arkivdeler.html')
    if enabled & {'technical','external','sources'}:
        names.append('vedlegg-c-teknisk-evidens.html')
    if 'period' in enabled:
        names.append('vedlegg-d-periodevurdering.html')
    return tuple(names)


def _validate_jobs(jobs):
    if not jobs:
        raise ValueError('Ingen jobber valgt')
    seen = {}
    for j in jobs:
        jid = str(getattr(j,'job_id',''))
        if not jid or '/' in jid or '\\' in jid:
            raise ValueError('Jobb mangler en gyldig lokal jobb-ID')
        # Repeated JOB-nnn across different jobs is a legacy report_package
        # identity collision for U2. Explicit failure is safer than false facts.
        if jid in seen and seen[jid] is not j:
            raise ValueError('Samme JOB-ID fra flere jobblister: ' + jid + '. '
                             'Behandle jobblistene separat til global jobbidentitet er innført.')
        if jid in seen:
            raise ValueError('Samme jobb er valgt flere ganger: ' + jid)
        seen[jid] = j



def _report_read_jobs(jobs, staging):
    """Give legacy *readers* a non-existent local path when Work is unknown.

    a20.7 correctly preserves ``work_operations=None`` for recovered extractions
    with no DWM work directory. a19's period_assessment.assessment_path still
    calls Path(work_operations) even for read-only report generation. Passing a
    shallow view with a non-existent LOCAL path avoids Path(None) without
    creating a fake depot report, writing to a source disk, or changing the
    persisted Job object. Never use these views for saving assessments or runs.
    """
    adapted=[]
    placeholders={}
    for job in jobs:
        known=(getattr(job,'_effective_work_operations',None)
               or getattr(job,'work_operations',None))
        if known:
            adapted.append(job)
            continue
        shadow=copy(job)
        # This directory is deliberately NOT created, and lives in the
        # private temporary report staging area (not on the unstable disk).
        placeholder=staging / '_work_not_registered' / str(job.job_id)
        shadow.work_operations=placeholder
        shadow._effective_work_operations=placeholder
        adapted.append(shadow)
        placeholders[str(job.job_id)]=placeholder
    return tuple(adapted),placeholders


def _missing_work_diagnostic(job_id):
    return (f'{job_id}: Ingen Work - operations er registrert. '
            'DWM-depotrapport og analysegrunnlag er ikke tilgjengelig; '
            'manglende tall er ukjent, ikke 0.')


def _annotate_missing_work(payload, missing_work):
    """Preserve the true lack of a report root in each exported JSON page."""
    for row in payload.get('jobs') or ():
        key=str(row.get('job_id') or '')
        if key in missing_work and not row.get('depot_report'):
            row['source_file']=None
            row['diagnostic']=_missing_work_diagnostic(key)
    return payload


def _destinations(directory, names, prefix, formats):
    return {(name,fmt):directory / (prefix + Path(name).stem + '.' + fmt)
            for name in names for fmt in formats}


def write_report_package(directory, jobs, options, *, prefix='', formats=('html',),
                         overwrite=False, on_warning=None,
                         _legacy_export: Callable | None = None,
                         _pdf_renderer: Callable | None = None):
    """Read-only selected-job reporting with one consistent a20 data snapshot.

    This function deliberately preserves the a19 signature. The two private
    injectable callables are for regression tests, not a second export engine.
    All requested outputs are built in a temporary directory and published
    only after the source/result data has been validated.
    """
    jobs=tuple(jobs)
    _validate_jobs(jobs)
    formats=tuple(dict.fromkeys(str(fmt).lower() for fmt in formats))
    if not formats or any(fmt not in SUPPORTED_FORMATS for fmt in formats):
        raise ValueError('Velg minst ett gyldig eksportformat: HTML, PDF, JSON eller CSV')
    prefix=_prefix(prefix)
    directory=Path(directory)
    if directory.exists() and not directory.is_dir():
        raise ValueError('Rapportmål er ikke en mappe')
    names=_available(options)
    paths=_destinations(directory,names,prefix,formats)
    if not overwrite:
        conflicts=[str(p) for p in paths.values() if p.exists()]
        if conflicts:
            raise FileExistsError('Rapportfiler finnes allerede: '+', '.join(conflicts))
    if _legacy_export is None or (_pdf_renderer is None and 'pdf' in formats):
        from .report_package_a16 import write_report_package as legacy_writer, _pdf_bytes
    else:
        legacy_writer, _pdf_bytes = None, None
    legacy_writer=_legacy_export or legacy_writer
    pdf_render=_pdf_renderer or _pdf_bytes
    warnings=[]
    with tempfile.TemporaryDirectory(prefix='dwm-a20-report-') as staging:
        staged=Path(staging)
        # An extraction recovered WITHOUT a DWM work root is valid input to a
        # read-only report. Do not pass None to the legacy period/path readers.
        read_jobs,missing_work=_report_read_jobs(jobs,staged)
        # Always create the established authoritative HTML+JSON once. All
        # output formats are derived from these files, not from fresh scans.
        legacy_writer(staged,read_jobs,options,prefix=prefix,formats=('html','json'))
        base_file=staged/(prefix+'index.json')
        if not base_file.is_file():
            raise RuntimeError('Eksisterende rapportmotor laget ikke index.json')
        base=json.loads(base_file.read_text(encoding='utf-8'))
        if not isinstance(base,dict) or len(base.get('jobs') or []) != len(jobs):
            raise ValueError('Uventet rapportstruktur: jobbantall stemmer ikke med utvalget')
        # The legacy renderer's temporary sentinel must not appear as a
        # factual source location in JSON or the exported HTML diagnostics.
        if missing_work:
            _annotate_missing_work(base,missing_work)
        recovered_sources=_recovered_source_rows(jobs)
        if recovered_sources:
            base['report_recovery_sources']=recovered_sources
        snapshot=attach_content_profiles(build_snapshot(base),read_jobs,base)
        warnings.extend(snapshot['warnings'])
        prepared={}
        for name in names:
            stem=Path(name).stem
            html_path=staged/(prefix+name)
            if not html_path.is_file():
                raise RuntimeError('Eksisterende rapportmotor mangler: '+name)
            html=enrich_html(html_path.read_text(encoding='utf-8'),name,snapshot,
                             include_period='period' in options.enabled)
            html=augment_content_html(html,name,snapshot,level=options.level,
                        enabled=options.enabled,
                        extraction_appendix=options.extraction_appendix)
            html=improve_report_html(html,name,snapshot,base)
            # Clean ephemeral sentinel paths from all legacy HTML sections,
            # including appendix A and source traceability.
            for key,placeholder in missing_work.items():
                html=html.replace(str(placeholder), _missing_work_diagnostic(key))
            if name == 'index.html' and recovered_sources:
                html=html.replace('</body>',_recovered_source_html(recovered_sources)+'</body>',1)
            if 'html' in formats:
                prepared[(name,'html')]=html.encode('utf-8')
            if 'json' in formats:
                source=staged/(prefix+stem+'.json')
                payload=json.loads(source.read_text(encoding='utf-8'))
                if missing_work:
                    _annotate_missing_work(payload,missing_work)
                payload['a20_report_snapshot']=snapshot
                if recovered_sources:
                    payload['report_recovery_sources']=recovered_sources
                # Retain the former XPath-only label separately for auditing.
                # The primary per-job status now describes the professional
                # assessment and can use KDRS without asserting DWM ran.
                if len(payload.get('jobs') or []) == len(snapshot['jobs']):
                    for old, current in zip(payload['jobs'],snapshot['jobs']):
                        old['dwm_xpath_period_status']=old.get('period_status')
                        old['period_status']=current['professional_period_status']
                        old['professional_period_status']=current['professional_period_status']
                prepared[(name,'json')]=(json.dumps(payload,ensure_ascii=False,indent=2,default=str)+'\n').encode('utf-8')
            if 'csv' in formats:
                prepared[(name,'csv')]=csv_for_page(name,snapshot,base)
            if 'pdf' in formats:
                # Convert the exact same augmented HTML as the exported page.
                prepared[(name,'pdf')]=html
        # A separate normalized CSV avoids mixing category rows with the
        # established one-row-per-job a20 CSV contract. Export it only if
        # actual saved profile facts exist.
        if ('csv' in formats and 'totals' in options.enabled
                and options.level != 'Enkel' and any(
                (j.get('content_profile') or {}).get('status') == 'available'
                for j in snapshot['jobs'])):
            key=('innholdsprofil','csv')
            paths[key]=directory/(prefix+'innholdsprofil.csv')
            if paths[key].exists() and not overwrite:
                raise FileExistsError('Rapportfil finnes allerede: '+str(paths[key]))
            prepared[key]=content_csv(snapshot,level=options.level)
        if 'pdf' in formats:
            try:
                for name in names:
                    prepared[(name,'pdf')]=pdf_render(prepared[(name,'pdf')])
            except Exception as exc:
                if formats == ('pdf',):
                    raise RuntimeError('PDF-eksport feilet: '+str(exc)) from exc
                for name in names:
                    prepared.pop((name,'pdf'),None)
                warnings.append('PDF ble ikke eksportert: '+str(exc)+
                                '. Eventuelle eldre PDF-filer i målmappen er ikke oppdatert.')
        # Re-check destination before writing if caller prohibited overwrite.
        if not overwrite and any(paths[k].exists() for k in prepared):
            raise FileExistsError('Rapportfiler ble opprettet av en annen prosess under eksporten')
        directory.mkdir(parents=True,exist_ok=True)
        for key, content in prepared.items():
            dest=paths[key]
            temp=dest.with_name(dest.name+'.tmp')
            temp.write_bytes(content)
            temp.replace(dest)
    if warnings and on_warning is not None:
        for warning in warnings:
            on_warning(warning)
    for preferred in ('html','pdf','json','csv'):
        key=('index.html',preferred)
        if key in prepared:
            return paths[key]
    raise RuntimeError('Ingen rapportfiler produsert')


# Stable descriptive alias for callers that do not wish to use the a19 name.
export_selected_jobs = write_report_package
