"""Versioned job-local period reviews, separate from unchanged source evidence.

Schema v1 is preserved for existing extraction decisions.  Optional
``archive_part_assessments`` entries add independently assessed archive parts,
keyed by their stable native system-ID rather than title, index or KDRS U2 order.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

SERIES = ('folder_created', 'registration_created', 'journal_date_archive_structure',
          'document_description_created', 'document_object_parent_created')
DOCUMENT_SERIES = ('document_description_created', 'document_object_parent_created')
_STATUSES = {'ikke_vurdert', 'godkjent', 'undersokes'}


def _years(entry):
    span = (entry or {}).get('span') or {}
    try:
        a, b = int(span['first_year']), int(span['last_year'])
        if 1000 <= a <= b <= 9999:
            return a, b
    except (KeyError, ValueError, TypeError):
        pass
    return None


def review_candidate(data):
    recon = (data or {}).get('period_reconciliation') or {}
    observed = recon.get('observed_series') or {}
    series = {key: _years(observed.get(key)) for key in SERIES}
    ranges = [v for v in series.values() if v]
    documents = [series[k] for k in DOCUMENT_SERIES if series[k]]
    reported = (min(x[0] for x in ranges), max(x[1] for x in ranges)) if ranges else None
    doc = (min(x[0] for x in documents), max(x[1] for x in documents)) if documents else None
    inconsistent = bool(doc and any(v and v[1] > doc[1] for k, v in series.items() if k not in DOCUMENT_SERIES))
    declared = recon.get('declared_period') or {}
    try:
        declared_years = (int(declared['start_year']), int(declared['end_year']))
    except (ValueError, TypeError, KeyError):
        declared_years = None
    needs_review = (inconsistent or bool(declared_years and reported != declared_years)) if reported else None
    return {
        'declared_years': list(declared_years) if declared_years else None,
        'observed_years': list(reported) if reported else None,
        'document_years': list(doc) if doc else None,
        'source_years': {k: list(v) if v else None for k, v in series.items()},
        'conflicting_sources': inconsistent,
        'proposed_years': list(doc) if inconsistent else (list(reported) if reported else None),
        'needs_review': needs_review,
        'evaluation_status': ('vurdering_kreves' if needs_review else 'ingen_periodeavvik' if reported
                              else 'kan_ikke_vurderes'),
    }


def assessment_path(job):
    effective = getattr(job, '_effective_work_operations', None)
    base = Path(effective or getattr(job, 'work_operations'))
    if base.name.lower() != 'dwm':
        base = base / 'dwm'
    job_id = str(job.job_id)
    if not job_id or '/' in job_id or '\\' in job_id or job_id in ('.', '..'):
        raise ValueError('Ugyldig jobb-ID')
    return base / 'noark5_reports' / 'period_assessments' / (job_id + '.json')


def load_assessment(job):
    path = assessment_path(job)
    if not path.is_file():
        return None
    value = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(value, dict) or value.get('schema_version') != 1 or value.get('job_id') != str(job.job_id):
        raise ValueError(f'Ukjent periodevurdering: {path}')
    return value


def _normalize_years(years):
    if years is None:
        return None
    if (not isinstance(years, (list, tuple)) or len(years) != 2
            or any(not str(x).isdigit() or not 1000 <= int(x) <= 9999 for x in years)
            or int(years[0]) > int(years[1])):
        raise ValueError('Ugyldige ytterår')
    return [int(x) for x in years]


def _decision(previous, *, status=None, years=None, comment=None):
    new_status = status if status is not None else previous.get('status', 'ikke_vurdert')
    if new_status not in _STATUSES:
        raise ValueError('Ukjent vurderingsstatus')
    selected = _normalize_years(years if years is not None else previous.get('selected_years'))
    if new_status == 'godkjent' and selected is None:
        raise ValueError('Godkjent vurdering må ha ytterår')
    return {'status': new_status, 'selected_years': selected,
            'comment': comment if comment is not None else previous.get('comment', '')}


def _write(job, value):
    path = assessment_path(job)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + '.tmp')
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    tmp.replace(path)
    return path


def save_assessment(job, data, *, status=None, years=None, comment=None):
    """Save whole-extraction review, retaining every per-part assessment."""
    previous = load_assessment(job) or {}
    updated = dict(previous)
    updated.update({'schema_version': 1, 'job_id': str(job.job_id),
                    'updated_at': datetime.now(timezone.utc).isoformat(),
                    'source_report': str((data or {}).get('run_id') or ''),
                    'candidate': review_candidate(data),
                    **_decision(previous, status=status, years=years, comment=comment)})
    return _write(job, updated)


def _part_index(data):
    return {str((p.get('archive_part') or {}).get('system_id')): p
            for p in (data or {}).get('archive_parts') or []
            if (p.get('archive_part') or {}).get('system_id') is not None}


def part_review_candidate(data, system_id):
    """Read the part's own DWM evidence without borrowing the extraction years."""
    key = str(system_id)
    part = _part_index(data).get(key)
    if part is None:
        raise ValueError('Arkivdelen finnes ikke i valgt uttrekksrapport')
    for item in ((data or {}).get('period_reconciliation') or {}).get('archive_parts') or []:
        if str((item.get('archive_part') or {}).get('system_id')) == key:
            obs = _years({'span': item.get('observed_period') or {}})
            return {'dwm_observed_years': list(obs) if obs else None,
                    'dwm_metrics': item.get('metrics') or {},
                    'archive_part': part.get('archive_part') or {},
                    'data_scope': 'archive_part'}
    return {'dwm_observed_years': None, 'dwm_metrics': {},
            'archive_part': part.get('archive_part') or {}, 'data_scope': 'archive_part'}


def load_part_assessment(job, system_id):
    value = load_assessment(job) or {}
    return (value.get('archive_part_assessments') or {}).get(str(system_id))


def save_part_assessment(job, data, system_id, *, status=None, years=None,
                         comment=None, source_note=None):
    """Store one archive-part decision without changing the overall decision.

    A U2 number/title is NOT sufficient to establish a DWM system-ID; the
    operator explicitly selects the native part in the assessment dialog.
    """
    key = str(system_id)
    if not key or key in ('.', '..'):
        raise ValueError('Ugyldig arkivdel-ID')
    candidate = part_review_candidate(data, key)
    previous = load_assessment(job) or {
        'schema_version': 1, 'job_id': str(job.job_id),
        'status': 'ikke_vurdert', 'selected_years': None, 'comment': '',
        'candidate': review_candidate(data),
        'source_report': str((data or {}).get('run_id') or ''),
    }
    parts = dict(previous.get('archive_part_assessments') or {})
    old = parts.get(key) or {}
    entry = {**old, 'system_id': key,
             'title': candidate['archive_part'].get('title') or key,
             'updated_at': datetime.now(timezone.utc).isoformat(),
             'candidate': candidate,
             **_decision(old, status=status, years=years, comment=comment)}
    if source_note is not None:
        entry['source_note'] = str(source_note)
    parts[key] = entry
    result = dict(previous, archive_part_assessments=parts,
                  updated_at=datetime.now(timezone.utc).isoformat())
    return _write(job, result)


def reviewed_years(assessment):
    if assessment and assessment.get('status') == 'godkjent':
        years = assessment.get('selected_years')
        if isinstance(years, list) and len(years) == 2:
            return tuple(years)
    return None
