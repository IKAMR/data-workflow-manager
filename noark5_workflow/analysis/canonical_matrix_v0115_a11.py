"""Read-only control matrix with explicit source provenance and no automatic approval.

A draft is not a verified Noark requirement profile. Registered workflow
completion is not a tested outcome. No missing sources are assumed to be zero.
"""
from __future__ import annotations

from collections import Counter
import hashlib
import json
from pathlib import Path
from typing import Any

from noark5_workflow.analysis.canonical_outcomes_v0115_a8 import evaluate_recorded_outcomes
from noark5_workflow.analysis.canonical_control_requirements_v0115_a7 import load_control_profile
from noark5_workflow.analysis.canonical_external_import_v0115_a10 import OUT as EXTERNAL_OUT, MAX_FILE


def _hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def load_external_status(work: str | Path) -> dict[str, Any]:
    """Return accurate per-file status, comparing hashes to the current source.

    Old or unrelated analyses are stale. Missing analysis is not a failed test.
    """
    from noark5_workflow.analysis.canonical_results import _validate_work
    root, identity = _validate_work(Path(work))
    target = root / EXTERNAL_OUT
    if not target.is_file() or target.is_symlink() or target.stat().st_size > MAX_FILE:
        return {'state': 'not_analyzed', 'sources': {}, 'analysis': None}
    try:
        doc = json.loads(target.read_text(encoding='utf-8-sig'))
        if (not isinstance(doc, dict) or doc.get('model_id') != 'noark5.external-analysis.v1'
                or doc.get('extraction_stable_id') != identity['job_uid']
                or not isinstance(doc.get('sources'), list)):
            return {'state': 'stale_or_invalid', 'sources': {}, 'analysis': None}
        canonical = root / 'noark5_evidence' / 'canonical-results.json'
        if (not canonical.is_file() or canonical.is_symlink()
                or doc.get('canonical_reference', {}).get('sha256') != _hash(canonical)):
            return {'state': 'stale_or_invalid', 'sources': {}, 'analysis': None}
        entries = {}
        for item in doc['sources']:
            ref = item['evidence']
            rel = ref['work_relative_path']
            candidate = (root / rel).resolve()
            if not candidate.is_relative_to(root.resolve()) or not candidate.is_file() or candidate.is_symlink():
                entries[rel] = 'source_missing_or_changed'
            elif _hash(candidate) != ref['sha256']:
                entries[rel] = 'source_missing_or_changed'
            else:
                analysis = item.get('analysis', {})
                entries[rel] = ('analyzed' if analysis.get('interpretation') != 'not_parsed'
                                else 'not_parsed')
        return {'state': 'linked', 'sources': entries, 'analysis': doc}
    except (KeyError, TypeError, ValueError, OSError, UnicodeError, json.JSONDecodeError):
        return {'state': 'stale_or_invalid', 'sources': {}, 'analysis': None}


def evaluate_control_matrix(work: str | Path, profile_path: str | Path) -> dict[str, Any]:
    """Combine DWM outcome evidence and selected external analysis, never certify it."""
    profile = load_control_profile(profile_path)
    internal = evaluate_recorded_outcomes(work, profile_path)
    external = load_external_status(work)
    sources = (external['analysis'] or {}).get('sources', [])
    by_area: dict[str, list[dict]] = {'arkade_noark': [], 'arkade_pronom': [], 'siegfried_pronom': []}
    for item in sources:
        ref = item.get('evidence', {})
        rel = ref.get('work_relative_path')
        if external['sources'].get(rel) != 'analyzed':
            continue
        analysis = item.get('analysis', {})
        kind = analysis.get('source_format')
        area = ('arkade_noark' if kind == 'arkade_normalized_v2' else
                'arkade_pronom' if kind == 'arkade_pronom_statistics_v1' else
                'siegfried_pronom' if kind == 'siegfried_json' else None)
        if area:
            by_area[area].append({'source_path': rel, 'source_format': kind, 'analysis': analysis})
    rows = []
    for row in internal['controls']:
        area = row['control_id']
        external_evidence = by_area.get(area, [])
        status_counts = Counter()
        external_test_count = 0
        format_rows = 0
        for item in external_evidence:
            analysis = item['analysis']
            if area == 'arkade_noark':
                status_counts.update({k: v for k, v in analysis.get('reported_status_counts', {}).items()
                                      if isinstance(v, int) and v >= 0})
                external_test_count += analysis.get('record_count', 0)
            elif area == 'arkade_pronom':
                format_rows += analysis.get('format_rows', 0)
        if area == 'arkade_noark' and status_counts.get('error', 0):
            assessment = 'reported_errors_require_review'
        elif external_evidence:
            assessment = 'external_results_registered_unverified'
        else:
            assessment = row['reported_outcome']
        rows.append({'control_id': area, 'title': row['title'],
                     'requirement': row['requirement'], 'condition': row.get('condition'),
                     'condition_evaluated': False if row['requirement'] == 'conditional' else None,
                     'internal_observations': row['observation_count'],
                     'internal_reported_outcome': row['reported_outcome'],
                     'external_sources': [e['source_path'] for e in external_evidence],
                     'external_test_records': external_test_count,
                     'external_status_counts': dict(sorted(status_counts.items())),
                     'pronom_format_rows': format_rows,
                     'assessment': assessment,
                     'test_outcomes_verified': False,
                     'requirement_satisfied': None})
    required = [r for r in rows if r['requirement'] == 'required']
    return {'model_id': 'noark5.control-matrix.v1',
            'profile_id': profile['profile_id'], 'profile_approved': False,
            'work_job_uid': internal['work_job_uid'],
            'external_analysis_state': external['state'], 'controls': rows,
            'summary': {'required_categories': len(required),
                        'required_with_registered_evidence': sum(bool(r['internal_observations'] or r['external_sources']) for r in required),
                        'reported_arkade_errors': sum(r['external_status_counts'].get('error', 0) for r in rows),
                        'unresolved_conditional_categories': [r['control_id'] for r in rows if r['requirement'] == 'conditional'],
                        'all_required_tests_verified': False, 'coverage_complete': None,
                        'archive_creator_acceptance': None, 'depot_approval': None},
            'warning': 'Kontrollprofil er utkast. Kildestatus er ikke faglig verifikasjon eller depotgodkjenning.'}
