"""Read-only, GUI-independent presentation of a saved DWM job's progress.

A persisted job cursor is a state snapshot, NOT a recovered historical run log.
This module never scans source folders or creates output files.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SavedProgress:
    title: str
    percent: int
    lines: tuple[str, ...]
    log_text: str


def saved_progress(details) -> SavedProgress:
    """Summarize a JobDetails-like object without changing underlying state."""
    job = details.job
    count = max(0, int(job.operation_count))
    current = max(0, min(int(job.current_operation), count))
    percent = max(0, min(100, round(100 * float(job.progress))))
    status = str(job.status)
    title = f"{job.job_id} · {status} · {current}/{count} operasjoner (lagret jobbstatus)"
    lines = []
    for operation in details.operations:
        state = "OK (lagret)" if operation.completed else "Ikke fullført i lagret jobbstatus"
        lines.append(f"{operation.position:>2}. {operation.name} — {state}")
    if not lines:
        lines.append("Ingen operasjoner er konfigurert.")
    if status == "Klar" and not current:
        heading = "Ingen fullført kjøring er registrert for denne jobben."
    else:
        heading = "Dette er status fra jobblisten, ikke en detaljert historisk kjørelogg."
    message = str(details.message or "").strip()
    snapshot = (
        f"{heading}\n\nJobb: {job.job_id} · {job.name}\n"
        f"Status: {status}\nFremdrift: {percent} % · Operasjoner: {current}/{count}"
        + (f"\nSiste jobbmelding: {message}" if message else "")
        + "\n\nOperasjoner ved siste lagring:\n" + "\n".join(lines)
        + "\n\nDetaljerte meldinger kan bare hentes fra loggfiler som faktisk ble lagret."
    )
    return SavedProgress(title, percent, tuple(lines), snapshot)
