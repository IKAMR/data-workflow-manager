"""A22: conservative, persisted continuation after a documented A150 failure.

Use the existing reserved operation_params metadata convention (a15). Only a
specific external-tool failure with a durable raw result can be deferred. The
cursor describes handled positions, NOT successful controls.
"""
from __future__ import annotations

import re
import json
from pathlib import Path, PureWindowsPath

STATE_KEY = 'dwm_a22_deferred_validators'
A150 = 'arkade5_noark5_test'
A160 = 'arkade5_pronom_analysis'
A200 = 'import_arkade5_reports'
A230 = 'audit_noark5_evidence'
PARTIAL_STATUS = 'Fullf\u00f8rt med avvik'
PIPELINE = (
    A160, A200, 'build_noark5_canonical_evidence',
    'analyze_noark5_external_evidence', A230, 'compose_noark5_views',
    'build_noark5_depot_report', 'build_noark5_qa_draft',
)
# Only this class of errors is known to permit a verified partial evidence
# workflow in the current release. Do not swallow generic exceptions, timeouts,
# launch/configuration errors, dependency errors or corrupted evidence.
_ACCESS = re.compile(r"^\s*\[Error\]\s+Access to the path ['\"](.+?)['\"] is denied\.?\s*$", re.I)
_ERROR = re.compile(r'^\s*\[Error\]', re.I)


def access_failure(run, source):
    """Recognize actual Arkade CLI source-file access errors, not log guesses."""
    result = getattr(run, 'result', None)
    plan = getattr(run, 'plan', None)
    if (result is None or plan is None or getattr(run, 'ok', False)
            or not getattr(result, 'ok', False) or result.exit_code != 0
            or result.cancelled or result.timed_out or result.launch_error
            or getattr(run, 'generated_reports', ())):
        return None
    text = '\n'.join((str(result.stdout or ''), str(result.stderr or '')))
    errors = [line for line in text.splitlines() if _ERROR.match(line)]
    if not errors or 'finished with errors' not in text.casefold():
        return None
    # PureWindowsPath also understands slash-separated paths, and works in
    # headless Linux regression tests for recorded Windows CLI messages.
    root = PureWindowsPath(str(source))
    if not root.is_absolute():
        return None
    paths = []
    for line in errors:
        match = _ACCESS.fullmatch(line)
        if not match:
            return None
        path = PureWindowsPath(match.group(1))
        if '..' in path.parts or not path.is_relative_to(root) or path == root:
            return None
        paths.append(str(path))
    run_id = str(getattr(plan, 'run_id', '') or '')
    if not run_id:
        return None
    return {'kind': 'source_access_denied', 'cli_run_id': run_id,
            'paths': list(dict.fromkeys(paths)), 'exit_code': result.exit_code}


def failures(job):
    data = getattr(job, 'operation_params', {}).get(STATE_KEY, {})
    if not isinstance(data, dict):
        raise ValueError('Ugyldig A22-avvikstilstand')
    for key, record in data.items():
        if (key != A150 or key not in job.workflow_ids or not isinstance(record, dict)
                or record.get('kind') != 'source_access_denied'
                or not record.get('cli_run_id') or not record.get('raw_result_id')):
            raise ValueError('Ugyldig A22-avviksoppf\u00f8ring')
    return dict(data)


def can_defer(job, index, result, work):
    if job.workflow_ids[index] != A150 or result.ok or job.has_checkpoint(A150):
        return False
    flow = list(job.workflow_ids)
    if ('run_noark5_xpath_tests_2026' not in flow[:index]
            or any(op not in flow[index + 1:] for op in PIPELINE)
            or 'dias_package' in flow):
        return False
    if [flow.index(op) for op in PIPELINE] != sorted(flow.index(op) for op in PIPELINE):
        return False
    data = result.data or {}
    record = data.get('a22_validator_failure') or {}
    ref = data.get('_result_ref') or {}
    uid = str(getattr(job, 'job_uid', '') or '')
    if (record.get('kind') != 'source_access_denied' or not record.get('cli_run_id')
            or not uid or ref.get('job_uid') != uid or not ref.get('result_id')
            or not ref.get('run_id') or not work):
        return False
    # Old Arkade imports need explicit source selection. Never treat the
    # failed current test as covered by an earlier or partially imported report.
    root = Path(work)
    try:
        owner = json.loads((root / 'job.json').read_text(encoding='utf-8-sig'))
        if (owner.get('file_type') != 'dwm-work-job' or owner.get('job_uid') != uid
                or (owner.get('job') or {}).get('job_id') != job.job_id):
            return False
    except (OSError, ValueError, TypeError, AttributeError):
        return False
    if any((root / 'external_evidence' / 'arkade5').glob('*/manifest.json')):
        return False
    return True


def defer(job, index, result):
    data = result.data
    record = dict(data['a22_validator_failure'])
    ref = data['_result_ref']
    record.update(raw_result_id=ref['result_id'], workflow_run_id=ref['run_id'],
                  message=str(result.message), operation_id=A150)
    job.set_operation_params(STATE_KEY, {**failures(job), A150: record})
    job.next_operation_index = index + 1
    job.progress = job.next_operation_index / len(job.workflow_ids)


def failure_message(job, op_id):
    return str(failures(job).get(op_id, {}).get('message') or '')


def completion_message(job):
    return ('Workflow fullf\u00f8rt med avvik: A150 Arkade Noark 5 mangler. '
            'KS er et ufullstendig utkast, ikke godkjenning.') if failures(job) else 'Workflow fullf\u00f8rt'


def audit_matches(result):
    data = result.data or {}
    return (result.ok and data.get('status') == 'missing_expected_sources'
            and data.get('missing') == ['arkade_noark']
            and data.get('evidence_complete') is False)


def file_snapshot(output):
    """Cheap freshness check for both Arkade PRONOM output files."""
    output = Path(output)
    result = {}
    for name in ('filformatinfo', 'filformatinfo-statistikk.csv'):
        path = output / name
        if path.is_symlink():
            raise ValueError('PRONOM-output er en symbolsk lenke: ' + name)
        try:
            st = path.stat()
            result[name] = (st.st_size, st.st_mtime_ns)
        except FileNotFoundError:
            result[name] = None
    return result


def fresh_output(before, after):
    return all(value is not None and value[0] > 0 and value != before.get(name)
               for name, value in after.items()) and len(after) == 2


def has_pronom_history(plan, settings):
    """Resume may enter a never-started A160. Refuse ambiguous old artifacts."""
    from noark5_workflow.core.work_paths import resolve_dwm_work_root
    root = resolve_dwm_work_root(plan.work_operations, settings=settings)
    if not re.fullmatch(r'[A-Za-z0-9._-]+', plan.job_id):
        return True
    return (any((root / 'external_runs' / 'arkade5' / plan.job_id / 'pronom_analysis').glob('*'))
            or any(value is not None for value in file_snapshot(plan.output_dir).values()))
