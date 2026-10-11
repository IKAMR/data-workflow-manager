#!/usr/bin/env python3
"""Read-only, selected-job inventory and print-friendly reports from DWM native Noark5 JSON.

No automatic approval. Run: python tools/noark5_batch_overview_a6.py --source PATH --output PATH
"""
from __future__ import annotations
import argparse
import csv
import hashlib
from datetime import datetime, timezone
import html
import json
from pathlib import Path
import re
import sys
import os

METRICS = [
    ('archive_part_count', 'Arkivdeler'), ('folder_count', 'Mapper'),
    ('registration_count', 'Registreringer'), ('journalpost_count', 'Journalposter'),
    ('document_description_count', 'Dokumentbeskrivelser'),
    ('document_object_count', 'Dokumentobjekter'),
]


def get_count(value):
    if isinstance(value, bool): return None
    if isinstance(value, (int, float)) and value >= 0: return int(value)
    if isinstance(value, dict):
        if value.get('status') not in (None, 'ok', 'available'): return None
        return get_count(value.get('value'))
    return None


def display(value):
    return f'{value:,}'.replace(',', ' ') if value is not None else 'Ikke tilgjengelig'


def read_report(path):
    with path.open(encoding='utf-8') as f: data=json.load(f)
    if data.get('report_type') != 'noark5_depot_validation' or not isinstance(data.get('archive_parts'),list):
        raise ValueError('ikke et DWM Noark 5 depot_validation_report.json')
    return data


def progress(message):
    """Immediate single-line progress output, visible in Windows cmd."""
    print(f"[STATUS] {message}", flush=True)


def _report_directories(candidate):
    """Bounded probes of report-only locations, including optional dwm run folders.

    Never descend into SIP content, DOKUMENT, or arbitrary directories.
    """
    bases = [candidate / 'repository_operations' / 'dwm',
             candidate / 'dwm']
    if candidate.name.lower() == 'dwm':
        bases.append(candidate)
    # A caller may provide dwm/a01 directly.
    if candidate.parent.name.lower() == 'dwm':
        bases.append(candidate)
    for base in bases:
        if not base.is_dir():
            continue
        yield base / 'noark5_reports' / 'depot_validation'
        # Backward-compatible early DWM layout: noark5_reports/JOB-.../report.
        yield base / 'noark5_reports'
        # One deliberately bounded directory level is the supported run folder.
        for entry in base.iterdir():
            if entry.is_dir() and not entry.is_symlink() and entry.name.lower() not in {
                'noark5_reports','external_evidence','logs','content','dokument',
                'temp','temporary','cache','archive','aip','sip'}:
                yield entry / 'noark5_reports' / 'depot_validation'
    yield candidate / 'noark5_reports' / 'depot_validation'
    yield candidate / 'noark5_reports'
    yield candidate / 'depot_validation'


def locate_reports(source):
    """Probe DWM report paths at root, extraction and municipality/extraction levels.

    This is deliberately NOT recursive: never visit SIP/content/document directories.
    """
    source = Path(source)
    if source.is_file():
        if source.name != 'depot_validation_report.json':
            raise ValueError('Velg depot_validation_report.json eller en arbeidsmappe')
        return [source]
    if not source.is_dir():
        raise ValueError(f'Kilden finnes ikke: {source}')

    excluded = {'content', 'sip', 'aip', 'dokument', 'dokumenter', 'documents',
                'schemas', 'original', 'storage', 'temp', 'logs', 'repository_content',
                'noark5_reports', 'depot_validation', 'external_evidence', '_work',
                '_dwg_zip', '.git', '__pycache__'}
    candidates = [source]
    # Probe only directory entries at the first two levels; no unrestricted rglob.
    # A source already inside a work/report directory must not be expanded.
    if source.name.lower() not in {'repository_operations', 'dwm', 'noark5_reports', 'depot_validation'} and source.parent.name.lower() != 'dwm':
        progress(f'Leser maksimalt to mappenivåer under {source} (ingen dokumentsøk)')
        with os.scandir(source) as entries:
            first = [Path(e.path) for e in entries
                     if e.name.lower() not in excluded and e.is_dir(follow_symlinks=False)]
        candidates.extend(first)
        for parent in first:
            # An identified extraction already has its own DWM operations area.
            # Do not descend from an extraction into its archive payload.
            if (parent / 'repository_operations').is_dir() or (parent / 'dwm').is_dir():
                continue
            with os.scandir(parent) as entries:
                candidates.extend(Path(e.path) for e in entries
                                  if e.name.lower() not in excluded and e.is_dir(follow_symlinks=False))

    reports = set()
    for index, candidate in enumerate(candidates, 1):
        progress(f'Mapper undersøkt: {index}/{len(candidates)} | Rapporter funnet: {len(reports)} | {candidate.name}')
        for report_root in _report_directories(candidate):
            if not report_root.is_dir():
                continue
            for path in report_root.glob('*/depot_validation_report.json'):
                if path.is_file() and path not in reports:
                    reports.add(path)
                    progress(f'FUNNET {len(reports)}: {path.parent.name} ({candidate.name})')
            direct = report_root / 'depot_validation_report.json'
            if direct.is_file():
                reports.add(direct)
    progress(f'Søket fullført | Mapper undersøkt: {len(candidates)} | Rapporter funnet: {len(reports)}')
    return sorted(reports)


def identity(path, data):
    # Prefer versioned DWM run-folder job id over unrelated folder names.
    job = next((m.group(1) for p in [path.parent.name,*[x.name for x in path.parents]]
                if (m:=re.search(r'(JOB-\d{3,})(?:__|\b)',p))), None)
    return job or 'Ukjent jobb'


def part_rows(data):
    rows=[]
    for i, p in enumerate(data.get('archive_parts',[]),1):
        identity_data = p.get('archive_part') or {}
        counts = p.get('summary') or p
        if isinstance(p.get('content'),dict) and not any(k in counts for k,_ in METRICS[1:]): counts=p['content']
        row={'nr':i,'title':str(identity_data.get('title') or f'Arkivdel {i}'), 'system_id':str(identity_data.get('system_id') or '')}
        for key,_ in METRICS[1:]: row[key]=get_count(counts.get(key))
        rows.append(row)
    return rows


