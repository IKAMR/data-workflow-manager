from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable


FORMAT_VERSION = 1


def _mapping_path() -> Path:
    return (
        Path(__file__).resolve().parents[2]
        / "config"
        / "noark5"
        / "external"
        / "dwm_arkade5_mapping.json"
    )


def _catalog_path() -> Path:
    return (
        Path(__file__).resolve().parents[2]
        / "config"
        / "noark5"
        / "external"
        / "arkade5_test_catalog.json"
    )


def _load_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _normalise_dwm_ids(values: Iterable[str] | None) -> set[str]:
    return {str(value).strip() for value in (values or []) if str(value).strip()}


def build_combined_coverage(
    *,
    arkade_normalized: dict[str, Any] | None = None,
    dwm_test_ids_present: Iterable[str] | None = None,
    mapping: dict[str, Any] | None = None,
    arkade_catalog: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build one coverage view without merging the meaning of DWM and Arkade.

    The model answers which implementation supplied evidence for each Arkade
    Noark 5 control area. It does not promote Arkade results to DWM master
    results and does not infer semantic equivalence from a shared number.
    """
    mapping = mapping or _load_json(_mapping_path())
    arkade_catalog = arkade_catalog or _load_json(_catalog_path())
    dwm_present = _normalise_dwm_ids(dwm_test_ids_present)
    arkade_tests = {
        str(item.get("test_id") or "").upper(): item
        for item in (arkade_normalized or {}).get("tests") or []
        if str(item.get("test_id") or "").strip()
    }
    catalog_tests = {
        str(item.get("arkade_test_id") or "").upper(): item
        for item in arkade_catalog.get("tests") or []
    }

    rows: list[dict[str, Any]] = []
    summary = {
        "control_areas": 0,
        "covered_by_both": 0,
        "covered_by_arkade": 0,
        "covered_by_dwm": 0,
        "not_covered_in_run": 0,
        "arkade_errors": 0,
        "arkade_warnings": 0,
    }

    for rule in mapping.get("arkade_to_dwm") or []:
        arkade_id = str(rule.get("arkade_test_id") or "").upper()
        relation = str(rule.get("relation") or rule.get("coverage") or "unmapped")
        dwm_ids = [str(value) for value in rule.get("dwm_test_ids") or []]
        present_dwm = [value for value in dwm_ids if value in dwm_present]
        arkade_test = arkade_tests.get(arkade_id)
        arkade_present = arkade_test is not None
        dwm_present_for_area = bool(present_dwm)

        if arkade_present and dwm_present_for_area:
            combined_status = "covered_by_both"
        elif arkade_present:
            combined_status = "covered_by_arkade"
        elif dwm_present_for_area:
            combined_status = "covered_by_dwm"
        else:
            combined_status = "not_covered_in_run"

        summary[combined_status] += 1
        summary["control_areas"] += 1

        arkade_status = str((arkade_test or {}).get("source_status") or "not_present")
        if arkade_status == "error":
            summary["arkade_errors"] += 1
        elif arkade_status == "warning":
            summary["arkade_warnings"] += 1

        catalog = catalog_tests.get(arkade_id) or {}
        rows.append(
            {
                "control_id": f"arkade:{arkade_id}",
                "arkade_test_id": arkade_id,
                "arkade_test_name": catalog.get("name_nb")
                or (arkade_test or {}).get("test_name"),
                "arkade_type": catalog.get("arkade_type")
                or (arkade_test or {}).get("test_type"),
                "relation": relation,
                "combined_status": combined_status,
                "coverage_strategy": (
                    "arkade_fills_dwm_gap" if relation == "arkade_only" else "retain_both_sources"
                ),
                "dwm_test_ids": dwm_ids,
                "dwm_test_ids_present": present_dwm,
                "arkade": {
                    "present": arkade_present,
                    "status": arkade_status,
                    "number_of_errors": int((arkade_test or {}).get("number_of_errors") or 0),
                    "result_count": len((arkade_test or {}).get("results") or []),
                },
                "note_nb": rule.get("note_nb"),
            }
        )

    dwm_only_rows = []
    for item in mapping.get("dwm_only") or []:
        dwm_id = str(item.get("dwm_test_id") or "")
        dwm_only_rows.append(
            {
                "control_id": f"dwm:{dwm_id}",
                "dwm_test_id": dwm_id,
                "legacy_namespace_id": item.get("legacy_namespace_id"),
                "present": dwm_id in dwm_present,
                "relation": "dwm_only",
                "note_nb": item.get("note_nb"),
            }
        )

    return {
        "format_version": FORMAT_VERSION,
        "model_id": "noark5.combined-dwm-arkade5-coverage.v1",
        "principles": {
            "arkade_does_not_become_dwm_master": True,
            "raw_source_identity_is_preserved": True,
            "same_number_is_not_equivalence": True,
            "arkade_can_fill_documented_dwm_gaps": True,
        },
        "mapping_id": mapping.get("mapping_id"),
        "arkade_catalog_id": arkade_catalog.get("catalog_id"),
        "summary": summary,
        "arkade_control_areas": rows,
        "dwm_only": dwm_only_rows,
    }
