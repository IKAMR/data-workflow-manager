from __future__ import annotations

from dataclasses import dataclass

from noark5_workflow.core.job import JobStatus
from noark5_workflow.core.result_selection import operation_results


@dataclass(frozen=True)
class WorkflowStatusSpec:
    key: str
    symbol: str
    color: str
    label: str
    tooltip: str


STATUS_SPECS: dict[str, WorkflowStatusSpec] = {
    "ok": WorkflowStatusSpec("ok", "✓", "#2fbf71", "Fullført / OK", "Resultatet er gjeldende og operasjonen er fullført."),
    "not_run": WorkflowStatusSpec("not_run", "–", "#7c8799", "Ingen resultat", "Operasjonen er ikke kjørt ennå, eller har ikke noe gjeldende resultat."),
    "running": WorkflowStatusSpec("running", "◷", "#2388ff", "Kjører", "Operasjonen kjøres nå."),
    "stale": WorkflowStatusSpec("stale", "!", "#f6b91a", "Foreldet", "Resultatet er foreldet av et nyere resultat fra en avhengig operasjon. Regenerer for å oppdatere."),
    "failed": WorkflowStatusSpec("failed", "!", "#ff4d4f", "Feil", "Operasjonen feilet ved siste relevante kjøring. Se kjørelogg for detaljer."),
    "review": WorkflowStatusSpec("review", "?", "#9b5de5", "Til vurdering", "Det finnes resultat(er) som må vurderes før de eventuelt blir gjeldende."),
    "skipped": WorkflowStatusSpec("skipped", "Ⅱ", "#7c8799", "Hoppet over", "Operasjonen ble hoppet over i denne kjøringen."),
    "cancelled": WorkflowStatusSpec("cancelled", "…", "#31c7c7", "Avbrutt", "Operasjonen eller kjøringen ble avbrutt."),
    "partial": WorkflowStatusSpec("partial", "↻", "#f6c23e", "Delvis fullført", "Operasjonen er delvis fullført eller venter på videre behandling."),
}


def status_spec(key: str) -> WorkflowStatusSpec:
    return STATUS_SPECS.get(str(key or ""), STATUS_SPECS["not_run"])


def _latest_recorded_result_status(job, operation_id: str) -> str | None:
    """Return ok/failed from the newest persisted raw result, when available.

    Selective re-runs deliberately preserve the workflow cursor and overall
    job status. The per-operation icon must therefore use the newest operation
    result when a failed cursor operation has later been re-run successfully.
    """
    try:
        items = operation_results(job, operation_id)
    except Exception:
        return None
    if not items:
        return None
    return "ok" if bool(items[-1].ok) else "failed"


def operation_status_key(job, operation_id: str, stale_ids=()) -> str:
    """Return a compact visual status for one workflow operation.

    Identity is always operation_id; workflow position is only used to interpret
    the current execution cursor. Stale state has priority because a technically
    completed operation must not look current when its upstream result changed.

    A selective re-run does not move the workflow cursor. If the cursor still
    points at a previously failed operation, the newest persisted raw result for
    that operation is authoritative for the operation icon.
    """
    if operation_id in set(stale_ids or ()):
        return "stale"
    if job is None or operation_id not in list(getattr(job, "workflow_ids", ()) or ()):
        return "not_run"

    workflow_ids = list(job.workflow_ids)
    index = workflow_ids.index(operation_id)
    cursor = max(0, min(int(getattr(job, "next_operation_index", 0) or 0), len(workflow_ids)))
    status = getattr(job, "status", JobStatus.READY)

    if status == JobStatus.OK:
        return "ok"
    if status == JobStatus.FAILED and index == cursor:
        recorded = _latest_recorded_result_status(job, operation_id)
        return recorded or "failed"
    if status == JobStatus.RUNNING and index == cursor:
        return "running"
    if index < cursor:
        return "ok"
    if status == JobStatus.SKIPPED:
        return "skipped"
    if status == JobStatus.WAITING and index == cursor:
        return "partial"
    return "not_run"
