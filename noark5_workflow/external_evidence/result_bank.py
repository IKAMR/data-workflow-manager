from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .arkade5 import list_arkade5_imports, load_arkade5_import
from .arkade5_coverage import build_arkade5_coverage
from .kdrs_query import list_kdrs_query_imports, load_kdrs_query_import


BANK_FORMAT_VERSION = 2
BANK_FILENAME = "result-bank.json"


def _coverage_by_test(normalized: dict[str, Any]) -> dict[str, dict[str, Any]]:
    coverage = build_arkade5_coverage(normalized)
    return {
        str(item.get("arkade_test_id") or ""): item
        for item in coverage.get("items") or []
        if isinstance(item, dict)
    }


def _reconciliation_by_test(
    reconciliation: dict[str, Any] | None,
) -> dict[str, dict[str, Any]]:
    value = reconciliation or {}
    return {
        str(item.get("arkade_test_id") or ""): item
        for item in value.get("items") or []
        if isinstance(item, dict)
    }


def _relationship(reconciliation_row: dict[str, Any] | None) -> str:
    if reconciliation_row is None:
        return "external_only_or_unmapped"

    status = str(reconciliation_row.get("status") or "")
    if status == "match":
        return "corroborates_internal"
    if status == "mismatch":
        return "conflicts_with_internal"
    return "comparison_not_available"


def _group_summary(resources: list[dict[str, Any]]) -> dict[str, int]:
    return {
        "resources": len(resources),
        "corroborates_internal": sum(
            row["relationship_to_internal"] == "corroborates_internal"
            for row in resources
        ),
        "conflicts_with_internal": sum(
            row["relationship_to_internal"] == "conflicts_with_internal"
            for row in resources
        ),
        "comparison_not_available": sum(
            row["relationship_to_internal"] == "comparison_not_available"
            for row in resources
        ),
        "external_only_or_unmapped": sum(
            row["relationship_to_internal"] == "external_only_or_unmapped"
            for row in resources
        ),
    }


