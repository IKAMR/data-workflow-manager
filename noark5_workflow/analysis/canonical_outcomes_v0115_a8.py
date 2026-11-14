"""Read-only, evidence-bounded control outcomes and KS preparation (v0.1.15-a8).

This module does not turn raw workflow completion into validation, and never
claims archive acceptance. A draft control profile cannot authorize approval.
"""
from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any

from noark5_workflow.analysis.canonical_control_requirements_v0115_a7 import evaluate_control_profile
from noark5_workflow.analysis.canonical_control_plan_v0115_a6 import _load
from noark5_workflow.analysis import canonical_results

# Status is recorded by a source, not verified as professional acceptance.
_OK = {'ok', 'passed', 'pass', 'success', 'successful', 'bestatt', 'bestått'}
_FAIL = {'failed', 'fail', 'error', 'feil', 'invalid', 'not_ok'}
_WARN = {'warning', 'warn', 'advarsel'}
_SKIP = {'skipped', 'skip', 'hoppet_over', 'not_run', 'not_applicable'}
_PREFIXES = {
    'xml_schema': ('noark5.xml-schema-validation.v1/',),
    'xpath': ('kdrs.', 'noark5-kdrs-query-'),
    'arkade_noark': ('arkade5_noark5_test',),
    'siegfried_pronom': ('siegfried_pronom_identification',),
    'arkade_pronom': ('arkade5_pronom_analysis',),
    'depot_report': ('build_noark5_depot_report',),
}


def _status(value: Any) -> str:
    normalized = str(value or '').strip().casefold().replace(' ', '_').replace('-', '_')
    if normalized in _OK:
        return 'reported_ok'
    if normalized in _FAIL:
        return 'reported_failure'
    if normalized in _WARN:
        return 'reported_warning'
    if normalized in _SKIP:
        return 'not_executed_or_not_applicable'
    return 'unknown'


def _classify(source: str, statuses: Counter) -> str:
    """Summarize reported outcome, with a strict execution-vs-test boundary."""
    if source == 'dwm_raw':
        return 'execution_only'
    if not statuses:
        return 'not_documented'
    if statuses['reported_failure']:
        return 'reported_failure'
    if statuses['reported_warning']:
        return 'reported_warning'
    if statuses['unknown'] or statuses['not_executed_or_not_applicable']:
        return 'unresolved'
    if statuses['reported_ok']:
        return 'reported_ok_unverified'
    return 'unresolved'


def evaluate_recorded_outcomes(work: str | Path, profile_path: str | Path) -> dict[str, Any]:
    """Join canonical observations to an explicit draft profile, without writing.

    A raw operation's 'ok' means execution only; a master test's 'ok' is
    presented as reported status, not a verified regulatory/depot conclusion.
    """
    base = evaluate_control_profile(work, profile_path)
    root, identity = canonical_results._validate_work(Path(work))
    canonical, _ = _load(root, 'noark5_evidence/canonical-results.json',
                         'noark5.canonical-results.v1')
    if canonical.get('extraction', {}).get('stable_id') != identity['job_uid']:
        raise ValueError('Kanonisk indeks tilhorer annen Work-jobb')
    observations = canonical.get('observations')
    if not isinstance(observations, list):
        raise ValueError('Mangler observasjoner i kanonisk indeks')

    controls = []
    for row in base['controls']:
        matches = [obs for obs in observations if isinstance(obs, dict)
                   and isinstance(obs.get('test_id'), str)
                   and any(obs['test_id'].startswith(prefix) for prefix in _PREFIXES[row['control_id']])]
        by_source: dict[str, Counter] = {}
        for item in matches:
            source = str(item.get('source_kind') or 'unknown')
            by_source.setdefault(source, Counter())[_status(item.get('status'))] += 1
        sources = [{'source_kind': source, 'observation_count': sum(count.values()),
                    'reported_status_counts': dict(sorted(count.items())),
                    'interpretation': _classify(source, count)}
                   for source, count in sorted(by_source.items())]
        interpretations = [item['interpretation'] for item in sources]
        if not interpretations:
            outcome = 'not_documented'
        elif 'reported_failure' in interpretations:
            outcome = 'reported_failure_needs_review'
        elif 'reported_warning' in interpretations or 'unresolved' in interpretations:
            outcome = 'unresolved_needs_review'
        elif 'reported_ok_unverified' in interpretations:
            outcome = 'reported_ok_not_verified'
        else:
            outcome = 'execution_recorded_only'
        controls.append({**row, 'reported_outcome': outcome,
                         'sources': sources, 'professional_review': 'not_verified',
                         'requirement_satisfied': None})

    required = [r for r in controls if r['requirement'] == 'required']
    missing = [r['control_id'] for r in required if r['reported_outcome'] == 'not_documented']
    execution_only = [r['control_id'] for r in required
                      if r['reported_outcome'] == 'execution_recorded_only']
    flagged = [r['control_id'] for r in controls if r['reported_outcome'] in
               ('reported_failure_needs_review', 'unresolved_needs_review')]
    return {
        'model_id': 'noark5.control-outcome-review.v1',
        'profile_id': base['profile_id'], 'profile_approved': False,
        'work_job_uid': base['work_job_uid'],
        'canonical_sha256': base['canonical_sha256'],
        'context_status': base['context_status'],
        'controls': controls,
        'summary': {
            'required_categories': len(required),
            'required_with_registered_evidence': len(required) - len(missing),
            'required_without_registered_evidence': missing,
            'required_execution_only': execution_only,
            'controls_flagged_for_review': flagged,
            'all_required_outcomes_verified': False,
            'requirements_verified': False,
            'archive_creator_acceptance': None,
            'depot_approval': None,
            'preservation_package_ready': None,
        },
        'quality_assurance_preparation': {
            'purpose': 'Utkast til faktagrunnlag for kvalitetssikringsrapport til arkivskaper',
            'content_and_provenance_confirmed': None,
            'archive_creator_response': 'not_requested',
            'open_questions': [
                'Bekreft at arkivinnhold, avgrensning og periode stemmer med leveransen',
                'Bekreft arkivskaper, system, proveniens og eventuelle kjente mangler',
                'Gjennomga rapporterte kontrollfunn og avvik',
                'Dokumenter vurdering av vilkar og betingede tester',
            ],
            'document_status': 'not_approved_draft',
        },
        'warning': ('Rapporterte utfall er ikke faglig verifisert. '
                    'Kontrollprofilen er et utkast; dette er verken arkivskapers aksept '
                    'eller depotgodkjenning.'),
    }
