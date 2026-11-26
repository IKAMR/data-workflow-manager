"""v0.2.7-a15: dependency-aware post-run repairs for an unchanged parent job.

Only saved Work-owned jobs are eligible. Successful independent technical runs
invalidate dependent *previously completed* processing. Every attempted repair
gets its own normal subjob log. This module never rewrites a job's original
workflow, progress, cursor, Source, Work, or historical approvals.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import Callable
import json

from app.application_api import DwmApiError
from app.additional_subjobs_v027_a14 import (
    SIEGFRIED, additional_ids, run_additional_subjob,
)
from app.run_log_history_v018_a8 import RunLogStore
from app.workflow_dependencies_v022_a7 import BY_ID, BY_NUMBER, dependency_label

STATE_KEY = 'dwm_a15_aftercare'
PROCESSING = frozenset(oid for oid, spec in BY_ID.items() if spec.phase == 'processing')
ROOT = 'noark5_evidence'


@dataclass(frozen=True)
class AftercarePlan:
    operation_id: str
    downstream: tuple[str, ...]
    not_configured: tuple[str, ...]
    deferred: tuple[str, ...]

    @property
    def runnable_count(self) -> int:
        return len(self.downstream)


def affected_operations(changed_id: str) -> tuple[str, ...]:
    """Compute transitive data dependencies, not only adjacent operations."""
    if changed_id not in BY_ID or changed_id == 'dias_package':
        raise DwmApiError('Ukjent eller ikke-stottet Noark 5-deljobb.')
    affected = {changed_id}
    while True:
        expanded = affected | {
            oid for oid, spec in BY_ID.items()
            if spec.phase == 'processing'
            and any(BY_NUMBER[n].operation_id in affected
                    for n in (*spec.follows, *spec.required))
        }
        if expanded == affected:
            break
        affected = expanded
    affected.discard(changed_id)
    return tuple(sorted((oid for oid in affected if oid in PROCESSING),
                        key=lambda oid: BY_ID[oid].number))


def aftercare_plan(job, changed_id: str) -> AftercarePlan:
    available = set(job.workflow_ids) | set(additional_ids(job))
    if changed_id not in available:
        raise DwmApiError('Registrer deljobben i jobben forst.')
    impacted = affected_operations(changed_id)
    original = tuple(job.workflow_ids)
    completed = set(original[:max(0, min(int(job.next_operation_index or 0), len(original)))])
    # Do not run an unexecuted downstream operation out of sequence; the
    # unfinished main workflow has that responsibility.
    ready = tuple(oid for oid in impacted if oid in completed)
    deferred = tuple(oid for oid in impacted if oid in available and oid not in completed)
    missing = tuple(oid for oid in impacted if oid not in available)
    # Never invent an operation absent from a historical job or assume it ran.
    return AftercarePlan(changed_id, ready, missing, deferred)


def read_aftercare(job) -> dict:
    raw = getattr(job, 'operation_params', {}).get(STATE_KEY, {})
    if not isinstance(raw, dict):
        return {}
    pending = raw.get('pending', ())
    done = raw.get('done', ())
    if (not isinstance(pending, list) or not isinstance(done, list)
            or any(not isinstance(v, str) or v not in BY_ID for v in pending + done)):
        return {}
    return dict(raw)


def aftercare_summary(job) -> str:
    record = read_aftercare(job)
    status = record.get('status')
    if status == 'current':
        return 'Etterkontroll: evidens og rapporter oppdatert (faglig vurdering gjenstar)'
    if status == 'complete_unverified':
        return 'Etterkontroll kjort; kontroller kildevalg og rapportgrunnlag'
    if status in {'pending', 'running', 'blocked'}:
        pending = len(record.get('pending', []))
        label = {'pending': 'Venter', 'running': 'Oppdateres',
                 'blocked': 'Stoppet / utdaterte rapporter'}[status]
        return f'Etterkontroll: {label} ({pending} etterjobber gjenstar)'
    return ''


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


def _store(api, job_id: str, state: dict, *, message: str = '') -> None:
    """Persist Work authority first, then the .n5jobs index (outside Lock)."""
    with api._guard:
        api._assert_idle()
        if job_id not in api._work_references:
            raise DwmApiError('Jobben mangler autoritativ Work-identitet.')
        if job_id in getattr(api, '_unavailable_work_ids', set()):
            raise DwmApiError('Work er frakoblet.')
        if not api.workspace().job_list_path:
            raise DwmApiError('Lagre jobblisten forst.')
        job = api._require_job(job_id)
        before = job.get_operation_params(STATE_KEY)
        payload = dict(state)
        payload['updated_at_utc'] = _utc()
        job.set_operation_params(STATE_KEY, payload)
        try:
            api._persist_work_event(job, 'aftercare.' + str(state.get('status', 'pending')),
                                    message)
            api._dirty = True
        except Exception:
            if before:
                job.set_operation_params(STATE_KEY, before)
            else:
                job.operation_params.pop(STATE_KEY, None)
            raise
    # The API has a non-reentrant Lock. Never save while holding it.
    # If the index cannot be saved, the Work record remains authoritative.
    api.save_job_list()


def _work(api, job_id: str) -> Path:
    for view in api.workspace().jobs:
        if view.job_id == job_id and view.effective_work_operations:
            folder = Path(view.effective_work_operations)
            ref = api._work_references.get(job_id)
            if (ref is None or ref.parent.resolve(strict=False) !=
                    folder.resolve(strict=False)):
                raise DwmApiError('Work-identiteten stemmer ikke med valgt jobb.')
            return folder
    raise DwmApiError('Work-mappen er ikke tilgjengelig.')


def _runs(work: Path, job_id: str, operation_id: str) -> dict[str, str]:
    return {run.run_id: run.status for run in RunLogStore(work, job_id).list_runs(limit=500)
            if run.run_kind == 'subjob' and run.operation_id == operation_id}


def _read_small_json(path: Path, *, limit: int = 24_000_000) -> dict:
    if path.is_symlink() or not path.is_file() or path.stat().st_size > limit:
        raise DwmApiError('Evidensfil mangler, er for stor eller er en lenke: ' + str(path))
    doc = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(doc, dict):
        raise DwmApiError('Ugyldig evidensformat: ' + path.name)
    return doc


def _safe_work_member(work: Path, rel: str) -> Path:
    member = work / rel
    target = member.resolve(strict=True)
    if not target.is_relative_to(work.resolve(strict=True)) or member.is_symlink():
        raise DwmApiError('Evidensreferansen ligger utenfor Work eller er en lenke.')
    return target


def _canonical_siegfried_source(path: Path) -> dict | None:
    """Stream a potentially huge canonical-results document when needed."""
    if path.is_symlink() or not path.is_file():
        raise DwmApiError('Kanonisk evidens mangler eller er en utrygg lenke.')
    if path.stat().st_size <= 60_000_000:
        doc = _read_small_json(path, limit=60_000_000)
        return (doc.get('a7_evidence_sources') or {}).get('siegfried_pronom')
    try:
        import ijson
    except ImportError as exc:
        raise DwmApiError('Stort Noark 5-resultat krever ijson for trygg streaming.') from exc
    with path.open('rb') as handle:
        return next(ijson.items(handle, 'a7_evidence_sources.siegfried_pronom'), None)


def _sha256_file(path: Path) -> str:
    digest = sha256()
    with path.open('rb') as source:
        for block in iter(lambda: source.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def verify_siegfried_link(work: Path, source_run_id: str) -> dict:
    """A210 is not fresh unless it links the *new* A140 run and its SHA-256."""
    source = _canonical_siegfried_source(work / ROOT / 'canonical-results.json')
    if not isinstance(source, dict) or not source_run_id:
        raise DwmApiError('A210 mangler referanse til ny Siegfried-evidens.')
    manifest_path = _safe_work_member(work, str(source.get('manifest') or ''))
    statistics_path = _safe_work_member(work, str(source.get('file') or ''))
    manifest = _read_small_json(manifest_path)
    if str(manifest.get('run_id') or '') != source_run_id:
        raise DwmApiError('A210 valgte ikke resultatet fra den nye Siegfried-kjoringen.')
    if (_sha256_file(manifest_path) != source.get('manifest_sha256')
            or _sha256_file(statistics_path) != source.get('sha256')):
        raise DwmApiError('A210 refererer Siegfried-evidens med feil SHA-256.')
    return {'run_id': source_run_id, 'manifest': str(source.get('manifest') or '')}


def reconcile_supplemental_audit(work: Path, operation_id: str,
                                 source_run_id: str) -> bool:
    """Repair the legacy A230 'not configured' label after verified A140.

    A230 gets its declared controls from the historic 13-step workflow, which
    correctly remains frozen. After A140 we must also classify its verified
    Work supplement, not mislabel the actual Siegfried source as absent.
    The existing versioning publisher saves earlier audit content.
    """
    if operation_id != SIEGFRIED:
        return False
    verify_siegfried_link(work, source_run_id)
    path = work / ROOT / 'evidence-audit.json'
    audit = _read_small_json(path)
    linked = {row.get('kind') for row in audit.get('verified_references', [])
              if isinstance(row, dict)}
    if 'siegfried_pronom' not in linked:
        raise DwmApiError('A230 bekreftet ikke Siegfried som verifisert kilde.')
    not_configured = list(audit.get('not_configured_source_families') or [])
    missing = list(audit.get('missing_source_families') or [])
    if 'siegfried_pronom' in missing:
        raise DwmApiError('A230 rapporterer Siegfried som manglende evidens.')
    if 'siegfried_pronom' not in not_configured:
        return False
    audit['not_configured_source_families'] = [v for v in not_configured
                                                if v != 'siegfried_pronom']
    existing = list(audit.get('supplemental_source_families') or [])
    audit['supplemental_source_families'] = list(dict.fromkeys(
        existing + ['siegfried_pronom']))
    audit['supplemental_source_run_id'] = source_run_id
    audit['supplemental_source_note'] = (
        'Separat A140-etterkontroll, verifisert mot kanonisk manifest og SHA-256; '
        'opprinnelig arbeidsflyt ble ikke omskrevet.')
    from noark5_workflow.operations.canonical_evidence_v022_a7 import _publish_json
    _publish_json(work, ROOT + '/evidence-audit.json', audit)
    return True


def _preflight(api, job_id: str, operation_id: str,
               approved: set[tuple[str, str]]) -> None:
    from app.additional_subjobs_v027_a14 import inspect_additional_subjob
    report = inspect_additional_subjob(api, job_id, operation_id)
    problems = [i.message for i in report.errors]
    problems.extend('Work-klargjoring nodvendig: ' + a.path for a in report.actions)
    if problems:
        raise DwmApiError(' / '.join(problems))
    unknown = [i.message for i in report.warnings
               if (operation_id, str(i.message)) not in approved]
    if unknown:
        raise DwmApiError('Nye advarsler krever godkjenning: ' + ' / '.join(unknown))


def execute_aftercare(api, job_id: str, changed_id: str, *,
                      update_dependents: bool = True, resume: bool = False,
                      approved_warnings: tuple[tuple[str, str], ...] = (),
                      cancelled: Callable[[], bool] | None = None,
                      progress: Callable[[str, bool, str], None] | None = None) -> bool:
    """Run technical operation then derived operations sequentially.

    Each failure or cancellation leaves durable pending state for a later
    resume. Parent 13/13 remains unchanged. A failed/unfinished parent may be
    repaired selectively but its unexecuted downstream is deferred.
    """
    job = api._require_job(job_id)
    plan = aftercare_plan(job, changed_id)
    if job_id not in api._work_references:
        raise DwmApiError('Jobben mangler varig Work-identitet.')
    approved = set(approved_warnings)
    work = _work(api, job_id)
    stored = read_aftercare(job)
    can_resume = (resume and stored.get('source_operation') == changed_id
                  and stored.get('source_completed') is True
                  and stored.get('status') in ('blocked', 'pending', 'running')
                  and isinstance(stored.get('pending'), list))
    if can_resume:
        record = dict(stored)
        record['status'] = 'running'
        record['error'] = ''
    else:
        record = {
            'source_operation': changed_id, 'source_completed': False,
            'source_run_id': '', 'status': 'pending', 'pending': list(plan.downstream),
            'done': [], 'deferred': list(plan.deferred),
            'not_configured': list(plan.not_configured), 'error': '',
        }
    _store(api, job_id, record, message='Planlagt ' + dependency_label(changed_id))
    try:
        if not can_resume:
            if cancelled and cancelled():
                raise DwmApiError('Avbrutt for start.')
            _preflight(api, job_id, changed_id, approved)
            before = _runs(work, job_id, changed_id)
            if changed_id in job.workflow_ids:
                success = api.run_subjob(
                    job_id, changed_id, allow_rerun=True,
                    acknowledge_warnings=bool(approved),
                )
            else:
                success = run_additional_subjob(
                    api, job_id, changed_id,
                    acknowledge_warnings=bool(approved),
                )
            if not success:
                raise DwmApiError('Teknisk deljobb feilet; etterbehandling ble ikke startet.')
            completed_runs = _runs(work, job_id, changed_id)
            new_runs = [rid for rid, status in completed_runs.items()
                        if rid not in before and status == 'finished']
            if not new_runs:
                raise DwmApiError('Finner ingen varig, vellykket kjorelogg for ny deljobb.')
            record['source_run_id'] = sorted(new_runs)[-1]
            record['source_completed'] = True
            record['status'] = 'pending'
            _store(api, job_id, record, message='Teknisk deljobb fullfort')
            if progress:
                progress(changed_id, True, 'Teknisk resultat er lagret')
        if not update_dependents:
            record['status'] = 'pending' if record['pending'] else 'complete_unverified'
            _store(api, job_id, record, message='Etterbehandling utsatt av bruker')
            return True
        while record['pending']:
            oid = record['pending'][0]
            if cancelled and cancelled():
                raise DwmApiError('Stoppet; etterbehandling kan fortsettes senere.')
            _preflight(api, job_id, oid, approved)
            record['status'] = 'running'
            _store(api, job_id, record, message='Starter ' + dependency_label(oid))
            ok = (api.run_subjob(job_id, oid, allow_rerun=True,
                                 acknowledge_warnings=bool(approved))
                  if oid in api._require_job(job_id).workflow_ids
                  else run_additional_subjob(api, job_id, oid,
                                             acknowledge_warnings=bool(approved)))
            if not ok:
                raise DwmApiError(dependency_label(oid) + ' feilet; resten er utsatt.')
            if oid == 'build_noark5_canonical_evidence' and changed_id == SIEGFRIED:
                verify_siegfried_link(work, record['source_run_id'])
            if oid == 'audit_noark5_evidence' and changed_id == SIEGFRIED:
                reconcile_supplemental_audit(work, changed_id,
                                             record['source_run_id'])
            record['pending'].pop(0)
            if oid not in record['done']:
                record['done'].append(oid)
            _store(api, job_id, record, message=dependency_label(oid) + ' fullfort')
            if progress:
                progress(oid, True, 'Etterjobb fullfort')
        # Do not claim everything is updated if a dependency is unconfigured or
        # a main workflow step was not completed before this selected run.
        if record['deferred'] or record['not_configured']:
            record['status'] = 'complete_unverified'
        else:
            record['status'] = ('current' if changed_id == SIEGFRIED
                                else 'complete_unverified')
        _store(api, job_id, record, message='Etterkontroll avsluttet')
        return True
    except Exception as exc:
        record['status'] = 'blocked'
        record['error'] = str(exc)[:1000]
        try:
            _store(api, job_id, record, message=str(exc)[:300])
        except Exception as storage_exc:
            raise DwmApiError(str(exc) + ' | Etterkontrollstatus kunne ikke lagres: '
                              + str(storage_exc)) from exc
        if progress:
            progress((record.get('pending') or [changed_id])[0], False, str(exc))
        return False