def _kdrs_query_resources(
    import_id: str,
    manifest: dict[str, Any],
    normalized_by_type: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    resources: list[dict[str, Any]] = []
    file_by_type = {
        str(row.get("report_type") or ""): row
        for row in manifest.get("files") or []
        if isinstance(row, dict)
    }

    for report_type, normalized in normalized_by_type.items():
        source = normalized.get("source") or {}
        file_row = file_by_type.get(report_type) or {}
        sections = normalized.get("sections") or []
        for index, section in enumerate(sections, start=1):
            if not isinstance(section, dict):
                continue
            test_id = str(section.get("test_id") or "")
            legacy_job_id = str(section.get("legacy_job_id") or "")
            resource = {
                "resource_id": f"kdrs_query:{import_id}:{report_type}:{index}:{test_id or legacy_job_id or 'section'}",
                "role": "external_result_resource",
                "authoritative_internal_master": False,
                "source_system": "KDRS Query",
                "source_version": normalized.get("source_tool_version"),
                "source_import_id": import_id,
                "source_file": source.get("file") or file_row.get("original_name"),
                "source_sha256": source.get("sha256") or file_row.get("sha256"),
                "source_test_date": None,
                "report_type": report_type,
                "test_id": test_id or f"legacy.{legacy_job_id.casefold()}",
                "legacy_job_id": legacy_job_id,
                "test_point": section.get("test_point"),
                "test_name": section.get("name"),
                "status": "imported",
                "has_results": bool(section.get("lines")),
                "results": section.get("lines") or [],
                "raw_text": section.get("raw_text"),
                "archive_part_index": section.get("archive_part_index"),
                "archive_part_title": section.get("archive_part_title"),
                "definition_source": normalized.get("definition_source"),
                "coverage_classification": (
                    "mapped_to_dwm_test" if str(section.get("test_id") or "").startswith("kdrs.")
                    else "historical_reference"
                ),
                "coverage_reason": (
                    "Legacy test-ID/testpunkt er koblet til DWM XPath-katalogen."
                    if str(section.get("test_id") or "").startswith("kdrs.")
                    else "U1/U2 beholdes som historisk/regresjonsbasert evidens."
                ),
                "dwm_candidates": (
                    [str(section.get("test_id"))]
                    if str(section.get("test_id") or "").startswith("kdrs.")
                    else []
                ),
                "relationship_to_internal": "comparison_not_available",
                "reconciliation": None,
            }
            resources.append(resource)
    return resources


def build_external_result_bank(work_operations: str | Path) -> dict[str, Any]:
    """Build reusable external result resources grouped by source run/report.

    Every imported external report/run remains a distinct source group. External
    evidence may supplement DWM coverage but never replaces internal master data.
    """
    work = Path(work_operations)
    resources: list[dict[str, Any]] = []
    groups: list[dict[str, Any]] = []

    for manifest in list_arkade5_imports(work):
        import_id = str(manifest.get("import_id") or "")
        if not import_id:
            continue

        loaded = load_arkade5_import(work, import_id)
        normalized = loaded.get("normalized") or {}
        reconciliation = loaded.get("reconciliation") or {}
        coverage_by_test = _coverage_by_test(normalized)
        reconciliation_by_test = _reconciliation_by_test(reconciliation)

        source = normalized.get("source") or {}
        summary = normalized.get("summary") or {}

        group_resources: list[dict[str, Any]] = []

        for test in normalized.get("tests") or []:
            if not isinstance(test, dict):
                continue

            test_id = str(test.get("test_id") or "")
            coverage = coverage_by_test.get(test_id) or {}
            rec = reconciliation_by_test.get(test_id)

            resource = {
                "resource_id": f"arkade5:{import_id}:{test_id}",
                "role": "external_result_resource",
                "authoritative_internal_master": False,
                "source_system": "Arkade 5",
                "source_version": normalized.get("source_version"),
                "source_import_id": import_id,
                "source_file": source.get("file"),
                "source_sha256": source.get("sha256"),
                "source_test_date": summary.get("date_of_testing"),
                "test_id": test_id,
                "test_name": test.get("test_name"),
                "test_type": test.get("test_type"),
                "test_description": test.get("test_description"),
                "status": test.get("source_status"),
                "number_of_errors": test.get("number_of_errors"),
                "has_results": bool(test.get("has_results")),
                "results": test.get("results") or [],
                "coverage_classification": coverage.get("classification"),
                "coverage_reason": coverage.get("reason"),
                "dwm_candidates": coverage.get("dwm_candidates") or [],
                "relationship_to_internal": _relationship(rec),
                "reconciliation": rec,
            }
            group_resources.append(resource)
            resources.append(resource)

        groups.append({
            "group_id": f"arkade5:{import_id}",
            "source_system": "Arkade 5",
            "source_version": normalized.get("source_version"),
            "source_import_id": import_id,
            "source_file": source.get("file"),
            "source_sha256": source.get("sha256"),
            "source_test_date": summary.get("date_of_testing"),
            "source_number_of_tests": summary.get("number_of_tests_run"),
            "source_number_of_errors": summary.get("number_of_errors"),
            "source_number_of_warnings": summary.get("number_of_warnings"),
            "summary": _group_summary(group_resources),
            "resources": group_resources,
        })

    for manifest in list_kdrs_query_imports(work):
        import_id = str(manifest.get("import_id") or "")
        if not import_id:
            continue
        loaded = load_kdrs_query_import(work, import_id)
        normalized_by_type = loaded.get("normalized") or {}
        group_resources = _kdrs_query_resources(import_id, manifest, normalized_by_type)
        resources.extend(group_resources)
        source_files = [
            str(row.get("original_name") or "")
            for row in manifest.get("files") or []
            if isinstance(row, dict)
        ]
        groups.append({
            "group_id": f"kdrs_query:{import_id}",
            "source_system": "KDRS Query",
            "source_version": "0.6",
            "source_import_id": import_id,
            "source_file": "; ".join(value for value in source_files if value),
            "source_sha256": None,
            "source_test_date": None,
            "report_types": manifest.get("report_types") or [],
            "summary": _group_summary(group_resources),
            "resources": group_resources,
        })

    return {
        "format_version": BANK_FORMAT_VERSION,
        "bank_type": "external_test_result_resources",
        "principle": (
            "Eksterne testresultater beholdes som kildeangitte ressurser. "
            "De kan supplere DWM-dekning, men overstyrer aldri autoritative "
            "interne masterresultater."
        ),
        "summary": _group_summary(resources),
        "groups": groups,
        "resources": resources,
    }


def write_external_result_bank(work_operations: str | Path) -> Path:
    work = Path(work_operations)
    target = work / "external_evidence" / BANK_FILENAME
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(
            build_external_result_bank(work),
            ensure_ascii=False,
            indent=2,
        ) + "\n",
        encoding="utf-8",
    )
    return target
