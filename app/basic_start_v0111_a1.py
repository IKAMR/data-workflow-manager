"""One-job Noark 5 starter for the v0.1.11 Basic interface.

Basic selects the *actual* Work directory, not a container to which profile,
app and job-list folder rules are automatically appended. The existing API
still owns preflight, approved provisioning, persistence and execution.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping


# Explicitly excludes AIP building and optional third-party Arkade CLI.
BASIC_WORKFLOW_ID = 'noark5_dwm'


@dataclass(frozen=True)
class BasicControlPlan:
    source_extraction: Path
    work_root: Path
    work_operations: Path
    storage_profile_id: str
    operation_ids: tuple[str, ...]


def _same_path(first: str | Path | None, second: str | Path | None) -> bool:
    if not first or not second:
        return False
    return Path(first).resolve(strict=False) == Path(second).resolve(strict=False)


def _within(child: Path, parent: Path) -> bool:
    try:
        child.resolve(strict=False).relative_to(parent.resolve(strict=False))
        return True
    except ValueError:
        return False


def ensure_separate_source_and_work(source: Path, operations: Path) -> None:
    """Reject Source/Work overlap, including aliases, before creating a job."""
    if _within(operations, source) or _within(source, operations):
        raise ValueError(
            'Work-operasjoner må ligge utenfor selve uttrekksmappen (Source). '
            'Velg en annen Work-mappe. Originaluttrekket skal ikke endres.'
        )


def prepare_basic_plan(source: str | Path, selected_work: str | Path,
                       settings: Mapping[str, Any] | None = None) -> BasicControlPlan:
    """Read-only Source/Work check. Never add profile or DWM subfolders."""
    from app.job_preflight_v018_a6 import check_extraction_folder
    from app.storage_profiles_v0110_a2 import resolve_storage_profile
    from app.workflow_sequences import workflow_sequence_by_id

    if not str(source or '').strip():
        raise ValueError('Velg mappen som inneholder Noark 5-uttrekket.')
    if not str(selected_work or '').strip():
        raise ValueError('Velg en eksisterende Work-mappe.')
    extraction = Path(source).expanduser()
    issues = check_extraction_folder(extraction, profile_id='noark5')
    if issues:
        raise ValueError('\n'.join(issue.message for issue in issues))
    chosen = Path(selected_work).expanduser()
    if not chosen.is_dir():
        raise ValueError('Work-mappen finnes ikke eller er utilgjengelig: ' + str(chosen))
    ensure_separate_source_and_work(extraction, chosen)
    profile = resolve_storage_profile(settings)
    sequence = workflow_sequence_by_id(BASIC_WORKFLOW_ID)
    if sequence is None or sequence.profile_id != 'noark5' or not sequence.operation_ids:
        raise ValueError('Standard Noark 5-kontroll er ikke tilgjengelig. Bruk Avansert modus.')
    if 'dias_package' in sequence.operation_ids or 'arkade5_noark5_test' in sequence.operation_ids:
        raise ValueError('Basic-kontrollen må ikke produsere AIP eller kreve Arkade CLI.')
    return BasicControlPlan(
        source_extraction=extraction,
        work_root=chosen,
        work_operations=chosen,
        storage_profile_id=profile,
        operation_ids=tuple(sequence.operation_ids),
    )


def existing_basic_job(api, plan: BasicControlPlan) -> str | None:
    """Reuse an identical job; never reinterpret an old nested Work layout."""
    for job in api.workspace().jobs:
        if not _same_path(job.source_extraction, plan.source_extraction):
            continue
        if _same_path(job.work_operations, plan.work_operations) and _same_path(
            getattr(job, 'effective_work_operations', job.work_operations),
            plan.work_operations,
        ):
            details = api.job_details(job.job_id)
            operations = tuple(operation.operation_id for operation in details.operations)
            if operations != plan.operation_ids:
                raise ValueError(
                    'Det finnes allerede en jobb med denne Source- og Work-plasseringen, '
                    'men med en annen arbeidsflyt. Åpne Avansert modus eller velg en annen Work-mappe.'
                )
            return job.job_id
        if _same_path(getattr(job, 'work_root', None), plan.work_root):
            raise ValueError(
                'Dette uttrekket har allerede en jobb med den valgte Work-hovedmappen, '
                'men den bruker et eldre mappeoppsett med undermapper. '
                'Bruk Avansert modus for den eksisterende jobben, eller velg en annen, tom Work-mappe. '
                'Eksisterende resultatfiler flyttes ikke automatisk.'
            )
    return None


def select_or_create_basic_job(api, plan: BasicControlPlan) -> tuple[str, bool]:
    """Create one direct-Work job through the API, without touching the disk."""
    previous = existing_basic_job(api, plan)
    if previous is not None:
        api.select_job(previous)
        return previous, False
    # A new Basic Work folder must be dedicated. Never write job.json/logs
    # into an arbitrary, nonempty folder or a different job's Work root.
    try:
        has_contents = any(plan.work_operations.iterdir())
    except OSError as exc:
        raise ValueError('Kan ikke kontrollere innholdet i Work-mappen: ' + str(exc)) from exc
    if has_contents:
        raise ValueError(
            'Work-mappen er ikke tom. Velg en tom mappe for en ny Basic-jobb, '
            'eller åpne en eksisterende DWM-jobb i Avansert modus.'
        )
    view = api.create_job(
        source_extraction=str(plan.source_extraction),
        name=plan.source_extraction.name,
        profile_id='noark5',
    )
    try:
        api.update_storage(view.job_id, {
            'work_root': str(plan.work_root),
            'work_operations': str(plan.work_operations),
        })
        api.set_workflow(view.job_id, plan.operation_ids)
        # The API stores the per-job marker persistently, without changing the
        # global Setup app_subfolder or job-list output rule.
        api.use_selected_work_directly(view.job_id)
    except Exception:
        try:
            api.remove_job(view.job_id)
        except Exception:
            pass
        raise
    return view.job_id, True
