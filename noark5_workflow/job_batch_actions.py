from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from app.storage_layouts import suggest_storage_roles
from noark5_workflow.core.job import Job


_STORAGE_ROLE_ATTRS = (
    "source_root",
    "source_tar",
    "source_unzipped",
    "source_extraction",
    "work_root",
    "work_content",
    "work_operations",
    "archive_root",
)


@dataclass(frozen=True)
class StorageSuggestionJobResult:
    job_id: str
    filled: tuple[str, ...]
    preserved: tuple[str, ...]
    suggested: tuple[str, ...]


@dataclass(frozen=True)
class StorageSuggestionBatchResult:
    selected_jobs: int
    changed_jobs: int
    filled_fields: int
    jobs_without_suggestions: int
    job_results: tuple[StorageSuggestionJobResult, ...]


def fill_missing_storage_suggestions(
    jobs: Iterable[Job],
    *,
    layout_id: str | None,
) -> StorageSuggestionBatchResult:
    """Fill only empty storage roles for a collection of jobs.

    This intentionally reuses the same suggestion engine as the Mapper dialog,
    but batch mode never overwrites an existing role. Conflicts remain untouched
    and can still be reviewed per job in Mapper.
    """
    selected = list(jobs)
    results: list[StorageSuggestionJobResult] = []
    changed_jobs = 0
    filled_fields = 0
    without_suggestions = 0

    for job in selected:
        suggestions = suggest_storage_roles(
            source_root=Path(job.source_root) if job.source_root is not None else None,
            extraction_root=(
                Path(job.source_extraction)
                if job.source_extraction is not None
                else None
            ),
            layout_id=layout_id,
        )
        suggestions = {
            name: Path(value)
            for name, value in suggestions.items()
            if name in _STORAGE_ROLE_ATTRS and value is not None
        }

        if not suggestions:
            without_suggestions += 1

        filled: list[str] = []
        preserved: list[str] = []
        for attr, suggested in suggestions.items():
            current = getattr(job, attr, None)
            if current is None:
                setattr(job, attr, suggested)
                filled.append(attr)
            else:
                preserved.append(attr)

        if filled:
            changed_jobs += 1
            filled_fields += len(filled)

        results.append(
            StorageSuggestionJobResult(
                job_id=job.job_id,
                filled=tuple(filled),
                preserved=tuple(preserved),
                suggested=tuple(suggestions),
            )
        )

    return StorageSuggestionBatchResult(
        selected_jobs=len(selected),
        changed_jobs=changed_jobs,
        filled_fields=filled_fields,
        jobs_without_suggestions=without_suggestions,
        job_results=tuple(results),
    )
