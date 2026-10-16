"""Depot-configurable receiving (ingest) directory creation.

Creates a new empty directory tree only. Canonical METS metadata is read but
never modified; receiving numbers and operator decisions are a separate record.
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from string import Formatter
from typing import Mapping
from uuid import uuid4

SETUP_FILE_TYPE = "dwm-receiving-folder-profiles"
SETUP_VERSION = 1
SOURCE_FIELDS = frozenset({
    "label", "system", "system_version", "reference_code", "period_start",
    "period_end", "package_number", "archive_description", "submission_agreement",
    "owner_org", "producer_org", "submitter_org", "recipient", "project_name",
})
RECEIPT_FIELDS = frozenset({"year", "month", "day", "date", "time"})
_WINDOWS_RESERVED = frozenset({"CON", "PRN", "AUX", "NUL"} | {
    f"{prefix}{digit}" for prefix in ("COM", "LPT") for digit in range(1, 10)
})
_INVALID_WINDOWS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


@dataclass(frozen=True)
class ReceiveProfile:
    profile_id: str
    name: str
    name_template: str
    folders: tuple[str, ...]
    receipt_number_template: str = "{date}-{time}"
    audit_file: str = "ingest.events.jsonl"


@dataclass(frozen=True)
class ReceivePlan:
    base: Path
    root: Path
    paths: tuple[Path, ...]
    profile: ReceiveProfile
    label: str = ""
    receipt_number: str = ""
    info_xml: Path | None = None
    audit_path: Path | None = None


def read_info_xml(path: str | Path) -> dict[str, str]:
    """Read METS via the established DWM parser. No modifications to source."""
    from noark5_workflow.operations.dias_mets import read_meta_from_mets

    source = Path(path)
    if not source.is_file():
        raise ValueError(f"Finner ikke info.xml: {source}")
    result = read_meta_from_mets(source)
    return {key: str(result.get(key, "") or "").strip() for key in SOURCE_FIELDS}


def _template_fields(template: str, allowed: frozenset[str]) -> None:
    try:
        parsed = list(Formatter().parse(template))
    except ValueError as exc:
        raise ValueError(f"Ugyldig mal: {exc}") from exc
    for _literal, field, fmt, conv in parsed:
        if field is not None and (field not in allowed or fmt or conv):
            raise ValueError(f"Ugyldig felt i mappeprofil: {field}")


def _validate_template(template: str) -> None:
    _template_fields(template, SOURCE_FIELDS)


def _validate_relative_template(template: str) -> None:
    _validate_template(template)
    _validate_relative_path(template)


def _validate_relative_path(value: str) -> None:
    if not value.strip() or value.startswith(("/", "\\")) or re.match(r"^[A-Za-z]:", value):
        raise ValueError("Krever en relativ mappesti")
    if any(part in ("", ".", "..") for part in value.replace("\\", "/").split("/")):
        raise ValueError("Ugyldig relativ mappesti")


def _check_segment(value: str) -> str:
    if (not value or value != value.strip() or value in (".", "..")
            or value.endswith((".", " ")) or _INVALID_WINDOWS.search(value)
            or value.split(".", 1)[0].upper() in _WINDOWS_RESERVED):
        raise ValueError(f"Ugyldig mappenavn: {value!r}")
    return value


def _segments(value: str) -> tuple[str, ...]:
    _validate_relative_path(value)
    parts = tuple(value.replace("\\", "/").split("/"))
    for item in parts:
        _check_segment(item)
    return parts


def _check_receipt_number(value: str) -> str:
    value = str(value or "").strip()
    if not value or len(value) > 160 or any(ord(ch) < 32 for ch in value):
        raise ValueError("Mottaksnummer m\u00e5 ha en gyldig verdi")
    return value


def safe_suggestion(value: str) -> str:
    """Derive Windows-safe folder name; the original LABEL remains unchanged."""
    result = _INVALID_WINDOWS.sub(" - ", str(value or "").strip())
    result = re.sub(r"\s+", " ", result).strip(" .")
    if result and result.split(".", 1)[0].upper() in _WINDOWS_RESERVED:
        result = "_" + result
    return result[:180].rstrip(" .")


def adjusted_label_folder(label: str) -> str:
    original = str(label or "").strip()
    if not original:
        raise ValueError("LABEL m\u00e5 ha en verdi")
    return _check_segment(safe_suggestion(original))


def load_profiles(path: str | Path) -> tuple[ReceiveProfile, ...]:
    source = Path(path)
    try:
        data = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Kunne ikke lese mottaks-setup: {exc}") from exc
    if not isinstance(data, dict) or data.get("file_type") != SETUP_FILE_TYPE:
        raise ValueError("Ukjent type mottaks-setup")
    if data.get("format_version") != SETUP_VERSION:
        raise ValueError("Ust\u00f8ttet versjon av mottaks-setup")
    entries = data.get("profiles")
    if not isinstance(entries, list) or not entries:
        raise ValueError("Setup m\u00e5 inneholde minst en mappeprofil")
    profiles = []
    seen = set()
    for item in entries:
        if not isinstance(item, dict):
            raise ValueError("Mappeprofil m\u00e5 v\u00e6re et objekt")
        profile_id = str(item.get("id", "")).strip()
        name = str(item.get("name", "")).strip()
        template = str(item.get("name_template", "{label}")).strip()
        directories = item.get("folders", [])
        number_template = str(item.get("receipt_number_template", "{date}-{time}")).strip()
        audit_file = str(item.get("audit_file", "ingest.events.jsonl")).strip()
        if not profile_id or not name or not template or not number_template or not audit_file:
            raise ValueError("Mappeprofil mangler id, name, name_template, mottaksnummermal eller loggfil")
        if profile_id in seen:
            raise ValueError(f"Duplisert mappeprofil: {profile_id}")
        if not isinstance(directories, list) or any(not isinstance(v, str) for v in directories):
            raise ValueError(f"Profil {profile_id}: folders m\u00e5 v\u00e6re en tekstliste")
        _validate_template(template)
        _template_fields(number_template, RECEIPT_FIELDS)
        _validate_relative_path(audit_file)
        for segment in audit_file.replace("\\", "/").split("/"):
            _check_segment(segment)
        for folder in directories:
            _validate_relative_template(folder)
        profiles.append(ReceiveProfile(profile_id, name, template, tuple(directories),
                                       number_template, audit_file))
        seen.add(profile_id)
    return tuple(profiles)


def suggested_receipt_number(profile: ReceiveProfile, *, now: datetime | None = None) -> str:
    dt = now or datetime.now().astimezone()
    _template_fields(profile.receipt_number_template, RECEIPT_FIELDS)
    return _check_receipt_number(profile.receipt_number_template.format_map({
        "date": dt.strftime("%Y%m%d"), "time": dt.strftime("%H%M%S"),
        "year": dt.strftime("%Y"), "month": dt.strftime("%m"), "day": dt.strftime("%d"),
    }))


def resolve_receiving_base(disk: str | Path, relative_root: str = "") -> Path:
    """An existing receiving root inside the chosen disk, never create it silently."""
    if not str(disk).strip():
        raise ValueError("Velg disk / volum")
    disk_root = Path(disk).expanduser()
    if not disk_root.is_dir():
        raise ValueError("Valgt disk finnes ikke eller er ikke tilgjengelig")
    root = disk_root
    if relative_root.strip():
        for part in _segments(relative_root.strip()):
            root = root / part
    disk_resolved = disk_root.resolve(strict=True)
    try:
        root_resolved = root.resolve(strict=True)
    except (OSError, FileNotFoundError) as exc:
        raise ValueError("Mottaksroten finnes ikke; velg en eksisterende rotmappe") from exc
    if not root_resolved.is_dir() or not root_resolved.is_relative_to(disk_resolved):
        raise ValueError("Mottaksrot m\u00e5 ligge p\u00e5 den valgte disken")
    # Validate the canonical target for containment, but retain the path form
    # selected by the caller. On Windows, resolve() may expand an 8.3 user
    # directory (TORBJO~1.AAS -> torbjorn.aasen), which makes equal paths
    # compare unequal and unexpectedly changes displayed target paths.
    return root


def _render(template: str, metadata: Mapping[str, str]) -> str:
    _validate_template(template)
    values = {key: str(metadata.get(key, "") or "").strip() for key in SOURCE_FIELDS}
    required = {field for _lit, field, _fmt, _conv in Formatter().parse(template) if field}
    missing = sorted(key for key in required if not values[key])
    if missing:
        raise ValueError("info.xml mangler felt som profilen krever: " + ", ".join(missing))
    return template.format_map(values)


def suggested_folder_name(profile: ReceiveProfile, metadata: Mapping[str, str]) -> str:
    return adjusted_label_folder(_render(profile.name_template, metadata))


def plan_receiving_folders(base: str | Path, name: str, profile: ReceiveProfile,
                           metadata: Mapping[str, str] | None = None, *,
                           label: str = "", receipt_number: str = "",
                           info_xml: str | Path | None = None) -> ReceivePlan:
    base = Path(base).expanduser()
    if not base.is_dir():
        raise ValueError("Valgt disk/mappe finnes ikke. Velg en eksisterende rotmappe")
    _check_segment(name)
    root = base / name
    if root.exists() or root.is_symlink() or any(p.name.casefold() == name.casefold() for p in base.iterdir()):
        raise FileExistsError(f"Mottaksmappen finnes allerede: {root}")
    if receipt_number:
        _check_receipt_number(receipt_number)
    metadata = metadata or {}
    directories: set[Path] = {root}
    for template in profile.folders:
        _validate_relative_template(template)
        rendered = _render(template, metadata)
        parent = root
        for part in _segments(rendered):
            parent = parent / part
            directories.add(parent)
    _validate_relative_path(profile.audit_file)
    audit_parts = _segments(profile.audit_file)
    audit_path = root.joinpath(*audit_parts)
    if audit_path.parent not in directories:
        raise ValueError("Loggmappen fra setup m\u00e5 inng\u00e5 i mottaksstrukturen")
    paths = tuple(sorted(directories, key=lambda x: (len(x.relative_to(base).parts), str(x).casefold())))
    return ReceivePlan(base, root, paths, profile, label.strip() or name,
                       receipt_number.strip(), Path(info_xml) if info_xml else None,
                       audit_path)


def create_receiving_folders(plan: ReceivePlan, *, actor=None) -> tuple[Path, ...]:
    """Create once and record a canonical ingest event; rollback on error.

    The source `info.xml` is NOT copied or modified. No existing folder is merged.
    """
    if not plan.base.is_dir() or plan.root.exists() or plan.root.is_symlink():
        raise FileExistsError(f"Mottaksmappen kan ikke opprettes: {plan.root}")
    created: list[Path] = []
    try:
        for folder in plan.paths:
            folder.mkdir(exist_ok=False)
            created.append(folder)
        if plan.receipt_number:
            if plan.audit_path is None:
                raise ValueError("Manglende hendelseslogg for mottaket")
            # Reuse DWM's canonical event schema and mandatory JSONL event sink.
            from noark5_workflow.core.events import WorkflowEvent
            from noark5_workflow.sinks.event_store import GenericEventStoreSink
            source_hash = ""
            if plan.info_xml is not None:
                source_hash = hashlib.sha256(plan.info_xml.read_bytes()).hexdigest()
            event = WorkflowEvent.now(
                "ingest.receiving_folders.created",
                run_id=f"INGEST-{uuid4().hex}",
                operation_id="ingest.create_receiving_folders",
                operation_name="Opprett mottaksstruktur",
                user=actor,
                data={
                    "receipt_number": plan.receipt_number,
                    "label": plan.label,
                    "folder_name": plan.root.name,
                    "receiving_root": str(plan.base),
                    "created_path": str(plan.root),
                    "profile_id": plan.profile.profile_id,
                    "folders": [str(path.relative_to(plan.root)) for path in plan.paths],
                    "info_xml": str(plan.info_xml) if plan.info_xml else "",
                    "info_xml_sha256": source_hash,
                },
            )
            GenericEventStoreSink(plan.audit_path).handle(event)
    except Exception:
        # An event log may have been created but not completed; remove only files
        # belonging to this newly-created, otherwise empty receiving tree.
        if plan.audit_path and plan.audit_path.is_file():
            try:
                plan.audit_path.unlink()
            except OSError:
                pass
        for folder in reversed(created):
            try:
                folder.rmdir()
            except OSError:
                pass
        raise
    return tuple(created)
