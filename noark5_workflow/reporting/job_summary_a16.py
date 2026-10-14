"""Read-only report for selected Noark 5 jobs; never starts an operation."""
from __future__ import annotations
import json
from dataclasses import dataclass
from datetime import datetime
from html import escape
from pathlib import Path
from noark5_workflow.reporting.period_assessment_a16 import load_assessment, reviewed_years, review_candidate

SECTIONS = {
    'overview': 'Jobboversikt', 'totals': 'Hovedtall',
    'technical': 'Tekniske kontroller', 'deviations': 'Vurderingspunkter',
    'external': 'Ekstern evidens', 'period': 'Periodeavstemming',
    'sources': 'Kildesporbarhet',
}
PRESETS = {
    'Enkel': ('overview', 'technical'),
    'Medium': ('overview', 'totals', 'technical', 'deviations', 'external'),
    'Full': tuple(SECTIONS),
}

@dataclass(frozen=True)
class ReportOptions:
    level: str = 'Medium'
    sections: tuple[str, ...] = ()
    extraction_appendix: bool = False
    archive_part_appendix: bool = False

    @property
    def enabled(self):
        return tuple(s for s in (self.sections or PRESETS[self.level]) if s in SECTIONS)


def _report_locations(job):
    """Known report roots, not a recursive scan of unrelated jobs or documents."""
    bases = []
    for value in (getattr(job, '_effective_work_operations', None),
                  getattr(job, 'work_operations', None)):
        if value:
            base = Path(value)
            for candidate in (base, base / 'dwm'):
                if candidate not in bases:
                    bases.append(candidate)
    return tuple(base / 'noark5_reports' / 'depot_validation' for base in bases)


def _latest_report(job):
    """Find the newest readable report for this job across documented work layouts.

    Returns (data, file_path, diagnostic).  A corrupt/unreadable report cannot
    masquerade as a report that has never been generated.
    """
    candidates = []
    locations = _report_locations(job)
    for location in locations:
        candidates.extend(p for p in location.glob('*/depot_validation_report.json')
                          if p.parent.name.startswith(str(job.job_id) + '__'))
    candidates = sorted(set(candidates), key=lambda p: p.stat().st_mtime, reverse=True)
    errors = []
    for path in candidates:
        try:
            value = json.loads(path.read_text(encoding='utf-8'))
            if isinstance(value, dict):
                return value, path, ''
            errors.append(f'{path}: rapporten er ikke et JSON-objekt')
        except (OSError, ValueError) as exc:
            errors.append(f'{path}: {exc}')
    if errors:
        return None, None, 'Kunne ikke lese depotrapport: ' + '; '.join(errors)
    if not locations:
        return None, None, 'Work - operations er ikke angitt for jobben'
    return None, None, 'Ingen depotrapport funnet. Søkte i: ' + '; '.join(map(str, locations))


def _h(v):
    return escape(str(v if v is not None else ''), quote=True)


def _table(headers, rows):
    head = ''.join('<th>' + _h(x) + '</th>' for x in headers)
    body = ''.join('<tr>' + ''.join('<td>' + _h(v) + '</td>' for v in row) + '</tr>' for row in rows)
    return '<table><thead><tr>' + head + '</tr></thead><tbody>' + body + '</tbody></table>'


def _section(title, content, css=''):
    return '<section class="' + css + '"><h2>' + _h(title) + '</h2>' + content + '</section>'


def _observed_overall_years(data):
    """Report observed archive activity, never the submitted period or change-log dates."""
    observed = (((data or {}).get('period_reconciliation') or {}).get('observed_series') or {})
    years = []
    for field in ('folder_created', 'registration_created', 'journal_date_archive_structure',
                  'document_description_created', 'document_object_parent_created'):
        span = (observed.get(field) or {}).get('span') or {}
        a, b = span.get('first_year'), span.get('last_year')
        if a is not None and b is not None and str(a).isdigit() and str(b).isdigit():
            years.extend((int(a), int(b)))
    if not years:
        return None
    return min(years), max(years)


def _observed_label(data):
    years = _observed_overall_years(data)
    if not years:
        return 'Ikke tilgjengelig'
    return str(years[0]) if years[0] == years[1] else f'{years[0]}–{years[1]}'