def overlay_accepted_evidence(path, native_metrics, parts):
    """Read-only overlay. Trust only scoped explicit approvals bound to native SHA."""
    projection_path = path.with_name('depot-effective-evidence.json')
    info={'status':'Ingen evidensprojeksjon', 'approved':0, 'rejected':0, 'source':None, 'whole_selected':{}, 'part_selected':[]}
    if not projection_path.is_file():
        return info
    info['source']=str(projection_path)
    try:
        raw=projection_path.read_bytes()
        projection=json.loads(raw.decode('utf-8-sig'))
        if (projection.get('kind')!='noark5_effective_evidence_projection' or
            projection.get('native_report_unmodified') is not True or
            projection.get('native_report_sha256')!=hashlib.sha256(path.read_bytes()).hexdigest()):
            info['status']='Avvist: projeksjon passer ikke originalrapporten'
            return info
        # The companion SHA protects against stale or replaced source decisions.
        companion_name=projection.get('evidence_companion_file')
        companion_hash=projection.get('evidence_companion_sha256')
        if not companion_name or Path(companion_name).name != companion_name or not companion_hash:
            info['status']='Avvist: manglende evidenskilde'
            return info
        companion=path.with_name(companion_name)
        if not companion.is_file() or hashlib.sha256(companion.read_bytes()).hexdigest()!=companion_hash:
            info['status']='Avvist: evidenskilde er endret eller mangler'
            return info
        proposals=[]
        def consider(metric_row, target, metric):
            if not isinstance(metric_row,dict): return
            if (metric_row.get('status')!='external_evidence_selected' or
                metric_row.get('effective_source')!='KDRS Query' or
                type(metric_row.get('effective_value')) is not int or metric_row['effective_value']<0 or
                not isinstance(metric_row.get('evidence'),dict)):
                return
            if metric not in dict(METRICS): return
            proposals.append((target,metric,metric_row['effective_value']))
        for metric, row in (projection.get('whole') or {}).items():
            consider(row,native_metrics,metric)
        for key, record in (projection.get('archive_parts') or {}).items():
            if not str(key).isdigit() or not 1 <= int(key) <= len(parts):
                info['status']='Avvist: ugyldig arkivdelindeks'
                return info
            part=parts[int(key)-1]
            candidate=record.get('archive_part') or {}
            # Identity must match by system ID, or fallback to title only if ID absent.
            sid=str(candidate.get('system_id') or '').strip()
            if sid:
                matches=sid==part['system_id']
            else:
                matches=(not part['system_id'] and str(candidate.get('title') or '').strip()==part['title'])
            if not matches:
                info['status']='Avvist: arkivdelidentitet stemmer ikke'
                return info
            for metric,row in (record.get('metrics') or {}).items():
                consider(row,part,metric)
        for target,metric,value in proposals:
            if target is native_metrics:
                info['whole_selected'][metric] = value
            else:
                info['part_selected'].append({'archive_part':target['nr'], 'metric':metric, 'value':value})
            target[metric]=value
            target.setdefault('evidence_fields',[]).append(metric)
        info['approved']=len(proposals)
        info['status']='Kontrollert, godkjent evidens innarbeidet' if proposals else 'Kontrollert, ingen godkjente verdier'
        return info
    except (OSError,ValueError,TypeError,KeyError,json.JSONDecodeError) as exc:
        info['status']='Avvist: kunne ikke kontrollere evidensprojeksjon'
        return info



def extract_arkade_quantity(test, control_id):
    """Read only explicitly labelled whole-extraction count messages.

    Per-archive-part counts, error counts, and PRONOM inventory are not totals.
    Conflicting totals within one control are not accepted.
    """
    if not isinstance(test, dict) or test.get('test_id') != control_id:
        return None
    patterns = [r'^Totalt\s*:\s*([0-9]+)\s*$']
    if control_id == 'N5.59':
        patterns = [r'^Antall journalposter funnet i arkivstrukturen\s*:\s*([0-9]+)\s*$']
    found = set()
    for row in test.get('results') or []:
        if not isinstance(row, dict):
            continue
        msg = str(row.get('message') or '').strip()
        for pattern in patterns:
            match = re.fullmatch(pattern, msg, flags=re.IGNORECASE)
            if match:
                found.add(int(match.group(1)))
    return next(iter(found)) if len(found) == 1 else None


def imported_quantity_candidates(value, source):
    """Extract separately sourced Arkade counts, never summing import runs."""
    control_to_metric = {v:k for k,v in ARKADE_QUANTITY_CONTROLS.items()}
    out = []
    for test in value.get('tests') or []:
        if not isinstance(test, dict):
            continue
        cid = test.get('test_id')
        if cid not in control_to_metric:
            continue
        count = extract_arkade_quantity(test, cid)
        if count is not None:
            out.append({'metric':control_to_metric[cid], 'control':cid,
                        'count':count, 'scope':'Hele uttrekket',
                        'source':str(source),
                        'source_version':str(value.get('source_version') or ''),
                        'source_sha256':str((value.get('source') or {}).get('sha256') or '')})
    return out


