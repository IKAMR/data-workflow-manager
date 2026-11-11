from __future__ import annotations

import re
from pathlib import Path

from noark5_workflow.core.output_subfolder import render_output_subfolder_rule


_INVALID_COMPONENT = re.compile(r'[<>:"/\\|?*\x00-\x1f]')

# The established job serializer preserves operation_params in .n5jobs and
# Work/job.json.  This reserved DWM key is storage metadata, not an operation.
# Only Basic's explicitly selected, one-job Work folders use this override.
DWM_WORK_LAYOUT_PARAM = '__dwm_work_layout__'


class AppWorkSubfolderError(ValueError):
    pass


def validate_app_work_subfolder(value: str | None) -> str:
    """Validate the optional application-owned level under Work - operations.

    Blank means: use Work - operations directly.
    Non-blank values are deliberately one filesystem component. Job-specific
    nesting remains the responsibility of the job-list output rule.
    """
    value = str(value or '').strip()
    if not value:
        return ''
    if value in {'.', '..'}:
        raise AppWorkSubfolderError('App-undermappen kan ikke være «.» eller «..».')
    if _INVALID_COMPONENT.search(value):
        raise AppWorkSubfolderError(
            'App-undermappen må være ett mappenivå og kan ikke inneholde '
            r'<>:"/\|?* eller kontrolltegn.'
        )
    value = value.rstrip(' .')
    if not value:
        raise AppWorkSubfolderError('App-undermappen kan ikke være tom/ugyldig.')
    return value


def uses_direct_work_folder(job) -> bool:
    """Recognize an explicitly approved Basic Work layout persisted with Job.

    No inference from a folder's name is allowed. This also works after Work
    recovery or .n5jobs reload, since operation_params is serialized.
    """
    params = getattr(job, 'operation_params', None)
    if not isinstance(params, dict):
        return False
    marker = params.get(DWM_WORK_LAYOUT_PARAM)
    return isinstance(marker, dict) and marker.get('mode') == 'selected'


def effective_work_operations(
    base: Path | None,
    app_subfolder: str | None,
    rule: str,
    job,
    position: int,
) -> Path | None:
    """Return Work - operations / optional app-subfolder / job-rule.

    A Basic job with an explicit, persisted direct-Work marker uses exactly
    its selected Work - operations folder. Other jobs remain unchanged.
    """
    if base is None:
        return None
    result = Path(base)
    if uses_direct_work_folder(job):
        return result
    app_component = validate_app_work_subfolder(app_subfolder)
    if app_component:
        result = result / app_component
    job_component = render_output_subfolder_rule(rule, job, position)
    if job_component:
        result = result / job_component
    return result


def validate_layout(
    app_subfolder: str | None,
    rule: str,
    jobs: list,
) -> list[tuple[str, Path | None]]:
    """Validate complete layout and reject collisions between jobs."""
    validate_app_work_subfolder(app_subfolder)
    rendered: list[tuple[str, Path | None]] = []
    seen: dict[str, str] = {}
    for position, job in enumerate(jobs, start=1):
        path = effective_work_operations(
            getattr(job, 'work_operations', None), app_subfolder,
            rule, job, position,
        )
        job_id = str(getattr(job, 'job_id', '') or '')
        rendered.append((job_id, path))
        if path is None:
            continue
        key = str(path).casefold()
        previous = seen.get(key)
        if previous is not None and previous != job_id:
            raise AppWorkSubfolderError(
                'App-undermappe + jobbregel gir samme Work-output for '
                f'{previous} og {job_id}: {path}'
            )
        seen[key] = job_id
    return rendered
