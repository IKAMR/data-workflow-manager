from __future__ import annotations

import hashlib
import json
import re
import shutil
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


NORMALIZED_FORMAT_VERSION = 2
MANIFEST_FORMAT_VERSION = 2
SOURCE_SYSTEM = "Arkade 5"


class Arkade5ImportError(ValueError):
    pass


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise Arkade5ImportError(f"Kunne ikke lese Arkade 5-rapporten: {exc}") from exc
    if not isinstance(value, dict):
        raise Arkade5ImportError("Arkade 5-rapporten må være et JSON-objekt.")
    return value


def _validate_report(report: dict[str, Any]) -> None:
    summary = report.get("Summary")
    tests = report.get("TestsResults")
    if not isinstance(summary, dict) or not isinstance(tests, list):
        raise Arkade5ImportError(
            "Filen gjenkjennes ikke som en Arkade 5 Noark 5-testrapport "
            "(forventer Summary og TestsResults)."
        )
    invalid = [
        item
        for item in tests
        if not isinstance(item, dict)
        or not str(item.get("TestId") or "").startswith("N5.")
    ]
    if invalid:
        raise Arkade5ImportError(
            "TestsResults inneholder elementer som ikke gjenkjennes som Noark 5-tester."
        )


def _infer_source_version(source_path: Path) -> str | None:
    for part in reversed(source_path.parts):
        match = re.search(
            r"arkade5[_-]?v?(\d+(?:\.\d+)+)", part, flags=re.IGNORECASE
        )
        if match:
            return match.group(1)
    return None


def _extra(source: dict[str, Any], known: set[str]) -> dict[str, Any]:
    return {key: deepcopy(value) for key, value in source.items() if key not in known}


def _normalise_location(value: Any) -> dict[str, Any]:
    loc = value if isinstance(value, dict) else {}
    return {
        "string": loc.get("String"),
        "file_name": loc.get("FileName"),
        "line_numbers": deepcopy(loc.get("LineNumbers")),
        "source_extra": _extra(loc, {"String", "FileName", "LineNumbers"}),
        "source_raw": deepcopy(loc),
    }


def _flatten_result_set(
    result_set: dict[str, Any] | None,
    path: tuple[str, ...] = (),
) -> list[dict[str, Any]]:
    if not isinstance(result_set, dict):
        return []
    current_name = str(result_set.get("Name") or "").strip()
    current_path = path + ((current_name,) if current_name else ())
    flattened: list[dict[str, Any]] = []
    for raw in result_set.get("Results") or []:
        if not isinstance(raw, dict):
            continue
        flattened.append(
            {
                "result_type": str(raw.get("ResultType") or "").strip() or None,
                "message": str(raw.get("Message") or ""),
                "location": _normalise_location(raw.get("Location")),
                "result_set_path": list(current_path),
                "source_extra": _extra(raw, {"ResultType", "Message", "Location"}),
                "source_raw": deepcopy(raw),
            }
        )
    for child in result_set.get("ResultSets") or []:
        if isinstance(child, dict):
            flattened.extend(_flatten_result_set(child, current_path))
    return flattened


def _result_set_tree(result_set: Any) -> dict[str, Any] | None:
    if not isinstance(result_set, dict):
        return None
    return deepcopy(result_set)


def normalize_arkade5_report(
    report: dict[str, Any],
    *,
    source_file: str = "",
    source_sha256: str = "",
    source_version: str | None = None,
) -> dict[str, Any]:
    """Normalize one Arkade 5 JSON report without discarding source information."""
    _validate_report(report)
    source_summary = report.get("Summary") or {}
    tests: list[dict[str, Any]] = []

    for raw in report.get("TestsResults") or []:
        result_items = _flatten_result_set(raw.get("ResultSet"))
        try:
            error_count = int(raw.get("NumberOfErrors") or 0)
        except (TypeError, ValueError):
            error_count = 0
        result_types = {
            str(item.get("result_type") or "").casefold() for item in result_items
        }
        if error_count > 0 or "error" in result_types:
            source_status = "error"
        elif "warning" in result_types:
            source_status = "warning"
        else:
            source_status = "ok"

        tests.append(
            {
                "test_id": str(raw.get("TestId") or ""),
                "test_name": str(raw.get("TestName") or ""),
                "test_type": str(raw.get("TestType") or ""),
                "test_description": deepcopy(raw.get("TestDescription")),
                "has_results": bool(raw.get("HasResults")),
                "number_of_errors": error_count,
                "source_status": source_status,
                "results": result_items,
                "result_set_tree": _result_set_tree(raw.get("ResultSet")),
                "source_extra": _extra(
                    raw,
                    {
                        "TestId",
                        "TestName",
                        "TestType",
                        "TestDescription",
                        "ResultSet",
                        "HasResults",
                        "NumberOfErrors",
                    },
                ),
                "source_raw": deepcopy(raw),
            }
        )

    summary_known = {
        "Uuid": "uuid",
        "ArchiveType": "archive_type",
        "ArchiveCreators": "archive_creators",
        "ArchivalPeriod": "archival_period",
        "SystemName": "system_name",
        "SystemType": "system_type",
        "DateOfTesting": "date_of_testing",
        "NumberOfProcessedFiles": "number_of_processed_files",
        "NumberOfProcessedRecords": "number_of_processed_records",
        "NumberOfTestsRun": "number_of_tests_run",
        "NumberOfErrors": "number_of_errors",
        "NumberOfWarnings": "number_of_warnings",
    }
    summary = {target: deepcopy(source_summary.get(source)) for source, target in summary_known.items()}
    summary["source_extra"] = _extra(source_summary, set(summary_known))
    summary["source_raw"] = deepcopy(source_summary)

    return {
        "format_version": NORMALIZED_FORMAT_VERSION,
        "evidence_type": "external_validation_report",
        "source_system": SOURCE_SYSTEM,
        "source_version": source_version,
        "source": {"file": source_file, "sha256": source_sha256},
        "summary": summary,
        "tests": tests,
        "source_extra": _extra(report, {"Summary", "TestsResults"}),
    }


