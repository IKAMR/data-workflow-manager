"""Conservative archive-part evidence view for existing KDRS Query U2 imports.

No XPath is run and no import is performed. A U2 resource is attributed to a
DWM archive part only when its normalized title uniquely matches a part of the
same job. The test text is evidence, never parsed as an authoritative number.
Only an independently SHA-bound, scope-verified projection can carry a chosen
count. This prevents silently assigning U2 observations to the wrong part.
"""
from __future__ import annotations

from collections import Counter
from html import escape
import hashlib
import json
from pathlib import Path
import re

from .external_report_a18 import collect_job_evidence

METRICS = (
    ('folder_count', 'Mapper'),
    ('registration_count', 'Registreringer'),
    ('journalpost_count', 'Journalposter'),
    ('document_description_count', 'Dokumentbeskrivelser'),
    ('document_object_count', 'Dokumentobjekter'),
)


def _key(value):
    return re.sub(r'\s+', ' ', str(value or '').strip()).casefold()


def _count(value):
    return value if type(value) is int and value >= 0 else None


def _h(value):
    return escape(str(value if value is not None else '\u2013'), quote=True)


def _table(cols, rows):
    head = ''.join('<th>' + _h(v) + '</th>' for v in cols)
    body = ''.join('<tr>' + ''.join('<td>' + _h(v) + '</td>' for v in row) + '</tr>' for row in rows)
    return '<table><thead><tr>' + head + '</tr></thead><tbody>' + body + '</tbody></table>'


def _read_scoped_projection(data, path):
    """Validate bound projection once; do not generate or update evidence."""
    if not data or not path:
        return {}, None
    path = Path(path)
    companion = path.with_name('depot-effective-evidence.json')
    if not companion.is_file():
        return {}, None
    try:
        p = json.loads(companion.read_text(encoding='utf-8'))
        if (p.get('kind') != 'noark5_effective_evidence_projection' or
            p.get('native_report_sha256') != hashlib.sha256(path.read_bytes()).hexdigest()):
            return {}, 'U2: Avstemt evidens har ikke gyldig rapportidentitet (SHA-256).'
        source_name = p.get('evidence_companion_file')
        source_hash = p.get('evidence_companion_sha256')
        if source_name or source_hash:
            if (not isinstance(source_name, str) or not source_name or
                Path(source_name).name != source_name or
                not isinstance(source_hash, str)):
                return {}, 'U2: Ugyldig kildeidentitet i avstemt evidens.'
            source = companion.with_name(source_name)
            if (not source.is_file() or hashlib.sha256(source.read_bytes()).hexdigest() != source_hash):
                return {}, 'U2: Kildeintegritet kunne ikke bekreftes.'
        return p.get('archive_parts') or {}, None
    except (OSError, ValueError, TypeError) as exc:
        return {}, 'U2: Avstemt evidens kunne ikke leses: ' + str(exc)


def _verified_part_metric(row, projected, key):
    native = _count(row.get(key))
    result = {'dwm': native, 'report': native,
              'source': 'DWM' if native is not None else None}
    if not isinstance(projected, dict):
        return result
    selection = (projected.get('metrics') or {}).get(key) or {}
    chosen = selection.get('effective_value')
    if (selection.get('status') == 'external_evidence_selected' and
        selection.get('effective_source') == 'KDRS Query' and
        selection.get('dwm_value') == native and
        isinstance(selection.get('evidence'), dict) and
        type(chosen) is int and chosen >= 0):
        result['report'] = chosen
        result['source'] = 'KDRS Query (verifisert)'
    return result