def _period_difference(data):
    years = _observed_overall_years(data)
    declared = (((data or {}).get('period_reconciliation') or {}).get('declared_period') or {})
    a, b = declared.get('start_year'), declared.get('end_year')
    if not years or not a or not b:
        return 'Kan ikke avstemmes'
    try:
        declared_years = (int(a), int(b))
    except (TypeError, ValueError):
        return 'Kan ikke avstemmes'
    return 'Avvik' if declared_years != years else 'Samsvar'


def _review_info(job, data):
    if not data:
        return None
    return load_assessment(job)


def _display_years(job, data):
    saved = _review_info(job, data)
    approved = reviewed_years(saved)
    if approved:
        return approved, 'faglig vurdert'
    candidate = review_candidate(data)
    if candidate['needs_review']:
        # Never advertise unreviewed extremes as the accepted period.
        return None, 'krever vurdering'
    return _observed_overall_years(data), ''


def _review_status(job, data):
    saved = _review_info(job, data)
    if saved and saved.get('status') == 'godkjent':
        return 'Godkjent'
    if saved and saved.get('status') == 'undersokes':
        return 'Under undersøkelse'
    candidate = review_candidate(data)
    return 'Krever vurdering' if candidate['needs_review'] else _period_difference(data)


def _extraction_label(job, data):
    """Prefer a descriptive extraction folder, retaining native job identity as fallback."""
    import re
    name = str(getattr(job, 'name', '') or getattr(job, 'job_id', ''))
    paths = (getattr(job, 'source_extraction', None), getattr(job, 'source', None),
             getattr(job, 'source_path', None), getattr(job, 'work_operations', None))
    for value in paths:
        if not value:
            continue
        for segment in reversed(str(value).replace('\\', '/').split('/')):
            match = re.match(r'^(\d{4}_\d{3})[_ -]+(.+?)(?:_noark5)?$', segment, re.I)
            if match:
                words = re.sub(r'_noark5$', '', match.group(2), flags=re.I).replace('_', ' ').replace('-', ' ').strip()
                period = ((data or {}).get('period_reconciliation') or {}).get('declared_period') or {}
                first, last = period.get('start_year'), period.get('end_year')
                observed_years, kind = _display_years(job, data)
                date = ((f' ({observed_years[0]}–{observed_years[1]}' + (f', {kind}' if kind else '') + ')' if observed_years[0] != observed_years[1] else f' ({observed_years[0]}' + (f', {kind}' if kind else '') + ')') if observed_years else
                        (f' (oppgitt {first}–{last}' + (f'; {kind}' if kind else '') + ')' if first and last else ''))
                return f'{match.group(1)} {words}{date}'
    return name


def _archive_names(data):
    return ', '.join(str((x.get('archive_part') or {}).get('title') or
                         (x.get('archive_part') or {}).get('system_id') or 'Uten navn')
                     for x in (data or {}).get('archive_parts') or []) or '–'


def _period_text(data):
    declared = ((data or {}).get('period_reconciliation') or {}).get('declared_period') or {}
    a, b = declared.get('start_date'), declared.get('end_date')
    return (f'{a} – {b}' if a and b else '–')


# Separate submitted metadata from observed XPath activity. Never merge distinct date semantics.
_PERIOD_SERIES = (
    ('folder_created', 'Saker (opprettet)'),
    ('registration_created', 'Registreringer (opprettet)'),
    ('journal_date_archive_structure', 'Journalposter (journaldato)'),
    ('document_description_created', 'Dok.beskr. (opprettet)'),
    ('document_object_parent_created', 'Dok.obj. (forelders dato)'),
)


def _span(series):
    """Return explicit XPath span only; missing values remain unknown."""
    span = (series or {}).get('span') or {}
    first, last = span.get('first_year'), span.get('last_year')
    if first and last:
        return str(first) if str(first) == str(last) else f'{first}–{last}'
    return '–'


def _xpath_periods(data):
    recon = ((data or {}).get('period_reconciliation') or {})
    observed = recon.get('observed_series') or {}
    return tuple(_span(observed.get(key)) for key, _ in _PERIOD_SERIES)