def _mapping_path() -> Path:
    return Path(__file__).with_name("arkade5_mapping.json")


def load_arkade5_mapping() -> dict[str, Any]:
    return json.loads(_mapping_path().read_text(encoding="utf-8"))


def _get_path(data: dict[str, Any], dotted: str) -> Any:
    value: Any = data
    for part in dotted.split("."):
        if not isinstance(value, dict):
            return None
        value = value.get(part)
    return value


def _messages(test: dict[str, Any]) -> Iterable[str]:
    for item in test.get("results") or []:
        message = str(item.get("message") or "").strip()
        if message:
            yield message


def _extract_arkade_value(test: dict[str, Any], selector: str) -> int | None:
    patterns: list[str]
    if selector == "total":
        patterns = [r"^Totalt:\s*(\d+)\s*$"]
    elif selector == "archive_structure_journalposts":
        patterns = [r"Antall journalposter funnet i arkivstrukturen:\s*(\d+)"]
    else:
        return None
    for message in _messages(test):
        for pattern in patterns:
            match = re.search(pattern, message, flags=re.IGNORECASE)
            if match:
                return int(match.group(1))
    return None


def build_arkade5_reconciliation(
    normalized: dict[str, Any], depot_model: dict[str, Any]
) -> dict[str, Any]:
    """Compare only runtime mappings explicitly marked equivalent and executable."""
    mapping = load_arkade5_mapping()
    tests = {
        str(item.get("test_id")): item for item in normalized.get("tests") or []
    }
    rows: list[dict[str, Any]] = []
    counts = {"match": 0, "mismatch": 0, "not_available": 0}
    for rule in mapping.get("mappings") or []:
        if rule.get("quality") != "equivalent":
            continue
        test_id = str(rule.get("arkade_test_id") or "")
        test = tests.get(test_id)
        arkade_value = (
            _extract_arkade_value(test or {}, str(rule.get("arkade_selector") or ""))
            if test
            else None
        )
        n5wf_value = _get_path(depot_model, str(rule.get("n5wf_path") or ""))
        if arkade_value is None or n5wf_value is None:
            status = "not_available"
        else:
            try:
                status = "match" if int(n5wf_value) == int(arkade_value) else "mismatch"
            except (TypeError, ValueError):
                status = "not_available"
        counts[status] += 1
        rows.append(
            {
                "arkade_test_id": test_id,
                "mapping_quality": rule.get("quality"),
                "n5wf_path": rule.get("n5wf_path"),
                "arkade_value": arkade_value,
                "n5wf_value": n5wf_value,
                "status": status,
            }
        )
    return {
        "format_version": 2,
        "comparison": "arkade5_to_dwm_depot_report",
        "source_sha256": (normalized.get("source") or {}).get("sha256"),
        "summary": counts,
        "items": rows,
        "semantic_mapping": "config/noark5/external/dwm_arkade5_mapping.json",
    }


