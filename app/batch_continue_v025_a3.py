"""v0.2.5-a3: read-only plan for continuing and finishing a whole job list.

No execution, Work mutation, checkpoint creation, implicit reset or rerun.
The shared Qt worker/API perform preflight and run the planned job IDs.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Any, Callable, Iterable


@dataclass(frozen=True)
class PlannedJob:
    job_id: str
    name: str
    mode: str  # 'start' or 'continue'
    position: int  # one-based next operation
    total: int

    @property
    def worker_target(self) -> tuple[str, bool, bool]:
        # The existing worker consumes (job_id, allow_rerun, continue_waiting).
        return (self.job_id, False, self.mode == 'continue')

    @property
    def description(self) -> str:
        verb = 'Fortsett' if self.mode == 'continue' else 'Start'
        return f'{self.job_id}: {self.name} – {verb} fra deljobb {self.position}/{self.total}'


@dataclass(frozen=True)
class BlockedJob:
    job_id: str
    reason: str


@dataclass(frozen=True)
class RemainingPlan:
    steps: tuple[PlannedJob, ...]
    completed: tuple[str, ...]
    blocked: tuple[BlockedJob, ...]

    @property
    def runnable(self) -> bool:
        return bool(self.steps) and not self.blocked

    @property
    def targets(self) -> list[tuple[str, bool, bool]]:
        return [step.worker_target for step in self.steps]


def _integer(value: Any) -> int | None:
    try:
        if isinstance(value, bool):
            return None
        number = int(value)
        if number != value and not (isinstance(value, str) and value.strip() == str(number)):
            return None
        return number
    except (ValueError, TypeError, OverflowError):
        return None


def _progress(value: Any) -> float | None:
    try:
        number = float(value)
        return number if isfinite(number) and 0 <= number <= 1 else None
    except (ValueError, TypeError, OverflowError):
        return None


def plan_remaining_jobs(
    jobs: Iterable[Any],
    *,
    details_for: Callable[[str], Any],
    resume_for: Callable[[str], Any],
) -> RemainingPlan:
    """Plan the complete saved list, in order, without mutating any job.

    Finished jobs are always excluded. A fresh READY job starts at operation 1;
    failed, checkpointed and READY/partial jobs must pass the real API resume
    policy. Unknown, disconnected, skipped or contradictory states block the
    entire request rather than silently rerunning, resetting or skipping.
    """
    steps: list[PlannedJob] = []
    done: list[str] = []
    blocked: list[BlockedJob] = []
    seen: set[str] = set()

    for view in jobs:
        job_id = str(getattr(view, 'job_id', '') or '')
        if not job_id or job_id in seen:
            blocked.append(BlockedJob(job_id or '(ukjent jobb)', 'Ugyldig eller duplisert jobb-ID.'))
            continue
        seen.add(job_id)
        name = str(getattr(view, 'name', '') or job_id)
        status = str(getattr(view, 'status', '') or '')
        if status == 'Ferdig':
            done.append(job_id)
            continue
        if status.startswith('Frakoblet'):
            blocked.append(BlockedJob(job_id, 'Work er frakoblet.'))
            continue
        if status not in ('Klar', 'Feil', 'Venter ved kontrollpunkt'):
            blocked.append(BlockedJob(job_id, f'Status {status or "ukjent"} krever manuell vurdering.'))
            continue

        cursor = _integer(getattr(view, 'current_operation', None))
        total = _integer(getattr(view, 'operation_count', None))
        progress = _progress(getattr(view, 'progress', None))
        if (cursor is None or total is None or progress is None
                or total <= 0 or not 0 <= cursor < total):
            blocked.append(BlockedJob(job_id, 'Ugyldig antall deljobber, kjøremarkør eller fremdrift.'))
            continue
        try:
            details = details_for(job_id)
            message = str(getattr(details, 'message', '') or '')
            if status == 'Klar' and cursor == 0 and progress == 0:
                if message.startswith('Konfigurasjon endret'):
                    blocked.append(BlockedJob(job_id, 'Endret konfigurasjon krever eksplisitt ny kjøring.'))
                else:
                    steps.append(PlannedJob(job_id, name, 'start', 1, total))
                continue
            if status == 'Klar' and cursor == 0:
                blocked.append(BlockedJob(job_id, 'Fremdrift og kjøremarkør stemmer ikke overens.'))
                continue

            option = resume_for(job_id)
            expected = {
                'Klar': 'partial_ready',
                'Feil': 'failed_operation',
                'Venter ved kontrollpunkt': 'checkpoint',
            }[status]
            if (not getattr(option, 'allowed', False)
                    or getattr(option, 'mode', '') != expected
                    or _integer(getattr(option, 'index', None)) != cursor
                    or _integer(getattr(option, 'total', None)) != total):
                reason = str(getattr(option, 'reason', '') or 'Ingen verifisert fortsettelsesmulighet.')
                blocked.append(BlockedJob(job_id, reason))
                continue
            steps.append(PlannedJob(job_id, name, 'continue', cursor + 1, total))
        except (KeyError, AttributeError, OSError, RuntimeError, ValueError, TypeError) as exc:
            blocked.append(BlockedJob(job_id, f'Kunne ikke kontrollere jobbstatus: {exc}'))

    return RemainingPlan(tuple(steps), tuple(done), tuple(blocked))


def batch_can_advance(success: bool, status: str | None) -> bool:
    """A successful checkpoint is *not* a completed job; stop the batch."""
    return bool(success) and str(status or '') == 'Ferdig'
