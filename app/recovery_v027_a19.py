"""Conservative recovery of completed operations in the same Work area."""
from pathlib import Path
import json
import re
import hashlib
import csv


def arkade_log_has_error(path):
    try:
        text = Path(path).read_text(encoding='utf-8-sig', errors='replace')
    except OSError:
        return False
    return bool(re.search(r'^\s*\[Error\]|finished with errors', text, re.I | re.M))


def recover_completed_stop(job, work):
    # Only recover the exact legacy cancellation boundary, not arbitrary history.
    from noark5_workflow.core.operation_history_a11 import OperationHistoryStore
    i = job.next_operation_index
    if not str(job.message).startswith('Avbrutt under ') or not 0 < i < len(job.workflow_ids)-1:
        return False
    try:
        store = OperationHistoryStore(work, job.job_uid)
        store._assert_owner()
        saved = json.loads((Path(work) / 'job-state.json').read_text(encoding='utf-8-sig'))
        if (saved.get('job_uid') != str(job.job_uid)
                or (saved.get('state') or {}).get('status') != 'Hoppet over'
                or (saved.get('state') or {}).get('next_operation_index') != i
                or not saved.get('last_run_id')):
            return False
        rows = [r for r in store.list_runs() if r.run_kind == 'workflow']
        if not rows:
            return False
        row = rows[0]
        if (row.run_id != saved['last_run_id']
                or row.operation_id != job.workflow_ids[i] or row.execution_ok is not True
                or row.execution_status != 'completed' or not row.work_results
                or not row.result_id or row.warning_count):
            return False
        same_run = [r for r in rows if r.run_id == row.run_id]
        if not any(r.operation_id == job.workflow_ids[i-1] and r.execution_ok is True for r in same_run):
            return False
        links = store.result_links(operation_id=row.operation_id, run_id=row.run_id)
        return set(row.work_results) == {link.relative_path for link in links}
    except (OSError, ValueError, AttributeError, TypeError):
        return False


def verified_pronom_run(plan):
    """Only reuse the latest successful same-source/run output, never launch here."""
    from noark5_workflow.core.work_paths import resolve_dwm_work_root
    try:
        work = resolve_dwm_work_root(plan.work_operations).resolve(strict=True)
        if not re.fullmatch(r'[A-Za-z0-9._-]+', plan.job_id):
            return None
        owner = json.loads((work/'job.json').read_text(encoding='utf-8'))
        owned_job = owner.get('job') or {}
        if (owner.get('file_type') != 'dwm-work-job' or not owner.get('job_uid')
                or owned_job.get('job_id') != plan.job_id
                or Path(owned_job.get('source_extraction') or owned_job.get('source_root') or '').resolve() != Path(plan.source).resolve()):
            return None
        base = work/'external_runs'/'arkade5'/plan.job_id/'pronom_analysis'
        manifests = sorted(base.glob('*/manifest.json'), reverse=True)
        if not manifests:
            return None
        m = manifests[0]
        m.resolve(strict=True).relative_to(work)
        d = json.loads(m.read_text(encoding='utf-8-sig'))
        meta = d['metadata']
        if (d['run_id'] != m.parent.name or d['job_id'] != plan.job_id or d['operation_id'] != 'pronom_analysis'
                or d['tool_id'] != 'arkade5' or d['ok'] is not True or d['exit_code'] != 0
                or d['cancelled'] or d['timed_out'] or d.get('launch_error')
                or meta['tool_version'] != plan.tool_version):
            return None
        for key, expected in [('source_extraction',plan.source),('work_operations',plan.work_operations),('arkade_output_dir',plan.output_dir)]:
            if Path(meta[key]).resolve() != Path(expected).resolve():
                return None
        output = Path(plan.output_dir).resolve(strict=True)
        output.relative_to(work)
        stdout = m.parent/'stdout.txt'
        log = stdout.read_bytes()
        if hashlib.sha256(log).hexdigest() != d['stdout']['sha256_utf8']:
            # Windows newline translation may have been applied by writer.
            if hashlib.sha256(log.replace(b'\r\n', b'\n')).hexdigest() != d['stdout']['sha256_utf8']:
                return None
        stderr = m.parent / 'stderr.txt'
        if (not stderr.is_file() or hashlib.sha256(stderr.read_bytes()).hexdigest() != d['stderr']['sha256_utf8']
                or arkade_log_has_error(stderr) or arkade_log_has_error(stdout)
                or b'successfully finished' not in log.lower()):
            return None
        for name in ('filformatinfo','filformatinfo-statistikk.csv'):
            f = output/name
            if not f.is_file() or f.is_symlink() or f.stat().st_size == 0:
                return None
            f.resolve(strict=True).relative_to(output)
        # Reject empty/malformed statistics rather than treating mere file
        # presence as verified evidence. No changes are made to source files.
        with (output / 'filformatinfo-statistikk.csv').open(encoding='utf-8-sig', newline='') as handle:
            rows = csv.DictReader(handle)
            if not {'Format-ID', 'Antall'}.issubset(rows.fieldnames or ()):
                return None
            count = 0
            for row in rows:
                value = int(row['Antall'])
                if not row['Format-ID'] or value < 0:
                    return None
                count += value
            if count <= 0:
                return None
        return str(d['run_id'])
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        return None