def infer_work_operations_from_depot_report(report_path: str | Path) -> Path:
    path = Path(report_path).resolve()
    for ancestor in path.parents:
        if ancestor.name == "noark5_reports":
            return ancestor.parent
    raise Arkade5ImportError(
        "Kunne ikke finne work_operations fra depotrapportens plassering."
    )


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def import_arkade5_report(
    source_path: str | Path,
    *,
    work_operations: str | Path,
    depot_report_path: str | Path | None = None,
    imported_by: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Import Arkade evidence while preserving both source and lossless normalization."""
    source = Path(source_path)
    if not source.is_file():
        raise Arkade5ImportError(f"Arkade 5-rapporten finnes ikke: {source}")
    report = _read_json(source)
    _validate_report(report)
    digest = _sha256(source)
    summary = report.get("Summary") or {}
    raw_date = str(summary.get("DateOfTesting") or "").strip()
    month_names = {
        "januar": 1,
        "februar": 2,
        "mars": 3,
        "april": 4,
        "mai": 5,
        "juni": 6,
        "juli": 7,
        "august": 8,
        "september": 9,
        "oktober": 10,
        "november": 11,
        "desember": 12,
    }
    date = ""
    iso_match = re.search(r"(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})", raw_date)
    if iso_match:
        year, month, day = map(int, iso_match.groups())
        date = f"{year:04d}{month:02d}{day:02d}"
    else:
        no_match = re.search(
            r"(\d{1,2})\.?\s+([A-Za-zæøåÆØÅ]+)\s+(\d{4})", raw_date
        )
        if no_match:
            day = int(no_match.group(1))
            month = month_names.get(no_match.group(2).casefold())
            year = int(no_match.group(3))
            if month:
                date = f"{year:04d}{month:02d}{day:02d}"
    if not date:
        date = re.sub(r"[^0-9]", "", raw_date)[:14] or "undated"

    import_id = f"{date}-{digest[:12]}"
    work_root = Path(work_operations)
    root = work_root / "external_evidence" / "arkade5" / import_id
    source_dir = root / "source"
    normalized_dir = root / "normalized"
    reconciliation_dir = root / "reconciliation"
    source_dir.mkdir(parents=True, exist_ok=True)

    copied_source = source_dir / source.name
    if not copied_source.exists() or _sha256(copied_source) != digest:
        shutil.copy2(source, copied_source)

    normalized = normalize_arkade5_report(
        report,
        source_file=source.name,
        source_sha256=digest,
        source_version=_infer_source_version(source),
    )
    normalized_path = normalized_dir / "arkade5_results.json"
    _write_json(normalized_path, normalized)

    reconciliation_path = None
    reconciliation = None
    if depot_report_path is not None:
        depot_path = Path(depot_report_path)
        try:
            depot_model = json.loads(depot_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise Arkade5ImportError(
                f"Kunne ikke lese DWM depotrapporten: {exc}"
            ) from exc
        reconciliation = build_arkade5_reconciliation(normalized, depot_model)
        reconciliation_path = reconciliation_dir / "arkade5_dwm_reconciliation.json"
        _write_json(reconciliation_path, reconciliation)

    manifest = {
        "format_version": MANIFEST_FORMAT_VERSION,
        "import_id": import_id,
        "evidence_source": SOURCE_SYSTEM,
        "imported_at": _utc_now(),
        "imported_by": dict(imported_by or {}),
        "source": {
            "original_name": source.name,
            "sha256": digest,
            "preserved_file": str(copied_source.relative_to(work_root)),
        },
        "normalized_file": str(normalized_path.relative_to(work_root)),
        "normalized_format_version": NORMALIZED_FORMAT_VERSION,
        "reconciliation_file": (
            str(reconciliation_path.relative_to(work_root))
            if reconciliation_path
            else None
        ),
        "semantic_mapping": "config/noark5/external/dwm_arkade5_mapping.json",
        "source_summary": normalized.get("summary"),
        "reconciliation_summary": (reconciliation or {}).get("summary"),
    }
    _write_json(root / "manifest.json", manifest)
    return manifest


def list_arkade5_imports(work_operations: str | Path) -> list[dict[str, Any]]:
    root = Path(work_operations) / "external_evidence" / "arkade5"
    if not root.is_dir():
        return []
    imports: list[dict[str, Any]] = []
    for manifest_path in root.glob("*/manifest.json"):
        try:
            value = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError):
            continue
        if isinstance(value, dict):
            value = dict(value)
            value["manifest_path"] = str(manifest_path)
            imports.append(value)
    return sorted(
        imports, key=lambda item: str(item.get("imported_at") or ""), reverse=True
    )


def load_arkade5_import(
    work_operations: str | Path, import_id: str
) -> dict[str, Any]:
    root = Path(work_operations) / "external_evidence" / "arkade5" / import_id
    manifest = _read_json(root / "manifest.json")
    normalized = _read_json(
        Path(work_operations) / str(manifest.get("normalized_file"))
    )
    reconciliation = None
    rec_file = manifest.get("reconciliation_file")
    if rec_file:
        reconciliation = _read_json(Path(work_operations) / str(rec_file))
    return {
        "manifest": manifest,
        "normalized": normalized,
        "reconciliation": reconciliation,
    }