def imported_arkade_evidence(report_path):
    """Summarize previously imported Arkade 5 results; never parse source SIP.

    These are separate evidence streams, not replacements for DWM XPath counts.
    """
    info = {'status': 'Ingen import funnet', 'imports': 0, 'tests': None,
            'error_occurrences': None, 'failed_controls': [], 'controls': [],
            'pronom_rows': None, 'pronom_files': None, 'pronom_classes': {},
            'pronom_formats': [], 'sources': [], 'warnings': [], 'quantity_candidates': []}
    try:
        # Canonical: repository_operations/dwm/noark5_reports/depot_validation/RUN/report.json
        dwm = next((parent for parent in report_path.parents if parent.name.lower() == 'dwm'), None)
        if dwm is None:
            return info
        report_dir = next((parent for parent in report_path.parents if parent.name.lower() == 'noark5_reports'), None)
        root = (report_dir.parent if report_dir else dwm) / 'external_evidence' / 'arkade5'
        if not root.is_dir():
            root = dwm / 'external_evidence' / 'arkade5'
        if not root.is_dir():
            return info
        # Limit to explicitly imported normalized artifacts, not original large JSON.
        for directory in sorted(root.iterdir()):
            if not directory.is_dir():
                continue
            normalized = directory / 'normalized'
            report = normalized / 'arkade5_results.json'
            pronom = normalized / 'pronom_statistics.json'
            if not report.is_file() and not pronom.is_file():
                continue
            info['imports'] += 1
            if report.is_file():
                value = json.loads(report.read_text(encoding='utf-8-sig'))
                info['quantity_candidates'].extend(imported_quantity_candidates(value, report))
                summary = value.get('summary') or {}
                info['tests'] = summary.get('number_of_tests_run')
                info['error_occurrences'] = decimal_count(summary.get('number_of_errors'))
                failures = []
                controls = []
                for test in value.get('tests', []):
                    if not isinstance(test, dict):
                        continue
                    count = extract_arkade_failures(test)
                    controls.append({'id': test.get('test_id'), 'name': test.get('test_name'),
                                     'occurrences': count, 'status':test.get('source_status'),
                                     'has_results':test.get('has_results')})
                    if count:
                        failures.append({'id': test.get('test_id'), 'name': test.get('test_name'), 'occurrences': count})
                info['failed_controls'] = failures
                info['controls'] = controls
                info['sources'].append(str(report))
            if pronom.is_file():
                value = json.loads(pronom.read_text(encoding='utf-8-sig'))
                rows = (value.get('csv') or {}).get('rows') or []
                classes = {}
                formats = []
                for row in rows:
                    if not isinstance(row, dict):
                        continue
                    count = decimal_count(row.get('Antall'))
                    if count is None:
                        info['warnings'].append('Ugyldig Antall i PRONOM-statistikk')
                        continue
                    key = str(row.get('RAF-220301') or 'Ukjent').strip()
                    classes[key] = classes.get(key, 0) + count
                    formats.append({'id': row.get('Format-ID'), 'type': row.get('Filtype'),
                                    'version': row.get('Formatversjon'), 'classification': key, 'count': count})
                info['pronom_rows'] = len(rows)
                info['pronom_files'] = sum(classes.values())
                info['pronom_classes'] = classes
                info['pronom_formats'] = sorted(formats, key=lambda r: -r['count'])
                info['sources'].append(str(pronom))
        info['status'] = 'Importerte Arkade 5-data' if info['imports'] else 'Ingen import funnet'
    except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
        info['status'] = 'Kunne ikke lese importerte Arkade 5-data'
        info['warnings'].append(str(exc))
    return info


def decimal_count(value):
    if isinstance(value, bool):
        return None
    if isinstance(value, int) and value >= 0:
        return value
    if isinstance(value, str) and re.fullmatch(r'[0-9]+', value.strip()):
        return int(value.strip())
    return None


def extract_arkade_failures(test):
    """Only read documented numeric error fields; no guessing from test status."""
    for key in ('number_of_errors', 'error_count', 'errors_count'):
        result = decimal_count(test.get(key))
        if result is not None:
            return result
    return 0


def metric_coverage(item, key):
    """Full native count versus known lower bound from incomplete part coverage."""
    total = item['metrics'].get(key)
    if total is not None:
        return {'known': total, 'complete': True, 'parts_known': len(item['archive_parts']),
                'parts_total': len(item['archive_parts']), 'source': 'DWM/KDRS rapporttotal'}
    parts = item['archive_parts']
    known = [p.get(key) for p in parts if p.get(key) is not None]
    return {'known': sum(known) if known else None,
            'complete': len(known) == len(parts) and bool(parts),
            'parts_known': len(known), 'parts_total': len(parts),
            'source': 'Sum av arkivdeler; ufullstendig' if known else 'Ikke tilgjengelig'}


def coverage_rows(items):
    rows = []
    for key, label in METRICS:
        known = [metric_coverage(x, key) for x in items]
        present = [x['known'] for x in known if x['known'] is not None]
        fully = sum(x['complete'] for x in known)
        rows.append((label, sum(present) if present else None,
                     fully == len(items), fully, len(items),
                     sum(x['parts_known'] for x in known), sum(x['parts_total'] for x in known)))
    return rows

# Noark 5 Arkade controls potentially reporting whole-extraction quantities.
# A positive has_results flag only means the control has data, not a vetted count.
ARKADE_QUANTITY_CONTROLS = {
    'archive_part_count': 'N5.05',
    'folder_count': 'N5.10',
    'registration_count': 'N5.16',
    'journalpost_count': 'N5.59',
    'document_description_count': 'N5.23',
    'document_object_count': 'N5.26',
}


