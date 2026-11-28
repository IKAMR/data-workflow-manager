"""v0.2.4-a2: single-source policy for explicit job resume and reset.

Status, 0-based execution cursor and the verified previous checkpoint decide
which operation will run. This module never modifies a Job or its Work files.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ResumeOption:
    mode: str = ""
    index: int = 0
    total: int = 0
    reason: str = ""

    @property
    def allowed(self) -> bool:
        return self.mode in ("checkpoint", "failed_operation", "partial_ready")

    @property
    def position(self) -> int:
        return self.index + 1 if self.allowed else 0


def resume_option(*, status: str, cursor: int, total: int,
                  previous_checkpoint: bool = False, message: str = "") -> ResumeOption:
    """Choose a mode without confusing retry of a failure with a checkpoint.

    JobRunner.run uses a partial cursor only for READY/WAITING. On FAILED the
    API must explicitly turn the status into READY before invoking run().
    An out-of-bounds cursor must never silently cause a new complete run.
    """
    state = str(getattr(status, 'value', status) or '')
    if state.startswith('Frakoblet'):
        return ResumeOption(reason='Work er frakoblet; koble til riktig arbeidsomr\u00e5de.')
    try:
        i, n = int(cursor), int(total)
    except (TypeError, ValueError, OverflowError):
        return ResumeOption(reason='Ugyldig kj\u00f8remark\u00f8r.')
    if n <= 0 or not (0 <= i < n):
        return ResumeOption(reason='Ingen gyldig neste deljobb \u00e5 fortsette med.')
    if state == 'Venter ved kontrollpunkt':
        if i == 0 or not previous_checkpoint:
            return ResumeOption(reason='Ventestatus er ikke knyttet til et gyldig kontrollpunkt.')
        return ResumeOption('checkpoint', i, n)
    if state in ('Feil', 'Avbrutt') or (state == 'Hoppet over' and str(message or '').startswith('Avbrutt')):
        # A real operation failure leaves its zero-based index pointing at
        # the failed operation. Retry that operation; do not skip it.
        if str(message or '').startswith('Konfigurasjon endret'):
            return ResumeOption(reason='Endret oppsett krever ny kj\u00f8ring.')
        return ResumeOption('failed_operation', i, n)
    if state == 'Klar' and i > 0:
        if str(message or '').startswith('Konfigurasjon endret'):
            return ResumeOption(reason='Endret oppsett krever ny kj\u00f8ring.')
        return ResumeOption('partial_ready', i, n)
    return ResumeOption(reason='Jobben er ikke i en status som kan fortsettes.')


def can_reset(*, status: str, cursor: int, progress: float = 0.0) -> bool:
    """Only enable an explicit reset after the job has an execution state."""
    state = str(getattr(status, 'value', status) or '')
    if state.startswith('Frakoblet') or state == 'Kj\u00f8rer':
        return False
    if state in ('Feil', 'Ferdig', 'Fullf\u00f8rt med avvik', 'Hoppet over', 'Avbrutt', 'Venter ved kontrollpunkt'):
        return True
    try:
        return state == 'Klar' and (int(cursor) > 0 or float(progress) > 0)
    except (ValueError, TypeError, OverflowError):
        return False
