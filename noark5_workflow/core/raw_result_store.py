from __future__ import annotations

from dataclasses import dataclass
import datetime as _dt
import json
from pathlib import Path
import threading
from typing import Any
import uuid

from .result_review import RawTestResultRef


_APPEND_LOCK = threading.Lock()


@dataclass(frozen=True)
class RawResultEnvelope:
    """One immutable, append-only raw result produced by an operation."""

    result_id: str
    recorded_at: str
    operation_id: str
    test_id: str
    definition_version: str
    ok: bool
    message: str
    data: dict[str, Any]
    warnings: list[str]
    outputs: list[str]
    source_root: str = ""
    job_id: str = ""
    run_id: str = ""

    @property
    def ref(self) -> RawTestResultRef:
        return RawTestResultRef(
            result_id=self.result_id,
            test_id=self.test_id,
            definition_version=self.definition_version,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": 2,
            "result_id": self.result_id,
            "recorded_at": self.recorded_at,
            "operation_id": self.operation_id,
            "test_id": self.test_id,
            "definition_version": self.definition_version,
            "ok": self.ok,
            "message": self.message,
            "data": _json_safe(self.data),
            "warnings": [_json_safe(item) for item in self.warnings],
            "outputs": [_json_safe(item) for item in self.outputs],
            "source_root": self.source_root,
            "job_id": self.job_id,
            "run_id": self.run_id,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RawResultEnvelope":
        schema_version = int(data.get("schema_version", 0))
        if schema_version not in {1, 2}:
            raise ValueError("Ukjent schema_version for råresultat")
        return cls(
            result_id=str(data.get("result_id", "")),
            recorded_at=str(data.get("recorded_at", "")),
            operation_id=str(data.get("operation_id", "")),
            test_id=str(data.get("test_id", "")),
            definition_version=str(data.get("definition_version", "")),
            ok=bool(data.get("ok", False)),
            message=str(data.get("message", "")),
            data=dict(data.get("data") or {}),
            warnings=[str(item) for item in (data.get("warnings") or [])],
            outputs=[str(item) for item in (data.get("outputs") or [])],
            source_root=str(data.get("source_root", "")),
            job_id=str(data.get("job_id", "")),
            run_id=str(data.get("run_id", "")),
        )


def _json_safe(value: Any) -> Any:
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(item) for item in value]
    enum_value = getattr(value, "value", None)
    if isinstance(enum_value, (bool, int, float, str)):
        return enum_value
    return str(value)


class RawResultStore:
    """Append-only JSONL store for machine-generated raw test/analysis results."""

    def __init__(self, path) -> None:
        self.path = Path(path)

    @staticmethod
    def _now() -> str:
        return _dt.datetime.now().astimezone().isoformat(timespec="seconds")

    def append(
        self,
        *,
        operation_id: str,
        test_id: str,
        definition_version: str,
        ok: bool,
        message: str,
        data: dict[str, Any] | None = None,
        warnings: list[str] | None = None,
        outputs: list[str] | None = None,
        source_root: str = "",
        job_id: str = "",
        run_id: str = "",
        result_id: str | None = None,
        recorded_at: str | None = None,
    ) -> RawResultEnvelope:
        if not str(operation_id).strip():
            raise ValueError("operation_id kan ikke være tom")
        if not str(test_id).strip():
            raise ValueError("test_id kan ikke være tom")
        envelope = RawResultEnvelope(
            result_id=result_id or str(uuid.uuid4()),
            recorded_at=recorded_at or self._now(),
            operation_id=str(operation_id),
            test_id=str(test_id),
            definition_version=str(definition_version or ""),
            ok=bool(ok),
            message=str(message or ""),
            data=dict(data or {}),
            warnings=list(warnings or []),
            outputs=list(outputs or []),
            source_root=str(source_root or ""),
            job_id=str(job_id or ""),
            run_id=str(run_id or ""),
        )
        record = json.dumps(
            envelope.to_dict(),
            ensure_ascii=False,
            sort_keys=True,
        ) + "\n"
        with _APPEND_LOCK:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8", newline="\n") as handle:
                handle.write(record)
        return envelope

    def results(self) -> list[RawResultEnvelope]:
        if not self.path.is_file():
            return []
        items: list[RawResultEnvelope] = []
        with self.path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, 1):
                text = line.strip()
                if not text:
                    continue
                try:
                    items.append(RawResultEnvelope.from_dict(json.loads(text)))
                except Exception as exc:
                    raise ValueError(
                        f"Ugyldig råresultatlogg på linje {line_number}: {exc}"
                    ) from exc
        return items

    def get(self, result_id: str) -> RawResultEnvelope | None:
        for item in self.results():
            if item.result_id == result_id:
                return item
        return None


def raw_result_store_path(ctx) -> Path | None:
    work_operations = getattr(ctx, "work_operations", None)
    if work_operations is None:
        return None
    return Path(work_operations) / "wf" / "results" / "raw-results.jsonl"


def persist_operation_raw_result(operation, result, ctx) -> RawResultEnvelope | None:
    if not bool(getattr(operation, "raw_result_record", False)):
        return None
    path = raw_result_store_path(ctx)
    if path is None:
        return None

    identity = {}
    provider = getattr(operation, "raw_result_identity", None)
    if callable(provider):
        identity = dict(provider(result, ctx) or {})
    definition = getattr(operation, "definition", None)
    operation_id = str(getattr(definition, "operation_id", "") or "")
    test_id = str(identity.get("test_id") or operation_id)
    definition_version = str(identity.get("definition_version") or "")

    metadata = getattr(ctx, "metadata", {}) or {}
    settings = getattr(ctx, "settings", {}) or {}
    run_id = str(
        metadata.get("run_id", "")
        or settings.get("_current_run_id", "")
        or ""
    )
    envelope = RawResultStore(path).append(
        operation_id=operation_id,
        test_id=test_id,
        definition_version=definition_version,
        ok=bool(getattr(result, "ok", False)),
        message=str(getattr(result, "message", "") or ""),
        data=dict(getattr(result, "data", {}) or {}),
        warnings=list(getattr(result, "warnings", []) or []),
        outputs=list(getattr(result, "outputs", []) or []),
        source_root=str(getattr(ctx, "input_root", "") or ""),
        job_id=str(metadata.get("job_id", "") or ""),
        run_id=run_id,
    )
    result_data = getattr(result, "data", None)
    if isinstance(result_data, dict):
        result_data["_result_ref"] = {
            "result_id": envelope.result_id,
            "test_id": envelope.test_id,
            "definition_version": envelope.definition_version,
            "run_id": envelope.run_id,
            "raw_store": str(path),
        }
    try:
        ctx.log(
            f"Råresultat lagret: {envelope.result_id} "
            f"({envelope.test_id}) | run={envelope.run_id or '-'} - {path}"
        )
    except Exception:
        pass
    return envelope