def quantity_evidence_comparison(item):
    """Expose source provenance and scope without selecting alternative totals.

    Archive-part selections remain scoped to their actual part. A whole-extraction
    Arkade total can be compared with a whole-extraction DWM value, but is never
    substituted for absent native data or apportioned to archive parts.
    """
    ark = item.get('arkade5_import') or {}
    controls = {r.get('id'): r for r in ark.get('controls', []) if isinstance(r, dict)}
    native = item.get('native_metrics') or item['metrics']
    effective = item['metrics']
    evidence = item.get('external_evidence') or {}
    whole_selected = evidence.get('whole_selected') or {}
    part_selected = evidence.get('part_selected') or []
    result = []
    for key, label in METRICS:
        test_id = ARKADE_QUANTITY_CONTROLS[key]
        control = controls.get(test_id)
        candidates = [c for c in ark.get('quantity_candidates', []) if c.get('metric') == key]
        distinct = {c['count'] for c in candidates}
        verified = next(iter(distinct)) if len(distinct) == 1 else None
        if candidates:
            ark_status = ('Dokumentert total i Arkade 5' if verified is not None
                          else 'Ulike totalverdier mellom importer – må avklares')
        else:
            ark_status = ('Resultatgrunnlag finnes – antall ikke verifisert' if control and control.get('has_results')
                          else 'Kontroll registrert, ingen resultatverdier' if control
                          else 'Ingen kontroll påvist')
        selected_whole = key in whole_selected
        selected_parts = [v for v in part_selected if v.get('metric') == key]
        dwm_count = native.get(key)
        # Backward compatibility: older effective reports may identify an approved
        # change but lack the later whole/part scope fields. Preserve provenance
        # without falsely attributing that value to the whole extraction.
        # Compatibility for evidence summaries written before scoped selections.
        # A changed effective count with an approved external decision retains
        # its provenance, but its geographic/archive scope remains unknown.
        approved_count = evidence.get('approved', 0)
        try:
            has_approval = int(approved_count) > 0
        except (TypeError, ValueError):
            has_approval = False
        legacy_approved_change = (
            not selected_whole and not selected_parts
            and has_approval
            and get_count(effective.get(key)) is not None
            and get_count(effective.get(key)) != get_count(dwm_count)
        )
        source = ('KDRS Query (valgt for hele uttrekket)' if selected_whole
                  else 'KDRS Query (godkjent)' if legacy_approved_change
                  else 'DWM')
        # An Arkade total is comparable only to another whole-extraction count
        # of the *same metric*. Its absence is not a reason to infer equality.
        comparable = verified is not None and dwm_count is not None
        agreement = ('Samsvarer' if verified == dwm_count else 'Avvik') if comparable else 'Ikke sammenlignet'
        if candidates and verified is None:
            availability = 'Motstridende Arkade-importer'
        elif verified is not None:
            availability = 'Arkade-total tilgjengelig'
        elif control:
            availability = 'Kontroll finnes, total ikke dokumentert'
        else:
            availability = 'Ingen Arkade-total påvist'
        result.append({
            'metric': key, 'label': label,
            'dwm_count': dwm_count, 'effective_count': effective.get(key),
            'effective_source': source,
            'arkade_control': test_id, 'arkade_status': ark_status,
            'arkade_count': verified, 'arkade_candidates': candidates,
            'scope': 'Hele uttrekket (Arkade 5)',
            'availability': availability,
            'comparable': comparable,
            'comparison_status': agreement,
            'selected_source': source,
            'arkade_selected': False,
            'kdrs_whole_selected': selected_whole,
            'kdrs_archive_parts_selected': selected_parts,
            'selection_scope': ('Hele uttrekket' if selected_whole else
                                'Bare arkivdel' if selected_parts else
                                'Ikke dokumentert i eldre grunnlag' if legacy_approved_change
                                else 'Ingen ekstern verdi valgt'),
        })
    return result



def apply_explicit_quantity_choices(items, selection):
    """Separate reporting choices: never change native/effective metrics or GO.

    Schema: {"choices": [{"job": "JOB-002", "extraction": "folder-name",
             "metric": "folder_count", "source": "Arkade 5", "count": 66834}]}
    A selected number must be corroborated by an imported explicit Arkade total.
    """
    if not isinstance(selection, dict) or not isinstance(selection.get('choices'), list):
        raise ValueError('Valgfilen må inneholde en liste i feltet choices')
    used = set()
    allowed_metrics = {k for k, _ in METRICS}
    for choice in selection['choices']:
        if not isinstance(choice, dict):
            raise ValueError('Ugyldig valgoppføring')
        job, extraction, metric = (str(choice.get(k, '')).strip() for k in ('job', 'extraction', 'metric'))
        if metric not in allowed_metrics or choice.get('source') != 'Arkade 5':
            raise ValueError('Bare dokumenterte Arkade 5-uttrekkstotaler støttes i denne versjonen')
        if not extraction:
            raise ValueError('Uttrekksnavn må oppgis for entydig identifikasjon')
        matching = [i for i in items if i['job'] == job and Path(i['extraction']).name.casefold() == extraction.casefold()]
        if len(matching) != 1:
            raise ValueError(f'Valget identifiserer ikke nøyaktig ett uttrekk: {job} / {extraction}')
        row = next(r for r in matching[0]['quantity_comparison'] if r['metric'] == metric)
        count = choice.get('count')
        if type(count) is not int or count < 0 or row.get('arkade_count') is None or row['arkade_count'] != count:
            raise ValueError(f'Valgt tall er ikke entydig dokumentert i Arkade 5: {job} / {metric}')
        identity_key = (job, extraction.casefold(), metric)
        if identity_key in used:
            raise ValueError(f'Dobbelt valg for {job} / {metric}')
        used.add(identity_key)
        row['report_selected_count'] = count
        row['report_selected_source'] = 'Arkade 5 (eksplisitt rapportvalg)'
        row['report_selected_scope'] = 'Hele uttrekket'
        row['report_selection_only'] = True
    return len(used)

def report_quantity_value(item, metric):
    """User-selected *whole-extraction* reporting total, or existing DWM total.

    Never updates the native/effective metrics nor substitutes archive-part counts.
    """
    native = item['metrics'].get(metric)
    for row in item.get('quantity_comparison', []):
        if row.get('metric') != metric:
            continue
        if row.get('report_selection_only') and row.get('report_selected_scope') == 'Hele uttrekket':
            chosen = row.get('report_selected_count')
            if type(chosen) is int and chosen >= 0:
                return chosen, row.get('report_selected_source', 'Arkade 5 (eksplisitt rapportvalg)')
        break
    return native, next((r.get('selected_source','DWM') for r in item.get('quantity_comparison', []) if r.get('metric') == metric), 'DWM')


def build_report_metrics(item):
    """Materialized, source-labelled report values, independent of original metrics.

    The source scope remains at whole-extraction level for user-selected Arkade
    totals. Unknown native values are not silently treated as zero.
    """
    result = {}
    for key, _label in METRICS:
        value, source = report_quantity_value(item, key)
        row = next((r for r in item.get('quantity_comparison', []) if r.get('metric') == key), {})
        explicit = bool(row.get('report_selection_only') and
                        row.get('report_selected_scope') == 'Hele uttrekket')
        result[key] = {
            'value': value,
            'source': source,
            'scope': 'Hele uttrekket' if explicit else row.get('selection_scope', 'Ukjent'),
            'explicit_selection': explicit,
            'dwm_original': (item.get('native_metrics') or item.get('metrics') or {}).get(key),
            'dwm_effective': (item.get('metrics') or {}).get(key),
        }
    return result


