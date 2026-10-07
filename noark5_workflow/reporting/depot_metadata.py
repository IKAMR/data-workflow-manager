from __future__ import annotations

import hashlib
import json
import os
import re
import xml.etree.ElementTree as ET
from uuid import uuid4
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

from noark5_workflow.core.job import Job
from noark5_workflow.analysis.period_assessment import suggest_reviewed_period
from noark5_workflow.operations.dias_mets import read_meta_from_mets

FILE_TYPE = "dwm-depot-metadata"
FORMAT_VERSION = 2

METS_FIELDS = (
    "submission_agreement",
    "label",
    "system",
    "system_version",
    "archivist_type",
    "period_start",
    "period_end",
    "owner_org",
    "archivist_org",
    "submitter_org",
    "submitter_person",
    "producer_org",
    "producer_person",
    "producer_software",
    "creator",
    "preserver",
)

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
    """Return a writable metadata sidecar outside the received source."""
    if job.work_operations is not None:
        return Path(job.work_operations) / "metadata" / "depot_metadata.json"
    if job.work_root is not None:
        return Path(job.work_root) / "repository_operations" / "metadata" / "depot_metadata.json"
    return None


def _blank_current() -> dict[str, str]:
    return {key: "" for key in ALL_EDITABLE_FIELDS}


def _normalise_current(value: Any) -> dict[str, str]:
    current = _blank_current()
    if isinstance(value, dict):
        for key in ALL_EDITABLE_FIELDS:
            current[key] = str(value.get(key, "") or "").strip()
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
    if path is None or not path.is_file():
        return empty_metadata(job)
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
    result = {
        "file_type": FILE_TYPE,
        "format_version": FORMAT_VERSION,
        "job_id": str(job.job_id),
        "updated_at": _now_iso(),
        "source_imports": list(payload.get("source_imports", []) or []),
        "current": _normalise_current(payload.get("current", {})),
        "review": _normalise_review(payload.get("review", {})),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + ".tmp")
    try:
        temp.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        temp.replace(path)
    finally:
        if temp.exists():
            try:
                temp.unlink()
            except OSError:
                pass
    return path


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
    """Import one METS source and retain every distinct source version as evidence."""
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
    """Export current/editable METS metadata as a reusable package-metadata XML.

    This is deliberately a metadata-transfer document, not the final DIAS
    package info.xml: package-specific object identity, TAR reference, size and
    checksum are only known when the final package is built. The document is
    nevertheless valid for this application's METS metadata importer and keeps
    the same field semantics used by ``read_meta_from_mets``.
    """
    current = _normalise_current(values if values is not None else load_depot_metadata(job)["current"])
    target_path = Path(target)
    if target_path.suffix.casefold() != ".xml":
        target_path = target_path.with_suffix(".xml")

    mets = _METS_NS
    xsi = "http://www.w3.org/2001/XMLSchema-instance"
    ET.register_namespace("mets", mets)
    ET.register_namespace("xsi", xsi)

    attrs = {
        f"{{{xsi}}}schemaLocation": f"{mets} http://schema.arkivverket.no/METS/info.xsd",
        "PROFILE": "http://xml.ra.se/METS/RA_METS_eARD.xml",
        "TYPE": "SIP",
        "ID": "ID" + str(uuid4()),
    }
    if current.get("label"):
        attrs["LABEL"] = current["label"]
    root = ET.Element(f"{{{mets}}}mets", attrs)
    hdr = ET.SubElement(
        root,
        f"{{{mets}}}metsHdr",
        {"CREATEDATE": _now_iso(), "RECORDSTATUS": "DRAFT"},
    )

    def add_agent(type_: str, role: str, value: str, *, othertype: str = "", otherrole: str = "") -> None:
        text = str(value or "").strip()
        if not text:
            return
        agent_attrs = {"TYPE": type_, "ROLE": role}
        if othertype:
            agent_attrs["OTHERTYPE"] = othertype
        if otherrole:
            agent_attrs["OTHERROLE"] = otherrole
        agent = ET.SubElement(hdr, f"{{{mets}}}agent", agent_attrs)
        ET.SubElement(agent, f"{{{mets}}}name").text = text

    add_agent("ORGANIZATION", "ARCHIVIST", current.get("archivist_org", ""))
    add_agent("OTHER", "ARCHIVIST", current.get("system", ""), othertype="SOFTWARE")
    add_agent("OTHER", "ARCHIVIST", current.get("system_version", ""), othertype="SOFTWARE")
    add_agent("OTHER", "ARCHIVIST", current.get("archivist_type", ""), othertype="SOFTWARE")
    add_agent("ORGANIZATION", "CREATOR", current.get("creator", ""))
    add_agent("ORGANIZATION", "OTHER", current.get("producer_org", ""), otherrole="PRODUCER")
    add_agent("INDIVIDUAL", "OTHER", current.get("producer_person", ""), otherrole="PRODUCER")
    add_agent("OTHER", "OTHER", current.get("producer_software", ""), othertype="SOFTWARE", otherrole="PRODUCER")
    add_agent("ORGANIZATION", "OTHER", current.get("submitter_org", ""), otherrole="SUBMITTER")
    add_agent("INDIVIDUAL", "OTHER", current.get("submitter_person", ""), otherrole="SUBMITTER")
    add_agent("ORGANIZATION", "IPOWNER", current.get("owner_org", ""))
    add_agent("ORGANIZATION", "PRESERVATION", current.get("preserver", ""))

    for kind, key in (
        ("SUBMISSIONAGREEMENT", "submission_agreement"),
        ("STARTDATE", "period_start"),
        ("ENDDATE", "period_end"),
    ):
        value = current.get(key, "")
        if value:
            ET.SubElement(hdr, f"{{{mets}}}altRecordID", {"TYPE": kind}).text = value

    ET.SubElement(hdr, f"{{{mets}}}metsDocumentID").text = "info.xml"
    struct_map = ET.SubElement(root, f"{{{mets}}}structMap")
    ET.SubElement(struct_map, f"{{{mets}}}div", {"LABEL": "Reusable metadata export"})

    tree = ET.ElementTree(root)
    ET.indent(tree, space="  ")
    target_path.parent.mkdir(parents=True, exist_ok=True)
    tree.write(target_path, encoding="utf-8", xml_declaration=True)
    return target_path

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
    if "info.xsd" in schema_location:
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
    for item in payload.get("source_imports", []) or []:
        if not isinstance(item, dict):
            continue
        fields = item.get("fields", {})
        if not isinstance(fields, dict):
            continue
        value = str(fields.get(field, "") or "").strip()
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