def collect_u2_archive_parts(rows, *, evidence_by_job=None, source_comparison=None):
    """For a 1..N job selection, retain unmatched U2 resources explicitly."""
    result = {'archive_parts': [], 'unmatched_u2': [], 'diagnostics': []}
    # a18-fix11: Reuse the *same* exact semantic observations already prepared
    # for appendix C. Never mine numbers from arbitrary raw text a second time.
    # None means an older caller without that comparison (legacy behaviour).
    comparison_by_job = {}
    if source_comparison is not None:
        for cjob in source_comparison.get('jobs') or []:
            if not isinstance(cjob, dict):
                continue
            jid = str(cjob.get('job_id') or '')
            for fact in ((cjob.get('kdrs_query') or {}).get('exact_comparisons') or []):
                if isinstance(fact, dict) and fact.get('kdrs_type') in ('u02','u2'):
                    comparison_by_job.setdefault(jid, []).append(fact)
    for job, data, report_path, _diagnostic in rows:
        jid = str(job.job_id)
        evidence = (evidence_by_job or {}).get(jid)
        if evidence is None:
            evidence = collect_job_evidence(job, data)
        u2 = [resource for resource in ((evidence.get('kdrs_query') or {}).get('resources') or [])
              if str(resource.get('report_type') or '').lower() in ('u02', 'u2')]
        parts = (data or {}).get('archive_parts') or []
        names = Counter(_key((p.get('archive_part') or {}).get('title')) for p in parts)
        indexes = { _key((p.get('archive_part') or {}).get('title')): i
                    for i, p in enumerate(parts) if names[_key((p.get('archive_part') or {}).get('title'))] == 1
                    and _key((p.get('archive_part') or {}).get('title')) }
        matches = {i: [] for i in range(len(parts))}
        for resource in u2:
            title = str(resource.get('archive_part_title') or '')
            index = indexes.get(_key(title))
            item = {'job_id': jid, 'title': title or None,
                    'archive_part_index': resource.get('archive_part_index'),
                    'test': resource.get('test_point') or resource.get('test_id'),
                    'name': resource.get('test_name'),
                    'source_file': resource.get('source_file'),
                    'source_sha256': resource.get('source_sha256'),
                    'source_import_id': resource.get('source_import_id'),
                    'observations': list(resource.get('observations') or [])}
            if index is None:
                item['reason'] = ('Ingen depotrapport med arkivdeler' if not parts else
                                  'Mangler entydig, eksakt arkivdeltittel')
                result['unmatched_u2'].append(item)
            else:
                matches[index].append(item)
        projection, warning = _read_scoped_projection(data, report_path)
        if warning:
            result['diagnostics'].append(jid + ': ' + warning)
        for index, part in enumerate(parts, 1):
            identity = part.get('archive_part') or {}
            title = str(identity.get('title') or identity.get('system_id') or 'Ukjent arkivdel')
            scoped = projection.get(str(index)) or {}
            saved_identity = scoped.get('archive_part') or {}
            # The effective projection carries title and system-ID as the
            # immutable scope identity. Never reuse it for a different part.
            valid = bool(saved_identity and
                         str(saved_identity.get('system_id') or '') == str(identity.get('system_id') or '') and
                         str(saved_identity.get('title') or '') == str(identity.get('title') or ''))
            effective = {key: _verified_part_metric(part, scoped if valid else {}, key)
                         for key, _label in METRICS}
            # The comparison model has already matched a U2 title uniquely to
            # DWM's archive-part system_id. Keep all source occurrences, but
            # do not treat imported counts as a chosen depot report value.
            observed = {}
            for metric, _label in METRICS:
                occurrences = [dict(fact) for fact in comparison_by_job.get(jid, [])
                               if fact.get('scope') == 'arkivdel'
                               and fact.get('metric_id') == metric
                               and fact.get('archive_part_system_id') == identity.get('system_id')
                               and fact.get('archive_part') == identity.get('title')]
                values = {fact.get('kdrs_value') for fact in occurrences
                          if _count(fact.get('kdrs_value')) is not None}
                if not occurrences:
                    status, value = 'ikke_tilgjengelig', None
                elif len(values) == 1 and len(occurrences) == len([f for f in occurrences if _count(f.get('kdrs_value')) is not None]):
                    status, value = 'kildedokumentert', next(iter(values))
                else:
                    status, value = 'motstrid', None
                observed[metric] = {'value': value, 'status': status,
                                    'sources': occurrences}
            result['archive_parts'].append({
                'job_id': jid, 'title': title,
                'system_id': identity.get('system_id'),
                'archive_part_number': index,
                'metrics': effective,
                'kdrs_u2_observations': observed,
                'u2': matches[index-1],
                'u2_count': len(matches[index-1]),
                'u2_status': ('Koblet via entydig arkivdeltittel' if matches[index-1] else
                              'Ingen entydig tilordnet U2-evidens'),
            })
    return result


def _fmt_count(value):
    return 'Ukjent' if _count(value) is None else f'{value:,}'.replace(',', ' ')


def _display_observation(entry):
    if entry.get('status') == 'motstrid':
        return 'Motstrid – se kilder'
    return _fmt_count(entry.get('value'))


def _verified_report_selections(part):
    """Display only explicit, SHA-bound scoped selections, never raw U2 counts.

    _verified_part_metric and _read_scoped_projection have already validated
    the source, native report identity, archive-part identity and selected scope.
    """
    selected = []
    for metric, label in METRICS:
        item = (part.get('metrics') or {}).get(metric) or {}
        if (item.get('source') == 'KDRS Query (verifisert)' and
            _count(item.get('report')) is not None):
            selected.append(f"{label}: {_fmt_count(item['report'])} (KDRS)")
    return ' · '.join(selected) if selected else '–'


