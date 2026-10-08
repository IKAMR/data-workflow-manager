from __future__ import annotations

import hashlib
import json
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from noark5_workflow.core.work_paths import resolve_dwm_work_root, resolve_work_operations_base
from typing import Any, Iterable


NORMALIZED_FORMAT_VERSION = 1
MANIFEST_FORMAT_VERSION = 1
SOURCE_SYSTEM = "KDRS Query"

_DEFINITION_BY_TYPE = {
    "standard": "docs/reference/kdrs-query/xml-queries_noark5_2026-05-26.txt",
    "u01": "docs/reference/kdrs-query/xml-queries_noark5_2026-05-26_U1.txt",
    "u02": "docs/reference/kdrs-query/xml-queries_noark5_2026-05-26_U2.txt",
}


class KdrsQueryImportError(ValueError):
    pass


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_text(path: Path) -> tuple[str, str]:
    data = path.read_bytes()
    attempts = (
        ("utf-8-sig", "utf-8-sig"),
        ("utf-8", "utf-8"),
        ("cp1252", "cp1252"),
        ("latin-1", "latin-1"),
    )
    for codec, label in attempts:
        try:
            return data.decode(codec), label
        except UnicodeDecodeError:
            continue
    raise KdrsQueryImportError(f"Kunne ikke dekode tekstfilen: {path}")


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _catalog_path() -> Path:
    return _repo_root() / "config" / "noark5" / "tests" / "xpath_catalog_2026_05_26.json"