def extract(path):
    data=read_report(path)
    summary=data.get('summary') or {}
    metrics={key:get_count(summary.get(key)) for key,_ in METRICS}
    native_metrics=metrics.copy()
    parts=part_rows(data)
    evidence=overlay_accepted_evidence(path,metrics,parts)
    deviations=data.get('deviations') or []
    tech=data.get('technical_validation') or {}
    assessment=data.get('assessment') or {}
    result = {
        'job':identity(path,data), 'source':str(path.resolve()),
        'extraction': next((str(p.parent) for p in path.parents if p.name.lower()=='repository_operations'), str(path.parent)),
        'name':path.parent.name, 'metrics':metrics,'native_metrics':native_metrics,'archive_parts':parts, 'external_evidence':evidence,
        'arkade5_import':imported_arkade_evidence(path),
        'technical_status':str(tech.get('status') or 'Ukjent'),
        'assessment_status':str(assessment.get('status') or 'Ikke vurdert'),
        'deviation_count':len(deviations),
        'review_required':any(x.get('requires_review') for x in deviations if isinstance(x,dict)),
        'deviations':[str(x.get('summary') or '') for x in deviations if isinstance(x,dict)],
        'warning':'Automatisk oversikt er ikke depotgodkjenning eller grunnlag alene for sletting av kildecontainer.'
    }
    result['quantity_comparison'] = quantity_evidence_comparison(result)
    result['go_assessment'] = go_assessment(result)
    return result


def choose_latest_per_job(items):
    """Deduplicate only matching extraction + job + run-folder family.

    JOB-001 from separate job lists must never be merged accidentally.
    """
    groups = {}
    for item in items:
        groups.setdefault((item['extraction'].casefold(), item['job']), []).append(item)
    chosen = []
    for rows in groups.values():
        chosen.append(max(rows, key=lambda x: Path(x['source']).stat().st_mtime))
    return sorted(chosen, key=lambda x:(x['extraction'],x['job'],x['source']))


def go_assessment(item):
    """Evidence sufficiency, not formal depot acceptance.

    Missing relevant tests are not assumed passing; any native technical error blocks GO.
    """
    reasons = []
    if item['technical_status'].lower() in {'error','failed','failure'}:
        reasons.append('Teknisk validering rapporterer feil')
        verdict = 'STOPP'
    else:
        verdict = 'GO'
    for key, label in METRICS:
        if not metric_coverage(item, key)['complete']:
            reasons.append(f'Mangelfull datadekning: {label}')
    ark = item['arkade5_import']
    if ark['imports'] == 0:
        reasons.append('Arkade 5-resultater er ikke dokumentert i rapportgrunnlaget')
    elif ark['failed_controls']:
        reasons.append('Arkade 5 har kontroller med feilforekomster')
    if item['assessment_status'] not in ('approved','accepted','ok'):
        reasons.append('Faglig depotvurdering er ikke ferdig godkjent')
    if item['deviation_count']:
        reasons.append(f"{item['deviation_count']} registrerte avvik krever vurdering")
    if verdict != 'STOPP' and reasons:
        verdict = 'AVKLARING'
    return {'status': verdict, 'reasons': reasons,
            'scope': 'Tilstrekkelig kontrollgrunnlag, ikke depotgodkjenning eller slettetillatelse'}


def e(value):return html.escape(str(value),quote=True)


def table(headers, rows):
    th=''.join(f'<th>{e(h)}</th>' for h in headers)
    body=''.join('<tr>'+''.join(f'<td>{e(v)}</td>' for v in row)+'</tr>' for row in rows)
    return f'<table><thead><tr>{th}</tr></thead><tbody>{body}</tbody></table>'


REPORT_SECTIONS = {
    'coverage': 'Datadekning',
    'sources': 'Kildesammenligning – mengdetall',
    'arkade_sources': 'Arkade 5 – kilde per import og måltall',
    'archive_parts': 'Arkivdeler',
    'arkade_tests': 'Arkade 5 – importert testgrunnlag',
    'pronom': 'PRONOM – importert filformatstatistikk',
    'deviations': 'Registrerte avvik',
}
REPORT_PROFILES = {
    'oversikt': set(),
    'standard': {'coverage', 'sources', 'archive_parts', 'arkade_tests', 'deviations'},
    'detaljert': set(REPORT_SECTIONS),
}

def selected_report_sections(profile, section_choices=None):
    if profile not in REPORT_PROFILES:
        raise ValueError('Ukjent rapportprofil: '+str(profile))
    if section_choices is None:
        return set(REPORT_PROFILES[profile])
    unknown = set(section_choices) - set(REPORT_SECTIONS)
    if unknown:
        raise ValueError('Ukjente rapportseksjoner: '+', '.join(sorted(unknown)))
    return set(section_choices)

def filter_report_html(document, profile, sections):
    """Filter HTML presentation only; preserve the complete JSON/CSV evidence."""
    import re
    if profile == 'oversikt' and not sections:
        return re.sub(r'<section class="page">.*?</section>', '', document, flags=re.S)

    def filter_one(match):
        block = match.group(0)
        # Split on top-level h3 boundaries, keeping the initial h2/status preamble.
        pieces = re.split(r'(?=<h3>)', block)
        output = [pieces[0]]
        headings = {v: k for k, v in REPORT_SECTIONS.items()}
        for piece in pieces[1:]:
            hit = re.match(r'<h3>(.*?)</h3>', piece, flags=re.S)
            if not hit:
                output.append(piece)
                continue
            key = headings.get(hit.group(1))
            if key == 'sources':
                source_selected = 'sources' in sections
                provenance_selected = 'arkade_sources' in sections
                if not (source_selected or provenance_selected):
                    continue
                if not provenance_selected:
                    piece = re.sub(r'<h4>Arkade 5 – kilde per import og måltall</h4>.*', '', piece, flags=re.S)
                elif not source_selected:
                    piece = re.sub(r'(<h3>Kildesammenligning – mengdetall</h3>).*?(<h4>Arkade 5 – kilde per import og måltall</h4>)', r'\2', piece, flags=re.S)
                output.append(piece)
            elif key is None or key in sections:
                output.append(piece)
        return ''.join(output)

    return re.sub(r'<section class="page">.*?</section>', filter_one, document, flags=re.S)


