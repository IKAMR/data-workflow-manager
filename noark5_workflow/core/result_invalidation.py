from __future__ import annotations

from dataclasses import dataclass
import datetime as _dt
import json
from pathlib import Path
import uuid


INVALIDATION_FILENAME = "result-invalidations.jsonl"

# Explicit semantic dependency graph. This deliberately does not infer
# dependencies from workflow position: users may move operations up/down, while
# operation_id remains stable. Extend this graph when new derived operations are
# introduced.
DOWNSTREAM_DEPENDENCIES: dict[str, tuple[str, ...]] = {
    "run_noark5_xpath_tests_2026": ("compose_noark5_views",),
    "compose_noark5_views": ("build_noark5_depot_report",),
}


@dataclass(frozen=True)
class ResultInvalidationEvent:
    event_id: str
    recorded_at: str
    job_id: str
    source_operation_id: str
    source_result_id: str
    stale_operation_id: str
    reason: str

    def to_dict(self) -> dict:
        return {
            "schema_version": 1,
            "event_id": self.event_id,
            "recorded_at": self.recorded_at,
            "job_id": self.job_id,
            "source_operation_id": self.source_operation_id,
            "source_result_id": self.source_result_id,
            "stale_operation_id": self.stale_operation_id,
            "reason": self.reason,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ResultInvalidationEvent":
        if int(data.get("schema_version", 0)) != 1:
            raise ValueError("Ukjent schema_version for resultatinvalidering")
        return cls(
            event_id=str(data.get("event_id", "")),
            recorded_at=str(data.get("recorded_at", "")),
            job_id=str(data.get("job_id", "")),
            source_operation_id=str(data.get("source_operation_id", "")),
            source_result_id=str(data.get("source_result_id", "")),
            stale_operation_id=str(data.get("stale_operation_id", "")),
            reason=str(data.get("reason", "")),
        )


def invalidation_ledger_path_for_job(job) -> Path | None:
    root = getattr(job, "work_operations", None)
    if root is None:
        return None
    return Path(root) / "wf" / "results" / INVALIDATION_FILENAME


def downstream_operation_ids(operation_id: str) -> list[str]:
    """Return all transitive semantic dependants, stable by operation_id."""
    result: list[str] = []
    queue = list(DOWNSTREAM_DEPENDENCIES.get(str(operation_id), ()))
    while queue:
        candidate = queue.pop(0)
        if candidate in result:
            continue
        result.append(candidate)
        queue.extend(DOWNSTREAM_DEPENDENCIES.get(candidate, ()))
    return result


class ResultInvalidationLedger:
    def __init__(self, path) -> None:
        self.path = Path(path)

    @staticmethod
    def _now() -> str:
        return _dt.datetime.now().astimezone().isoformat(timespec="seconds")

    def append(
        self,
        *,
        job_id: str,
        source_operation_id: str,
        source_result_id: str,
        stale_operation_id: str,
        reason: str,
        event_id: str | None = None,
        recorded_at: str | None = None,
    ) -> ResultInvalidationEvent:
        event = ResultInvalidationEvent(
            event_id=event_id or str(uuid.uuid4()),
            recorded_at=recorded_at or self._now(),
            job_id=str(job_id or ""),
            source_operation_id=str(source_operation_id or ""),
            source_result_id=str(source_result_id or ""),
            stale_operation_id=str(stale_operation_id or ""),
            reason=str(reason or ""),
        )
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(event.to_dict(), ensure_ascii=False, sort_keys=True))
            handle.write("\n")
        return event

    def events(self) -> list[ResultInvalidationEvent]:
        if not self.path.is_file():
            return []
        result: list[ResultInvalidationEvent] = []
        with self.path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, 1):
                text = line.strip()
                if not text:
                    continue
                try:
                    result.append(ResultInvalidationEvent.from_dict(json.loads(text)))
                except Exception as exc:
                    raise ValueError(
                        f"Ugyldig resultatinvalideringslogg på linje {line_number}: {exc}"
                    ) from exc
        return result


def mark_downstream_stale(job, source_operation_id: str, source_result_id: str) -> list[str]:
    """Append invalidation events for derived operations present in this job.

    This does not delete or rewrite existing outputs. It records that those
    outputs were produced from an older authoritative upstream result and must
    be regenerated before they should be treated as current.
    """
    path = invalidation_ledger_path_for_job(job)
    if path is None:
        return []
    workflow_ids = set(getattr(job, "workflow_ids", []) or [])
    stale = [oid for oid in downstream_operation_ids(source_operation_id) if oid in workflow_ids]
    ledger = ResultInvalidationLedger(path)
    for oid in stale:
        ledger.append(
            job_id=str(getattr(job, "job_id", "") or ""),
            source_operation_id=source_operation_id,
            source_result_id=source_result_id,
            stale_operation_id=oid,
            reason="Gjeldende upstream-resultat er endret; avledet resultat må regenereres",
        )
    return stale
