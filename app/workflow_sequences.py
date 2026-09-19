from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFINITION_PATH = ROOT / "config" / "workflow_sequences.json"


@dataclass(frozen=True)
class WorkflowSequence:
    sequence_id: str
    name: str
    profile_id: str
    description: str
    operation_ids: tuple[str, ...]


def load_workflow_sequences(path: Path = DEFINITION_PATH) -> list[WorkflowSequence]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    result: list[WorkflowSequence] = []
    for item in payload.get("sequences", []):
        result.append(
            WorkflowSequence(
                sequence_id=str(item["sequence_id"]),
                name=str(item["name"]),
                profile_id=str(item.get("profile_id", "")),
                description=str(item.get("description", "")),
                operation_ids=tuple(str(value) for value in item.get("operation_ids", [])),
            )
        )
    return result


def workflow_sequence_by_id(sequence_id: str | None) -> WorkflowSequence | None:
    wanted = str(sequence_id or "none")
    if wanted == "none":
        return None
    for sequence in load_workflow_sequences():
        if sequence.sequence_id == wanted:
            return sequence
    return None


def noark5_workflow_labels() -> dict[str, str]:
    labels = {"none": "Ingen automatisk workflow"}
    for sequence in load_workflow_sequences():
        if sequence.profile_id == "noark5":
            labels[sequence.sequence_id] = sequence.name
    return labels