def _period_annex(data):
    recon = ((data or {}).get('period_reconciliation') or {})
    observed = recon.get('observed_series') or {}
    if not recon:
        return '<p>Periodeavstemming er ikke tilgjengelig i lagret depotrapport.</p>'
    rows = [('Uttrekksperiode (arkivuttrekk.xml)', _period_text(data))]
    rows += [(label, _span(observed.get(key))) for key, label in _PERIOD_SERIES]
    for key, label in (('running_journal','Løpende journal'), ('public_journal','Offentlig journal'), ('change_log','Endringslogg (ikke arkivperiode)')):
        rows.append((label, _span(observed.get(key))))
    return '<h3>Oppgitt periode og observerte XPath-ytterår</h3>' + _table(('Kilde / datofelt','Periode / ytterår'), rows)


def _part_period_annex(data, info):
    """Match archive part by system ID, not by title or a guessed index."""
    recon = ((data or {}).get('period_reconciliation') or {})
    wanted = info.get('system_id')
    if not wanted:
        return '<p>Arkivdelens XPath-ytterår kan ikke kobles uten system-ID.</p>'
    for entry in recon.get('archive_parts') or []:
        part = entry.get('archive_part') or {}
        if part.get('system_id') != wanted:
            continue
        obs = entry.get('observed_period') or {}
        metrics = entry.get('metrics') or {}
        values = [('Observert aktivitet i arkivdel', _span({'span':obs}))]
        for key, label in (('folder_created','Saker (opprettet)'), ('registration_created','Registreringer (opprettet)'), ('journal_date','Journalposter (journaldato)'), ('document_description_created','Dok.beskr. (opprettet)'), ('document_object_parent_created','Dok.obj. (forelders dato)')):
            values.append((label, _span(metrics.get(key))))
        return '<h3>XPath-ytterår for arkivdelen</h3>' + _table(('Kilde / datofelt','Observerte ytterår'), values)
    return '<p>Ingen arkivdelvis XPath-periodeavstemming funnet for denne system-ID-en.</p>'


def _external_values(data):
    arkade = (((data or {}).get('external_validation') or {}).get('arkade5') or {})
    summary = arkade.get('summary') or {}
    imports = arkade.get('imports') or []
    versions = ', '.join(sorted(set(str(x.get('source_version')) for x in imports if x.get('source_version')))) or '–'
    return (versions, summary.get('imports', 0), summary.get('arkade_errors', '–'),
            summary.get('arkade_warnings', '–'), summary.get('covered_by_arkade', '–'),
            summary.get('pronom_statistics_imports', 0), summary.get('pronom_total_files', '–'))


def _archive_part_annex(job, data, entry):
    info = entry.get('archive_part') or {}
    title = info.get('title') or info.get('system_id') or 'Uten navn'
    kv = [('Uttrekk', _extraction_label(job, data))]
    kv.extend((k, v) for k, v in info.items() if not isinstance(v, (dict,list)))
    kv.extend((k, v) for k, v in entry.items() if k != 'archive_part' and not isinstance(v, (dict,list)))
    table = _table(('Egenskap', 'Verdi'), kv)
    table += _part_period_annex(data, info)
    yearly = entry.get('yearly_volume') or {}
    if yearly:
        years = sorted(set().union(*(set(x) for x in yearly.values() if isinstance(x, dict))))
        table += '<h3>Omfang per år</h3>' + _table(('År', 'Mapper', 'Journalposter', 'Dokumentbeskrivelser', 'Dokumentobjekter'), [
            (y,) + tuple((yearly.get(k) or {}).get(y, '–') for k in ('folder','journal','document_description','document_object')) for y in years])
    return _section('Vedlegg – arkivdel: ' + _extraction_label(job, data) + ' / ' + str(title), table, 'appendix')


