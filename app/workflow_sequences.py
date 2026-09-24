
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

from settings import load_config, save_config

ROOT = Path(__file__).resolve().parents[1]
DEFINITION_PATH = ROOT / "config" / "workflow_sequences.json"


@dataclass(frozen=True)
class WorkflowSequence:
    sequence_id: str
    name: str
    profile_id: str
    description: str
    operation_ids: tuple[str, ...]
    source: str = "builtin"

    @property
    def is_custom(self) -> bool:
        return self.source == "custom"


def _sequence_from_item(item: dict, *, source: str) -> WorkflowSequence:
    return WorkflowSequence(
        sequence_id=str(item["sequence_id"]),
        name=str(item["name"]),
        profile_id=str(item.get("profile_id", "")),
        description=str(item.get("description", "")),
        operation_ids=tuple(str(value) for value in item.get("operation_ids", [])),
        source=source,
    )


def load_builtin_workflow_sequences(
    path: Path = DEFINITION_PATH,
) -> list[WorkflowSequence]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    return [
        _sequence_from_item(item, source="builtin")
        for item in payload.get("sequences", [])
    ]


def load_custom_workflow_sequences(
    settings: dict | None = None,
) -> list[WorkflowSequence]:
    cfg = dict(settings) if settings is not None else load_config()
    items = cfg.get("custom_workflow_sequences", [])
    if not isinstance(items, list):
        return []

    result: list[WorkflowSequence] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        try:
            result.append(_sequence_from_item(item, source="custom"))
        except (KeyError, TypeError, ValueError):
            continue
    return result


def load_workflow_sequences(
    path: Path = DEFINITION_PATH,
    *,
    include_custom: bool = True,
    settings: dict | None = None,
) -> list[WorkflowSequence]:
    result = load_builtin_workflow_sequences(path)
    if include_custom:
        result.extend(load_custom_workflow_sequences(settings))
    return result


def workflow_sequence_by_id(
    sequence_id: str | None,
    *,
    settings: dict | None = None,
) -> WorkflowSequence | None:
    wanted = str(sequence_id or "none")
    if wanted == "none":
        return None
    for sequence in load_workflow_sequences(settings=settings):
        if sequence.sequence_id == wanted:
            return sequence
    return None


def noark5_workflow_labels(
    *,
    settings: dict | None = None,
) -> dict[str, str]:
    labels = {"none": "Ingen automatisk workflow"}
    for sequence in load_workflow_sequences(settings=settings):
        if sequence.profile_id == "noark5":
            labels[sequence.sequence_id] = sequence.name
    return labels


def _slug(value: str) -> str:
    text = re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")
    return text or "workflow"


def save_custom_workflow_sequence(
    *,
    name: str,
    profile_id: str,
    operation_ids: list[str] | tuple[str, ...],
    description: str = "",
    sequence_id: str | None = None,
) -> WorkflowSequence:
    cleaned_name = str(name or "").strip()
    if not cleaned_name:
        raise ValueError("Profilnavn kan ikke være tomt.")

    operations = tuple(str(value) for value in operation_ids if str(value).strip())
    if not operations:
        raise ValueError("Workflowen må inneholde minst én operasjon.")

    cfg = load_config()
    items = cfg.get("custom_workflow_sequences", [])
    if not isinstance(items, list):
        items = []

    wanted_id = str(sequence_id or "").strip()
    if not wanted_id:
        base_id = f"user-{_slug(cleaned_name)}"
        wanted_id = base_id
        used = {
            str(item.get("sequence_id") or "")
            for item in items
            if isinstance(item, dict)
        }
        builtin_ids = {
            sequence.sequence_id
            for sequence in load_builtin_workflow_sequences()
        }
        suffix = 2
        while wanted_id in used or wanted_id in builtin_ids:
            wanted_id = f"{base_id}-{suffix}"
            suffix += 1

    payload = {
        "sequence_id": wanted_id,
        "name": cleaned_name,
        "profile_id": str(profile_id or "noark5"),
        "description": str(description or "").strip(),
        "operation_ids": list(operations),
    }

    replaced = False
    new_items: list[dict] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        if str(item.get("sequence_id") or "") == wanted_id:
            new_items.append(payload)
            replaced = True
        else:
            new_items.append(item)
    if not replaced:
        new_items.append(payload)

    save_config({"custom_workflow_sequences": new_items})
    return _sequence_from_item(payload, source="custom")


def delete_custom_workflow_sequence(sequence_id: str) -> bool:
    wanted = str(sequence_id or "").strip()
    if not wanted:
        return False

    cfg = load_config()
    items = cfg.get("custom_workflow_sequences", [])
    if not isinstance(items, list):
        return False

    kept = [
        item
        for item in items
        if isinstance(item, dict)
        and str(item.get("sequence_id") or "") != wanted
    ]
    if len(kept) == len([item for item in items if isinstance(item, dict)]):
        return False

    save_config({"custom_workflow_sequences": kept})
    return True
