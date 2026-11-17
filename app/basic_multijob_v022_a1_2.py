"""v0.2.2-a1.2: register Basic jobs in the ONE shared, persisted job list.

Creating/choosing a job never starts a worker. Existing Work evidence is not
adopted just because its path looks suitable. All mutations use the workbench
API, not a Basic-only job object or an independent job-list writer.
"""
from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
from typing import Callable


@dataclass(frozen=True)
class Registration:
    job_id: str
    created: bool
    workflow_changed: bool = False


def same_path(first, second) -> bool:
    if not first or not second:
        return False
    left = os.path.normcase(str(Path(first).resolve(strict=False))).casefold()
    right = os.path.normcase(str(Path(second).resolve(strict=False))).casefold()
    return left == right


def _job_paths_match(job, plan) -> bool:
    return (same_path(getattr(job, 'source_extraction', None), plan.source_extraction)
            and same_path(getattr(job, 'work_operations', None), plan.work_operations)
            and same_path(getattr(job, 'effective_work_operations', None), plan.work_operations))


def register_basic_plan(api, plan, *, selected_job_id: str | None = None,
                        create_new: bool = False, work_approved: bool = False,
                        inspect: Callable | None = None) -> Registration:
    """Register one Basic plan without execution, never replacing other jobs.

    `create_new=False` edits only the *same* currently selected Source/Work
    identity; a different Source/Work requires explicit 'Legg til jobb'.
    `inspect` is injectable for tests; production uses the established Work guard.
    """
    jobs = tuple(api.workspace().jobs)
    # A Work path must not be shared, even if it is still empty on disk. The
    # Work guard alone cannot find a second, not-yet-run job in the job list.
    matching = None
    for item in jobs:
        candidate = api.job_details(item.job_id).job
        assigned_work = (getattr(candidate, 'effective_work_operations', None)
                         or getattr(candidate, 'work_operations', None))
        if same_path(assigned_work, plan.work_operations):
            if not _job_paths_match(candidate, plan):
                raise ValueError('Work er allerede knyttet til ' + item.job_id +
                                 '. Velg en egen Work-mappe for hver jobb.')
            matching = candidate
        # Do not silently adopt an old layout for a duplicate Source.
        if (same_path(getattr(candidate, 'source_extraction', None), plan.source_extraction)
                and same_path(getattr(candidate, 'work_root', None), plan.work_root)
                and not _job_paths_match(candidate, plan)):
            raise ValueError('Source/Work finnes med et annet lagringsoppsett. '
                             'Åpne eksisterende jobb i Avansert modus.')

    if not create_new:
        current = next((item for item in jobs if item.job_id == selected_job_id), None)
        if current is None or not _job_paths_match(api.job_details(current.job_id).job, plan):
            raise ValueError('Source eller Work er endret. Bruk «Legg til uttrekk» '
                             'for en ny jobb; eksisterende jobb overskrives ikke.')
        details = api.job_details(current.job_id)
        current_ops = tuple(operation.operation_id for operation in details.operations)
        changed = current_ops != tuple(plan.operation_ids)
        if changed:
            api.set_workflow(current.job_id, plan.operation_ids)
        api.select_job(current.job_id)
        return Registration(current.job_id, False, changed)

    if matching is not None:
        current_ops = tuple(op.operation_id for op in api.job_details(matching.job_id).operations)
        if current_ops != tuple(plan.operation_ids):
            raise ValueError('Source og Work tilhører allerede ' + matching.job_id +
                             ' med andre kontroller. Velg jobben i jobbvelgeren for å endre.')
        api.select_job(matching.job_id)
        return Registration(matching.job_id, False)

    if inspect is None:
        from app.basic_work_guard_v0113_a3 import inspect_work
        inspect = inspect_work
    observation = inspect(plan.work_operations, plan.source_extraction)
    kind = str(observation.kind)
    count = int(getattr(observation, 'count', 0))
    if kind in ('different_source', 'unknown_job', 'same_job'):
        raise ValueError('Work har annen eller ikke-verifisert jobbidentitet. '
                         'Åpne riktig jobbliste eller velg en annen Work-mappe.')
    if kind not in ('empty', 'unrelated'):
        raise ValueError('Work kan ikke brukes uten ny faglig kontroll: ' + kind)
    if (kind == 'unrelated' or count > 0) and not work_approved:
        raise ValueError('Work inneholder data. Bekreft Work i Work-steget før jobb opprettes.')

    view = api.create_job(source_extraction=str(plan.source_extraction),
                          name=plan.source_extraction.name, profile_id='noark5')
    try:
        api.update_storage(view.job_id, {
            'work_root': str(plan.work_root),
            'work_operations': str(plan.work_operations),
        })
        api.set_workflow(view.job_id, plan.operation_ids)
        api.use_selected_work_directly(view.job_id)
        api.select_job(view.job_id)
    except Exception:
        # Roll back *only* the newly created job. Never reset the shared list.
        try:
            api.remove_job(view.job_id)
        except Exception:
            pass
        raise
    return Registration(view.job_id, True)


def list_job_labels(api) -> tuple[tuple[str, str], ...]:
    """Canonical list order for both GUI modes; no second Basic job registry."""
    return tuple((job.job_id, job.name or str(job.source_extraction or 'Uten navn'))
                 for job in api.workspace().jobs)


def basic_selector_visible(job_count: int, step: str, *, new_draft: bool = False) -> bool:
    """Defer batch controls until the first extraction reaches the run stage.

    The first job is still registered immediately when Source and Work are
    approved. This rule only controls *presentation*, not registration, saving,
    job selection or Advanced mode. A second extraction needs a selector on
    every step so that the operator can return to the previous extraction.
    """
    if job_count <= 0:
        return False
    return job_count > 1 or new_draft or step in ('run', 'overview')


def basic_extraction_status(status: str | None, *, progress: float = 0.0,
                            current_operation: int = 0) -> str:
    """Describe a registered extraction separately from .n5jobs file saving.

    DWM's actual job statuses are Klar, Kjører, Venter ved kontrollpunkt,
    Ferdig, Feil and Hoppet over. A new Klar job with zero progress is not yet
    run; a reset or interrupted previously-used job may be ready to run again.
    """
    raw = str(status or '').strip()
    normalized = raw.casefold()
    if normalized == 'klar':
        if (float(progress or 0) > 0 or int(current_operation or 0) > 0):
            return 'Klar for ny kjøring'
        return 'Registrert, ikke kjørt'
    return {
        'kjører': 'Kontroll pågår',
        'venter ved kontrollpunkt': 'Venter ved kontrollpunkt',
        'ferdig': 'Kontroll fullført',
        'feil': 'Kontroll feilet',
        'hoppet over': 'Kontroll hoppet over',
    }.get(normalized, raw or 'Registrert')
