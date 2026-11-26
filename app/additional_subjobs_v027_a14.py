"""Explicit post-completion individual runs without rewriting the parent workflow.

An already-finished job keeps its original operation_ids/cursor/status. Newly
admitted operations are recorded in Work job metadata, and their actual runs
use the established Work run logs and A39JobRunner.run_operation().
"""
from __future__ import annotations

from copy import copy, deepcopy
from datetime import datetime, timezone
from pathlib import Path

from app.application_api import DwmApiError
from app.run_log_history_v018_a8 import RunLogStore
from app.workflow_dependencies_v022_a7 import (
    BY_ID, BY_NUMBER, dependency_label, validate_dependencies,
)
from noark5_workflow.core.job import JobStatus

EXTRA_KEY = 'dwm_a14_additional_operations'
SIEGFRIED = 'siegfried_pronom_identification'
FORBIDDEN = frozenset({'dias_package'})


def additional_ids(job) -> tuple[str, ...]:
    """Safe, backward-compatible read of the explicit supplemental registry."""
    data = getattr(job, 'operation_params', {}).get(EXTRA_KEY, {})
    ids = data.get('operation_ids', ()) if isinstance(data, dict) else ()
    if not isinstance(ids, (list, tuple)) or not all(isinstance(x, str) for x in ids):
        return ()
    return tuple(dict.fromkeys(ids))


def operation_label(operation_id: str) -> str:
    return f'{dependency_label(operation_id)} {operation_id}'


def extended_workflow(job, operation_id: str, known: dict | None = None) -> tuple[str, ...]:
    """Build a validation-only sequence; NEVER assign this to the saved job.

    Insert technical operations ahead of postprocessing, otherwise respect
    A-number ordering of derived processing. AIP creation is never an ad-hoc
    operation. Existing workflow ids and historical cursor remain untouched.
    """
    op = str(operation_id or '').strip()
    ids = list(job.workflow_ids or ())
    if not op or op in FORBIDDEN:
        raise DwmApiError('Valgt deljobb kan ikke brukes som tilleggskjøring.')
    if known is not None and op not in known:
        raise DwmApiError('Deljobben finnes ikke i DWM-registeret: ' + op)
    if op in ids:
        return tuple(ids)
    if not ids:
        raise DwmApiError('Jobben har ingen registrert arbeidsflyt.')
    if op not in BY_ID:
        raise DwmApiError('Tilleggskjøring støttes bare for kjente Noark 5-deljobber.')
    number = BY_ID[op].number
    insertion = next((i for i, previous in enumerate(ids)
                      if previous in FORBIDDEN or
                      (previous in BY_ID and BY_ID[previous].number > number)), len(ids))
    ids.insert(insertion, op)
    problems = validate_dependencies(ids)
    if problems:
        raise DwmApiError('Deljobben kan ikke legges til her: ' + '; '.join(problems))
    # A selective run cannot pretend to have executed mandatory predecessors.
    # Job.next_operation_index is the canonical completed prefix, not 100% of
    # the newly synthesized view.
    completed = set(job.workflow_ids[:max(0, min(int(job.next_operation_index or 0),
                                                   len(job.workflow_ids)))])
    spec = BY_ID[op]
    required = set()
    for number in (*spec.follows, *spec.required):
        other = BY_NUMBER[number].operation_id
        if other in ids and other != op:
            required.add(other)
    missing = sorted(required - completed)
    if missing:
        raise DwmApiError('Kjør forutgående deljobber først: ' + ', '.join(missing))
    return tuple(ids)


def inspect_additional_subjob(api, job_id: str, operation_id: str):
    """Read-only preflight with the real Work identity and a synthetic plan."""
    with api._guard:
        api._assert_idle()
        job = api._require_job(job_id)
        if job.status in (JobStatus.RUNNING, JobStatus.WAITING):
            raise DwmApiError('Avslutt hovedkjøringen eller kontrollpunktet først.')
        if operation_id not in job.workflow_ids:
            extended = extended_workflow(job, operation_id, api._registry_catalog())
            temporary = copy(job)
            temporary.workflow_ids = list(extended)
            return api._inspect_job(temporary, operation_id=operation_id)
    # The canonical API acquires a non-reentrant Lock itself.
    return api.preflight_subjob(job_id, operation_id)


def add_additional_subjob(api, job_id: str, operation_id: str) -> bool:
    """Persist an additional operation *without* calling set_workflow()."""
    with api._guard:
        api._assert_idle()
        if api.workspace().job_list_path is None:
            raise DwmApiError('Lagre jobblisten før du legger til en deljobb.')
        job = api._require_job(job_id)
        if operation_id in job.workflow_ids:
            return False
        extended_workflow(job, operation_id, api._registry_catalog())
        if job_id not in api._work_references:
            raise DwmApiError('Jobben mangler varig Work-identitet; kontroller Work først.')
        if job_id in getattr(api, '_unavailable_work_ids', set()):
            raise DwmApiError('Work er frakoblet. Tilleggskjøring er blokkert.')
        before = deepcopy(job.operation_params.get(EXTRA_KEY))
        ids = list(additional_ids(job))
        if operation_id in ids:
            return False
        ids.append(operation_id)
        job.set_operation_params(EXTRA_KEY, {
            'operation_ids': ids,
            'last_modified_utc': datetime.now(timezone.utc).isoformat(timespec='seconds'),
        })
        try:
            # Work is the authority; save its definition while guarded.
            api._persist_work_event(job, 'subjob.additional_registered', operation_id)
            api._dirty = True
        except Exception:
            if before is None:
                job.operation_params.pop(EXTRA_KEY, None)
            else:
                job.operation_params[EXTRA_KEY] = before
            raise
    # save_job_list() owns the same *non-reentrant* API Lock, so do it after
    # leaving our guard. Do not call it inside the lock.
    try:
        api.save_job_list()
    except Exception:
        with api._guard:
            if before is None:
                job.operation_params.pop(EXTRA_KEY, None)
            else:
                job.operation_params[EXTRA_KEY] = before
            # Work and joblist must not silently disagree after a failed save.
            api._persist_work_event(job, 'subjob.additional_rollback', operation_id)
        raise
    return True


