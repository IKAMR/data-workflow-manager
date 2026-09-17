from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Iterable

_CONFIG_PATH = Path(__file__).resolve().parents[1] / "config" / "operations.json"

MATURITY_LEVELS = {
    "alpha": 0,
    "beta": 1,
    "stable": 2,
}

MATURITY_LABELS = {
    "alpha": "Alpha",
    "beta": "Beta",
    "stable": "Stabil",
}

MATURITY_SHORT_LABELS = {
    "alpha": "A",
    "beta": "B",
    "stable": "S",
}

VISIBILITY_LABELS = {
    0: "Alle (inkl. Alpha)",
    1: "Beta og stabile",
    2: "Kun stabile",
}

VISIBILITY_VALUES = {label: value for value, label in VISIBILITY_LABELS.items()}


@lru_cache(maxsize=1)
def load_operation_metadata() -> dict:
    try:
        data = json.loads(_CONFIG_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, TypeError):
        return {"profiles": {}, "display_categories": {}, "operations": {}}
    if not isinstance(data, dict):
        return {"profiles": {}, "display_categories": {}, "operations": {}}
    operations = data.get("operations", {})
    profiles = data.get("profiles", {})
    categories = data.get("display_categories", {})
    return {
        **data,
        "operations": operations if isinstance(operations, dict) else {},
        "profiles": profiles if isinstance(profiles, dict) else {},
        "display_categories": categories if isinstance(categories, dict) else {},
    }


def _operation_metadata(operation_id: str) -> dict:
    raw = load_operation_metadata().get("operations", {}).get(operation_id, {})
    return raw if isinstance(raw, dict) else {}


def maturity_name(operation_id: str) -> str:
    raw = _operation_metadata(operation_id)
    maturity = str(raw.get("maturity", "alpha")).strip().lower()
    return maturity if maturity in MATURITY_LEVELS else "alpha"


def maturity_level(operation_id: str) -> int:
    return MATURITY_LEVELS[maturity_name(operation_id)]


def maturity_label(operation_id: str) -> str:
    return MATURITY_LABELS[maturity_name(operation_id)]


def maturity_short_label(operation_id: str) -> str:
    return MATURITY_SHORT_LABELS[maturity_name(operation_id)]


def is_visible(operation_id: str, minimum_level: int) -> bool:
    try:
        threshold = int(minimum_level)
    except (TypeError, ValueError):
        threshold = 2
    threshold = max(0, min(2, threshold))
    return maturity_level(operation_id) >= threshold


def visibility_label(value: int | str) -> str:
    try:
        level = int(value)
    except (TypeError, ValueError):
        level = 2
    return VISIBILITY_LABELS.get(level, VISIBILITY_LABELS[2])


def visibility_value(label: str) -> int:
    return VISIBILITY_VALUES.get(str(label), 2)


def short_name(operation_id: str, fallback: str = "") -> str:
    """Short user-facing label for operation cards and sequence editors."""
    value = str(_operation_metadata(operation_id).get("short_name", "")).strip()
    return value or fallback or operation_id


def display_category(operation_id: str, fallback: str = "") -> str:
    """User-facing operation group independent of the executor definition."""
    value = str(_operation_metadata(operation_id).get("display_category", "")).strip()
    return value or fallback or "Annet"


def operation_profiles(operation_id: str) -> tuple[str, ...]:
    """Profiles in which an operation belongs in the operation catalogue."""
    raw = _operation_metadata(operation_id).get("profiles", [])
    if isinstance(raw, str):
        raw = [raw]
    if not isinstance(raw, list):
        return ()
    return tuple(str(item).strip() for item in raw if str(item).strip())


def belongs_to_profile(operation_id: str, profile_id: str) -> bool:
    profiles = operation_profiles(operation_id)
    # Backwards compatibility for third-party/unlisted operations: if no
    # catalogue scope is declared, keep the operation visible.
    return not profiles or profile_id in profiles


def profile_definitions() -> dict[str, dict]:
    return dict(load_operation_metadata().get("profiles", {}))


def display_category_names(operations: Iterable, profile_id: str) -> list[str]:
    """Return configured categories in stable display order for a profile."""
    present: set[str] = set()
    for operation in operations:
        op_id = operation.definition.operation_id
        if not belongs_to_profile(op_id, profile_id):
            continue
        present.add(display_category(op_id, operation.definition.category))

    configured = load_operation_metadata().get("display_categories", {})
    ordered = [name for name in configured if name in present]
    ordered.extend(sorted(present.difference(ordered)))
    return ordered


def display_category_color(category: str, fallback: str = "") -> str:
    raw = load_operation_metadata().get("display_categories", {}).get(category, {})
    if isinstance(raw, dict):
        color = str(raw.get("color", "")).strip()
        if color:
            return color
    return fallback
