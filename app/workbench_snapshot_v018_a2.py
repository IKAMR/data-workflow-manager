"""Cheap, GUI-neutral projections for the v0.1.8-a2 laptop workbench.

Never scan Source, Work or Archive when repainting a job list. A network
share can be absent or slow. The authoritative Job objects remain owned by
the established runtime; these are strictly read-only display projections.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class WorkbenchJobRow:
    job_id: str
    name: str
    status: str
    percentage: int
    source: str
    work_operations: str
    active: bool


def _status_text(job: object) -> str:
    status = getattr(job, "status", "")
    return str(getattr(status, "value", status) or "")


def _path_text(value: object) -> str:
    return str(value) if value is not None else "Ikke valgt"


def job_rows(jobs: Iterable[object], active_job_id: str | None) -> tuple[WorkbenchJobRow, ...]:
    """Produce stable display rows without filesystem access or mutations."""
    result: list[WorkbenchJobRow] = []
    for job in jobs:
        job_id = str(getattr(job, "job_id", ""))
        source = getattr(job, "active_extraction_root", None)
        if source is None:
            source = getattr(job, "source_extraction", None) or getattr(job, "source_root", None)
        try:
            progress = float(getattr(job, "progress", 0) or 0)
        except (ValueError, TypeError):
            progress = 0.0
        percentage = round(max(0.0, min(1.0, progress)) * 100)
        result.append(WorkbenchJobRow(
            job_id=job_id,
            name=str(getattr(job, "name", "") or job_id),
            status=_status_text(job),
            percentage=percentage,
            source=_path_text(source),
            work_operations=_path_text(getattr(job, "work_operations", None)),
            active=bool(active_job_id and job_id == active_job_id),
        ))
    return tuple(result)


def elide_path(value: str, max_chars: int = 90) -> str:
    """Middle-elide long paths without losing drive/UNC prefix or leaf name."""
    text = str(value)
    if max_chars < 12:
        raise ValueError("max_chars must be at least 12")
    if len(text) <= max_chars:
        return text
    left = max(8, (max_chars - 3) // 3)
    right = max_chars - left - 3
    return f"{text[:left]}...{text[-right:]}"


def clamp_geometry(
    x: int, y: int, width: int, height: int,
    *, monitor_x: int, monitor_y: int, monitor_width: int, monitor_height: int,
    margin: int = 12,
) -> tuple[int, int, int, int]:
    """Clamp normal geometry to a current monitor work area, not full desktop.

    Monitor coordinates may be negative for a secondary monitor.
    """
    min_x = monitor_x + margin
    min_y = monitor_y + margin
    available_width = max(1, monitor_width - 2 * margin)
    available_height = max(1, monitor_height - 2 * margin)
    width = min(max(1, width), available_width)
    height = min(max(1, height), available_height)
    x = min(max(x, min_x), min_x + available_width - width)
    y = min(max(y, min_y), min_y + available_height - height)
    return x, y, width, height
