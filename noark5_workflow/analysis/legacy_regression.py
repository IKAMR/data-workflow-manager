from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def _get_path(value: Any, dotted: str) -> Any:
    current = value
    for part in dotted.split("."):
        if not isinstance(current, dict) or part not in current:
            raise KeyError(dotted)
        current = current[part]
    return current


def _load_result(results_dir: Path, test_id: str) -> dict[str, Any]:
    path = results_dir / (test_id.replace(".", "_") + ".json")
    return json.loads(path.read_text(encoding="utf-8"))


def _compare(legacy: Any, canonical: Any) -> dict[str, Any]:
    return {
        "legacy": legacy,
        "canonical": canonical,
        "status": "match" if legacy == canonical else "mismatch",
    }


def build_legacy_regression_comparison(
    results_dir: str | Path,
    contract: dict[str, Any],
) -> dict[str, Any]:
    results_dir = Path(results_dir)
    u01 = _load_result(results_dir, "kdrs.u01")
    u02 = _load_result(results_dir, "kdrs.u02")
    cache: dict[str, dict[str, Any]] = {}

    def result(test_id: str) -> dict[str, Any]:
        if test_id not in cache:
            cache[test_id] = _load_result(results_dir, test_id)
        return cache[test_id]

    whole = {}
    for spec in contract.get("whole_extraction_comparisons", []):
        try:
            legacy = _get_path(u01["values"], spec["legacy_path"])
            canonical = _get_path(result(spec["canonical_test"])["values"], spec["canonical_path"])
            whole[spec["id"]] = _compare(legacy, canonical)
        except (KeyError, FileNotFoundError) as exc:
            whole[spec["id"]] = {"status": "not_comparable", "error": str(exc)}

    canonical_part_cache: dict[str, dict[str, dict[str, Any]]] = {}

    def canonical_parts(test_id: str) -> dict[str, dict[str, Any]]:
        if test_id not in canonical_part_cache:
            rows = result(test_id)["values"].get("_archive_parts") or []
            by_id = {}
            for row in rows:
                archive_part = row.get("archive_part") or {}
                system_id = archive_part.get("system_id")
                if system_id:
                    by_id[system_id] = row.get("values") or {}
            canonical_part_cache[test_id] = by_id
        return canonical_part_cache[test_id]

    archive_parts = {}
    legacy_rows = u02["values"].get("archive_parts") or []
    for legacy_row in legacy_rows:
        identity = legacy_row.get("archive_part") or {}
        system_id = identity.get("system_id")
        key = system_id or str(identity.get("index"))
        checks = {}
        for spec in contract.get("archive_part_comparisons", []):
            try:
                legacy = _get_path(legacy_row["values"], spec["legacy_path"])
                rows = canonical_parts(spec["canonical_test"])
                if system_id not in rows:
                    raise KeyError(f"archive_part:{system_id}")
                canonical = _get_path(rows[system_id], spec["canonical_path"])
                checks[spec["id"]] = _compare(legacy, canonical)
            except (KeyError, FileNotFoundError) as exc:
                checks[spec["id"]] = {"status": "not_comparable", "error": str(exc)}
        archive_parts[key] = {
            "archive_part": identity,
            "checks": checks,
        }

    statuses = [x["status"] for x in whole.values()]
    for row in archive_parts.values():
        statuses.extend(x["status"] for x in row["checks"].values())

    summary = {
        "checks": len(statuses),
        "matches": sum(1 for s in statuses if s == "match"),
        "mismatches": sum(1 for s in statuses if s == "mismatch"),
        "not_comparable": sum(1 for s in statuses if s == "not_comparable"),
    }
    summary["status"] = (
        "match" if statuses and summary["mismatches"] == 0 and summary["not_comparable"] == 0
        else "review"
    )

    return {
        "comparison_format_version": 1,
        "purpose": "legacy_regression_reference_vs_canonical_results",
        "whole_extraction": whole,
        "archive_parts": archive_parts,
        "summary": summary,
    }
