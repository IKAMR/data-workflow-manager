"""Versioned, job-local period review data, independent of source metadata and reports."""
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path

SERIES = ('folder_created', 'registration_created', 'journal_date_archive_structure',
          'document_description_created', 'document_object_parent_created')
DOCUMENT_SERIES = ('document_description_created', 'document_object_parent_created')


def _years(entry):
    span = (entry or {}).get('span') or {}
    try:
        a, b = int(span['first_year']), int(span['last_year'])
        if 1000 <= a <= b <= 9999:
            return (a, b)
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
    return {
        'declared_years': list(declared_years) if declared_years else None,
        'observed_years': list(reported) if reported else None,
        'document_years': list(doc) if doc else None,
        'source_years': {k: list(v) if v else None for k, v in series.items()},
        'conflicting_sources': inconsistent,
        'proposed_years': list(doc) if inconsistent else (list(reported) if reported else None),
        # None means no observed DWM XPath period, NOT an approved/no-review result.
        'needs_review': (inconsistent or bool(declared_years and reported != declared_years)) if reported else None,
        'evaluation_status': ('vurdering_kreves' if (inconsistent or (reported and declared_years and reported != declared_years))
                              else 'ingen_periodeavvik' if reported else 'kan_ikke_vurderes'),
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


def save_assessment(job, data, *, status=None, years=None, comment=None):
    """Persist evidence; preserve previous decision unless explicitly revised."""
    candidate = review_candidate(data)
    previous = load_assessment(job) or {}
    accepted = {'ikke_vurdert', 'godkjent', 'undersokes'}
    new_status = status if status is not None else previous.get('status', 'ikke_vurdert')
    if new_status not in accepted:
        raise ValueError('Ukjent vurderingsstatus')
    selected = years if years is not None else previous.get('selected_years')
    if selected is not None:
        if len(selected) != 2 or any(not str(x).isdigit() or not 1000 <= int(x) <= 9999 for x in selected) or int(selected[0]) > int(selected[1]):
            raise ValueError('Ugyldige ytterår')
        selected = [int(x) for x in selected]
    if new_status == 'godkjent' and not selected:
        raise ValueError('Godkjent vurdering må ha ytterår')
    value = {
        'schema_version': 1, 'job_id': str(job.job_id),
        'updated_at': datetime.now(timezone.utc).isoformat(),
        'source_report': str((data or {}).get('run_id') or ''),
        'candidate': candidate,
        'status': new_status, 'selected_years': selected,
        'comment': comment if comment is not None else previous.get('comment', ''),
    }
    path = assessment_path(job)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + '.tmp')
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    tmp.replace(path)
    return path


def reviewed_years(assessment):
    if assessment and assessment.get('status') == 'godkjent':
        years = assessment.get('selected_years')
        if isinstance(years, list) and len(years) == 2:
            return tuple(years)
    return None