def _load_catalog() -> tuple[dict[str, dict[str, Any]], dict[str, list[dict[str, Any]]]]:
    try:
        raw = json.loads(_catalog_path().read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise KdrsQueryImportError(f"Kunne ikke lese DWM XPath-katalogen: {exc}") from exc

    by_job: dict[str, dict[str, Any]] = {}
    by_point: dict[str, list[dict[str, Any]]] = {}
    for row in raw.get("tests") or []:
        if not isinstance(row, dict):
            continue
        legacy = row.get("legacy") or {}
        job_id = str(legacy.get("job_id") or "").strip().upper()
        test_point = str(legacy.get("test_point") or "").strip().upper()
        item = {
            "legacy_job_id": job_id,
            "test_id": str(row.get("test_id") or ""),
            "test_point": test_point,
            "name": str(row.get("name") or ""),
            "source_xml": str(row.get("source_xml") or ""),
        }
        if job_id:
            by_job[job_id] = item
        if test_point:
            by_point.setdefault(test_point, []).append(item)
    return by_job, by_point


def detect_report_type(path: str | Path, text: str | None = None) -> str:
    source = Path(path)
    name = source.name.casefold()
    if text is None:
        text, _encoding = _read_text(source)
    sample = text[:20000]

    if re.search(r"(?im)^\s*U2\.?\s*N5\.102\b", sample) or re.search(
        r"(?i)(?:^|[_-])U0?2(?:[_\-.]|$)", source.name
    ):
        return "u02"
    if re.search(r"(?im)^\s*U1\.?\s*N5\.101\b", sample) or re.search(
        r"(?i)(?:^|[_-])U0?1(?:[_\-.]|$)", source.name
    ):
        return "u01"
    if "u02" in name or "_u2" in name:
        return "u02"
    if "u01" in name or "_u1" in name:
        return "u01"
    if re.search(r"(?i)\bN5\.\d+(?:\.\d+)?\b", sample):
        return "standard"
    raise KdrsQueryImportError(
        f"Filen gjenkjennes ikke som KDRS Query standard/U1/U2-output: {source.name}"
    )


def _number(value: str) -> int | float | str:
    compact = value.strip().replace(" ", "")
    if re.fullmatch(r"-?\d+", compact):
        try:
            return int(compact)
        except ValueError:
            pass
    if re.fullmatch(r"-?\d+[,.]\d+", compact):
        try:
            return float(compact.replace(",", "."))
        except ValueError:
            pass
    return value.strip()


def _parse_line(line: str) -> dict[str, Any]:
    values: list[dict[str, Any]] = []
    for match in re.finditer(r"([^;,@\n]{1,120}?):\s*(-?\d[\d ]*(?:[,.]\d+)?)\b", line):
        label = re.sub(r"\s+", " ", match.group(1)).strip(" ;,@")
        if not label:
            continue
        values.append({"label": label, "value": _number(match.group(2))})

    year_counts: dict[str, int] = {}
    for match in re.finditer(r"(?<!\d)(18\d{2}|19\d{2}|20\d{2}|21\d{2})\s*:\s*(\d+)\b", line):
        year_counts[match.group(1)] = int(match.group(2))

    return {
        "text": line,
        "values": values,
        "year_counts": year_counts,
    }


def _point_candidates(line: str) -> list[str]:
    return [value.upper() for value in re.findall(r"(?i)\bN5\.\d+(?:\.\d+)?(?:/\d+(?:\.\d+)?)?\b", line)]


def _match_catalog_row(
    line: str,
    by_job: dict[str, dict[str, Any]],
    by_point: dict[str, list[dict[str, Any]]],
) -> dict[str, Any] | None:
    upper = line.upper()
    # Prefer explicit legacy job identifiers when the report contains them.
    for job_id in sorted(by_job, key=len, reverse=True):
        if re.search(rf"(?<![A-Z0-9.]){re.escape(job_id)}(?![A-Z0-9.])", upper):
            return by_job[job_id]

    for point in _point_candidates(line):
        candidates = list(by_point.get(point) or [])
        if len(candidates) == 1:
            return candidates[0]
        if candidates:
            # The 2026 catalog can contain derived/archive-part tests that keep
            # the same legacy N5 test point as the original KDRS Query job.
            # A historic standard report refers to the original legacy job, so
            # prefer the plain legacy identifier (C09, C16, ...), not derived
            # identifiers such as C09_R4/C16_R6.
            canonical = [
                row for row in candidates
                if re.fullmatch(r"[A-Z]+\d+(?:\.\d+)?", str(row.get("legacy_job_id") or ""))
            ]
            if len(canonical) == 1:
                return canonical[0]

        # Some legacy output labels combine points, e.g. N5.05/06.
        prefix = point.split("/")[0]
        matching = [row for key, rows in by_point.items() if key.startswith(prefix) for row in rows]
        canonical = [
            row for row in matching
            if re.fullmatch(r"[A-Z]+\d+(?:\.\d+)?", str(row.get("legacy_job_id") or ""))
        ]
        unique = {row["test_id"]: row for row in (canonical or matching)}
        if len(unique) == 1:
            return next(iter(unique.values()))
    return None


def _section_payload(meta: dict[str, Any], lines: list[str]) -> dict[str, Any]:
    return {
        **meta,
        "line_count": len(lines),
        "lines": [_parse_line(line) for line in lines],
        "raw_text": "\n".join(lines),
    }


def _normalize_standard(text: str) -> dict[str, Any]:
    by_job, by_point = _load_catalog()
    sections: list[dict[str, Any]] = []
    unassigned: list[str] = []
    current_meta: dict[str, Any] | None = None
    current_lines: list[str] = []

    def flush() -> None:
        nonlocal current_meta, current_lines
        if current_meta is not None:
            sections.append(_section_payload(current_meta, current_lines))
        current_meta = None
        current_lines = []

    for raw in text.splitlines():
        line = raw.rstrip("\r\n")
        match = _match_catalog_row(line, by_job, by_point)
        if match is not None and (
            current_meta is None or match.get("test_id") != current_meta.get("test_id")
        ):
            flush()
            current_meta = dict(match)
        if current_meta is None:
            unassigned.append(line)
        else:
            current_lines.append(line)
    flush()

    return {
        "report_type": "standard",
        "sections": sections,
        "unassigned_lines": [_parse_line(line) for line in unassigned],
        "summary": {
            "section_count": len(sections),
            "mapped_test_count": len({row.get("test_id") for row in sections if row.get("test_id")}),
            "source_line_count": len(text.splitlines()),
            "unassigned_line_count": len(unassigned),
        },
    }


def _split_embedded_definition(text: str, report_type: str) -> tuple[list[str], list[str]]:
    """Split KDRS Query's echoed query definition from the actual U1/U2 output.

    Historical KDRS Query result files can contain the complete query definition
    before the evaluated output.  The result marker itself is unquoted while the
    definition contains the same text inside a quoted XQuery literal.
    """
    lines = text.splitlines()
    marker = (
        re.compile(r"^\s*U1\.\s*N5\.101\b", flags=re.IGNORECASE)
        if report_type == "u01"
        else re.compile(r"^\s*U2\.\s*N5\.102\b", flags=re.IGNORECASE)
    )
    for index, line in enumerate(lines):
        if marker.search(line):
            return lines[:index], lines[index:]
    return [], lines


def _normalize_u01(text: str) -> dict[str, Any]:
    definition_lines, lines = _split_embedded_definition(text, "u01")
    return {
        "report_type": "u01",
        "scope": "whole_extraction",
        "legacy_job_id": "U01",
        "test_point": "N5.101",
        "sections": [
            _section_payload(
                {
                    "legacy_job_id": "U01",
                    "test_id": "legacy.u01",
                    "test_point": "N5.101",
                    "name": "Konsentrert opptelling for hele Noark 5-uttrekket",
                },
                lines,
            )
        ],
        "definition_preamble": [_parse_line(line) for line in definition_lines],
        "summary": {
            "section_count": 1,
            "source_line_count": len(text.splitlines()),
            "result_line_count": len(lines),
            "definition_line_count": len(definition_lines),
        },
    }


def _normalize_u02(text: str) -> dict[str, Any]:
    definition_lines, lines = _split_embedded_definition(text, "u02")
    preamble: list[str] = []
    parts: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    current_lines: list[str] = []

    def flush() -> None:
        nonlocal current, current_lines
        if current is None:
            return
        payload = _section_payload(current, current_lines)
        payload["archive_part_index"] = current.get("archive_part_index")
        payload["archive_part_title"] = current.get("archive_part_title")
        parts.append(payload)
        current = None
        current_lines = []

    pattern = re.compile(r"^\s*Arkivdel\s+(\d+)\s*:\s*(.*)$", flags=re.IGNORECASE)
    for line in lines:
        match = pattern.match(line)
        if match:
            flush()
            current = {
                "legacy_job_id": "U02",
                "test_id": f"legacy.u02.archive_part.{int(match.group(1))}",
                "test_point": "N5.102",
                "name": "Konsentrert opptelling pr. arkivdel",
                "archive_part_index": int(match.group(1)),
                "archive_part_title": match.group(2).strip(),
            }
            current_lines = [line]
            continue
        if current is None:
            preamble.append(line)
        else:
            current_lines.append(line)
    flush()

    # Some historical variants may not contain an explicit Arkivdel <n>: line.
    # Preserve the whole output as one section rather than dropping data.
    if not parts:
        parts = [
            _section_payload(
                {
                    "legacy_job_id": "U02",
                    "test_id": "legacy.u02",
                    "test_point": "N5.102",
                    "name": "Konsentrert opptelling pr. arkivdel",
                    "archive_part_index": None,
                    "archive_part_title": None,
                },
                lines,
            )
        ]
        preamble = []

    return {
        "report_type": "u02",
        "scope": "archive_part",
        "legacy_job_id": "U02",
        "test_point": "N5.102",
        "definition_preamble": [_parse_line(line) for line in definition_lines],
        "preamble": [_parse_line(line) for line in preamble],
        "sections": parts,
        "summary": {
            "section_count": len(parts),
            "archive_part_count": sum(1 for row in parts if row.get("archive_part_index") is not None),
            "source_line_count": len(text.splitlines()),
            "result_line_count": len(lines),
            "definition_line_count": len(definition_lines),
        },
    }


def normalize_kdrs_query_output(
    text: str,
    *,
    report_type: str,
    source_file: str,
    source_sha256: str,
    source_encoding: str,
) -> dict[str, Any]:
    kind = str(report_type).casefold()
    if kind == "standard":
        body = _normalize_standard(text)
    elif kind == "u01":
        body = _normalize_u01(text)
    elif kind == "u02":
        body = _normalize_u02(text)
    else:
        raise KdrsQueryImportError(f"Ukjent KDRS Query rapporttype: {report_type}")

    return {
        "format_version": NORMALIZED_FORMAT_VERSION,
        "evidence_type": "external_xpath_result",
        "source_system": SOURCE_SYSTEM,
        "source_tool_name": "XML Queries",
        "source_tool_version": "0.6",
        "definition_source": _DEFINITION_BY_TYPE[kind],
        "source": {
            "file": source_file,
            "sha256": source_sha256,
            "encoding": source_encoding,
        },
        **body,
    }


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def migrate_legacy_kdrs_query_storage(
    *,
    work_operations: str | Path,
    legacy_work_operations: str | Path | None = None,
) -> dict[str, Any]:
    """Copy short-lived misplaced KDRS evidence into the effective DWM area.

    Legacy files are deliberately left untouched until the operator has
    verified the migrated copy.
    """
    work = resolve_dwm_work_root(work_operations)
    legacy_work = (
        Path(legacy_work_operations)
        if legacy_work_operations is not None
        else resolve_work_operations_base(work_operations)
    )
    legacy_root = legacy_work / "external_evidence" / "kdrs_query"
    target_root = work / "external_evidence" / "kdrs_query"
    migrated = 0
    if legacy_work != work and legacy_root.is_dir():
        target_root.mkdir(parents=True, exist_ok=True)
        for legacy_import in legacy_root.iterdir():
            if not legacy_import.is_dir():
                continue
            target = target_root / legacy_import.name
            existed = target.is_dir()
            shutil.copytree(legacy_import, target, dirs_exist_ok=True)
            if not existed:
                migrated += 1
    return {
        "work_root": str(work),
        "legacy_root": str(legacy_root),
        "target_root": str(target_root),
        "migrated_imports": migrated,
    }


def import_kdrs_query_reports(
    source_paths: Iterable[str | Path],
    *,
    work_operations: str | Path,
    imported_by: dict[str, str] | None = None,
    legacy_work_operations: str | Path | None = None,
) -> dict[str, Any]:
    sources = [Path(value) for value in source_paths]
    if not sources:
        raise KdrsQueryImportError("Ingen KDRS Query-resultatfiler er valgt.")

    prepared: list[dict[str, Any]] = []
    seen_types: set[str] = set()
    for source in sources:
        if not source.is_file():
            raise KdrsQueryImportError(f"Filen finnes ikke: {source}")
        text, encoding = _read_text(source)
        report_type = detect_report_type(source, text)
        if report_type in seen_types:
            raise KdrsQueryImportError(
                f"Det er valgt mer enn én {report_type.upper()}-fil. Velg én standard, én U1 og én U2 per import."
            )
        seen_types.add(report_type)
        digest = _sha256(source)
        prepared.append(
            {
                "path": source,
                "text": text,
                "encoding": encoding,
                "report_type": report_type,
                "sha256": digest,
            }
        )

    combined = hashlib.sha256()
    for row in sorted(prepared, key=lambda item: item["report_type"]):
        combined.update(str(row["report_type"]).encode("utf-8"))
        combined.update(str(row["sha256"]).encode("ascii"))
    import_id = f"kdrs-{combined.hexdigest()[:16]}"

    work = resolve_dwm_work_root(work_operations)

    # a2-fix: preserve any short-lived misplaced imports before writing the
    # current import into the authoritative DWM/job area.
    migrate_legacy_kdrs_query_storage(
        work_operations=work_operations,
        legacy_work_operations=legacy_work_operations,
    )

    root = work / "external_evidence" / "kdrs_query" / import_id
    source_dir = root / "source"
    normalized_dir = root / "normalized"
    source_dir.mkdir(parents=True, exist_ok=True)

    files: list[dict[str, Any]] = []
    for row in prepared:
        source = row["path"]
        report_type = str(row["report_type"])
        copied = source_dir / f"{report_type}__{source.name}"
        if not copied.exists() or _sha256(copied) != row["sha256"]:
            shutil.copy2(source, copied)

        normalized = normalize_kdrs_query_output(
            str(row["text"]),
            report_type=report_type,
            source_file=source.name,
            source_sha256=str(row["sha256"]),
            source_encoding=str(row["encoding"]),
        )
        normalized_path = normalized_dir / f"{report_type}.json"
        _write_json(normalized_path, normalized)
        files.append(
            {
                "report_type": report_type,
                "original_name": source.name,
                "sha256": row["sha256"],
                "encoding": row["encoding"],
                "preserved_file": str(copied.relative_to(work)),
                "normalized_file": str(normalized_path.relative_to(work)),
                "definition_source": _DEFINITION_BY_TYPE[report_type],
                "summary": normalized.get("summary") or {},
            }
        )

    manifest = {
        "format_version": MANIFEST_FORMAT_VERSION,
        "import_id": import_id,
        "evidence_source": SOURCE_SYSTEM,
        "imported_at": _utc_now(),
        "imported_by": dict(imported_by or {}),
        "files": sorted(files, key=lambda item: item["report_type"]),
        "report_types": sorted(seen_types),
        "principle": (
            "KDRS Query-output bevares som ekstern/historisk evidens og overstyrer ikke DWM sine autoritative masterresultater."
        ),
    }
    _write_json(root / "manifest.json", manifest)
    return manifest


def list_kdrs_query_imports(work_operations: str | Path) -> list[dict[str, Any]]:
    root = resolve_dwm_work_root(work_operations) / "external_evidence" / "kdrs_query"
    if not root.is_dir():
        return []
    rows: list[dict[str, Any]] = []
    for manifest_path in root.glob("*/manifest.json"):
        try:
            value = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError):
            continue
        if isinstance(value, dict):
            row = dict(value)
            row["manifest_path"] = str(manifest_path)
            rows.append(row)
    return sorted(rows, key=lambda item: str(item.get("imported_at") or ""), reverse=True)


def load_kdrs_query_import(work_operations: str | Path, import_id: str) -> dict[str, Any]:
    work = resolve_dwm_work_root(work_operations)
    root = work / "external_evidence" / "kdrs_query" / import_id
    try:
        manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise KdrsQueryImportError(f"Kunne ikke lese KDRS Query-manifest: {exc}") from exc

    normalized: dict[str, dict[str, Any]] = {}
    for row in manifest.get("files") or []:
        if not isinstance(row, dict):
            continue
        report_type = str(row.get("report_type") or "")
        rel = str(row.get("normalized_file") or "")
        if not report_type or not rel:
            continue
        try:
            normalized[report_type] = json.loads((work / rel).read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise KdrsQueryImportError(
                f"Kunne ikke lese normalisert KDRS Query-resultat ({report_type}): {exc}"
            ) from exc
    return {"manifest": manifest, "normalized": normalized}
