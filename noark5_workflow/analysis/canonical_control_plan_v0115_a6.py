"""Conservative, evidence-driven Noark 5 control coverage for one Work snapshot.

This is a baseline coverage checklist, NOT a regulatory certification or proof
that every mandatory control has executed. Only a signed/versioned institution
profile can establish final required/conditional controls.
"""
from __future__ import annotations

from collections import Counter
import json
from pathlib import Path
from typing import Any

PROFILE = 'dwm.noark5.baseline-coverage.v1'
MAX_INPUT = 30_000_000

# Baseline categories, deliberately not an assertion of Noark-standard mandatory tests.
CONTROL_CATEGORIES = (
    ('xml_schema', 'XML/XSD', ('noark5.xml-schema-validation.v1/',)),
    ('xpath', 'DWM Noark 5 XPath', ('kdrs.', 'noark5-kdrs-query-')),
    ('arkade_noark', 'Arkade 5 Noark', ('arkade5_noark5_test',)),
    ('siegfried_pronom', 'Siegfried PRONOM', ('siegfried_pronom_identification',)),
    ('arkade_pronom', 'Arkade 5 PRONOM', ('arkade5_pronom_analysis',)),
    ('depot_report', 'DWM depotrapport', ('build_noark5_depot_report',)),
)


def _load(root: Path, rel: str, expected: str) -> tuple[dict, Path]:
    work = root.resolve()
    path = (work / rel).resolve()
    if not path.is_relative_to(work) or not path.is_file():
        raise ValueError('Mangler eller ugyldig Work-fil: ' + rel)
    if path.stat().st_size > MAX_INPUT:
        raise ValueError('For stor Work-fil: ' + rel)
    document = json.loads(path.read_text(encoding='utf-8-sig'))
    if not isinstance(document, dict) or document.get('model_id') != expected:
        raise ValueError('Ukjent format: ' + rel)
    return document, path


def coverage_report(work: str | Path) -> dict[str, Any]:
    """Read only; return presence, recorded status and unverified requirements."""
    from noark5_workflow.analysis.canonical_results import _validate_work
    root, identity = _validate_work(Path(work))
    canonical, canonical_path = _load(root, 'noark5_evidence/canonical-results.json',
                                       'noark5.canonical-results.v1')
    if canonical.get('extraction', {}).get('stable_id') != identity['job_uid']:
        raise ValueError('Kanonisk resultatindeks tilhorer annen Work-jobb')
    observations = canonical.get('observations')
    if not isinstance(observations, list):
        raise ValueError('Mangler liste over observasjoner')
    # A raw workflow completion is evidence of a run, not a validated test outcome.
    items = []
    for key, title, prefixes in CONTROL_CATEGORIES:
        matches = [o for o in observations if isinstance(o, dict)
                   and isinstance(o.get('test_id'), str)
                   and any(o['test_id'].startswith(prefix) for prefix in prefixes)]
        statuses = Counter(str(m.get('status') or 'unknown') for m in matches)
        items.append({'control_id': key, 'title': title,
                      'presence': 'registered' if matches else 'not_documented',
                      'observation_count': len(matches),
                      'recorded_statuses': dict(sorted(statuses.items())),
                      'compliance': 'not_assessed', 'requirement': 'profile_not_selected',
                      'reference_test_ids': sorted(set(m['test_id'] for m in matches))[:100]})
    import hashlib
    canonical_hash = hashlib.sha256(canonical_path.read_bytes()).hexdigest()
    context_rel = 'noark5_evidence/canonical-context.json'
    context_status = 'not_present'
    ctx_path = root / context_rel
    if ctx_path.is_file():
        try:
            ctx, _ = _load(root, context_rel, 'noark5.canonical-context.v1')
            context_status = ('linked' if ctx.get('canonical_reference', {}).get('sha256') == canonical_hash
                              and ctx.get('extraction_stable_id') == identity['job_uid']
                              else 'stale_or_mismatched')
        except (ValueError, OSError, UnicodeError, json.JSONDecodeError):
            context_status = 'unreadable'
    missing = [x['control_id'] for x in items if x['presence'] == 'not_documented']
    return {'model_id': 'noark5.control-coverage.v1', 'profile_id': PROFILE,
            'work_job_uid': identity['job_uid'],
            'canonical_sha256': canonical_hash,
            'context_status': context_status,
            'controls': items,
            'summary': {'categories': len(items), 'categories_with_registered_evidence': len(items) - len(missing),
                        'categories_without_registered_evidence': len(missing),
                        'not_documented': missing,
                        'mandatory_tests_verified': False,
                        'coverage_complete': None, 'archive_approved': False},
            'limitations': [
                'Baseline categories only; mandatory/conditional profile not approved or selected',
                'Registered execution does not imply test passed or full coverage',
                'Only sources present in the canonical snapshot are considered',
                'External report details are not inferred from workflow status',
                'Context hash must match current canonical snapshot',
            ]}
