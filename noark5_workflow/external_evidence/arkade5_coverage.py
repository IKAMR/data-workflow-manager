from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def _mapping_path() -> Path:
    return Path(__file__).resolve().parents[2] / "config" / "noark5" / "external" / "dwm_arkade5_mapping.json"


def _load_mapping() -> dict[str, Any]:
    path = _mapping_path()
    if not path.is_file():
        return {"arkade_to_dwm": []}
    return json.loads(path.read_text(encoding="utf-8"))


def build_arkade5_coverage(normalized: dict[str, Any]) -> dict[str, Any]:
    """Classify imported Arkade tests from the verified a2 mapping.

    Shared legacy N5 numbering is never used as proof of equivalence.
    """
    mapping = _load_mapping()
    by_id = {
        str(row.get("arkade_test_id") or "").upper(): row
        for row in mapping.get("arkade_to_dwm") or []
    }
    allowed = {"equivalent", "partial", "complementary", "arkade_only"}
    counts = {key: 0 for key in sorted(allowed)}
    counts["unmapped"] = 0
    rows = []

    for test in normalized.get("tests") or []:
        test_id = str(test.get("test_id") or "").upper()
        rule = by_id.get(test_id)
        if rule is None:
            classification = "unmapped"
            reason = "Arkade-testen finnes ikke i den verifiserte DWM-Arkade-mappingen."
            dwm = []
        else:
            classification = str(rule.get("relation") or rule.get("coverage") or "unmapped")
            if classification not in allowed:
                classification = "unmapped"
            reason = str(rule.get("note_nb") or "")
            dwm = [
                {"dwm_test_id": str(value), "relation": classification}
                for value in (rule.get("dwm_test_ids") or [])
            ]
        counts[classification] = counts.get(classification, 0) + 1
        rows.append({
            "arkade_test_id": test_id,
            "arkade_test_name": str(test.get("test_name") or ""),
            "arkade_status": str(test.get("source_status") or ""),
            "classification": classification,
            "reason": reason,
            "dwm_candidates": dwm,
        })

    return {
        "format_version": 2,
        "source_system": "Arkade 5",
        "mapping_id": mapping.get("mapping_id"),
        "arkade_tests_present": len(rows),
        "summary": counts,
        "items": rows,
    }