def render_selected_jobs_report(jobs, options: ReportOptions):
    if options.level not in PRESETS:
        raise ValueError('Ukjent detaljnivå')
    jobs = tuple(jobs)
    if not jobs:
        raise ValueError('Ingen jobber er valgt')
    rows = [(job, *_latest_report(job)) for job in jobs]
    enabled = set(options.enabled)
    parts = ['<!doctype html><html lang="no"><head><meta charset="utf-8"><title>Samlerapport – Noark 5</title>',
             '<style>body{font:11pt Segoe UI,Arial,sans-serif;color:#223;max-width:1250px;margin:36px auto;padding:0 24px}h1{font-size:18pt}h2{font-size:13pt;margin-top:30px}h3{font-size:11pt}table{border-collapse:collapse;width:100%;font-size:10pt;margin:12px 0}th,td{border:1px solid #ccd2db;padding:7px;text-align:left;vertical-align:top}th{background:#eef2f7}section{break-inside:avoid}.muted{color:#586579}details{margin:12px 0} .appendix{break-before:page}@media print{body{margin:0;padding:0}button{display:none}details{display:block}details>*{display:block}}</style></head><body>',
             '<h1>Samlerapport – Noark 5</h1>', '<p>Generert: ' + _h(datetime.now().astimezone().isoformat(timespec='seconds')) + ' · Jobber: ' + str(len(rows)) + ' · Detaljnivå: ' + _h(options.level) + '</p>',
             '<p class="muted">Leser lagrede depotrapporter. Manglende resultatgrunnlag merkes; ingen analyser kjøres på nytt. Rapporten er ikke en automatisk depotgodkjenning.</p>']
    if 'overview' in enabled:
        parts.append(_section('Jobboversikt', '<p>Årstall i uttrekksnavn er observerte ytterår fra XPath der de finnes. Oppgitt uttrekksperiode vises separat under Periodeavstemming. Avvik betyr ulike ytterår, ikke automatisk feil i uttrekket.</p>' + _table(('Jobb','Uttrekk (periode med kilde)','Arkivdel(er)','Periodevurdering','Status','Fremdrift','Depotrapport'), [
            (j.job_id, _extraction_label(j,d), _archive_names(d), _review_status(j,d), j.status.value, f'{round(j.progress*100)} %', 'Funnet' if d else 'Mangler / kan ikke leses') for j,d,p,diagnostic in rows])))
    keys = [('archive_part_count','Arkivdeler'),('folder_count','Mapper'),('registration_count','Registreringer'),('document_description_count','Dokumentbeskrivelser'),('document_object_count','Dokumentobjekter')]
    if 'totals' in enabled:
        summaries = [d.get('summary') or {} for _,d,_,_ in rows if d]
        aggregate = [(label, sum(v.get(key, 0) for v in summaries if isinstance(v.get(key), (int,float)))) for key,label in keys]
        parts.append(_section('Samlet omfang', '<p>Resultatgrunnlag for ' + str(len(summaries)) + ' av ' + str(len(rows)) + ' valgte jobber.</p>' + _table(('Måltall', 'Sum'), aggregate)))
        parts.append(_section('Hovedtall per uttrekk', _table(('Uttrekk',)+tuple(x[1] for x in keys), [
            (_extraction_label(j,d),)+(tuple((d.get('summary') or {}).get(k, '–') for k,_ in keys) if d else ('–',)*len(keys)) for j,d,p,diagnostic in rows])))
    if 'technical' in enabled:
        parts.append(_section('Tekniske kontroller', _table(('Uttrekk','Teknisk status','XPath OK','XPath feil','Krysskontroll avvik'), [
            (_extraction_label(j,d), (d.get('technical_validation') or {}).get('status','–'),
             ((d.get('technical_validation') or {}).get('summary') or {}).get('ok','–'),
             ((d.get('technical_validation') or {}).get('summary') or {}).get('error','–'),
             ((d.get('technical_validation') or {}).get('reconciliation') or {}).get('mismatch','–')) if d else (_extraction_label(j,d),'Mangler','–','–','–') for j,d,p,diagnostic in rows])))
    if 'deviations' in enabled:
        parts.append(_section('Vurderingspunkter', _table(('Uttrekk','Antall','Funn'), [
            (_extraction_label(j,d), len(d.get('deviations') or []), '; '.join(str(x.get('summary','')) for x in (d.get('deviations') or []))) if d else (_extraction_label(j,d),'–','Ingen rapport') for j,d,p,diagnostic in rows])))
    if 'external' in enabled:
        parts.append(_section('Ekstern evidens', '<p>Dette er evidens registrert i siste lagrede depotrapport per jobb. Nyere Arkade- eller KDRS-import krever ny depotrapport for å bli gjenspeilet.</p>' + _table(('Uttrekk','Arkade-versjon','Importer','Kontrollområder med feil','Advarsler','Kun Arkade','PRONOM-statistikksett','PRONOM-filer'), [
            (_extraction_label(j,d), *_external_values(d)) for j,d,p,diagnostic in rows])))
    if 'period' in enabled:
        columns = ('Uttrekk', 'Oppgitt (arkivuttrekk.xml)', 'XPath samlet', 'Avstemming') + tuple(label for _,label in _PERIOD_SERIES)
        period_rows = [(_extraction_label(j,d), _period_text(d), _observed_label(d), _review_status(j,d), *_xpath_periods(d)) if d else
                       (_extraction_label(j,d), '–', '–', 'Kan ikke avstemmes', *('–' for _ in _PERIOD_SERIES))
                       for j,d,p,diagnostic in rows]
        parts.append(_section('Periodeavstemming', '<p>Oppgitt uttrekksperiode og observerte ytterår fra ulike XPath-datofelt holdes adskilt. Dokumentobjekter bruker forelders opprettelsesår, ikke dokumentets egen dato. Endringslogg vises separat i uttrekksvedlegg og inngår ikke i arkivperioden.</p>' + _table(columns, period_rows)))
    if 'period' in enabled:
        review_rows = []
        for j, d, _p, _diagnostic in rows:
            if not d:
                continue
            proposal = review_candidate(d)
            saved = _review_info(j, d) or {}
            if proposal['needs_review'] or saved:
                review_rows.append((j.job_id, _extraction_label(j,d),
                    str(proposal['declared_years'] or '–'), str(proposal['observed_years'] or '–'),
                    str(proposal['document_years'] or '–'),
                    str(proposal['proposed_years'] or '–'),
                    _review_status(j,d), str(saved.get('selected_years') or '–'),
                    saved.get('comment') or '–'))
        if review_rows:
            parts.append(_section('Forslag og lagrede periodevurderinger',
                '<p>Forslag er ikke godkjent periode. Dokumentbaserte forslag krever faglig gjennomgang og endrer aldri opprinnelige metadata.</p>'
                + _table(('Jobb','Uttrekk','Oppgitt','XPath samlet','Dokumentgrunnlag',
                          'Automatisk forslag','Status','Godkjent/valgt','Begrunnelse'), review_rows)))
    if 'sources' in enabled:
        parts.append(_section('Kildesporbarhet', _table(('Uttrekk','Resultatkilde'),[(_extraction_label(j,d),str(p) if p else diagnostic) for j,d,p,diagnostic in rows])))
    if options.extraction_appendix:
        for j,d,p,diagnostic in rows:
            parts.append(_section('Vedlegg – uttrekk: ' + _extraction_label(j,d), '<p>Jobb-ID: ' + _h(j.job_id) + ' · Arkivdeler: ' + _h(_archive_names(d)) + ' · Oppgitt periode: ' + _h(_period_text(d)) + ' · Observert XPath: ' + _h(_observed_label(d)) + ' · Vurdering: ' + _h(_review_status(j,d)) + '</p>' + (_table(('Måltall','Verdi'), [(key, value) for key,value in (d.get('summary') or {}).items()]) if d else '<p>' + _h(diagnostic) + '</p>') + (_period_annex(d) if d else '') + ('<h3>Vurderingspunkter</h3>' + _table(('Kategori','Observasjon'),[(x.get('category'), x.get('summary')) for x in d.get('deviations') or []]) if d else ''), 'appendix'))
    if options.archive_part_appendix:
        for j,d,p,diagnostic in rows:
            if not d:
                parts.append(_section('Vedlegg – arkivdeler: ' + _extraction_label(j,d), '<p>' + _h(diagnostic) + '</p>', 'appendix'))
                continue
            for entry in d.get('archive_parts') or []:
                parts.append(_archive_part_annex(j, d, entry))
    parts.append('</body></html>')
    return '\n'.join(parts)


def write_selected_jobs_report(path, jobs, options):
    path = Path(path).with_suffix('.html')
    content = render_selected_jobs_report(jobs, options)
    path.parent.mkdir(parents=True,exist_ok=True)
    tmp = path.with_name(path.name+'.tmp')
    tmp.write_text(content,encoding='utf-8')
    tmp.replace(path)
    return path
