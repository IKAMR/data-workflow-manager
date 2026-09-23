
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any


FORMAT_VERSION = 1
MODEL_ID = "noark5.dwm-arkade5-gap-overlap.v1"


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _default_mapping() -> dict[str, Any]:
    return _read_json(
        _repo_root() / "config" / "noark5" / "external" / "dwm_arkade5_mapping.json"
    )


def _default_arkade_catalog() -> dict[str, Any]:
    return _read_json(
        _repo_root() / "config" / "noark5" / "external" / "arkade5_test_catalog.json"
    )


def _default_dwm_catalog() -> dict[str, Any]:
    return _read_json(
        _repo_root() / "config" / "noark5" / "tests" / "xpath_catalog_2026_05_26.json"
    )


def build_gap_overlap_analysis(
    *,
    mapping: dict[str, Any] | None = None,
    arkade_catalog: dict[str, Any] | None = None,
    dwm_catalog: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a static implementation-gap analysis from pinned project knowledge.

    This is not run coverage. It describes documented implementation relations
    between DWM and Arkade 5 v2.13.0 and keeps Arkade, KDRS and DWM namespaces
    explicit.
    """
    mapping = mapping or _default_mapping()
    arkade_catalog = arkade_catalog or _default_arkade_catalog()
    dwm_catalog = dwm_catalog or _default_dwm_catalog()

    arkade_by_id = {
        str(row.get("arkade_test_id") or "").upper(): row
        for row in arkade_catalog.get("tests") or []
    }
    dwm_by_id = {
        str(row.get("test_id") or ""): row
        for row in dwm_catalog.get("tests") or []
    }

    areas: list[dict[str, Any]] = []
    relation_counts: Counter[str] = Counter()
    arkade_gap_ids: list[str] = []
    overlap_ids: list[str] = []

    for rule in mapping.get("arkade_to_dwm") or []:
        arkade_id = str(rule.get("arkade_test_id") or "").upper()
        relation = str(rule.get("relation") or rule.get("coverage") or "unmapped")
        relation_counts[relation] += 1
        catalog = arkade_by_id.get(arkade_id) or {}
        dwm_ids = [str(value) for value in rule.get("dwm_test_ids") or []]

        if relation == "arkade_only":
            implementation_status = "dwm_gap_covered_by_arkade"
            arkade_gap_ids.append(arkade_id)
        elif relation == "equivalent":
            implementation_status = "documented_equivalent_overlap"
            overlap_ids.append(arkade_id)
        elif relation == "partial":
            implementation_status = "partial_overlap_retain_both"
            overlap_ids.append(arkade_id)
        elif relation == "complementary":
            implementation_status = "complementary_overlap_retain_both"
            overlap_ids.append(arkade_id)
        else:
            implementation_status = "unclassified"

        dwm_rows = []
        for dwm_id in dwm_ids:
            dwm = dwm_by_id.get(dwm_id) or {}
            legacy = dwm.get("legacy") or {}
            legacy_point = legacy.get("test_point")
            dwm_rows.append({
                "namespace_id": f"dwm:{dwm_id}",
                "dwm_test_id": dwm_id,
                "name": dwm.get("name"),
                "status": dwm.get("status"),
                "legacy_namespace_id": (
                    f"kdrs:{legacy_point}" if legacy_point else None
                ),
                "legacy_test_point": legacy_point,
            })

        areas.append({
            "namespace_id": f"arkade:{arkade_id}",
            "arkade_test_id": arkade_id,
            "arkade_test_name": catalog.get("name_nb"),
            "arkade_type": catalog.get("arkade_type"),
            "relation": relation,
            "implementation_status": implementation_status,
            "dwm": dwm_rows,
            "note_nb": rule.get("note_nb"),
        })

    dwm_only = []
    for row in mapping.get("dwm_only") or []:
        dwm_id = str(row.get("dwm_test_id") or "")
        dwm = dwm_by_id.get(dwm_id) or {}
        legacy = dwm.get("legacy") or {}
        legacy_point = legacy.get("test_point")
        dwm_only.append({
            "namespace_id": f"dwm:{dwm_id}",
            "dwm_test_id": dwm_id,
            "name": dwm.get("name") or row.get("note_nb"),
            "status": dwm.get("status"),
            "legacy_namespace_id": (
                f"kdrs:{legacy_point}"
                if legacy_point
                else row.get("legacy_namespace_id")
            ),
            "mapping_legacy_namespace_id": row.get("legacy_namespace_id"),
            "relation": "dwm_only",
            "note_nb": row.get("note_nb"),
        })

    expected_summary = mapping.get("summary") or {}
    summary = {
        "arkade_test_count": len(areas),
        "equivalent": relation_counts["equivalent"],
        "partial": relation_counts["partial"],
        "complementary": relation_counts["complementary"],
        "arkade_only": relation_counts["arkade_only"],
        "dwm_only": len(dwm_only),
        "dwm_gaps_covered_by_arkade": len(arkade_gap_ids),
        "overlap_control_areas": len(overlap_ids),
    }

    consistency = {
        "mapping_summary_matches": (
            summary["arkade_test_count"] == expected_summary.get("arkade_test_count")
            and summary["equivalent"] == expected_summary.get("equivalent")
            and summary["partial"] == expected_summary.get("partial")
            and summary["complementary"] == expected_summary.get("complementary")
            and summary["arkade_only"] == expected_summary.get("arkade_only")
            and summary["dwm_only"] == expected_summary.get("dwm_only_count")
        ),
        "catalog_contains_all_mapped_arkade_ids": all(
            row["arkade_test_id"] in arkade_by_id for row in areas
        ),
        "mapped_dwm_ids_missing_from_catalog": sorted({
            item["dwm_test_id"]
            for area in areas
            for item in area["dwm"]
            if item["dwm_test_id"] not in dwm_by_id
        }),
    }

    return {
        "format_version": FORMAT_VERSION,
        "model_id": MODEL_ID,
        "analysis_kind": "static_implementation_gap_overlap",
        "basis": {
            "mapping_id": mapping.get("mapping_id"),
            "arkade_catalog_id": arkade_catalog.get("catalog_id"),
            "arkade_version": mapping.get("arkade_version"),
            "arkade_source_commit": mapping.get("arkade_source_commit"),
            "dwm_test_catalog": "config/noark5/tests/xpath_catalog_2026_05_26.json",
        },
        "principles": {
            "not_run_coverage": True,
            "same_number_is_not_equivalence": True,
            "namespaces_are_explicit": True,
            "partial_and_complementary_retain_both": True,
            "arkade_only_identifies_documented_dwm_gap": True,
            "dwm_only_is_not_an_arkade_test": True,
        },
        "summary": summary,
        "consistency": consistency,
        "dwm_gaps_covered_by_arkade": arkade_gap_ids,
        "overlap_arkade_test_ids": overlap_ids,
        "arkade_control_areas": areas,
        "dwm_only": dwm_only,
    }
