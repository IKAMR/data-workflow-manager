from __future__ import annotations

"""Compare historical U01/U02 with canonical results without masking failures.

A regression test can legitimately produce ``status=error`` and therefore no
``values``.  Such evidence must remain unavailable, never turn into a zero,
an empty successful result, or an unhandled KeyError that destroys the run.
"""

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
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{test_id}: forventet et JSON-objekt, fikk {type(data).__name__}")
    return data


def _require_values(document: dict[str, Any], test_id: str) -> dict[str, Any]:
    """Reject unavailable/malformed evidence with actionable test identity."""
    status = document.get("status")
    if status is not None and status != "ok":
        detail = document.get("error") or document.get("missing_sources") or "mangler resultatverdier"
        raise ValueError(f"{test_id}: status={status}; {detail}")
    values = document.get("values")
    if not isinstance(values, dict):
        raise ValueError(f"{test_id}: values mangler eller er ikke et JSON-objekt")
    return values


def _compare(legacy: Any, canonical: Any) -> dict[str, Any]:
    return {
        "legacy": legacy,
        "canonical": canonical,
        "status": "match" if legacy == canonical else "mismatch",
    }


def _unavailable(exc: Exception) -> dict[str, str]:
    return {"status": "not_comparable", "error": f"{type(exc).__name__}: {exc}"}


def build_legacy_regression_comparison(
    results_dir: str | Path,
    contract: dict[str, Any],
) -> dict[str, Any]:
    results_dir = Path(results_dir)
    cache: dict[str, dict[str, Any]] = {}

    def result(test_id: str) -> dict[str, Any]:
        if test_id not in cache:
            cache[test_id] = _load_result(results_dir, test_id)
        return cache[test_id]

    def values(test_id: str) -> dict[str, Any]:
        return _require_values(result(test_id), test_id)

    whole = {}
    for spec in contract.get("whole_extraction_comparisons", []):
        try:
            legacy = _get_path(values("kdrs.u01"), spec["legacy_path"])
            canonical = _get_path(values(spec["canonical_test"]), spec["canonical_path"])
            whole[spec["id"]] = _compare(legacy, canonical)
        except (KeyError, FileNotFoundError, OSError, ValueError, TypeError) as exc:
            whole[spec["id"]] = _unavailable(exc)

    canonical_part_cache: dict[str, dict[str, dict[str, Any]]] = {}

    def canonical_parts(test_id: str) -> dict[str, dict[str, Any]]:
        if test_id not in canonical_part_cache:
            rows = values(test_id).get("_archive_parts") or []
            if not isinstance(rows, list):
                raise ValueError(f"{test_id}: _archive_parts er ikke en liste")
            by_id = {}
            for row in rows:
                if not isinstance(row, dict):
                    continue
                archive_part = row.get("archive_part") or {}
                if not isinstance(archive_part, dict):
                    continue
                system_id = archive_part.get("system_id")
                if system_id and isinstance(row.get("values"), dict):
                    by_id[system_id] = row["values"]
            canonical_part_cache[test_id] = by_id
        return canonical_part_cache[test_id]

    archive_parts = {}
    archive_part_reference = {"status": "available"}
    try:
        legacy_rows = values("kdrs.u02").get("archive_parts") or []
        if not isinstance(legacy_rows, list):
            raise ValueError("kdrs.u02: archive_parts er ikke en liste")
    except (KeyError, FileNotFoundError, OSError, ValueError, TypeError) as exc:
        archive_part_reference = _unavailable(exc)
        legacy_rows = []

    for legacy_row in legacy_rows:
        if not isinstance(legacy_row, dict):
            continue
        identity = legacy_row.get("archive_part") or {}
        if not isinstance(identity, dict):
            identity = {}
        system_id = identity.get("system_id")
        key = system_id or str(identity.get("index"))
        checks = {}
        for spec in contract.get("archive_part_comparisons", []):
            try:
                legacy = _get_path(_require_values(legacy_row, f"kdrs.u02/{key}"), spec["legacy_path"])
                rows = canonical_parts(spec["canonical_test"])
                if system_id not in rows:
                    raise KeyError(f"archive_part:{system_id}")
                canonical = _get_path(rows[system_id], spec["canonical_path"])
                checks[spec["id"]] = _compare(legacy, canonical)
            except (KeyError, FileNotFoundError, OSError, ValueError, TypeError) as exc:
                checks[spec["id"]] = _unavailable(exc)
        archive_parts[key] = {"archive_part": identity, "checks": checks}

    statuses = [x["status"] for x in whole.values()]
    for row in archive_parts.values():
        statuses.extend(x["status"] for x in row["checks"].values())
    # Number of historical archive parts is unknowable if U02 itself failed.
    # Do not fabricate archive-part records or counts; expose missing reference
    # separately, and ensure the aggregate can never be marked as 'match'.
    missing_ref = archive_part_reference["status"] != "available"
    summary = {
        "checks": len(statuses),
        "matches": sum(s == "match" for s in statuses),
        "mismatches": sum(s == "mismatch" for s in statuses),
        "not_comparable": sum(s == "not_comparable" for s in statuses),
    }
    summary["unavailable_archive_part_reference"] = missing_ref
    summary["status"] = (
        "match" if statuses and not missing_ref and
        summary["mismatches"] == 0 and summary["not_comparable"] == 0
        else "review"
    )
    return {
        "comparison_format_version": 1,
        "purpose": "legacy_regression_reference_vs_canonical_results",
        "whole_extraction": whole,
        "archive_parts": archive_parts,
        "archive_part_reference": archive_part_reference,
        "summary": summary,
    }
