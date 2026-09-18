from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .raw_result_store import RawResultEnvelope, RawResultStore
from .result_review import (
    RawTestResultRef,
    ResultAssessment,
    ResultDisposition,
    ResultReviewLedger,
)


REVIEW_FILENAME = "result-review.jsonl"


@dataclass(frozen=True)
class ResultVersionChoice:
    """One resolved current/candidate pair for a selectively re-run operation."""

    current: RawResultEnvelope | None
    candidate: RawResultEnvelope


def raw_store_path_for_job(job) -> Path | None:
    root = getattr(job, "work_operations", None)
    if root is None:
        return None
    return Path(root) / "wf" / "results" / "raw-results.jsonl"


def review_ledger_path_for_job(job) -> Path | None:
    root = getattr(job, "work_operations", None)
    if root is None:
        return None
    return Path(root) / "wf" / "results" / REVIEW_FILENAME


def operation_results(job, operation_id: str) -> list[RawResultEnvelope]:
    """Return raw results for one stable operation id, oldest first."""
    path = raw_store_path_for_job(job)
    if path is None:
        return []
    wanted_job = str(getattr(job, "job_id", "") or "")
    return [
        item
        for item in RawResultStore(path).results()
        if item.operation_id == operation_id
        and (not item.job_id or not wanted_job or item.job_id == wanted_job)
    ]


def _authoritative_result_ids(job) -> set[str]:
    path = review_ledger_path_for_job(job)
    if path is None:
        return set()
    return {
        item.result.result_id
        for item in ResultReviewLedger(path).authoritative_assessments()
    }


def current_result(job, operation_id: str, *, before_result_id: str = "") -> RawResultEnvelope | None:
    """Resolve current result without rewriting legacy history.

    An explicitly accepted/confirmed result wins. For legacy projects without
    assessments, the latest successful raw result is the implicit current one.
    ``before_result_id`` lets a caller exclude a newly created candidate.
    """
    items = operation_results(job, operation_id)
    if before_result_id:
        items = [item for item in items if item.result_id != before_result_id]
    if not items:
        return None

    authoritative = _authoritative_result_ids(job)
    for item in reversed(items):
        if item.result_id in authoritative:
            return item
    for item in reversed(items):
        if item.ok:
            return item
    return items[-1]


def latest_new_result(
    job,
    operation_id: str,
    *,
    known_result_ids: set[str],
) -> RawResultEnvelope | None:
    """Return the newest raw result added since ``known_result_ids`` was captured."""
    fresh = [
        item
        for item in operation_results(job, operation_id)
        if item.result_id not in known_result_ids
    ]
    return fresh[-1] if fresh else None


def choose_new_as_current(
    job,
    operation_id: str,
    candidate_result_id: str,
    *,
    actor: str = "",
) -> ResultVersionChoice:
    """Promote a candidate and supersede the previous current result append-only."""
    items = operation_results(job, operation_id)
    candidate = next((item for item in items if item.result_id == candidate_result_id), None)
    if candidate is None:
        raise ValueError("Ny resultatversjon finnes ikke i råresultatlageret")

    ledger_path = review_ledger_path_for_job(job)
    if ledger_path is None:
        raise ValueError("Jobben mangler Work - operasjoner for resultatvurdering")
    ledger = ResultReviewLedger(ledger_path)
    previous = current_result(job, operation_id, before_result_id=candidate.result_id)

    if previous is not None and previous.result_id != candidate.result_id:
        ledger.append(
            ResultAssessment(
                previous.ref,
                ResultDisposition.SUPERSEDED,
                reason="Erstattet av selektiv gjenkjøring",
                superseded_by_result_id=candidate.result_id,
            ),
            actor=actor,
        )

    ledger.append(
        ResultAssessment(candidate.ref, ResultDisposition.ACCEPTED),
        actor=actor,
    )
    return ResultVersionChoice(previous, candidate)


def keep_previous_current(
    job,
    operation_id: str,
    candidate_result_id: str,
    *,
    actor: str = "",
) -> ResultVersionChoice:
    """Keep previous current result and retain new candidate for comparison/review."""
    items = operation_results(job, operation_id)
    candidate = next((item for item in items if item.result_id == candidate_result_id), None)
    if candidate is None:
        raise ValueError("Ny resultatversjon finnes ikke i råresultatlageret")

    ledger_path = review_ledger_path_for_job(job)
    if ledger_path is None:
        raise ValueError("Jobben mangler Work - operasjoner for resultatvurdering")
    ledger = ResultReviewLedger(ledger_path)
    previous = current_result(job, operation_id, before_result_id=candidate.result_id)

    # Legacy projects may have no explicit assessment yet. Establish the old
    # result as current only when we now need an explicit version choice.
    if previous is not None and ledger.current_assessment(previous.result_id) is None:
        ledger.append(
            ResultAssessment(previous.ref, ResultDisposition.ACCEPTED),
            actor=actor,
        )

    ledger.append(
        ResultAssessment(
            candidate.ref,
            ResultDisposition.REQUIRES_REVIEW,
            reason="Ny selektiv gjenkjøring beholdt som alternativ resultatversjon",
        ),
        actor=actor,
    )
    return ResultVersionChoice(previous, candidate)
