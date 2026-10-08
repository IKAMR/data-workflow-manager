from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import xml.etree.ElementTree as ET
from uuid import uuid4
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

from noark5_workflow.core.job import Job
from noark5_workflow.core.work_paths import resolve_dwm_work_root, resolve_work_operations_base
from noark5_workflow.analysis.period_assessment import suggest_reviewed_period
from noark5_workflow.operations.dias_mets import (
    DIAS_METADATA_FIELDS,
    LEGACY_TO_CANONICAL,
    build_submission_description,
    read_meta_from_mets,
    submission_description_readiness,
    write_xml,
)

FILE_TYPE = "dwm-depot-metadata"
FORMAT_VERSION = 3

# Canonical DIAS/METS metadata follows rows 1-47 in the Arkade metadata sheet
# and Arkade 5's ArchiveMetadata model.  Older DWM keys are migrated below.
METS_FIELDS = DIAS_METADATA_FIELDS

DEPOT_FIELDS = (
    "owner_municipalities",
    "archive_creators",
    "system_region",
    "delivery_information",
)

ALL_EDITABLE_FIELDS = METS_FIELDS + DEPOT_FIELDS


def _now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def metadata_store_path(job: Job) -> Path | None:
    """Return the metadata sidecar inside DWM's configured Work subfolder."""
    if job.work_operations is not None:
        root = resolve_dwm_work_root(job.work_operations)
        return root / "metadata" / "depot_metadata.json"
    if job.work_root is not None:
        root = resolve_dwm_work_root(Path(job.work_root) / "repository_operations")
        return root / "metadata" / "depot_metadata.json"
    return None


def _legacy_metadata_store_path(job: Job) -> Path | None:
    """Pre-a2 location used before DWM-subfolder resolution was applied."""
    # Prefer Work root when available: it remains stable even after the GUI has
    # materialized app/job subfolders into job.work_operations.
    if job.work_root is not None:
        return Path(job.work_root) / "repository_operations" / "metadata" / "depot_metadata.json"
    if job.work_operations is not None:
        base = resolve_work_operations_base(job.work_operations)
        return base / "metadata" / "depot_metadata.json"
    return None


def metadata_root_path(job: Job) -> Path | None:
    """Return the authoritative metadata directory for one job."""
    path = metadata_store_path(job)
    return path.parent if path is not None else None


def _metadata_work_root(job: Job) -> Path | None:
    root = metadata_root_path(job)
    return root.parent if root is not None else None


def _metadata_evidence_id(item: dict[str, Any]) -> str:
    sha = str(item.get("sha256", "") or "").casefold()
    source_path = str(item.get("path", "") or "")
    fallback = f"{item.get('size')}|{item.get('mtime_ns')}|{item.get('imported_at')}"
    seed = f"{sha}|{source_path}|{fallback}".encode("utf-8", errors="replace")
    return "info-" + hashlib.sha256(seed).hexdigest()[:16]


