from __future__ import annotations

from typing import Any


def _int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def suggest_reviewed_period(row: dict[str, Any], *, tail_share: float = 0.02) -> tuple[int | None, int | None]:
    """Suggest a practical review period without changing observed source data.

    The suggestion is based primarily on folder + journal activity. Very small
    leading/trailing tails (default <= 2% of total primary activity per side)
    are trimmed. If primary activity is unavailable, document activity is used.
    The result is only a suggestion for depot review and is never source truth.
    """
    yearly = row.get("yearly_volume") or {}

    def series(name: str) -> dict[int, int]:
        raw = yearly.get(name) or {}
        out: dict[int, int] = {}
        if not isinstance(raw, dict):
            return out
        for year, count in raw.items():
            text = str(year or "")[:4]
            if len(text) != 4 or not text.isdigit():
                continue
            out[int(text)] = out.get(int(text), 0) + _int(count)
        return out

    folder = series("folder")
    journal = series("journal")
    desc = series("document_description")
    obj = series("document_object")
    years = sorted(set(folder) | set(journal) | set(desc) | set(obj))
    if not years:
        return None, None

    primary = {year: folder.get(year, 0) + journal.get(year, 0) for year in years}
    if sum(primary.values()) <= 0:
        primary = {year: desc.get(year, 0) + obj.get(year, 0) for year in years}

    active = [year for year in years if primary.get(year, 0) > 0]
    if not active:
        active = [year for year in years if desc.get(year, 0) + obj.get(year, 0) > 0]
    if not active:
        return None, None
    if len(active) <= 2:
        return active[0], active[-1]

    total = sum(primary.get(year, 0) for year in active)
    if total <= 0:
        return active[0], active[-1]

    threshold = total * max(0.0, float(tail_share))
    left = 0
    removed = 0
    while left < len(active) - 1:
        amount = primary.get(active[left], 0)
        if removed + amount > threshold:
            break
        removed += amount
        left += 1

    right = len(active) - 1
    removed = 0
    while right > left:
        amount = primary.get(active[right], 0)
        if removed + amount > threshold:
            break
        removed += amount
        right -= 1

    return active[left], active[right]


def period_text(start: int | None, end: int | None) -> str:
    if start is None and end is None:
        return "–"
    return f"{start if start is not None else '–'}–{end if end is not None else '–'}"