def render_go_reasons(items):
    """Concise reasons on overview pages, with no change to assessment logic."""
    rows = []
    for item in items:
        assessment = item.get('go_assessment') or {}
        reasons = assessment.get('reasons') or []
        explanation = '; '.join(str(x) for x in reasons) if reasons else 'Ingen registrerte begrunnelser'
        rows.append([item.get('job', ''), Path(item.get('extraction', '')).name,
                     assessment.get('status', 'Ukjent'), explanation])
    return '<h2>Vurderingsgrunnlag per uttrekk</h2>' + table(
        ['Jobb', 'Uttrekk', 'Status', 'Begrunnelse'], rows)

def render(items, generated):
    headers=['Jobb','Uttrekk','Rapportgrunnlag']+[label for _,label in METRICS]+['Teknisk status','Avvik','Depotvurdering','KDRS-evidens','GO-vurdering']
    records=[[x['job'],Path(x['extraction']).name,x['name']]+[display(x['report_metrics'][key]['value']) for key,_ in METRICS]+[x['technical_status'],str(x['deviation_count']),x['assessment_status'], x['external_evidence']['status']+f" ({x['external_evidence']['approved']} valgt)", x['go_assessment']['status']] for x in items]
    coverage = coverage_rows(items)
    incomplete = [label for label, _, complete, *_ in coverage if not complete]
    # Archive parts are *not* additive as logical unique parts unless each selected report is distinct.
    note=('Totaltall er summer fra valgte, forskjellige rapportjobber. Ingen summering av manglende felt som null. '
          'Ukjente eller overlappende uttrekk må avklares manuelt før tall brukes eksternt.')
    content=['<!DOCTYPE html><html lang="no"><head><meta charset="utf-8"><title>Noark 5 – samlet uttrekksoversikt</title>',
             '<style>body{font:11pt/1.45 Arial,sans-serif;color:#182336;max-width:1200px;margin:25px auto;padding:0 12px}h1{font-size:19pt}h2{font-size:14pt;margin-top:28px}h3{font-size:12pt}table{border-collapse:collapse;width:100%;font-size:9pt;margin:10px 0}td,th{border:1px solid #c7ced8;padding:6px;text-align:left;vertical-align:top}th{background:#edf2f8}tr:nth-child(even){background:#fafbfd}.warning{border-left:4px solid #8e5e12;padding:9px 12px;background:#fffaf0}.muted{color:#475569}a{color:#16457f}@media print{@page{size:A3 landscape;margin:12mm}body{margin:0;max-width:none}table{font-size:8pt}.page{break-before:page}thead{display:table-header-group}tr{break-inside:avoid}}</style></head><body>',
             '<h1>Samlet oversikt – Noark 5-uttrekk</h1>',
             f'<p class="muted">Laget {e(generated)}. {len(items)} valgte rapporter. Skrivebeskyttet gjennomgang av eksisterende DWM-resultater.</p>',
             '<h2>Valgte uttrekk</h2>',table(headers,records), render_go_reasons(items),
             '<p class="muted">Tall valgt eksplisitt fra Arkade 5 vises som rapportverdi for hele uttrekket. Originale DWM-tall, arkivdeler, dekningsberegninger og GO-vurdering endres ikke.</p>',
             '<h2>Kjente delsummer og datadekning</h2>',table(['Måltall','Kjent verdi','Dekning','Komplette uttrekk','Arkivdeler med tall'],[[label,display(value),'Komplett' if complete else 'DELSUM – ikke total',f'{full} av {num}',f'{pknown} av {ptotal}'] for label,value,complete,full,num,pknown,ptotal in coverage]),
             f'<p class="muted">{e(note)}</p>']
    if incomplete:content.append(f'<p><strong>Manglende grunnlag:</strong> {e(", ".join(incomplete))}. Summer er derfor delvise.</p>')
    for x in items:
        content += ['<section class="page">',f'<h2>{e(x["job"])} – {e(Path(x["extraction"]).name)} – {e(x["name"])}</h2>',
                    f'<p>Teknisk status: <strong>{e(x["technical_status"])}</strong> | Avvik: <strong>{x["deviation_count"]}</strong> | Depotvurdering: <strong>{e(x["assessment_status"])}</strong></p>',
                    f'<p><strong>GO-vurdering: {e(x["go_assessment"]["status"])}</strong> – {e("; ".join(x["go_assessment"]["reasons"]) or "Ingen mangler påvist i valgte kriterier")}</p>',
                    f'<p><strong>KDRS-evidens:</strong> {e(x["external_evidence"]["status"])} – {x["external_evidence"]["approved"]} godkjente verdier</p>',
                    '<h3>Datadekning</h3>', table(['Måltall','Kjent verdi','Status','Arkivdeler med tall'],
                    [[label,display(cov['known']),'Komplett' if cov['complete'] else 'DELSUM – ikke total',
                      f"{cov['parts_known']} av {cov['parts_total']}"] for key,label in METRICS if (cov:=metric_coverage(x,key))]),
                    '<h3>Kildesammenligning – mengdetall</h3>',
                    '<p class="muted">Arkade 5-totaler hentes bare fra eksplisitte uttrekkstotaler. Hver import beholdes med kilde; ulike verdier blir ikke slått sammen. Ingen Arkade-verdi overstyrer DWM eller fordeles automatisk på arkivdeler. PRONOM-filforekomster er ikke dokumentobjekter.</p>',
                    table(['Måltall','DWM opprinnelig','Valgt rapportverdi','Rapportverdiens kilde','Arkade 5-total','Tilgjengelighet','Sammenligning','KDRS-valgets omfang','Eksplisitt rapportvalg'],
                    [[r['label'],display(r['dwm_count']),display(x['report_metrics'][r['metric']]['value']),x['report_metrics'][r['metric']]['source'],
                      display(r['arkade_count']),r['availability'],r['comparison_status'],r['selection_scope'],
                      (r['report_selected_source']+': '+display(r['report_selected_count'])+' ('+r['report_selected_scope']+')') if 'report_selected_count' in r else 'Ikke valgt'] for r in x['quantity_comparison']]),
                    '<h4>Arkade 5 – kilde per import og måltall</h4>',
                    table(['Måltall','Kontroll','Uttrekkstotal','Versjon','Kilde (normalisert rapport)'],
                      [[r['label'],c['control'],display(c['count']),c['source_version'],c['source']]
                       for r in x['quantity_comparison'] for c in r['arkade_candidates']]),
                    '<h3>Arkivdeler</h3>',table(['Nr','Arkivdel']+[label for _,label in METRICS[1:]],
                      [[p['nr'],p['title']]+[(display(p[key])+(' (KDRS*)' if key in p.get('evidence_fields',[]) else '')) for key,_ in METRICS[1:]] for p in x['archive_parts']]),
                    '<p class="muted">* KDRS = eksplisitt godkjent ekstern evidens; original DWM-rapport er uendret.</p>',
                    '<h3>Arkade 5 – importert testgrunnlag</h3>',
                    f'<p>{e(x["arkade5_import"]["status"])}. Importer: {x["arkade5_import"]["imports"]}; Tester: {e(x["arkade5_import"]["tests"] or "Ukjent")}; Feilforekomster: {e(x["arkade5_import"]["error_occurrences"] if x["arkade5_import"]["error_occurrences"] is not None else "Ukjent")}. Dette er ikke DWM-kontroller.</p>',
                    table(['Kontroll','Navn','Status fra Arkade 5','Feilforekomster'],
                    [[r['id'] or '', r['name'] or '', r['status'] or 'Ukjent', display(r['occurrences'])] for r in x['arkade5_import']['controls']]),
                    '<h3>PRONOM – importert filformatstatistikk</h3>',
                    f'<p>Formater: {e(x["arkade5_import"]["pronom_rows"] if x["arkade5_import"]["pronom_rows"] is not None else "Ukjent")}; Filforekomster: {display(x["arkade5_import"]["pronom_files"])}. Klassifisering er fra Arkade 5, ikke depotgodkjenning.</p>',
                    table(['RAF-220301','Filforekomster'],
                    [[k,display(v)] for k,v in x['arkade5_import']['pronom_classes'].items()]),
                    table(['Format-ID','Filtype','Formatversjon','RAF-220301','Antall'],
                    [[r['id'] or '',r['type'] or '',r['version'] or '',r['classification'],display(r['count'])] for r in x['arkade5_import']['pronom_formats']]),
                    '<h3>Registrerte avvik</h3>']
        content += ['<p>Ingen registrerte avvik i denne rapportens avviksliste. Dette er ikke en garanti for feilfrihet.</p>' if not x['deviations'] else '<ul>'+''.join(f'<li>{e(d)}</li>' for d in x['deviations'])+'</ul>',
                    f'<p class="muted">Kilde: {e(x["source"])}</p>','</section>']
    content.append('</body></html>')
    return '\n'.join(content)


