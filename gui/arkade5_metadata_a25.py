
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


_TIMESTAMP_RE = re.compile(r"(?<!\d)(20\d{12})(?!\d)")


def _display_timestamp(value: str | None) -> str | None:
    raw = str(value or "").strip()
    if len(raw) != 14 or not raw.isdigit():
        return None
    return (
        f"{raw[6:8]}.{raw[4:6]}.{raw[0:4]} "
        f"{raw[8:10]}:{raw[10:12]}:{raw[12:14]}"
    )


def report_timestamp_from_filename(filename: str | None) -> str | None:
    """Return a clearly labelled filename timestamp, never a fabricated test date."""
    match = _TIMESTAMP_RE.search(str(filename or ""))
    return _display_timestamp(match.group(1)) if match else None


def enrich_arkade5_import(work_operations: str | Path, manifest: dict[str, Any]) -> dict[str, Any]:
    """Add display metadata from preserved normalized evidence.

    Old manifests did not persist source_version.  The normalized evidence does,
    so the GUI may safely enrich the presentation without rewriting evidence.
    """
    work = Path(work_operations)
    row = dict(manifest or {})
    source = dict(row.get("source") or {})
    summary = dict(row.get("source_summary") or {})

    normalized = {}
    normalized_file = str(row.get("normalized_file") or "").strip()
    if normalized_file:
        path = work / normalized_file
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(value, dict):
                normalized = value
        except (OSError, UnicodeError, json.JSONDecodeError):
            normalized = {}

    if not summary and isinstance(normalized.get("summary"), dict):
        summary = dict(normalized["summary"])
        row["source_summary"] = summary

    source_version = row.get("source_version") or normalized.get("source_version")
    row["source_version"] = source_version

    normalized_source = normalized.get("source") or {}
    source_file = (
        source.get("original_name")
        or normalized_source.get("file")
        or row.get("source_file")
        or row.get("source_path")
    )
    row["display_source_file"] = source_file

    test_date = summary.get("date_of_testing")
    row["display_test_date"] = test_date
    row["display_filename_timestamp"] = (
        report_timestamp_from_filename(source_file) if not test_date else None
    )
    return row


def enrich_arkade5_imports(
    work_operations: str | Path,
    imports: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    return [enrich_arkade5_import(work_operations, item) for item in imports]


def test_date_text(item: dict[str, Any]) -> str:
    date = item.get("display_test_date")
    if date:
        return str(date)
    inferred = item.get("display_filename_timestamp")
    if inferred:
        return f"ikke oppgitt (rapportfil: {inferred})"
    return "ikke oppgitt"


def version_text(item: dict[str, Any]) -> str:
    value = str(item.get("source_version") or "").strip()
    return value or "ikke oppgitt"
