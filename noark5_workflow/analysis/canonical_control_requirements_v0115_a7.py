"""Versioned, explicitly selected control-plan DRAFT evaluation.

An unapproved profile can never prove compliance, readiness or depot acceptance.
The only input evidence is the existing canonical Work snapshot, read-only.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from noark5_workflow.analysis.canonical_control_plan_v0115_a6 import coverage_report

MODEL_ID = 'noark5.control-profile.v1'
KNOWN_CONTROL_IDS = {'xml_schema', 'xpath', 'arkade_noark', 'siegfried_pronom',
                     'arkade_pronom', 'depot_report'}
MAX_PROFILE_BYTES = 1_000_000


def load_control_profile(path: str | Path) -> dict[str, Any]:
    path = Path(path)
    if not path.is_file() or path.stat().st_size > MAX_PROFILE_BYTES:
        raise ValueError('Kontrollprofil mangler eller er for stor')
    profile = json.loads(path.read_text(encoding='utf-8-sig'))
    if not isinstance(profile, dict) or profile.get('model_id') != MODEL_ID:
        raise ValueError('Ukjent kontrollprofilformat')
    if not isinstance(profile.get('profile_id'), str) or not profile['profile_id'].strip():
        raise ValueError('Kontrollprofil mangler profile_id')
    # a7 deliberately accepts drafts only: no formal approval workflow exists.
    if profile.get('approved') is not False:
        raise ValueError('a7 krever eksplisitt ikke-godkjent utkastprofil')
    rows = profile.get('requirements')
    if not isinstance(rows, list) or not rows:
        raise ValueError('Kontrollprofil har ingen krav')
    seen: set[str] = set()
    for row in rows:
        if not isinstance(row, dict) or row.get('control_id') not in KNOWN_CONTROL_IDS:
            raise ValueError('Kontrollprofil inneholder ukjent kontrollomrade')
        key = row['control_id']
        if key in seen:
            raise ValueError('Duplisert kontrollomrade: ' + key)
        seen.add(key)
        if row.get('requirement') not in ('required', 'conditional', 'optional'):
            raise ValueError('Ugyldig kravtype: ' + key)
        if row['requirement'] == 'conditional' and not row.get('condition'):
            raise ValueError('Betinget kontroll uten beskrevet betingelse: ' + key)
    return profile


def evaluate_control_profile(work: str | Path, profile_path: str | Path) -> dict[str, Any]:
    """Compare coverage to an operator-chosen draft; never certify completion."""
    profile = load_control_profile(profile_path)
    current = coverage_report(work)
    indexed = {row['control_id']: row for row in current['controls']}
    items = []
    for requirement in profile['requirements']:
        control = indexed[requirement['control_id']]
        # 'registered' is a reference to a recorded execution, NOT a passed test.
        observed = control['presence'] == 'registered'
        items.append({
            'control_id': control['control_id'], 'title': control['title'],
            'requirement': requirement['requirement'],
            'condition': requirement.get('condition'),
            'evidence_state': 'registered_unverified' if observed else 'not_documented',
            'observation_count': control['observation_count'],
            'recorded_statuses': control['recorded_statuses'],
            'test_outcomes_verified': False,
            'requirement_satisfied': None,
        })
    required = [r for r in items if r['requirement'] == 'required']
    missing = [r['control_id'] for r in required if r['evidence_state'] == 'not_documented']
    return {
        'model_id': 'noark5.control-plan-evaluation.v1',
        'profile_id': profile['profile_id'],
        'profile_approved': False,
        'work_job_uid': current['work_job_uid'],
        'canonical_sha256': current['canonical_sha256'],
        'context_status': current['context_status'],
        'controls': items,
        'summary': {
            'required_categories': len(required),
            'required_with_registered_evidence': len(required) - len(missing),
            'required_without_registered_evidence': missing,
            'requirements_verified': False,
            'coverage_complete': None,
            'archive_approved': False,
        },
        'warning': 'UTKAST: Registrert evidens beviser ikke kontrollutfall eller fullstendig dekning.',
    }
