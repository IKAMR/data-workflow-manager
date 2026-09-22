from __future__ import annotations

from dataclasses import dataclass

from app.workflow_sequences import workflow_sequence_by_id
from noark5_workflow.core.job import JobStatus


_TERMINAL_OR_HISTORICAL = {
    JobStatus.OK,
    JobStatus.FAILED,
    JobStatus.SKIPPED,
    JobStatus.WAITING,
}


@dataclass(frozen=True)
class WorkflowHealth:
    ok: bool
    message: str = ""


def has_historical_execution(job) -> bool:
    """Return True when an empty workflow cannot reasonably be intentional."""
    if getattr(job, "status", None) in _TERMINAL_OR_HISTORICAL:
        return True

    if float(getattr(job, "progress", 0.0) or 0.0) > 0.0:
        return True

    if int(getattr(job, "next_operation_index", 0) or 0) > 0:
        return True

    message = str(getattr(job, "message", "") or "").casefold()
    if "workflow fullført" in message or "workflow stoppet" in message:
        return True

    recent = "\n".join(
        str(entry).casefold()
        for entry in list(getattr(job, "log_entries", ()) or ())[-250:]
    )
    return (
        "workflow fullført" in recent
        or "start: metadataoversikt" in recent
        or "start: noark 5" in recent
    )


def configured_sequence(settings: dict, *, profile_id: str):
    """Return the configured sequence for a profile, with Noark 5 fallback."""
    profile_id = str(profile_id or "").casefold()
    if profile_id != "noark5":
        return None

    sequence_id = str(
        settings.get("noark5_discovery_workflow", "noark5_standard")
        or "noark5_standard"
    )
    sequence = workflow_sequence_by_id(sequence_id)

    if sequence is None or sequence.profile_id != "noark5":
        sequence = workflow_sequence_by_id("noark5_standard")

    return sequence


def restore_default_if_empty(
    job,
    settings: dict,
    *,
    historical_only: bool,
) -> tuple[bool, str]:
    """Restore a configured profile workflow only when the job is empty.

    historical_only=True is for automatic repair of legacy/corrupt persisted
    state. False is for explicit user actions such as Nullstill.
    """
    if list(getattr(job, "workflow_ids", ()) or ()):
        return False, ""

    profile_id = str(getattr(job, "profile_id", "") or "").casefold()
    if profile_id != "noark5":
        return False, ""

    if historical_only and not has_historical_execution(job):
        return False, ""

    sequence = configured_sequence(settings, profile_id=profile_id)
    if sequence is None or not sequence.operation_ids:
        return False, ""

    job.set_workflow(sequence.operation_ids)
    return True, sequence.name


def normalise_completed_state(job) -> bool:
    """Normalise safe derived state for a completed job.

    This does not change workflow content. It only aligns cursor/progress with
    a Job that is already explicitly marked OK.
    """
    workflow = list(getattr(job, "workflow_ids", ()) or ())
    if getattr(job, "status", None) != JobStatus.OK or not workflow:
        return False

    changed = False
    expected_index = len(workflow)

    if int(getattr(job, "next_operation_index", 0) or 0) != expected_index:
        job.next_operation_index = expected_index
        changed = True

    if float(getattr(job, "progress", 0.0) or 0.0) != 1.0:
        job.progress = 1.0
        changed = True

    return changed


def workflow_health(job, registry=None) -> WorkflowHealth:
    """Validate workflow state without mutating it."""
    workflow = list(getattr(job, "workflow_ids", ()) or ())

    if not workflow:
        return WorkflowHealth(
            False,
            f"{getattr(job, 'job_id', 'Jobb')} har 0 operasjoner i workflow.",
        )

    if len(workflow) != len(set(workflow)):
        return WorkflowHealth(
            False,
            f"{getattr(job, 'job_id', 'Jobb')} har dupliserte operasjoner i workflow.",
        )

    if registry is not None:
        unknown = []
        for operation_id in workflow:
            try:
                registry.get(operation_id)
            except Exception:
                unknown.append(operation_id)
        if unknown:
            return WorkflowHealth(
                False,
                f"{getattr(job, 'job_id', 'Jobb')} refererer til ukjente operasjoner: "
                + ", ".join(unknown),
            )

    cursor = int(getattr(job, "next_operation_index", 0) or 0)
    if cursor < 0 or cursor > len(workflow):
        return WorkflowHealth(
            False,
            f"{getattr(job, 'job_id', 'Jobb')} har ugyldig workflow-cursor "
            f"{cursor}/{len(workflow)}.",
        )

    return WorkflowHealth(True, "")
