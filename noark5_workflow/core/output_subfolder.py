from __future__ import annotations

import re
from pathlib import Path

_TOKEN_RE = re.compile(r"<([a-zA-Z0-9_]+)>")
_INVALID_COMPONENT = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_ALLOWED_TOKENS = {"jobno", "jobid", "nnn", "name", "source"}


class OutputSubfolderRuleError(ValueError):
    pass


def _safe_component(value: str) -> str:
    value = _INVALID_COMPONENT.sub("_", str(value or "").strip())
    value = value.rstrip(" .")
    if value in {"", ".", ".."}:
        return "_"
    return value


def _job_number(job_id: str) -> str:
    match = re.fullmatch(r"JOB-(\d+)", str(job_id or "").strip(), re.IGNORECASE)
    if not match:
        return _safe_component(job_id)
    return f"{int(match.group(1)):03d}"


def render_output_subfolder_rule(rule: str, job, position: int) -> str:
    """Render one job-list output subfolder rule to one filesystem component."""
    rule = str(rule or "").strip()
    if not rule:
        return ""

    unknown = {m.group(1).lower() for m in _TOKEN_RE.finditer(rule)} - _ALLOWED_TOKENS
    if unknown:
        raise OutputSubfolderRuleError(
            "Ukjent variabel i undermappe-regel: "
            + ", ".join(f"<{name}>" for name in sorted(unknown))
        )

    active = getattr(job, "active_extraction_root", None)
    source_name = getattr(active, "name", "") if active is not None else ""
    values = {
        "jobno": _job_number(getattr(job, "job_id", "")),
        "jobid": _safe_component(getattr(job, "job_id", "")),
        "nnn": f"{int(position):03d}",
        "name": _safe_component(getattr(job, "name", "")),
        "source": _safe_component(source_name),
    }

    rendered = _TOKEN_RE.sub(
        lambda m: values[m.group(1).lower()],
        rule,
    )
    rendered = _safe_component(rendered)
    if rendered == "_":
        raise OutputSubfolderRuleError(
            "Undermappe-regelen gir et tomt eller ugyldig mappenavn."
        )
    return rendered


def effective_work_operations(base: Path | None, rule: str, job, position: int) -> Path | None:
    if base is None:
        return None
    component = render_output_subfolder_rule(rule, job, position)
    return Path(base) / component if component else Path(base)


def validate_output_subfolder_rule(rule: str, jobs: list) -> list[tuple[str, Path | None]]:
    """Validate rule and reject collisions for jobs that share the same Work base."""
    rendered: list[tuple[str, Path | None]] = []
    seen: dict[str, str] = {}

    for position, job in enumerate(jobs, start=1):
        path = effective_work_operations(
            getattr(job, "work_operations", None),
            rule,
            job,
            position,
        )
        rendered.append((str(getattr(job, "job_id", "")), path))
        if path is None:
            continue
        key = str(path).casefold()
        previous = seen.get(key)
        if previous is not None and previous != getattr(job, "job_id", ""):
            raise OutputSubfolderRuleError(
                f"Undermappe-regelen gir samme Work - operations for "
                f"{previous} og {getattr(job, 'job_id', '')}: {path}"
            )
        seen[key] = str(getattr(job, "job_id", ""))

    return rendered
