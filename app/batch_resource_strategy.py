from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable

from app.resource_strategy import (
    AUTO_STREAMING_FILE_THRESHOLD,
    choose_resource_strategy,
    recommend_worker_count,
)


VALID_BATCH_MODES = {"auto", "sequential", "parallel"}


@dataclass(frozen=True)
class BatchResourceDecision:
    requested_mode: str
    selected_mode: str
    workers: int
    reason: str
    jobs: int
    storage_kinds: tuple[str, ...]
    largest_file_bytes: int | None
    available_memory_bytes: int | None

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _largest_top_level_file(root: Path) -> Path | None:
    """Return the largest immediate file without recursively walking content.

    For archive/extraction roots this gives a cheap signal for large metadata
    sources such as arkivstruktur.xml while avoiding an expensive document tree
    scan before a batch starts.
    """
    try:
        candidates = [p for p in root.iterdir() if p.is_file()]
    except OSError:
        return None

    largest = None
    largest_size = -1
    for path in candidates:
        try:
            size = int(path.stat().st_size)
        except OSError:
            continue
        if size > largest_size:
            largest = path
            largest_size = size
    return largest


def _job_source(job) -> Path | None:
    value = getattr(job, "active_extraction_root", None)
    if value is None:
        value = getattr(job, "source_root", None)
    if value is None:
        return None
    return Path(value)


def recommend_batch_execution(
    jobs: Iterable,
    *,
    environment: dict[str, Any] | None = None,
    requested_mode: str = "auto",
    max_workers: int | None = None,
) -> BatchResourceDecision:
    ordered = list(jobs)
    requested_mode = str(requested_mode or "auto").strip().lower()
    if requested_mode not in VALID_BATCH_MODES:
        raise ValueError(
            f"Ugyldig batchmodus: {requested_mode}. "
            f"Gyldige verdier: {', '.join(sorted(VALID_BATCH_MODES))}"
        )

    if len(ordered) <= 1:
        return BatchResourceDecision(
            requested_mode=requested_mode,
            selected_mode="sequential",
            workers=1,
            reason="batchen har én eller ingen jobber",
            jobs=len(ordered),
            storage_kinds=(),
            largest_file_bytes=None,
            available_memory_bytes=(environment or {}).get("available_memory_bytes"),
        )

    decisions = []
    largest_file = None
    largest_size = None

    for job in ordered:
        source = _job_source(job)
        if source is None:
            continue
        candidate = _largest_top_level_file(source)
        if candidate is None:
            continue

        try:
            size = int(candidate.stat().st_size)
        except OSError:
            size = None

        if size is not None and (largest_size is None or size > largest_size):
            largest_size = size
            largest_file = candidate

        decisions.append(
            choose_resource_strategy(
                candidate,
                requested="auto",
                workload="xml_tree",
                expected_reuse=2,
                environment=environment,
            )
        )

    if requested_mode == "sequential":
        workers = 1
        reason = "sekvensiell batch er eksplisitt valgt"
        selected_mode = "sequential"
    else:
        generic_limit = recommend_worker_count(
            environment=environment,
            max_workers=max_workers,
        )
        decision_limit = min(
            [d.recommended_workers for d in decisions] or [generic_limit]
        )
        workers = max(1, min(generic_limit, decision_limit, len(ordered), 4))

        storage_kinds = {d.storage_kind for d in decisions}
        if storage_kinds & {"network", "removable"}:
            workers = min(workers, 2)

        if largest_size is not None and largest_size >= AUTO_STREAMING_FILE_THRESHOLD:
            workers = min(workers, 2)

        if max_workers is not None and int(max_workers) > 0:
            workers = min(workers, int(max_workers))

        if requested_mode == "parallel":
            selected_mode = "parallel" if workers > 1 else "sequential"
            reason = (
                f"parallell batch valgt; ressursgrensen tillater {workers} worker(e)"
                if workers > 1
                else "parallell batch valgt, men ressursgrensen tillater bare én worker"
            )
        else:
            selected_mode = "parallel" if workers > 1 else "sequential"
            reason = (
                f"auto valgte {workers} parallelle workers"
                if workers > 1
                else "auto valgte sekvensiell kjøring"
            )

    kinds = tuple(sorted({d.storage_kind for d in decisions}))
    return BatchResourceDecision(
        requested_mode=requested_mode,
        selected_mode=selected_mode,
        workers=workers,
        reason=reason,
        jobs=len(ordered),
        storage_kinds=kinds,
        largest_file_bytes=largest_size,
        available_memory_bytes=(environment or {}).get("available_memory_bytes"),
    )
