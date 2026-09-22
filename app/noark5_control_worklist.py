from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable


STATUS_ORDER = {
    "FEIL": 0,
    "VURDER": 1,
    "MANGLER": 2,
    "UKJENT": 3,
    "OK": 4,
}


def load_control_overview(path: str | Path) -> dict:
    path = Path(path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("report_type") != "noark5_batch_validation_overview":
        raise ValueError("Filen er ikke en Noark 5-kontrolloversikt.")
    if not isinstance(payload.get("jobs"), list):
        raise ValueError("Kontrolloversikten mangler jobbliste.")
    return payload


def sort_rows(rows: Iterable[dict]) -> list[dict]:
    def key(row: dict):
        status = str(row.get("control_status", "") or "")
        name = str(row.get("name", "") or "").casefold()
        job_id = str(row.get("job_id", "") or "").casefold()
        return STATUS_ORDER.get(status, 99), name, job_id

    return sorted(list(rows), key=key)


def filter_rows(
    rows: Iterable[dict],
    *,
    status: str = "",
    search: str = "",
) -> list[dict]:
    wanted_status = str(status or "").strip()
    needle = str(search or "").strip().casefold()

    filtered = []
    for row in rows:
        if wanted_status and str(row.get("control_status", "") or "") != wanted_status:
            continue

        if needle:
            haystack = " ".join([
                str(row.get("job_id", "") or ""),
                str(row.get("name", "") or ""),
                str(row.get("source_extraction", "") or ""),
                str(row.get("assessment_status", "") or ""),
                str(row.get("control_message", "") or ""),
            ]).casefold()
            if needle not in haystack:
                continue

        filtered.append(row)

    return sort_rows(filtered)


def summary_text(model: dict) -> str:
    counts = model.get("counts") or {}
    return (
        f"Feil {int(counts.get('FEIL', 0) or 0)}  |  "
        f"Vurder {int(counts.get('VURDER', 0) or 0)}  |  "
        f"Mangler {int(counts.get('MANGLER', 0) or 0)}  |  "
        f"Ukjent {int(counts.get('UKJENT', 0) or 0)}  |  "
        f"OK {int(counts.get('OK', 0) or 0)}"
    )
