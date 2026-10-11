"""Bounded, read-only report/evidence discovery for the a10 job chooser.

Never walks archive content; all observations refer to existing DWM output.
"""
from __future__ import annotations

import json
from pathlib import Path


def extraction_root(value):
    """Resolve an existing extraction root from a job's source path."""
    path = Path(value) if value else None
    if not path:
        return None
    for parent in (path, *list(path.parents)[:8]):
        if (parent / 'repository_operations').is_dir():
            return parent
    return path if path.is_dir() else None


def _report_roots(extraction):
    if not extraction:
        return
    dwm = extraction / 'repository_operations' / 'dwm'
    if not dwm.is_dir():
        return
    yield dwm
    # Only one run-directory level below dwm.
    for entry in dwm.iterdir():
        if entry.is_dir() and not entry.is_symlink() and entry.name.lower() not in {
            'noark5_reports', 'external_evidence', 'logs', 'content', 'dokument',
            'tests', 'cache', 'temp', 'sip', 'aip'}:
            yield entry


def report_candidates(extraction, job_id=None):
    found = []
    for base in _report_roots(extraction):
        for relative in ('noark5_reports/depot_validation', 'noark5_reports'):
            location = base / relative
            if not location.is_dir():
                continue
            for candidate in location.glob('*/depot_validation_report.json'):
                if candidate.is_file() and (job_id is None or candidate.parent.name.startswith(job_id + '__')):
                    found.append(candidate)
    return sorted(set(found), key=lambda p: p.parent.name, reverse=True)


def evidence_status(extraction, job_id=None):
    """Only report what can be verified from bounded existing output paths."""
    reports = report_candidates(extraction, job_id)
    result = {'depot': 'Mangler', 'arkade': 'Ikke påvist', 'kdrs': 'Ikke påvist',
              'report_path': str(reports[0]) if reports else '',
              'technical': 'Ukjent', 'assessment': 'Ikke vurdert'}
    if reports:
        result['depot'] = 'Funnet'
        try:
            payload = json.loads(reports[0].read_text(encoding='utf-8-sig'))
            technical = payload.get('technical_validation') or {}
            result['technical'] = str(technical.get('status') or 'Ukjent')
            assessment = payload.get('depot_assessment') or {}
            result['assessment'] = str(assessment.get('status') or 'Ikke vurdert')
        except (OSError, ValueError, TypeError, AttributeError):
            result['depot'] = 'Uleselig'
    for base in _report_roots(extraction):
        arkade = base / 'external_evidence' / 'arkade5'
        if arkade.is_dir():
            for imported in arkade.iterdir():
                if imported.is_dir() and (imported / 'normalized' / 'arkade5_results.json').is_file():
                    result['arkade'] = 'Importert'
                    break
        # KDRS may have raw results or an approved evidence projection.
        if reports and any((report.parent / 'depot-effective-evidence.json').is_file() for report in reports):
            result['kdrs'] = 'Evidensfil'
        for folder in (base / 'external_evidence' / 'kdrs_query', base / 'external_evidence' / 'kdrs'):
            if folder.is_dir():
                result['kdrs'] = 'Tilgjengelig'
    return result
