"""One-job Noark 5 starter for the v0.1.11 Basic interface.

Basic selects the *actual* Work directory, not a container to which profile,
app and job-list folder rules are automatically appended. The existing API
still owns preflight, approved provisioning, persistence and execution.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping


# Keep AIP separate; Arkade 5 is opt-in and requires a verified CLI.
BASIC_WORKFLOW_ID = 'noark5_dwm'
BASIC_ARKADE_WORKFLOW_ID = 'noark5_standard_arkade'
BASIC_WORKFLOWS = (BASIC_WORKFLOW_ID, BASIC_ARKADE_WORKFLOW_ID)
BASIC_CUSTOM_WORKFLOW_ID = 'noark5_basic_selected'
BASIC_CONTROLS = ('dwm', 'siegfried', 'arkade_noark5', 'arkade_pronom')
SIEGFRIED_OPERATION_ID = 'siegfried_pronom_identification'
ARKADE_OPERATION_IDS = ('arkade5_noark5_test', 'arkade5_pronom_analysis')


def normalize_basic_controls(controls) -> tuple[str, ...]:
    """Whitelist, de-duplicate and establish an invariant run order."""
    if isinstance(controls, str):
        raise ValueError('Kontrollvalg må være en liste, ikke tekst.')
    chosen = set(controls or ())
    if not chosen or chosen - set(BASIC_CONTROLS):
        raise ValueError('Velg minst én av de fire kontrollene i Enkel modus.')
    return tuple(key for key in BASIC_CONTROLS if key in chosen)


def basic_options_for_operations(operation_ids) -> tuple[str, ...]:
    ids = set(operation_ids)
    chosen = []
    if 'run_noark5_xpath_tests_2026' in ids:
        chosen.append('dwm')
    if SIEGFRIED_OPERATION_ID in ids:
        chosen.append('siegfried')
    if ARKADE_OPERATION_IDS[0] in ids:
        chosen.append('arkade_noark5')
    if ARKADE_OPERATION_IDS[1] in ids:
        chosen.append('arkade_pronom')
    return tuple(chosen)


def basic_operation_ids(controls, *, sequence_loader=None) -> tuple[str, ...]:
    """Compose actual registered DWM operation IDs; no placeholder steps."""
    if sequence_loader is None:
        from app.workflow_sequences import workflow_sequence_by_id
        loader = workflow_sequence_by_id
    else:
        loader = sequence_loader
    selected = normalize_basic_controls(controls)
    if selected == ('dwm',):
        sequence = loader(BASIC_WORKFLOW_ID)
        if sequence is None or sequence.profile_id != 'noark5':
            raise ValueError('DWM-kontrollprofilen finnes ikke.')
        return tuple(sequence.operation_ids)
    if set(selected) == {'dwm', 'arkade_noark5', 'arkade_pronom'}:
        sequence = loader(BASIC_ARKADE_WORKFLOW_ID)
        if sequence is None or sequence.profile_id != 'noark5':
            raise ValueError('Arkade-kontrollprofilen finnes ikke.')
        return tuple(sequence.operation_ids)

    operations: list[str] = []
    if 'dwm' in selected:
        sequence = loader(BASIC_WORKFLOW_ID)
        if sequence is None or sequence.profile_id != 'noark5':
            raise ValueError('DWM-kontrollprofilen finnes ikke.')
        required = (
            'metadata_inventory', 'validate_xml_schema', 'analyse_arkivstruktur',
            'run_noark5_xpath_tests_2026', 'compose_noark5_views',
            'build_noark5_depot_report',
        )
        if any(op not in sequence.operation_ids for op in required):
            raise ValueError('DWM-standard mangler nødvendige kontrolloperasjoner.')
        operations.extend(required[:3])
    if 'arkade_noark5' in selected:
        operations.append(ARKADE_OPERATION_IDS[0])
    if 'arkade_pronom' in selected:
        operations.append(ARKADE_OPERATION_IDS[1])
    if 'siegfried' in selected:
        operations.append(SIEGFRIED_OPERATION_ID)
    if 'dwm' in selected:
        operations.append('run_noark5_xpath_tests_2026')
        if 'arkade_noark5' in selected:
            operations.append('import_arkade5_reports')
        operations.extend(('compose_noark5_views', 'build_noark5_depot_report'))
    return tuple(operations)


@dataclass(frozen=True)
class BasicControlPlan:
    source_extraction: Path
    work_root: Path
    work_operations: Path
    storage_profile_id: str
    operation_ids: tuple[str, ...]
    workflow_id: str = BASIC_WORKFLOW_ID
    controls: tuple[str, ...] = ()


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
                       settings: Mapping[str, Any] | None = None, *,
                       workflow_id: str = BASIC_WORKFLOW_ID,
                       controls=None) -> BasicControlPlan:
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
    if controls is not None:
        selected = normalize_basic_controls(controls)
        operation_ids = basic_operation_ids(selected)
        if any(item == 'dias_package' for item in operation_ids):
            raise ValueError('Basic skal ikke produsere AIP.')
        chosen_id = (BASIC_WORKFLOW_ID if selected == ('dwm',) else
                     BASIC_ARKADE_WORKFLOW_ID if set(selected) ==
                     {'dwm', 'arkade_noark5', 'arkade_pronom'} else
                     BASIC_CUSTOM_WORKFLOW_ID)
        return BasicControlPlan(
            extraction, chosen, chosen, profile, operation_ids,
            chosen_id, selected,
        )
    if workflow_id not in BASIC_WORKFLOWS:
        raise ValueError('Ukjent Basic-kontrollprofil. Velg en av de to definerte profilene.')
    sequence = workflow_sequence_by_id(workflow_id)
    if sequence is None or sequence.profile_id != 'noark5' or not sequence.operation_ids:
        raise ValueError('Noark 5-kontrollprofilen er ikke tilgjengelig. Bruk Avansert modus.')
    if 'dias_package' in sequence.operation_ids:
        raise ValueError('Basic skal ikke produsere AIP.')
    arkade_ids = {'arkade5_noark5_test', 'arkade5_pronom_analysis'}
    selected_ids = set(sequence.operation_ids) & arkade_ids
    if workflow_id == BASIC_WORKFLOW_ID and selected_ids:
        raise ValueError('Standard Basic-kontroll skal ikke kreve Arkade 5 CLI.')
    if workflow_id == BASIC_ARKADE_WORKFLOW_ID and selected_ids != arkade_ids:
        raise ValueError('Utvidet profil skal inneholde baade Arkade 5 Noark 5 og PRONOM.')
    return BasicControlPlan(
        source_extraction=extraction,
        work_root=chosen,
        work_operations=chosen,
        storage_profile_id=profile,
        operation_ids=tuple(sequence.operation_ids),
        workflow_id=workflow_id,
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


def require_basic_arkade_cli(api, plan: BasicControlPlan) -> None:
    """Check the real Arkade5Check contract before changing job-list state.

    DwmWorkbenchAPI.check_arkade5_cli returns Arkade5Check(severity, message,
    version), NOT Arkade5CliStatus(ok). Only severity='ok' is confirmed ready;
    warnings and errors must never be mistaken for an executable test result.
    """
    if not set(plan.operation_ids).intersection(ARKADE_OPERATION_IDS):
        return
    checker = getattr(api, 'check_arkade5_cli', None)
    if not callable(checker):
        raise ValueError('Arkade 5 CLI kan ikke kontrolleres. Velg DWM standard.')
    status = checker()
    if getattr(status, 'severity', None) != 'ok':
        reason = str(getattr(status, 'message', '') or '').strip()
        if not reason:
            reason = 'CLI-kontrollen ble ikke godkjent.'
        raise ValueError(
            'Arkade 5 CLI er ikke klar: ' + reason +
            ' Konfigurer og test CLI i Avansert modus > Setup.'
        )



def require_basic_siegfried(api, plan: BasicControlPlan) -> None:
    """Validate the shared sf.exe before a joblist is replaced or Work written."""
    if SIEGFRIED_OPERATION_ID not in plan.operation_ids:
        return
    from app.siegfried_tool_v0111_a3 import inspect_siegfried
    settings = getattr(api, 'settings', {}) or {}
    configured = str(settings.get('sf_executable') or '')
    status = inspect_siegfried(configured)
    if not status.ok:
        raise ValueError('Siegfried er ikke klar: ' + status.message +
                         ' Kontroller Setup > Eksterne verktøy.')


def select_or_create_basic_job(api, plan: BasicControlPlan) -> tuple[str, bool]:
    """Create one direct-Work job through the API, without touching the disk."""
    require_basic_arkade_cli(api, plan)
    require_basic_siegfried(api, plan)
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
