from __future__ import annotations

import re
from pathlib import Path

from noark5_workflow.core.output_subfolder import render_output_subfolder_rule


_INVALID_COMPONENT = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


class AppWorkSubfolderError(ValueError):
    pass


def validate_app_work_subfolder(value: str | None) -> str:
    """Validate the optional application-owned level under Work - operations.

    Blank means: use Work - operations directly.
    Non-blank values are deliberately one filesystem component. Job-specific
    nesting remains the responsibility of the job-list output rule.
    """
    value = str(value or "").strip()
    if not value:
        return ""

    if value in {".", ".."}:
        raise AppWorkSubfolderError(
            "App-undermappen kan ikke være «.» eller «..»."
        )
    if _INVALID_COMPONENT.search(value):
        raise AppWorkSubfolderError(
            "App-undermappen må være ett mappenivå og kan ikke inneholde "
            r'<>:"/\|?* eller kontrolltegn.'
        )

    value = value.rstrip(" .")
    if not value:
        raise AppWorkSubfolderError("App-undermappen kan ikke være tom/ugyldig.")
    return value


def effective_work_operations(
    base: Path | None,
    app_subfolder: str | None,
    rule: str,
    job,
    position: int,
) -> Path | None:
    """Return effective Work path:

    Work - operations / app-subfolder / job-rule

    Both optional levels may be blank.
    """
    if base is None:
        return None

    result = Path(base)
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
    """Validate the complete layout and reject collisions between jobs."""
    validate_app_work_subfolder(app_subfolder)

    rendered: list[tuple[str, Path | None]] = []
    seen: dict[str, str] = {}

    for position, job in enumerate(jobs, start=1):
        path = effective_work_operations(
            getattr(job, "work_operations", None),
            app_subfolder,
            rule,
            job,
            position,
        )
        job_id = str(getattr(job, "job_id", "") or "")
        rendered.append((job_id, path))

        if path is None:
            continue
        key = str(path).casefold()
        previous = seen.get(key)
        if previous is not None and previous != job_id:
            raise AppWorkSubfolderError(
                "App-undermappe + jobbregel gir samme Work-output for "
                f"{previous} og {job_id}: {path}"
            )
        seen[key] = job_id

    return rendered