def main(argv=None):
    parser=argparse.ArgumentParser(description='DWM Noark 5: samlet oversikt over valgte rapportjobber')
    parser.add_argument('--source',type=Path,required=True,help='Arbeidsrot eller depot_validation_report.json')
    parser.add_argument('--output',type=Path,required=True,help='Ny/eksisterende mappe for rapporter')
    parser.add_argument('--select',nargs='*',help='Jobb-IDer, f.eks. JOB-001 JOB-002; utelatt = alle oppdagede')
    parser.add_argument('--joblist',type=Path,help='Eksisterende .n5jobs med jobber fordelt på flere mapper')
    parser.add_argument('--prefix',default='',help='Valgfritt prefiks for alle fire rapportfiler')
    parser.add_argument('--quantity-selections',type=Path,help='JSON med eksplisitte, kildekontrollerte rapportvalg')
    parser.add_argument('--report-profile', choices=sorted(REPORT_PROFILES), default='detaljert', help='Oversikt, standard eller detaljert')
    parser.add_argument('--report-sections', help='Kommaseparerte rapportseksjoner; overstyrer profilens seksjonsvalg')
    parser.add_argument('--list',action='store_true',help='Vis oppdagede jobber uten rapportgenerering')
    args=parser.parse_args(argv)
    try:
        prefix=args.prefix.strip()
        if prefix and (prefix in {'.','..'} or len(prefix)>100 or any(c not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-.' for c in prefix)):
            raise ValueError('Ugyldig rapportprefiks. Bruk bare bokstaver A-Z, tall, bindestrek, understrek og punktum (maks 100 tegn).')
        basename=(prefix + '_' if prefix else '')+'noark5-uttrekksoversikt'
        progress(f'Starter: {args.source} | Jobbvalg: '+(', '.join(args.select) if args.select else 'ALLE'))
        configured_jobs = []
        if args.joblist:
            data=json.loads(args.joblist.read_text(encoding='utf-8-sig'))
            configured_jobs=[j for j in data.get('jobs',[]) if isinstance(j,dict)]
            if not configured_jobs: raise ValueError('Jobblisten inneholder ingen jobber')
            selected=set(args.select or [j.get('job_id') for j in configured_jobs])
            configured_jobs=[j for j in configured_jobs if j.get('job_id') in selected]
            paths=[]
            for j in configured_jobs:
                root=j.get('source_root') or j.get('source_extraction') or j.get('source_unzipped')
                if not root:
                    progress(f'Mangler kilde for {j.get("job_id")}')
                    continue
                source_path=Path(root)
                # Do not crawl archive files; probe only the known depot-report directories.
                work=j.get('work_operations')
                candidates=[source_path]
                if work: candidates.insert(0,Path(work))
                hits=set()
                for candidate in candidates:
                    if candidate.is_dir(): hits.update(locate_reports(candidate))
                for report in sorted(hits):
                    if identity(report,{})==j.get('job_id'): paths.append(report)
        else:
            paths=locate_reports(args.source)
        parsed=[]
        for n, path in enumerate(paths, 1):
            progress(f'Leser rapport {n}/{len(paths)} | {path.parent.name}')
            parsed.append(extract(path))
        items=choose_latest_per_job(parsed)
        missing_jobs=[]
        if args.joblist:
            for j in configured_jobs:
                jid=j.get('job_id') or 'Ukjent jobb'
                root=j.get('source_root') or j.get('source_extraction') or j.get('source_unzipped') or ''
                matching=[x for x in items if x['job']==jid and (not root or Path(root).name.casefold() in x['extraction'].casefold())]
                if matching:
                    # Do not merge unrelated extracts with the same JOB-ID.
                    chosen=max(matching,key=lambda x: Path(x['source']).stat().st_mtime)
                    items=[x for x in items if x['job']!=jid or x is chosen]
                    chosen['job_name']=j.get('name') or Path(root).name
                else:
                    missing_jobs.append({'job':jid,'name':j.get('name') or Path(root).name,
                        'extraction':str(root),'status':'MANGLER DEPOTRAPPORT',
                        'go_assessment':{'status':'AVKLARING','reasons':['Ingen depotrapport tilgjengelig']}})
        if args.list:
            for x in items:print(x['job'],'|',x['name'],'|',x['metrics']['archive_part_count'],'arkivdeler |',x['source'])
            return 0
        if args.select and not args.joblist:
            wanted=set(args.select)
            found={i['job'] for i in items}
            missing=wanted-found
            if missing:raise ValueError('Ukjente jobb-ID-er: '+', '.join(sorted(missing)))
            items=[i for i in items if i['job'] in wanted]
        if not items and not missing_jobs: raise ValueError('Ingen DWM depot_validation_report.json funnet for valget')
        selection_count = 0
        if args.quantity_selections:
            selection_data = json.loads(args.quantity_selections.read_text(encoding='utf-8-sig'))
            selection_count = apply_explicit_quantity_choices(items, selection_data)
            progress(f'Eksplisitte mengdevalg kontrollert: {selection_count} (kun rapportvisning)')
        for item in items:
            item['report_metrics'] = build_report_metrics(item)
        progress(f'Valgte jobber: {len(items)} | Oppretter rapportmappe: {args.output}')
        args.output.mkdir(parents=True,exist_ok=True)
        generated=datetime.now(timezone.utc).isoformat(timespec='seconds')
        # Core machine-readable exports must not depend on PDF/Edge availability.
        html_path = args.output / (basename+'.html')
        json_path = args.output / (basename+'.json')
        csv_path = args.output / (basename+'.csv')
        pdf_path = args.output / (basename+'.pdf')
        sections = selected_report_sections(args.report_profile, args.report_sections.split(',') if args.report_sections is not None and args.report_sections else ([] if args.report_sections == '' else None))
        html_content=filter_report_html(render(items, generated), args.report_profile, sections)
        if missing_jobs:
            missing_rows=''.join('<tr><td>'+e(j['job'])+'</td><td>'+e(j['name'])+'</td><td>'+e(j['extraction'])+'</td><td>AVKLARING – mangler depotrapport</td></tr>' for j in missing_jobs)
            html_content=html_content.replace('</body></html>', '<h2>Jobber uten depotrapport</h2><table><tr><th>Jobb</th><th>Uttrekk</th><th>Kilde</th><th>Kontrollgrunnlag</th></tr>'+missing_rows+'</table></body></html>')
        html_path.write_text(html_content, encoding='utf-8')
        progress(f'HTML klar: {html_path.name}')
        json_path.write_text(json.dumps({'generated':generated,'items':items,'coverage':coverage_rows(items),'missing_jobs':missing_jobs,'quantity_selection_count':selection_count,'report_presentation':{'profile':args.report_profile,'sections':sorted(sections),'format':'html/pdf; json/csv full evidence'}},ensure_ascii=False,indent=2),encoding='utf-8')
        progress(f'JSON klar: {json_path.name}')
        with csv_path.open('w',newline='',encoding='utf-8-sig') as f:
            w=csv.writer(f,delimiter=';');w.writerow(['Jobb','Uttrekk','Rapport']+[label for _,label in METRICS]+[label+' – kilde' for _,label in METRICS]+['Teknisk status','Avvik','Depotvurdering','KDRS-evidens','GO-vurdering'])
            for x in items:w.writerow([x['job'],Path(x['extraction']).name,x['name']]+[x['report_metrics'][key]['value'] if x['report_metrics'][key]['value'] is not None else '' for key,_ in METRICS]+[x['report_metrics'][key]['source'] for key,_ in METRICS]+[x['technical_status'],x['deviation_count'],x['assessment_status'],x['external_evidence']['status'],x['go_assessment']['status']])
            for j in missing_jobs:w.writerow([j['job'],j['name'],'Ingen depotrapport']+['']*(len(METRICS)*2)+['Mangler','','','','AVKLARING'])
        progress(f'CSV klar: {csv_path.name}')
        # Remove a previous PDF before attempting regeneration: stale files must
        # never be mistaken for this run's PDF output.
        pdf_path.unlink(missing_ok=True)
        try:
            try:
                from tools.report_outputs import html_to_pdf
            except ModuleNotFoundError:
                from report_outputs import html_to_pdf
            html_to_pdf(html_path, pdf_path)
            progress(f'PDF klar: {pdf_path.name}')
        except (OSError, ValueError, RuntimeError) as pdf_error:
            pdf_path.unlink(missing_ok=True)
            print(f'[ADVARSEL] PDF ikke opprettet: {pdf_error}', flush=True)
            print('[STATUS] HTML, JSON og CSV er ferdige og kan brukes.', flush=True)
        print(f'OK: {len(items)} rapport(er). Resultat: {args.output.resolve()}')
        return 0
    except (OSError,ValueError,RuntimeError,json.JSONDecodeError) as exc:
        print('FEIL:',exc,file=sys.stderr);return 2

if __name__=='__main__':raise SystemExit(main())