def render_u2_archive_parts(model, *, detailed=False):
    """Render U2 as independently documented observations, not promoted totals.

    Source_comparison is the only source for parsed U2 counts. Legacy report
    values remain DWM/explicitly SHA-bound selections. Missing != zero.
    """
    parts = model.get('archive_parts') or []
    if not (any(part.get('u2_count') or any(
            item.get('source') == 'KDRS Query (verifisert)'
            for item in (part.get('metrics') or {}).values())
            for part in parts) or model.get('unmatched_u2')):
        return '<p>Ingen arkivdelvise KDRS Query U2-resultater funnet i dette rapportgrunnlaget.</p>'
    out = [('<p>Arkivdelvise KDRS Query U2-tall vises fra eksisterende import og samme '
            'semantiske sammenstilling som i vedlegg C. DWM og KDRS er separate kilder; '
            'KDRS-verdiene er <strong>ikke</strong> automatisk godkjente rapportverdier. '
            'Manglende verdier er ukjent, ikke 0. Identitet må være entydig for hver arkivdel.</p>')]
    rows = []
    for part in parts:
        obs = part.get('kdrs_u2_observations') or {}
        kdrs_values = [_display_observation(obs.get(key) or {}) for key, _ in METRICS]
        dwm_known = sum((part.get('metrics') or {}).get(key, {}).get('dwm') is not None for key, _ in METRICS)
        rows.append((part['job_id'], part['title'], *kdrs_values,
                     f'{dwm_known}/{len(METRICS)} tall',
                     _verified_report_selections(part), part.get('u2_status')))
    out.append(_table(('Jobb','Arkivdel','U2 mapper','U2 registreringer','U2 journalposter',
                       'U2 dok.beskr.','U2 dok.obj.','DWM-dekning',
                       'Verifiserte rapportvalg','Tilordning'), rows))
    if detailed:
        for part in parts:
            if not part.get('u2') and not any(
                v.get('source') == 'KDRS Query (verifisert)'
                for v in (part.get('metrics') or {}).values()
            ):
                continue
            obs = part.get('kdrs_u2_observations') or {}
            out.append('<h3>' + _h(part['job_id']) + ' / ' + _h(part['title']) + '</h3>')
            detail = []
            for metric, label in METRICS:
                dm = (part.get('metrics') or {}).get(metric) or {}
                kd = obs.get(metric) or {}
                detail.append((label, _fmt_count(dm.get('dwm')),
                               _display_observation(kd), _fmt_count(dm.get('report')),
                               dm.get('source') or 'Ingen godkjent kilde',
                               len(kd.get('sources') or [])))
            out.append(_table(('Måltall','DWM','KDRS U2 (observert)','Rapportverdi',
                               'Rapportkilde','KDRS-kilder'), detail))
            provenance=[]
            for metric, label in METRICS:
                for fact in (obs.get(metric) or {}).get('sources') or []:
                    provenance.append((label, fact.get('kdrs_value'), fact.get('comparison'),
                                       fact.get('source_import_id'), fact.get('source_file'),
                                       fact.get('source_sha256'), fact.get('source_line')))
            if provenance:
                out.append('<h4>KDRS U2 – kildehenvisninger for måltall</h4>')
                out.append(_table(('Måltall','KDRS-observasjon','Avstemming','Import',
                                   'Kilde','SHA-256','Linje'), provenance))
            if part.get('u2'):
                out.append(_table(('Test','Navn','Import','Kildefil','SHA-256','Resultatlinjer'), [
                    (r['test'], r['name'], r['source_import_id'], r['source_file'],
                     r['source_sha256'], len(r['observations'])) for r in part['u2']]))
            else:
                out.append('<p>Ingen entydig tilordnet U2-evidens for denne arkivdelen.</p>')
    orphans = model.get('unmatched_u2') or []
    if orphans:
        out.append('<h3>U2-resultater uten entydig arkivdelkobling</h3>')
        out.append(_table(('Jobb','Oppgitt arkivdel','Test','Kilde','Status'), [
            (r['job_id'], r['title'], r['test'], r['source_file'], r['reason'])
            for r in orphans]))
    for warning in model.get('diagnostics') or []:
        out.append('<p>' + _h(warning) + '</p>')
    return ''.join(out)
