from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

_BUILTIN_PATH = Path(__file__).resolve().parents[1] / "config" / "workflow_sequences.json"


@dataclass(frozen=True)
class WorkflowSequence:
    sequence_id: str
    name: str
    profile_id: str
    operation_ids: tuple[str, ...]
    description: str = ""
    builtin: bool = True

    @classmethod
    def from_dict(cls, raw: dict, *, builtin: bool) -> "WorkflowSequence":
        sequence_id = str(raw.get("sequence_id", "")).strip()
        name = str(raw.get("name", "")).strip()
        profile_id = str(raw.get("profile_id", "")).strip()
        operation_ids_raw = raw.get("operation_ids", [])
        if not sequence_id or not name or not profile_id:
            raise ValueError("Kjøresekvens mangler sequence_id, name eller profile_id")
        if not isinstance(operation_ids_raw, list):
            raise ValueError(f"Kjøresekvens {sequence_id} har ugyldig operation_ids")
        operation_ids = tuple(str(item).strip() for item in operation_ids_raw if str(item).strip())
        if not operation_ids:
            raise ValueError(f"Kjøresekvens {sequence_id} har ingen operasjoner")
        if len(set(operation_ids)) != len(operation_ids):
            raise ValueError(f"Kjøresekvens {sequence_id} inneholder duplikate operasjoner")
        return cls(
            sequence_id=sequence_id,
            name=name,
            profile_id=profile_id,
            operation_ids=operation_ids,
            description=str(raw.get("description", "")).strip(),
            builtin=builtin,
        )


class WorkflowSequenceCatalog:
    """Profile-aware sequence catalogue shared by future GUI and CLI clients."""

    def __init__(self, sequences: Iterable[WorkflowSequence] = ()) -> None:
        self._sequences: dict[str, WorkflowSequence] = {}
        for sequence in sequences:
            self.register(sequence)

    def register(self, sequence: WorkflowSequence, *, replace: bool = False) -> None:
        if sequence.sequence_id in self._sequences and not replace:
            raise ValueError(f"Kjøresekvens finnes allerede: {sequence.sequence_id}")
        self._sequences[sequence.sequence_id] = sequence

    def get(self, sequence_id: str) -> WorkflowSequence:
        return self._sequences[sequence_id]

    def all(self) -> list[WorkflowSequence]:
        return list(self._sequences.values())

    def for_profile(self, profile_id: str) -> list[WorkflowSequence]:
        return [item for item in self._sequences.values() if item.profile_id == profile_id]

    def validate_operations(self, operation_ids: Iterable[str]) -> dict[str, tuple[str, ...]]:
        available = set(operation_ids)
        return {
            sequence.sequence_id: tuple(op for op in sequence.operation_ids if op not in available)
            for sequence in self._sequences.values()
        }


def _load_sequence_file(path: Path, *, builtin: bool) -> list[WorkflowSequence]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return []
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Kunne ikke lese kjøresekvenser fra {path}: {exc}") from exc
    rows = data.get("sequences", []) if isinstance(data, dict) else []
    if not isinstance(rows, list):
        raise ValueError(f"Ugyldig sekvensfil: {path}")
    return [WorkflowSequence.from_dict(row, builtin=builtin) for row in rows if isinstance(row, dict)]


def load_workflow_sequences(user_path: Path | None = None) -> WorkflowSequenceCatalog:
    """Load built-ins and optionally overlay user-created sequences by id."""
    catalog = WorkflowSequenceCatalog(_load_sequence_file(_BUILTIN_PATH, builtin=True))
    if user_path is not None:
        for sequence in _load_sequence_file(Path(user_path), builtin=False):
            catalog.register(sequence, replace=True)
    return catalog


def save_user_workflow_sequences(path: Path, sequences: Iterable[WorkflowSequence]) -> Path:
    """Persist user sequences only; built-in definitions remain repository-owned."""
    payload = {
        "format_version": 1,
        "sequences": [
            {
                "sequence_id": item.sequence_id,
                "name": item.name,
                "profile_id": item.profile_id,
                "description": item.description,
                "operation_ids": list(item.operation_ids),
            }
            for item in sequences
            if not item.builtin
        ],
    }
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path
