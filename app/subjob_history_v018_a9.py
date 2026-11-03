"""Read-only labels for actual, saved DWM run records.

Do not infer subjob completion from the parent job's saved progress cursor.
One selective run is not equivalent to completing the whole workflow.
"""
from __future__ import annotations


def run_history_lines(runs, *, names: dict[str, str] | None = None,
                      limit: int = 12) -> tuple[str, ...]:
    labels = names or {}
    records = tuple(runs)[:max(0, min(int(limit), 100))]
    if not records:
        return ("Ingen separate kjorelogger er registrert for denne jobben.",)
    lines = []
    state_names = {"finished": "OK", "failed": "Feil", "running": "Kjorer",
                   "checkpoint": "Kontrollpunkt", "skipped": "Hoppet over",
                   "stopped": "Stoppet"}
    for info in records:
        mode = str(getattr(info, "run_kind", "workflow") or "workflow")
        operation_id = str(getattr(info, "operation_id", "") or "")
        if mode == "subjob":
            title = (str(getattr(info, "operation_name", "") or "")
                     or labels.get(operation_id, operation_id))
            title = "Deljobb: " + title
        else:
            title = "Hele arbeidsflyten"
        timestamp = str(getattr(info, "started_at", "") or "").replace("T", " ")[:19]
        state = state_names.get(str(getattr(info, "status", "")),
                                str(getattr(info, "status", "unknown")))
        lines.append(f"{timestamp}  |  {title}  |  {state}")
    return tuple(lines)