def run_additional_subjob(api, job_id: str, operation_id: str, *,
                          acknowledge_warnings: bool = False) -> bool:
    """Run a recorded supplemental operation with durable subjob logs.

    The synthetic workflow lives on a shallow copy of Job; the authoritative
    parent is never given a new cursor, status or workflow, even on failures.
    """
    # Refuse unregistered additions before probing external tools or Work.
    initial = api._require_job(job_id)
    if operation_id in initial.workflow_ids or operation_id not in additional_ids(initial):
        raise DwmApiError('Deljobben må først registreres som tilleggskjøring.')
    if operation_id == SIEGFRIED:
        from app.siegfried_tool_v0111_a3 import inspect_siegfried
        tool = inspect_siegfried(str(api.settings.get('sf_executable') or ''))
        if not tool.ok:
            raise DwmApiError('Siegfried er ikke klar: ' + tool.message)
    report = inspect_additional_subjob(api, job_id, operation_id)
    if report.errors:
        raise DwmApiError('Deljobb blokkert: ' + '; '.join(issue.message for issue in report.errors))
    if report.actions:
        raise DwmApiError('Work må klargjøres gjennom ordinær Work-kontroll før kjøring.')
    if report.warnings and not acknowledge_warnings:
        raise DwmApiError('Advarsler krever uttrykkelig godkjenning før kjøring.')

    with api._guard:
        api._assert_idle()
        if not api.workspace().job_list_path:
            raise DwmApiError('Lagre jobblisten før deljobben kjøres.')
        original = api._require_job(job_id)
        if operation_id in original.workflow_ids:
            raise DwmApiError('Bruk ordinær Kjør deljobb på nytt for en eksisterende deljobb.')
        if operation_id not in additional_ids(original):
            raise DwmApiError('Tilleggsdeljobben må først registreres og lagres.')
        plan = extended_workflow(original, operation_id, api._registry_catalog())
        issues = api.check_storage()
        if issues:
            raise DwmApiError('Lagringskontroll feilet: ' + '; '.join(issues))
        job = copy(original)
        # Runtime configuration is a snapshot, not shared mutable parent state.
        job.operation_params = deepcopy(original.operation_params)
        job.log_entries = list(original.log_entries)
        job.workflow_ids = list(plan)
        # The original cursor is never changed; synthetic completion is ONLY
        # a runner compatibility view after separate prerequisite checking.
        job.next_operation_index = len(plan)
        job.status = JobStatus.OK
        job.progress = 1.0
        job.checkpoint_after = []
        view = next((v for v in api.workspace().jobs if v.job_id == job_id), None)
        if view is None or not view.effective_work_operations:
            raise DwmApiError('Jobben mangler godkjent Work-område.')
        work = Path(view.effective_work_operations)
        if job_id not in api._work_references or api._work_references[job_id].parent.resolve() != work.resolve():
            raise DwmApiError('Work har endret identitet. Koble til opprinnelig Work.')
        op_name = api._registry_catalog()[operation_id][0]
        api._running = True
        api._cancel.clear()
        api._active_job_id = job_id
        job._effective_work_operations = work

    writer = None
    api._a8_log_warning = ''
    try:
        writer = RunLogStore(work, job_id).begin(
            job_name=view.name, job_list_path=str(api.workspace().job_list_path),
            run_kind='subjob', operation_id=operation_id, operation_name=op_name,
            job_uid=str(getattr(original, 'job_uid', '') or ''),
        )
        api._a8_run_writer = writer
        job._active_run_id = writer.run_id
        job._active_run_kind = 'subjob'
        api._emit('subjob.started', original, message='Tilleggskjøring ' + operation_label(operation_id))
        def log(message):
            api._emit('subjob.log', original, message=str(message))
        def progress(value, message):
            api._emit('subjob.progress', original, progress=float(value), message=str(message))
        def state(updated):
            api._emit('subjob.state', updated, message=str(updated.message))
        settings = dict(api.settings)
        settings.update({'_current_run_id': writer.run_id,
                         '_current_job_uid': str(getattr(original, 'job_uid', '') or ''),
                         '_current_run_kind': 'subjob'})
        engine = api._runner_factory(settings)
        runner = getattr(engine, 'run_operation', None)
        if not callable(runner):
            raise DwmApiError('Arbeidsmotoren støtter ikke selektiv kjøring.')
        outcome = runner(job, operation_id, progress_cb=progress, log_cb=log,
                         cancelled_cb=api._cancel.is_set, state_cb=state)
        successful = bool(outcome.ok)
        writer.append('TILLEGGSKJØRING RESULTAT: ' + ('OK' if successful else 'FEIL'))
        writer.finish('finished' if successful else 'failed')
        api._emit('subjob.finished', original, message=op_name + (': OK' if successful else ': FEIL'),
                  progress=1.0 if successful else None)
        return successful
    except Exception as exc:
        if writer is not None:
            try:
                writer.append('TILLEGGSKJØRING FEIL: ' + str(exc))
                writer.finish('failed')
            except OSError:
                pass
        api._emit('subjob.error', original, message=str(exc))
        raise
    finally:
        api._a8_run_writer = None
        with api._guard:
            api._running = False
            api._cancel.clear()