def _write_json_atomic(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + ".tmp")
    try:
        temp.write_text(
            json.dumps(value, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        temp.replace(path)
    finally:
        if temp.exists():
            try:
                temp.unlink()
            except OSError:
                pass


def _upgrade_source_fields_from_file(item: dict[str, Any], source_file: Path | None) -> dict[str, Any]:
    """Re-read an unchanged imported METS file with the current DIAS mapper.

    This upgrades a1/a2 source-history records that only extracted the old
    reduced field set. The original bytes/checksum remain the provenance anchor.
    """
    enriched = dict(item)
    if source_file is None or not source_file.is_file():
        return enriched
    try:
        parsed = read_meta_from_mets(source_file)
    except (OSError, ValueError):
        return enriched
    canonical = {
        key: str(parsed.get(key, "") or "").strip()
        for key in METS_FIELDS
        if str(parsed.get(key, "") or "").strip()
    }
    if canonical:
        enriched["fields"] = canonical
        enriched["fields_mapper"] = "arkade5-dias-v3"
    return enriched


def _materialize_source_evidence(job: Job, item: dict[str, Any]) -> dict[str, Any]:
    """Preserve one imported info.xml source beside its extracted field values.

    The received/source file is never modified.  If an older metadata record
    only contains path + checksum, this function upgrades it by copying the
    exact source bytes when they are still available.  A manifest is written
    even when the source is unavailable so the historical values/checksum are
    not lost.
    """
    enriched = dict(item)
    metadata_root = metadata_root_path(job)
    work_root = _metadata_work_root(job)
    if metadata_root is None or work_root is None:
        return enriched

    evidence_id = str(enriched.get("evidence_import_id", "") or "").strip()
    if not evidence_id:
        evidence_id = _metadata_evidence_id(enriched)
    evidence_root = metadata_root / "source_evidence" / evidence_id
    manifest_path = evidence_root / "manifest.json"
    source_dir = evidence_root / "source"

    original_path_text = str(enriched.get("path", "") or "")
    original_path = Path(original_path_text) if original_path_text else None
    original_name = original_path.name if original_path is not None and original_path.name else "info.xml"
    preserved_file: Path | None = None
    status = "source_unavailable"
    expected_sha = str(enriched.get("sha256", "") or "").casefold()

    if original_path is not None and original_path.is_file():
        actual_sha = _sha256_file(original_path)
        if expected_sha and actual_sha.casefold() != expected_sha:
            status = "source_changed_since_import"
        else:
            source_dir.mkdir(parents=True, exist_ok=True)
            preserved_file = source_dir / original_name
            if not preserved_file.exists() or _sha256_file(preserved_file) != actual_sha:
                shutil.copy2(original_path, preserved_file)
            status = "preserved"
            if not expected_sha:
                enriched["sha256"] = actual_sha
                expected_sha = actual_sha
            try:
                stat = original_path.stat()
                enriched.setdefault("size", int(stat.st_size))
                enriched.setdefault("mtime_ns", int(stat.st_mtime_ns))
            except OSError:
                pass

    if preserved_file is None:
        previous = str(enriched.get("preserved_file", "") or "")
        if previous:
            candidate = work_root / previous
            if candidate.is_file():
                preserved_file = candidate
                status = "preserved"

    parse_source = preserved_file if preserved_file is not None and preserved_file.is_file() else None
    if parse_source is None and status == "preserved" and original_path is not None and original_path.is_file():
        parse_source = original_path
    enriched = _upgrade_source_fields_from_file(enriched, parse_source)

    rel_preserved = (
        str(preserved_file.relative_to(work_root))
        if preserved_file is not None and preserved_file.is_file()
        else None
    )
    rel_manifest = str(manifest_path.relative_to(work_root))
    manifest = {
        "format_version": 1,
        "evidence_type": "received_metadata_source",
        "evidence_import_id": evidence_id,
        "job_id": str(job.job_id),
        "original_path": original_path_text,
        "original_name": original_name,
        "imported_at": str(enriched.get("imported_at", "") or ""),
        "size": enriched.get("size"),
        "mtime_ns": enriched.get("mtime_ns"),
        "sha256": str(enriched.get("sha256", "") or ""),
        "fields": dict(enriched.get("fields", {}) or {}),
        "preservation_status": status,
        "preserved_file": rel_preserved,
        "principle": (
            "Mottatt/importert info.xml bevares uendret som kildeevidens. "
            "Gjeldende depotmetadata lagres separat og kan korrigeres uten å omskrive kilden."
        ),
    }
    _write_json_atomic(manifest_path, manifest)

    enriched["evidence_import_id"] = evidence_id
    enriched["evidence_manifest"] = rel_manifest
    enriched["evidence_status"] = status
    if rel_preserved is not None:
        enriched["preserved_file"] = rel_preserved
    return enriched


def _blank_current() -> dict[str, str]:
    return {key: "" for key in ALL_EDITABLE_FIELDS}


def _normalise_current(value: Any) -> dict[str, str]:
    current = _blank_current()
    if isinstance(value, dict):
        for key in ALL_EDITABLE_FIELDS:
            current[key] = str(value.get(key, "") or "").strip()
        # Migrate short-lived a1/a2 field names without losing operator work.
        for old_key, new_key in LEGACY_TO_CANONICAL.items():
            old_value = str(value.get(old_key, "") or "").strip()
            if old_value and not current.get(new_key):
                current[new_key] = old_value
    return current


def _blank_review() -> dict[str, Any]:
    return {
        "acknowledged_state_signature": "",
        "acknowledged_at": "",
        "last_scan_at": "",
        "last_scan_candidates": 0,
        "last_scan_errors": [],
        "history": [],
    }


def _normalise_review(value: Any) -> dict[str, Any]:
    review = _blank_review()
    if not isinstance(value, dict):
        return review
    review["acknowledged_state_signature"] = str(
        value.get("acknowledged_state_signature", "") or ""
    )
    review["acknowledged_at"] = str(value.get("acknowledged_at", "") or "")
    review["last_scan_at"] = str(value.get("last_scan_at", "") or "")
    try:
        review["last_scan_candidates"] = max(0, int(value.get("last_scan_candidates", 0)))
    except (TypeError, ValueError):
        review["last_scan_candidates"] = 0
    errors = value.get("last_scan_errors", [])
    review["last_scan_errors"] = [str(item) for item in errors] if isinstance(errors, list) else []
    history = value.get("history", [])
    review["history"] = history if isinstance(history, list) else []
    return review


def empty_metadata(job: Job) -> dict[str, Any]:
    return {
        "file_type": FILE_TYPE,
        "format_version": FORMAT_VERSION,
        "job_id": str(job.job_id),
        "updated_at": "",
        "source_imports": [],
        "current": _blank_current(),
        "review": _blank_review(),
    }


def load_depot_metadata(job: Job) -> dict[str, Any]:
    path = metadata_store_path(job)
    if path is None:
        return empty_metadata(job)
    if not path.is_file():
        # Read the short-lived pre-a2 location so existing operator work is not
        # lost. The next save writes to the configured DWM location.
        legacy = _legacy_metadata_store_path(job)
        if legacy is None or legacy == path or not legacy.is_file():
            return empty_metadata(job)
        path = legacy
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return empty_metadata(job)
    if not isinstance(raw, dict) or raw.get("file_type") != FILE_TYPE:
        return empty_metadata(job)

    imports = raw.get("source_imports", [])
    if not isinstance(imports, list):
        imports = []
    return {
        "file_type": FILE_TYPE,
        "format_version": FORMAT_VERSION,
        "job_id": str(job.job_id),
        "updated_at": str(raw.get("updated_at", "") or ""),
        "source_imports": imports,
        "current": _normalise_current(raw.get("current", {})),
        "review": _normalise_review(raw.get("review", {})),
    }


def save_depot_metadata(job: Job, payload: dict[str, Any]) -> Path:
    path = metadata_store_path(job)
    if path is None:
        raise ValueError(
            f"{job.job_id} mangler Work/operations. Metadata kan ikke lagres i mottatt kilde."
        )

    source_imports = []
    for item in list(payload.get("source_imports", []) or []):
        if not isinstance(item, dict):
            continue
        source_imports.append(_materialize_source_evidence(job, item))

    result = {
        "file_type": FILE_TYPE,
        "format_version": FORMAT_VERSION,
        "job_id": str(job.job_id),
        "updated_at": _now_iso(),
        "source_imports": source_imports,
        "current": _normalise_current(payload.get("current", {})),
        "review": _normalise_review(payload.get("review", {})),
    }
    _write_json_atomic(path, result)
    return path


def migrate_metadata_storage(job: Job) -> dict[str, Any]:
    """Materialize metadata and imported info.xml evidence in the current DWM area.

    The short-lived pre-a2 location remains untouched. This makes migration
    non-destructive while ensuring subsequent reads/writes use the configured
    DWM/job subfolder. Existing correct data is not rewritten unless an older
    source-import record still lacks its evidence manifest.
    """
    target = metadata_store_path(job)
    if target is None:
        raise ValueError(
            f"{job.job_id} mangler Work/operations. Metadata kan ikke migreres."
        )
    legacy = _legacy_metadata_store_path(job)
    target_existed = target.is_file()
    legacy_used = bool(
        not target_existed
        and legacy is not None
        and legacy != target
        and legacy.is_file()
    )
    payload = load_depot_metadata(job)
    imports = [
        item for item in (payload.get("source_imports") or [])
        if isinstance(item, dict)
    ]
    has_material = bool(
        imports
        or any(str(value or "").strip() for value in (payload.get("current") or {}).values())
        or str(payload.get("updated_at", "") or "").strip()
    )
    work_root = _metadata_work_root(job)
    needs_evidence_upgrade = False
    if imports and work_root is not None:
        for item in imports:
            rel_manifest = str(item.get("evidence_manifest", "") or "")
            fields = item.get("fields", {}) if isinstance(item.get("fields", {}), dict) else {}
            has_legacy_fields = any(old_key in fields for old_key in LEGACY_TO_CANONICAL)
            if (
                not rel_manifest
                or not (work_root / rel_manifest).is_file()
                or has_legacy_fields
                or item.get("fields_mapper") != "arkade5-dias-v3"
            ):
                needs_evidence_upgrade = True
                break

    if not has_material and not target_existed and not legacy_used:
        return {
            "target": str(target),
            "written": False,
            "migrated_legacy": False,
            "source_imports": 0,
        }
    if target_existed and not legacy_used and not needs_evidence_upgrade:
        return {
            "target": str(target),
            "written": False,
            "migrated_legacy": False,
            "source_imports": len(imports),
        }

    saved = save_depot_metadata(job, payload)
    return {
        "target": str(saved),
        "written": True,
        "migrated_legacy": legacy_used,
        "source_imports": len(imports),
    }


def update_current_metadata(job: Job, values: dict[str, Any]) -> Path:
    payload = load_depot_metadata(job)
    current = payload["current"]
    for key in ALL_EDITABLE_FIELDS:
        if key in values:
            current[key] = str(values.get(key, "") or "").strip()
    payload["current"] = current
    return save_depot_metadata(job, payload)



def job_display_name(job: Job) -> str:
    """Return depot LABEL when established, otherwise the technical job name.

    The technical job name remains unchanged in the job model. This is only the
    human-facing identity used by depot/report surfaces.
    """
    try:
        label = str(load_depot_metadata(job)["current"].get("label", "") or "").strip()
    except Exception:
        label = ""
    return label or str(job.name or job.job_id)


def _year_token(value: Any) -> str:
    text = str(value or "").strip()
    match = re.search(r"(?<!\d)(\d{4})(?!\d)", text)
    return match.group(1) if match else ""


def _bounded_reviewed_period(job: Job) -> tuple[str, str]:
    """Return a reviewed/suggested whole-extraction period from existing evidence.

    Priority is an explicit saved depot-period assessment. If none exists, reuse
    already materialized Noark 5 result JSON under Work/operations and run the
    same reviewed-period rule used by the result view. No source XML is reparsed
    here. In particular, document-only outliers such as 2099 do not become the
    assessed end year while folder/journal activity provides a stronger period.
    """
    roots = []
    for value in (job.work_operations, job.work_root):
        if value is None:
            continue
        path = Path(value)
        if path not in roots:
            roots.append(path)
    candidates: list[Path] = []
    pruned = {"dokument", "dokumenter", "document", "documents", "content", "temp", "tmp"}
    for root in roots:
        if not root.is_dir():
            continue
        queue: list[tuple[Path, int]] = [(root, 0)]
        visited = 0
        while queue and visited < 1500:
            folder, depth = queue.pop(0)
            try:
                entries = list(os.scandir(folder))
            except OSError:
                continue
            visited += len(entries)
            for entry in entries:
                if entry.name == "depot_period_assessment.json":
                    try:
                        if entry.is_file(follow_symlinks=False):
                            candidates.append(Path(entry.path))
                    except OSError:
                        pass
            if depth >= 4:
                continue
            for entry in entries:
                try:
                    is_dir = entry.is_dir(follow_symlinks=False)
                except OSError:
                    is_dir = False
                if is_dir and entry.name.casefold() not in pruned:
                    queue.append((Path(entry.path), depth + 1))
    candidates.sort(key=lambda item: item.stat().st_mtime_ns if item.exists() else 0, reverse=True)
    for path in candidates:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        scopes = payload.get("scopes", {}) if isinstance(payload, dict) else {}
        scope = scopes.get("__ALL_ARCHIVE_PARTS__", {}) if isinstance(scopes, dict) else {}
        if not isinstance(scope, dict):
            continue
        start = _year_token(scope.get("start_year"))
        end = _year_token(scope.get("end_year"))
        if start or end:
            return start, end
    observed = _reviewed_period_from_materialized_results(job)
    if observed != ("", ""):
        return observed
    return "", ""


def _materialized_result_json_candidates(job: Job) -> list[Path]:
    """Return bounded, likely result JSON files newest first.

    Only Work-side data is inspected. This deliberately avoids Source and document
    payload folders and avoids large generic JSON files that are unlikely to be a
    presentation/report model.
    """
    roots: list[Path] = []
    for value in (job.work_operations, job.work_root):
        if value is None:
            continue
        path = Path(value)
        if path not in roots:
            roots.append(path)

    pruned = {
        "dokument", "dokumenter", "document", "documents", "content",
        "temp", "tmp", "__pycache__", "metadata",
    }
    likely_tokens = ("report", "depot", "presentation", "view", "result", "summary")
    candidates: list[Path] = []
    seen: set[str] = set()
    visited = 0
    for root in roots:
        if not root.is_dir():
            continue
        queue: list[tuple[Path, int]] = [(root, 0)]
        while queue and visited < 5000:
            folder, depth = queue.pop(0)
            try:
                entries = list(os.scandir(folder))
            except OSError:
                continue
            visited += len(entries)
            for entry in entries:
                try:
                    is_file = entry.is_file(follow_symlinks=False)
                except OSError:
                    is_file = False
                if not is_file or not entry.name.casefold().endswith(".json"):
                    continue
                name = entry.name.casefold()
                if not any(token in name for token in likely_tokens):
                    continue
                path = Path(entry.path)
                try:
                    if path.stat().st_size <= 0 or path.stat().st_size > 64 * 1024 * 1024:
                        continue
                except OSError:
                    continue
                key = os.path.normcase(os.path.abspath(str(path)))
                if key not in seen:
                    seen.add(key)
                    candidates.append(path)
            if depth >= 5:
                continue
            for entry in entries:
                try:
                    is_dir = entry.is_dir(follow_symlinks=False)
                except OSError:
                    is_dir = False
                if is_dir and entry.name.casefold() not in pruned:
                    queue.append((Path(entry.path), depth + 1))

    def mtime(path: Path) -> int:
        try:
            return path.stat().st_mtime_ns
        except OSError:
            return 0

    candidates.sort(key=mtime, reverse=True)
    return candidates


def _yearly_rows(value: Any) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            yearly = node.get("yearly_volume")
            if isinstance(yearly, dict) and any(
                isinstance(yearly.get(key), dict)
                for key in ("folder", "journal", "document_description", "document_object")
            ):
                rows.append(node)
            for child in node.values():
                walk(child)
        elif isinstance(node, list):
            for child in node:
                walk(child)

    walk(value)
    return rows


def _merge_yearly_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    merged = {
        "yearly_volume": {
            "folder": {},
            "journal": {},
            "document_description": {},
            "document_object": {},
        }
    }
    seen_rows: set[str] = set()
    for row in rows:
        yearly = row.get("yearly_volume") or {}
        try:
            fingerprint = json.dumps(yearly, ensure_ascii=False, sort_keys=True)
        except (TypeError, ValueError):
            fingerprint = str(id(row))
        identity = row.get("archive_part") or {}
        system_id = str(identity.get("system_id", "") or "") if isinstance(identity, dict) else ""
        dedupe = system_id + "|" + fingerprint
        if dedupe in seen_rows:
            continue
        seen_rows.add(dedupe)
        for series in ("folder", "journal", "document_description", "document_object"):
            source = yearly.get(series) or {}
            if not isinstance(source, dict):
                continue
            target = merged["yearly_volume"][series]
            for year, count in source.items():
                text = str(year or "")[:4]
                if len(text) != 4 or not text.isdigit():
                    continue
                try:
                    amount = int(count or 0)
                except (TypeError, ValueError):
                    amount = 0
                target[text] = int(target.get(text, 0) or 0) + amount
    return merged


def _reviewed_period_from_materialized_results(job: Job) -> tuple[str, str]:
    """Suggest period from already generated Noark 5 year-series result data."""
    for path in _materialized_result_json_candidates(job):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, UnicodeDecodeError):
            continue
        rows = _yearly_rows(payload)
        if not rows:
            continue

        # Prefer an explicit all-archive-parts row. It is already the materialized
        # extraction-level view and avoids summing duplicate presentation copies.
        all_rows = [row for row in rows if bool(row.get("is_all_archive_parts"))]
        candidates = all_rows or rows
        if all_rows:
            for row in all_rows:
                start, end = suggest_reviewed_period(row)
                if start is not None or end is not None:
                    return ("" if start is None else str(start), "" if end is None else str(end))
        else:
            merged = _merge_yearly_rows(candidates)
            start, end = suggest_reviewed_period(merged)
            if start is not None or end is not None:
                return ("" if start is None else str(start), "" if end is None else str(end))
    return "", ""


def _label_identity_hint(job: Job) -> tuple[str, str, str]:
    """Infer stable identity hints from the job/source naming without claiming truth."""
    strings = [str(job.name or "")]
    for value in (job.source_root, job.source_extraction):
        if value is not None:
            path = Path(value)
            strings.extend(reversed(path.parts))

    joined = " ".join(strings)
    code_match = re.search(r"(?<!\d)(\d{4}_\d{3})(?!\d)", joined)
    code = code_match.group(1) if code_match else ""

    system = ""
    if re.search(r"ephorte", joined, re.IGNORECASE):
        system = "ePhorte"

    part = ""
    for text in strings:
        match = re.search(
            r"\d{4}_\d{3}[_-]+ephorte[-_](.+?)(?:_noark5|$)",
            text,
            re.IGNORECASE,
        )
        if not match:
            continue
        raw = match.group(1)
        tokens = [tok for tok in re.split(r"[_-]+", raw) if tok]
        kept = []
        for tok in tokens:
            low = tok.casefold()
            if re.fullmatch(r"\d+(?:tb|gb|mb)", low):
                continue
            if re.fullmatch(r"20\d{2}", low):
                continue
            if low in {"noark5", "sip", "content"}:
                continue
            kept.append(tok)
        if kept:
            part = "_".join(kept)
            break

    if not part:
        name = str(job.name or "")
        match = re.match(r"(.+?)-20\d{2}-", name)
        raw = match.group(1) if match else name
        tokens = [tok for tok in re.split(r"[_-]+", raw) if tok]
        kept = [
            tok for tok in tokens
            if not re.fullmatch(r"\d+(?:TB|GB|MB)", tok, re.IGNORECASE)
        ]
        if kept:
            part = "_".join(kept)

    return code, system, part


def suggest_label(job: Job) -> str:
    """Suggest, but never persist, a LABEL from current identity and period evidence.

    A fully resolved existing LABEL is left alone. A LABEL containing the visible
    YYYY placeholder is intentionally refreshable so a previously saved provisional
    value can later be completed when period evidence becomes available.
    """
    payload = load_depot_metadata(job)
    current = payload["current"]
    existing_label = str(current.get("label", "") or "").strip()
    if existing_label and "YYYY" not in existing_label:
        return ""

    start = _year_token(current.get("period_start"))
    end = _year_token(current.get("period_end"))
    if not start and not end:
        start, end = _bounded_reviewed_period(job)

    if start and end:
        period = f"({start}–{end})"
    elif start:
        period = f"({start}–YYYY)"
    elif end:
        period = f"(YYYY–{end})"
    else:
        period = "(YYYY-YYYY)"

    if existing_label:
        replaced = re.sub(r"\(\s*(?:YYYY|\d{4})\s*[-–]\s*(?:YYYY|\d{4})\s*\)\s*$", period, existing_label)
        return replaced if replaced != existing_label or start or end else existing_label

    code, inferred_system, part = _label_identity_hint(job)
    system = str(current.get("system", "") or "").strip() or inferred_system
    pieces = [value for value in (code, system, part) if value]
    if not pieces:
        return ""
    return " ".join(pieces) + " " + period


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            block = handle.read(1024 * 1024)
            if not block:
                break
            digest.update(block)
    return digest.hexdigest()


def _source_signature(path: Path) -> dict[str, Any]:
    try:
        stat = path.stat()
        return {
            "size": int(stat.st_size),
            "mtime_ns": int(stat.st_mtime_ns),
            "sha256": _sha256_file(path),
        }
    except OSError:
        return {"size": None, "mtime_ns": None, "sha256": ""}


def _same_import(item: dict[str, Any], resolved: str, signature: dict[str, Any]) -> bool:
    if str(item.get("path", "")) != resolved:
        return False
    old_hash = str(item.get("sha256", "") or "")
    new_hash = str(signature.get("sha256", "") or "")
    if old_hash and new_hash:
        return old_hash == new_hash
    return (
        item.get("size") == signature.get("size")
        and item.get("mtime_ns") == signature.get("mtime_ns")
    )


def import_info_xml(
    job: Job,
    path: str | Path,
    *,
    overwrite_current: bool = True,
    apply_current: bool = True,
) -> Path:
    """Import one METS source and retain values plus an immutable source copy as evidence."""
    source = Path(path)
    fields = read_meta_from_mets(source)
    payload = load_depot_metadata(job)
    signature = _source_signature(source)
    resolved = str(source.resolve()) if source.exists() else str(source)

    existing = payload.get("source_imports", [])
    duplicate = next(
        (
            item for item in existing
            if isinstance(item, dict) and _same_import(item, resolved, signature)
        ),
        None,
    )
    if duplicate is None:
        existing.append(
            {
                "kind": "dias-mets",
                "path": resolved,
                "imported_at": _now_iso(),
                "size": signature["size"],
                "mtime_ns": signature["mtime_ns"],
                "sha256": signature["sha256"],
                "fields": {key: str(value) for key, value in fields.items()},
            }
        )
        payload["source_imports"] = existing

    current = payload["current"]
    if apply_current:
        for key, value in fields.items():
            if key not in METS_FIELDS:
                continue
            if overwrite_current or not current.get(key):
                current[key] = str(value or "").strip()
    payload["current"] = current
    return save_depot_metadata(job, payload)


def import_selected_info_xml(job: Job, path: str | Path) -> Path:
    """Import one explicitly chosen package-level info.xml / DIAS-METS source.

    The selected file may live outside the job's automatic Source/Work search
    roots. It must still be semantically recognizable as the package-level
    DIAS metadata METS. Existing depot values are preserved, while blank
    current fields may be populated from the selected source.
    """
    source = Path(path)
    if not source.is_file():
        raise ValueError(f"Metadatafilen finnes ikke: {source}")
    if not _is_dias_info_mets(source):
        raise ValueError(
            "Valgt XML er ikke gjenkjent som package-level info.xml / DIAS-METS metadata."
        )
    return import_info_xml(
        job,
        source,
        overwrite_current=False,
        apply_current=True,
    )



def export_info_xml(
    job: Job,
    target: str | Path,
    *,
    values: dict[str, Any] | None = None,
) -> Path:
    """Export the outer DIAS submission description (commonly ``info.xml``).

    The editable values follow Arkade 5's ArchiveMetadata mapping.  DWM writes
    a package-level METS document using the current submissionDescription.xsd
    structure.  File inventory/checksums are intentionally omitted here because
    they are only known at final package creation; fileSec is optional in that
    schema.
    """
    current = _normalise_current(
        values if values is not None else load_depot_metadata(job)["current"]
    )
    problems = submission_description_readiness(current)
    if problems:
        raise ValueError(
            "Kan ikke eksportere en XSD-klar DIAS info.xml ennå. Mangler: "
            + "; ".join(problems)
        )

    try:
        from version import APP_NAME, VERSION
        software_name = str(APP_NAME or "Data Workflow Manager")
        software_version = str(VERSION or "")
    except Exception:
        software_name = "Data Workflow Manager"
        software_version = ""

    tree = build_submission_description(
        current,
        package_type="SIP",
        software_name=software_name,
        software_version=software_version,
    )
    return write_xml(tree, target)


def _candidate_roots(job: Job) -> list[Path]:
    # Metadata discovery is deliberately limited to Source and Work.
    # Archive/output may be very large preservation areas and are not metadata
    # discovery roots. The received Noark/DIAS content payload is pruned below.
    values = [
        job.source_root,
        job.source_extraction,
        job.work_root,
        job.work_operations,
    ]
    roots: list[Path] = []
    seen: set[str] = set()
    for value in values:
        if value is None:
            continue
        path = Path(value)
        key = os.path.normcase(os.path.abspath(str(path)))
        if key in seen:
            continue
        seen.add(key)
        roots.append(path)
    return roots


_METS_NS = "http://www.loc.gov/METS/"
_MAX_METADATA_XML_BYTES = 8 * 1024 * 1024


def _is_dias_info_mets(path: Path) -> bool:
    """Return True when a small XML file is the DIAS package-level info METS.

    The filename is deliberately irrelevant. In real deliveries the file may be
    named ``info.xml``, ``<uuid>.xml`` or e.g. ``1502_<uuid>_info.xml``. The
    decision is therefore based on METS semantics: the METS root plus the DIAS
    info schema and/or the internal metsDocumentID value.
    """
    try:
        stat = path.stat()
    except OSError:
        return False
    if stat.st_size <= 0 or stat.st_size > _MAX_METADATA_XML_BYTES:
        return False

    try:
        root = ET.parse(path).getroot()
    except (ET.ParseError, OSError, ValueError):
        return False

    if root.tag != f"{{{_METS_NS}}}mets":
        return False

    schema_location = " ".join(
        value for key, value in root.attrib.items()
        if key.endswith("schemaLocation") and value
    ).casefold()
    if "info.xsd" in schema_location or "submissiondescription.xsd" in schema_location:
        return True

    document_id = root.find(
        f"{{{_METS_NS}}}metsHdr/{{{_METS_NS}}}metsDocumentID"
    )
    if document_id is not None:
        value = (document_id.text or "").strip().replace("\\", "/").casefold()
        if value.rsplit("/", 1)[-1] == "info.xml":
            return True

    # Some delivered DIAS info files do not carry schemaLocation or
    # metsDocumentID. In those cases the external filename is only a hint,
    # never the sole criterion: require package-level METS header metadata too.
    # This supports both info.xml and e.g. 1502_<uuid>_info.xml without
    # misclassifying an ordinary inner mets.xml.
    name = path.name.casefold()
    filename_hint = name == "info.xml" or name.endswith("_info.xml")
    if filename_hint:
        hdr = root.find(f"{{{_METS_NS}}}metsHdr")
        if hdr is not None:
            for alt in hdr.findall(f"{{{_METS_NS}}}altRecordID"):
                if (alt.get("TYPE") or "").upper() in {
                    "SUBMISSIONAGREEMENT", "STARTDATE", "ENDDATE"
                }:
                    return True
            if hdr.find(f"{{{_METS_NS}}}agent") is not None:
                return True

    return False


def _find_info_xml(root: Path, *, max_depth: int = 4, max_entries: int = 4000) -> list[Path]:
    """Find DIAS info METS files without relying on the external filename."""
    if not root.is_dir():
        return []
    found: list[Path] = []
    queue: list[tuple[Path, int]] = [(root, 0)]
    visited = 0
    pruned = {
        # Package metadata is outside the preserved extraction payload. Never
        # crawl document payload trees, regardless of their common spelling.
        "content",
        "dokument",
        "dokumenter",
        "document",
        "documents",
        "schemas",
        "schema",
        "temp",
        "tmp",
        "__pycache__",
    }
    while queue and visited < max_entries:
        folder, depth = queue.pop(0)
        try:
            entries = list(os.scandir(folder))
        except OSError:
            continue
        visited += len(entries)
        for entry in entries:
            try:
                is_file = entry.is_file(follow_symlinks=False)
            except OSError:
                is_file = False
            if not is_file or not entry.name.casefold().endswith(".xml"):
                continue
            candidate = Path(entry.path)
            if _is_dias_info_mets(candidate):
                found.append(candidate)
        if depth >= max_depth:
            continue
        for entry in entries:
            try:
                is_dir = entry.is_dir(follow_symlinks=False)
            except OSError:
                is_dir = False
            if not is_dir or entry.name.casefold() in pruned:
                continue
            queue.append((Path(entry.path), depth + 1))
    return found


def candidate_info_xml_paths(job: Job) -> tuple[Path, ...]:
    candidates: list[Path] = []
    seen: set[str] = set()
    for root in _candidate_roots(job):
        for path in _find_info_xml(root):
            key = os.path.normcase(os.path.abspath(str(path)))
            if key in seen:
                continue
            seen.add(key)
            candidates.append(path)
    return tuple(candidates)


def _state_signature(payload: dict[str, Any]) -> str:
    imports = []
    for item in payload.get("source_imports", []) or []:
        if not isinstance(item, dict):
            continue
        imports.append(
            {
                "path": str(item.get("path", "") or ""),
                "sha256": str(item.get("sha256", "") or ""),
                "size": item.get("size"),
                "mtime_ns": item.get("mtime_ns"),
                "fields": item.get("fields", {}),
            }
        )
    body = {
        "imports": imports,
        "current": _normalise_current(payload.get("current", {})),
    }
    encoded = json.dumps(body, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def source_values(payload: dict[str, Any], field: str) -> tuple[str, ...]:
    values: list[str] = []
    legacy_keys = [old for old, new in LEGACY_TO_CANONICAL.items() if new == field]
    for item in payload.get("source_imports", []) or []:
        if not isinstance(item, dict):
            continue
        fields = item.get("fields", {})
        if not isinstance(fields, dict):
            continue
        raw = fields.get(field, "")
        if not raw:
            for old_key in legacy_keys:
                raw = fields.get(old_key, "")
                if raw:
                    break
        value = str(raw or "").strip()
        if value and value not in values:
            values.append(value)
    return tuple(values)


def metadata_review_state(job: Job) -> dict[str, Any]:
    payload = load_depot_metadata(job)
    review = payload["review"]
    current = payload["current"]
    imports = payload.get("source_imports", []) or []
    state_signature = _state_signature(payload)
    acknowledged = str(review.get("acknowledged_state_signature", "") or "")

    reasons: list[str] = []
    # Depotmetadata is optional. A completely untouched job must not acquire a
    # warning merely because the operator has chosen to focus on content
    # validation instead of package metadata. Once metadata exists or a scan
    # actually finds/encounters a METS source, the review state becomes active.
    engaged = bool(
        imports
        or any(str(value or "").strip() for value in current.values())
        or int(review.get("last_scan_candidates", 0) or 0) > 0
        or review.get("last_scan_errors")
    )

    unacknowledged = state_signature != acknowledged
    if engaged and not str(current.get("label", "") or "").strip():
        reasons.append("LABEL mangler")

    if engaged and unacknowledged:
        if review.get("last_scan_errors"):
            reasons.append("Feil oppstod ved søk/import av metadata")
        if int(review.get("last_scan_candidates", 0) or 0) > 1:
            reasons.append("Flere info.xml-filer er funnet og må avklares")

        conflicting_fields = [
            key for key in METS_FIELDS if len(source_values(payload, key)) > 1
        ]
        if conflicting_fields:
            reasons.append("Ulike kildeverdier finnes for: " + ", ".join(conflicting_fields))

        if imports:
            reasons.append("Metadata er ikke avklart etter siste import eller redigering")
        elif any(str(value or "").strip() for value in current.values()):
            reasons.append("Redigerte depotmetadata er ikke avklart")

    return {
        "required": bool(reasons),
        "reasons": tuple(reasons),
        "source_count": len(imports),
        "candidate_count": int(review.get("last_scan_candidates", 0) or 0),
        "acknowledged_at": str(review.get("acknowledged_at", "") or ""),
        "state_signature": state_signature,
    }


def acknowledge_metadata(job: Job) -> Path:
    """Explicitly mark the current metadata state as reviewed by depot staff."""
    payload = load_depot_metadata(job)
    if not str(payload["current"].get("label", "") or "").strip():
        raise ValueError("LABEL må være utfylt før metadata kan markeres som avklart.")
    review = payload["review"]
    now = _now_iso()
    review["acknowledged_state_signature"] = _state_signature(payload)
    review["acknowledged_at"] = now
    history = list(review.get("history", []) or [])
    history.append({"event": "acknowledged", "at": now})
    review["history"] = history
    payload["review"] = review
    return save_depot_metadata(job, payload)


def _set_scan_state(
    job: Job,
    *,
    candidate_count: int,
    errors: Iterable[str] = (),
    auto_acknowledge: bool = False,
) -> Path:
    payload = load_depot_metadata(job)
    review = payload["review"]
    review["last_scan_at"] = _now_iso()
    review["last_scan_candidates"] = max(0, int(candidate_count))
    review["last_scan_errors"] = [str(item) for item in errors]
    if auto_acknowledge and str(payload["current"].get("label", "") or "").strip():
        review["acknowledged_state_signature"] = _state_signature(payload)
        review["acknowledged_at"] = _now_iso()
    payload["review"] = review
    return save_depot_metadata(job, payload)


def scan_and_import_info_xml(job: Job) -> dict[str, Any]:
    """Search one job's own source/work roots and preserve every distinct info.xml version.

    A single first-time source may populate blank current metadata automatically.
    Existing current data is never overwritten by discovery. Multiple/new sources remain
    evidence and cause the metadata state to require explicit review.
    """
    before = load_depot_metadata(job)
    before_imports = len(before.get("source_imports", []) or [])
    had_current = any(str(value or "").strip() for value in before["current"].values())
    candidates = candidate_info_xml_paths(job)
    errors: list[str] = []

    first_clean_import = before_imports == 0 and not had_current and len(candidates) == 1
    for path in candidates:
        try:
            import_info_xml(
                job,
                path,
                overwrite_current=False,
                apply_current=first_clean_import,
            )
        except Exception as exc:
            errors.append(f"{path}: {exc}")

    after = load_depot_metadata(job)
    after_imports = len(after.get("source_imports", []) or [])
    imported_new = max(0, after_imports - before_imports)
    auto_ack = bool(first_clean_import and imported_new == 1 and not errors)
    _set_scan_state(
        job,
        candidate_count=len(candidates),
        errors=errors,
        auto_acknowledge=auto_ack,
    )
    state = metadata_review_state(job)
    return {
        "job_id": str(job.job_id),
        "candidates": tuple(str(path) for path in candidates),
        "candidate_count": len(candidates),
        "imported_new": imported_new,
        "errors": tuple(errors),
        "review_required": bool(state["required"]),
        "review_reasons": state["reasons"],
    }


def scan_and_import_info_xml_for_jobs(jobs: Iterable[Job]) -> tuple[dict[str, Any], ...]:
    return tuple(scan_and_import_info_xml(job) for job in jobs)


def auto_import_info_xml(job: Job) -> Path | None:
    """Backward-compatible helper: scan and import, returning the sidecar when data exists."""
    result = scan_and_import_info_xml(job)
    if result["imported_new"] or load_depot_metadata(job).get("source_imports"):
        return metadata_store_path(job)
    return None
