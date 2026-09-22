from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .arkade5 import load_arkade5_mapping


def _catalog_path() -> Path:
    return Path(__file__).resolve().parents[2] / "config" / "noark5" / "tests" / "xpath_catalog_2026_05_26.json"


def _load_catalog() -> dict[str, Any]:
    path = _catalog_path()
    if not path.is_file():
        return {"tests": []}
    return json.loads(path.read_text(encoding="utf-8"))


def _arkade_ids(value: object) -> set[str]:
    return {
        match.upper()
        for match in re.findall(r"\bN5\.\d+\b", str(value or ""), flags=re.IGNORECASE)
    }


def build_arkade5_coverage(normalized: dict[str, Any]) -> dict[str, Any]:
    """Classify every test present in an imported Arkade 5 report.

    Categories deliberately separate proven equivalence from mapping candidates.
    A shared N5 test-point identity is evidence for review, not proof that both
    implementations calculate the same thing.
    """
    mapping = load_arkade5_mapping()
    equivalent = {
        str(item.get("arkade_test_id") or "").upper(): item
        for item in mapping.get("mappings") or []
        if item.get("quality") == "equivalent"
    }
    non_equivalent = {
        str(item.get("arkade_test_id") or "").upper(): item
        for item in mapping.get("known_non_equivalent") or []
    }

    candidates: dict[str, list[dict[str, str]]] = {}
    for test in _load_catalog().get("tests") or []:
        legacy = test.get("legacy") or {}
        for arkade_id in _arkade_ids(legacy.get("test_point")):
            candidates.setdefault(arkade_id, []).append({
                "dwm_test_id": str(test.get("test_id") or ""),
                "dwm_name": str(test.get("name") or ""),
                "legacy_job_id": str(legacy.get("job_id") or ""),
            })

    rows = []
    counts = {
        "equivalent": 0,
        "candidate": 0,
        "known_non_equivalent": 0,
        "unmapped": 0,
    }
    for test in normalized.get("tests") or []:
        test_id = str(test.get("test_id") or "").upper()
        if test_id in equivalent:
            classification = "equivalent"
            reason = "Dokumentert som direkte sammenlignbar i Arkade 5-mappingen."
            dwm = candidates.get(test_id, [])
        elif test_id in non_equivalent:
            classification = "known_non_equivalent"
            reason = str(non_equivalent[test_id].get("reason") or "")
            dwm = candidates.get(test_id, [])
        elif test_id in candidates:
            classification = "candidate"
            reason = (
                "DWM har kontroll(er) med samme N5-testpunkt, men semantisk "
                "ekvivalens er ikke kvalitetssikret ennå."
            )
            dwm = candidates[test_id]
        else:
            classification = "unmapped"
            reason = "Ingen eksplisitt DWM-mapping er registrert ennå."
            dwm = []

        counts[classification] += 1
        rows.append({
            "arkade_test_id": test_id,
            "arkade_test_name": str(test.get("test_name") or ""),
            "arkade_status": str(test.get("source_status") or ""),
            "classification": classification,
            "reason": reason,
            "dwm_candidates": dwm,
        })

    return {
        "format_version": 1,
        "source_system": "Arkade 5",
        "arkade_tests_present": len(rows),
        "summary": counts,
        "items": rows,
    }
