"""a16: complete, source-bound METS metadata inventory and Work-only corrections.

The 47 established Arkade metadata fields are the editable current business
metadata. Every textual XML occurrence and attribute (including repeated agents,
fileSec, unknown extensions and distinct outer/inner METS namespaces) is also
available as an indexed source record. Raw sources are never rewritten.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import re
from typing import Any
from uuid import uuid4
from xml.etree import ElementTree as ET

from noark5_workflow.reporting.dias_metadata_views_v021_a16_1 import (
    extended_mets_rows, expected_references, field_references, technical_read_only,
)

MODEL = "ikamr.dwm.dias.metadata.a16.v1"
LOC_NS = "http://www.loc.gov/METS/"
INNER_NS = "http://arkivverket.no/standarder/METS"
ALLOWED_NS = frozenset((LOC_NS, INNER_NS))
WORK_META = "metadata/depot_metadata.json"
INNER_INDEX = "metadata/dias_mets_sources_v021_a16.json"
EVENT_DIR = "metadata/dias_mets_field_events_v021_a16"
MAX_XML = 32 * 1024 * 1024
MAX_META = 5 * 1024 * 1024
MAX_NODES = 180000
MAX_EVENTS = 5000
MAX_FIELD_VALUE = 6000

# Field order and categories are the original 0000-metadata-arkade.xlsx rows 1-47.
# They are not all XML elements: Arkade 5 renders them via root, header,
# altRecordID, role-based agents and notescontent: positional notes.
FIELD_ROWS = (
    ("archive_description", "Arkivbeskrivelse", "Arkiv / pakke"),
    ("submission_agreement", "Avtalenr", "Arkiv / pakke"),
    ("record_status", "Oppføringstype", "Arkiv / pakke"),
    ("delivery_type", "Arkivsystemtype", "Arkiv / pakke"),
    ("project_name", "Prosjektnavn", "Arkiv / pakke"),
    ("package_number", "Pakkenummer", "Arkiv / pakke"),
    ("reference_code", "Referansekode", "Arkiv / pakke"),
    ("archivist_org", "Arkivskaper", "Arkivskaper"),
    ("archivist_person", "Kontaktperson", "Arkivskaper"),
    ("archivist_address", "Adresse", "Arkivskaper"),
    ("archivist_phone", "Telefon", "Arkivskaper"),
    ("archivist_email", "E-post", "Arkivskaper"),
    ("submitter_org", "Overfører", "Overfører"),
    ("submitter_person", "Kontaktperson", "Overfører"),
    ("submitter_address", "Adresse", "Overfører"),
    ("submitter_phone", "Telefon", "Overfører"),
    ("submitter_email", "E-post", "Overfører"),
    ("producer_org", "Produsent", "Produsent"),
    ("producer_person", "Kontaktperson", "Produsent"),
    ("producer_address", "Adresse", "Produsent"),
    ("producer_phone", "Telefon", "Produsent"),
    ("producer_email", "E-post", "Produsent"),
    ("owner_org", "Eier", "Eier"),
    ("owner_person", "Kontaktperson", "Eier"),
    ("owner_address", "Adresse", "Eier"),
    ("owner_phone", "Telefon", "Eier"),
    ("owner_email", "E-post", "Eier"),
    ("creator_org", "Skaper av info.xml", "Skaper av info.xml"),
    ("creator_person", "Kontaktperson", "Skaper av info.xml"),
    ("creator_address", "Adresse", "Skaper av info.xml"),
    ("creator_phone", "Telefon", "Skaper av info.xml"),
    ("creator_email", "E-post", "Skaper av info.xml"),
    ("mets_creator_software", "METS-program", "METS-program"),
    ("mets_creator_software_version", "Programversjon", "METS-program"),
    ("recipient", "Mottaker", "Mottaker"),
    ("system", "Systemnavn", "System"),
    ("system_version", "Systemversjon", "System"),
    ("system_type", "Systemtype", "System"),
    ("system_type_version", "Systemets typeversjon", "System"),
    ("extraction_system", "Uttrekkssystem", "Uttrekkssystem"),
    ("extraction_system_version", "Uttrekksversjon", "Uttrekkssystem"),
    ("extraction_system_type", "Uttrekkstype", "Uttrekkssystem"),
    ("extraction_system_type_version", "Uttrekkets typeversjon", "Uttrekkssystem"),
    ("period_start", "Startdato", "Periode / uttrekk"),
    ("period_end", "Sluttdato", "Periode / uttrekk"),
    ("extraction_date", "Uttrekksdato (Work)", "Periode / uttrekk"),
    ("label", "METS LABEL", "Merkelapp"),
)
FIELD_KEYS = frozenset(row[0] for row in FIELD_ROWS)
# These are existing DWM depot/catalogue fields, not claimed to originate in
# METS or the 47-field Arkade spreadsheet. Keep the provenance distinction.
DEPOT_ROWS = (
    ("owner_municipalities", "Eierkommuner", "Depotopplysninger (ikke METS)"),
    ("archive_creators", "Arkivskapere / historiske kommuner", "Depotopplysninger (ikke METS)"),
    ("system_region", "IT-/systemregion", "Depotopplysninger (ikke METS)"),
    ("delivery_information", "Informasjon om innleveringen", "Depotopplysninger (ikke METS)"),
)


class MetadataA16Error(ValueError):
    """Unsafe, changed, missing or contradictory metadata source/Work."""


def _sha(data: bytes) -> str:
    return sha256(data).hexdigest()


def _canonical_json(value: dict) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":")).encode("utf-8")


def _work_path(work: str | Path, relative: str) -> Path:
    """Reject escaping Work and symlinks, including a symlinked parent."""
    root = Path(work).resolve(strict=True)
    rel = relative.replace("\\", "/")
    part = Path(rel)
    if (not rel or part.is_absolute() or rel.startswith("/") or
            any(x in (".", "..", "") for x in part.parts) or ":" in rel):
        raise MetadataA16Error("Ugyldig Work-relativ filsti")
    cursor = root
    for piece in part.parts:
        cursor = cursor / piece
        if cursor.is_symlink():
            raise MetadataA16Error("Symbolsk lenke i Work-sti er ikke tillatt")
    if not cursor.resolve(strict=False).is_relative_to(root):
        raise MetadataA16Error("Kilde eller mål utenfor Work")
    return cursor


def _read_json(path: Path, max_size: int = MAX_META) -> dict:
    if not path.is_file() or path.is_symlink() or path.stat().st_size > max_size:
        raise MetadataA16Error("Manglende, utrygg eller for stor Work-fil: " + path.name)
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError) as exc:
        raise MetadataA16Error("Ugyldig JSON: " + path.name) from exc
    if not isinstance(value, dict):
        raise MetadataA16Error("JSON-roten må være et objekt")
    return value


def _write_json(path: Path, payload: dict) -> None:
    if path.exists() and (path.is_symlink() or not path.is_file()):
        raise MetadataA16Error("Utrygt mål for metadata")
    if not path.parent.is_dir() or path.parent.is_symlink():
        raise MetadataA16Error("Mangler sikker metadata-katalog")
    data = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8") + b"\n"
    if len(data) > MAX_META:
        raise MetadataA16Error("Metadatafilen blir for stor")
    temp = path.with_name("." + uuid4().hex + ".tmp")
    try:
        with temp.open("xb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp, path)
    finally:
        if temp.exists():
            temp.unlink()


def _identity(work: Path) -> tuple[str, str]:
    job = _read_json(_work_path(work, "job.json"))
    if job.get("file_type") != "dwm-work-job":
        raise MetadataA16Error("Valgt mappe er ikke en DWM Work-jobb")
    job_data = job.get("job") or {}
    if not isinstance(job_data, dict):
        raise MetadataA16Error("Work mangler gyldig jobbidentitet")
    uid = str(job.get("job_uid") or job_data.get("job_uid") or "").strip()
    alias = str(job_data.get("job_id") or "").strip()
    if not uid or not alias:
        raise MetadataA16Error("Work mangler jobb-UID eller jobbnøkkel")
    return uid, alias


def _work_metadata(work: Path, alias: str) -> tuple[dict, str | None]:
    path = _work_path(work, WORK_META)
    if not path.exists():
        return {"file_type": "dwm-depot-metadata", "format_version": 3,
                "job_id": alias, "updated_at": "", "source_imports": [],
                "current": {}, "review": {"history": []}}, None
    raw = path.read_bytes()
    meta = _read_json(path)
    if meta.get("file_type") != "dwm-depot-metadata" or meta.get("job_id") != alias:
        raise MetadataA16Error("Work-metadata tilhører ikke den valgte jobben")
    if not isinstance(meta.get("current"), dict) or not isinstance(meta.get("source_imports"), list):
        raise MetadataA16Error("Ugyldig metadatastruktur")
    if not isinstance(meta.get("review") or {}, dict):
        raise MetadataA16Error("Ugyldig vurderingshistorikk")
    return meta, _sha(raw)


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _xml_tree(data: bytes) -> tuple[ET.Element, str]:
    if not data or len(data) > MAX_XML:
        raise MetadataA16Error("METS-kilde mangler eller overstiger 32 MiB")
    if b"<!DOCTYPE" in data.upper() or b"<!ENTITY" in data.upper():
        raise MetadataA16Error("DTD og entitetsdeklarasjoner er ikke tillatt")
    try:
        root = ET.fromstring(data)
    except ET.ParseError as exc:
        raise MetadataA16Error("Kilden er ikke gyldig XML") from exc
    namespace = root.tag.partition("}")[0].lstrip("{") if root.tag.startswith("{") else ""
    if namespace not in ALLOWED_NS or _local(root.tag) != "mets":
        raise MetadataA16Error("XML må være ytre METS eller indre DIAS METS")
    return root, "ytre info.xml" if namespace == LOC_NS else "indre dias-mets.xml"


def _qname(value: str) -> str:
    if value.startswith("{"):
        namespace, local = value[1:].split("}", 1)
        prefix = {LOC_NS: "mets", INNER_NS: "dias", "http://www.w3.org/1999/xlink": "xlink",
                  "http://www.w3.org/2001/XMLSchema-instance": "xsi"}.get(namespace)
        return (prefix if prefix else "{" + namespace + "}") + ":" + local
    return value


def _inventory(root: ET.Element) -> dict[str, dict]:
    """Index ALL text-bearing elements and attributes by ordinal full path.

    No first-occurrence collapse: multiple owners/contacts, extensions and file
    entries retain distinct paths. Empty elements are recorded as structure.
    """
    records: dict[str, dict] = {}
    count = 0
    stack = [(root, "/" + _qname(root.tag) + "[1]", 0)]
    while stack:
        node, path, depth = stack.pop()
        count += 1
        if count > MAX_NODES or depth > 100:
            raise MetadataA16Error("METS-strukturen overskrider sikker indeksgrense")
        group = ("Filfortegnelse" if "/mets:fileSec" in path or "/dias:fileSec" in path else
                 "Aktører / programvare" if "/mets:agent" in path or "/dias:agent" in path else
                 "METS-header" if "/mets:metsHdr" in path or "/dias:metsHdr" in path else
                 "METS-rot / struktur")
        if node.attrib:
            for name, value in sorted(node.attrib.items()):
                key = path + "/@" + _qname(name)
                records[key] = {"key": key, "label": _qname(name), "group": group,
                                "source_value": value, "editable": True}
        value = node.text or ""
        if value.strip():
            key = path + "/text()"
            records[key] = {"key": key, "label": _qname(node.tag) + " tekst", "group": group,
                            "source_value": value, "editable": True}
        elif len(node) == 0:
            key = path + "/[tomt element]"
            records[key] = {"key": key, "label": _qname(node.tag) + " (tomt)", "group": group,
                            "source_value": "", "editable": False}
        if (node.tail or "").strip():
            # Mixed XML content also survives the full metadata inventory.
            key = path + "/tail()"
            records[key] = {"key": key, "label": "Tekst etter " + _qname(node.tag),
                            "group": group, "source_value": node.tail, "editable": True}
        sibling_count: dict[str, int] = defaultdict(int)
        children = []
        for child in node:
            sibling_count[child.tag] += 1
            children.append((child, path + "/" + _qname(child.tag) +
                             f"[{sibling_count[child.tag]}]", depth + 1))
        stack.extend(reversed(children))
    return records


def _children(node: ET.Element | None, name: str) -> list[ET.Element]:
    return [child for child in node if _local(child.tag) == name] if node is not None else []


def _first(node: ET.Element | None, name: str) -> ET.Element | None:
    arr = _children(node, name)
    return arr[0] if arr else None


def _content(node: ET.Element | None) -> str:
    return (node.text or "").strip() if node is not None else ""


def _notes(agent: ET.Element) -> dict[str, str]:
    items = [_content(x) for x in _children(agent, "note") if _content(x)]
    markers = [x for x in items if x.startswith("notescontent:")]
    values = [x for x in items if not x.startswith("notescontent:")]
    if markers:
        keys = [x.strip() for x in markers[-1][len("notescontent:"):].split(",")]
        if len(keys) == len(values):
            return dict(zip(keys, values))
    # Older, pre-notescontent files used positional notes. The original values
    # remain inspectable in full in the raw XML inventory even when mapping is
    # ambiguous; this fallback should not guess names for contact notes.
    return {}


def _canonical_source(root: ET.Element) -> dict[str, str]:
    """Source presentation of the 47 Arkade fields; raw inventory remains exact."""
    result: dict[str, str] = {}
    if root.get("LABEL") is not None:
        result["label"] = root.get("LABEL", "")
    hdr = _first(root, "metsHdr")
    if hdr is None:
        return result
    result["record_status"] = hdr.get("RECORDSTATUS", "")
    identifiers = {"DELIVERYSPECIFICATION": "archive_description", "SUBMISSIONAGREEMENT": "submission_agreement",
                   "DELIVERYTYPE": "delivery_type", "PROJECTNAME": "project_name",
                   "PACKAGENUMBER": "package_number", "REFERENCECODE": "reference_code",
                   "STARTDATE": "period_start", "ENDDATE": "period_end"}
    for alt in _children(hdr, "altRecordID"):
        key = identifiers.get(str(alt.get("TYPE") or "").upper())
        if key and key not in result:
            result[key] = _content(alt)
    specs = {"ARCHIVIST": "archivist", "SUBMITTER": "submitter", "PRODUCER": "producer",
             "IPOWNER": "owner", "CREATOR": "creator"}
    for agent in _children(hdr, "agent"):
        role = agent.get("OTHERROLE") if agent.get("ROLE") == "OTHER" else agent.get("ROLE")
        role = str(role or "").upper()
        typ = str(agent.get("TYPE") or "").upper()
        name = _content(_first(agent, "name"))
        if typ == "ORGANIZATION" and role == "PRESERVATION":
            result.setdefault("recipient", name)
        elif typ == "ORGANIZATION" and role in specs:
            result.setdefault(specs[role] + "_org", name)
        elif typ == "INDIVIDUAL" and role in specs:
            prefix = specs[role]
            result.setdefault(prefix + "_person", name)
            notes = _notes(agent)
            for src, dst in (("Address", "address"), ("Telephone", "phone"), ("Email", "email")):
                if src in notes:
                    result.setdefault(prefix + "_" + dst, notes[src])
        elif typ == "OTHER" and agent.get("OTHERTYPE") == "SOFTWARE":
            if role == "CREATOR":
                result.setdefault("mets_creator_software", name)
                result.setdefault("mets_creator_software_version", _notes(agent).get("Version", ""))
            elif role in ("ARCHIVIST", "PRODUCER"):
                prefix = "system" if role == "ARCHIVIST" else "extraction_system"
                result.setdefault(prefix, name)
                notes = _notes(agent)
                for src, dst in (("Version", "version"), ("Type", "type"), ("TypeVersion", "type_version")):
                    if src in notes:
                        result.setdefault(prefix + "_" + dst, notes[src])
    # The extraction date deliberately has NO asserted outer XML mapping.
    return result


def _canonical_xml_paths(root: ET.Element) -> dict[str, str]:
    """Link the FIRST Arkade field occurrence to its canonical Work key.

    This prevents editing a field twice through the 47-field form and the raw
    XML inventory. Extra repeated agents/notes remain independently editable.
    """
    base = "/" + _qname(root.tag) + "[1]"
    links = {base + "/@LABEL": "label"}
    hdr = _first(root, "metsHdr")
    if hdr is None:
        return links
    hp = base + "/" + _qname(hdr.tag) + "[1]"
    links[hp + "/@RECORDSTATUS"] = "record_status"
    altkeys = {"DELIVERYSPECIFICATION": "archive_description",
               "SUBMISSIONAGREEMENT": "submission_agreement",
               "DELIVERYTYPE": "delivery_type", "PROJECTNAME": "project_name",
               "PACKAGENUMBER": "package_number", "REFERENCECODE": "reference_code",
               "STARTDATE": "period_start", "ENDDATE": "period_end"}
    taken = set()
    for i, alt in enumerate(_children(hdr, "altRecordID"), 1):
        k = altkeys.get(str(alt.get("TYPE") or "").upper())
        if k and k not in taken:
            links[hp + "/" + _qname(alt.tag) + f"[{i}]/text()"] = k
            taken.add(k)
    role_names = {"ARCHIVIST": "archivist", "SUBMITTER": "submitter",
                  "PRODUCER": "producer", "IPOWNER": "owner", "CREATOR": "creator"}
    used = set()
    for i, agent in enumerate(_children(hdr, "agent"), 1):
        role = agent.get("OTHERROLE") if agent.get("ROLE") == "OTHER" else agent.get("ROLE")
        role = str(role or "").upper()
        kind = str(agent.get("TYPE") or "").upper()
        prefix = role_names.get(role)
        name = _first(agent, "name")
        ap = hp + "/" + _qname(agent.tag) + f"[{i}]"
        if kind == "ORGANIZATION" and role == "PRESERVATION":
            key = "recipient"
        elif kind == "ORGANIZATION" and prefix:
            key = prefix + "_org"
        elif kind == "INDIVIDUAL" and prefix:
            key = prefix + "_person"
        elif kind == "OTHER" and agent.get("OTHERTYPE") == "SOFTWARE":
            key = {"CREATOR": "mets_creator_software", "ARCHIVIST": "system",
                   "PRODUCER": "extraction_system"}.get(role)
        else:
            key = None
        if key and key not in used and name is not None:
            links[ap + "/" + _qname(name.tag) + "[1]/text()"] = key
            used.add(key)
        values = _children(agent, "note")
        marker = next((n for n in values if _content(n).startswith("notescontent:")), None)
        if marker is None:
            continue
        parts = [x.strip() for x in _content(marker)[len("notescontent:"):].split(",")]
        items = [(j, n) for j, n in enumerate(values, 1) if not _content(n).startswith("notescontent:")]
        if len(parts) != len(items):
            continue
        for (j, note), field in zip(items, parts):
            if kind == "INDIVIDUAL" and prefix:
                suffix = {"Address": "address", "Telephone": "phone", "Email": "email"}.get(field)
                child_key = prefix + "_" + suffix if suffix else None
            elif kind == "OTHER" and key == "mets_creator_software":
                child_key = "mets_creator_software_version" if field == "Version" else None
            elif kind == "OTHER" and key in ("system", "extraction_system"):
                suffix = {"Version": "version", "Type": "type", "TypeVersion": "type_version"}.get(field)
                child_key = key + "_" + suffix if suffix else None
            else:
                child_key = None
            if child_key and child_key not in used:
                links[ap + "/" + _qname(note.tag) + f"[{j}]/text()"] = child_key
                used.add(child_key)
    return links


def _sources(work: Path, meta: dict) -> list[dict]:
    sources = []
    for item in meta.get("source_imports") or []:
        if not isinstance(item, dict) or item.get("kind") != "dias-mets":
            continue
        if not item.get("preserved_file") or not item.get("sha256"):
            continue  # historical values may exist without a verifiable byte copy
        sources.append({"source": "opprinnelig import", "path": str(item["preserved_file"]),
                        "sha256": str(item["sha256"]).lower(),
                        "original_name": Path(str(item.get("path") or "info.xml")).name})
    index = _work_path(work, INNER_INDEX)
    if index.exists():
        entries = _read_json(index).get("sources")
        if not isinstance(entries, list) or len(entries) > 100:
            raise MetadataA16Error("Ugyldig indre METS-kilderegister")
        for item in entries:
            if not isinstance(item, dict):
                raise MetadataA16Error("Ugyldig METS-kildereferanse")
            sources.append(dict(item))
    seen = set()
    unique = []
    for item in sources:
        binding = item.get("sha256")
        if binding not in seen:
            seen.add(binding)
            unique.append(item)
    return unique


def _read_source(work: Path, source: dict) -> tuple[ET.Element, dict, str]:
    relative = str(source.get("path") or "")
    file = _work_path(work, relative)
    if not file.is_file():
        raise MetadataA16Error("Bevart kildefil mangler: " + relative)
    if file.stat().st_size > MAX_XML:
        raise MetadataA16Error("Bevart kildefil overstiger 32 MiB")
    data = file.read_bytes()
    if _sha(data) != str(source.get("sha256") or "").lower():
        raise MetadataA16Error("SHA-256-avvik i bevart METS-kopi")
    root, kind = _xml_tree(data)
    return root, _inventory(root), kind


def _raw_events(work: Path, uid: str, source_sha: str) -> dict[str, dict]:
    folder = _work_path(work, EVENT_DIR)
    if not folder.exists():
        return {}
    if not folder.is_dir() or folder.is_symlink():
        raise MetadataA16Error("Ugyldig METS-endringsmappe")
    items = list(folder.iterdir())
    if len(items) > MAX_EVENTS:
        raise MetadataA16Error("For mange METS-endringshendelser")
    events = []
    for path in items:
        if path.suffix != ".json" or path.is_symlink() or not path.is_file():
            raise MetadataA16Error("Ukjent fil i endringshistorikken")
        record = _read_json(path, 20000)
        digest = record.pop("event_sha256", "")
        if record.get("model") != MODEL or digest != _sha(_canonical_json(record)):
            raise MetadataA16Error("METS-endringshendelse er endret")
        if record.get("job_uid") != uid:
            raise MetadataA16Error("METS-endringshendelse tilhører annen jobb")
        if record.get("source_sha256") == source_sha:
            events.append(record)
    events.sort(key=lambda x: (x["created_utc"], x["event_id"]))
    return {str(item["path"]): item for item in events}


def load_metadata(work: str | Path, source_sha256: str | None = None) -> dict:
    """Unified 47-field Work view plus lossless original XML field occurrences."""
    root = Path(work).resolve(strict=True)
    uid, alias = _identity(root)
    meta, fingerprint = _work_metadata(root, alias)
    sources = _sources(root, meta)
    source = next((s for s in sources if s["sha256"] == source_sha256), None) if source_sha256 else (
        sources[0] if sources else None)
    if source_sha256 and source is None:
        raise MetadataA16Error("Valgt METS-kilde finnes ikke i Work")
    original, items, kind = ({}, {}, "Ingen bevart XML-kilde")
    raw_links = {}
    xml_root = None
    reference_evidence: dict[str, dict] = {}
    if source:
        xml_root, items, kind = _read_source(root, source)
        original = _canonical_source(xml_root)
        raw_links = _canonical_xml_paths(xml_root)
        category = "outer" if kind == "ytre info.xml" else "inner"
        reference_evidence[category] = {
            "source": source, "canonical": original, "links": raw_links,
            "items": items,
        }
    # A selected info.xml never stands in for inner DIAS-METS, and vice versa.
    # When both are in Work, resolve actual element occurrences separately.
    # Only the first verified source of the missing type is paired with the
    # explicitly selected source. Source identifiers are included in the result.
    if len(reference_evidence) < 2:
        for candidate in sources:
            if source and candidate["sha256"] == source["sha256"]:
                continue
            declared = str(candidate.get("kind") or "")
            if (declared == "ytre info.xml" and "outer" in reference_evidence or
                    declared == "indre dias-mets.xml" and "inner" in reference_evidence):
                continue
            peer_root, peer_items, peer_kind = _read_source(root, candidate)
            category = "outer" if peer_kind == "ytre info.xml" else "inner"
            if category not in reference_evidence:
                reference_evidence[category] = {
                    "source": candidate, "canonical": _canonical_source(peer_root),
                    "links": _canonical_xml_paths(peer_root), "items": peer_items,
                }
            if len(reference_evidence) == 2:
                break
    references = field_references(tuple(field for field, *_ in FIELD_ROWS), reference_evidence)
    current = meta.get("current") or {}
    recorded = (meta.get("review") or {}).get("history") or []
    explicitly_edited = {x.get("path") for x in recorded
                         if isinstance(x, dict) and x.get("model") == MODEL and
                         x.get("kind") in ("canonical", "depot")}
    rows = []
    comparisons = {}
    for key, label, group in FIELD_ROWS:
        value = str(current.get(key) or "")
        historical = original.get(key)
        status = ("endret i Work" if historical is None and key in explicitly_edited else
                  "uten kilde" if historical is None else
                  "lik" if value == historical else
                  "ikke registrert" if not value and key not in explicitly_edited else "ulik")
        comparisons[key] = status
        outer = references[key]["outer"]
        inner = references[key]["inner"]
        source_conflict = bool(outer["status"] == "påvist" and inner["status"] == "påvist" and
                               outer["value"] != inner["value"])
        rows.append({"id": "field:" + key, "kind": "canonical", "group": group,
                     "label": label, "key": key, "historical": historical, "current": value,
                     "status": status, "changed": status in ("ulik", "endret i Work"),
                     "editable": True, "references": references[key],
                     "source_conflict": source_conflict})
    for key, label, group in DEPOT_ROWS:
        value = str(current.get(key) or "")
        rows.append({"id": "depot:" + key, "kind": "depot", "group": group,
                     "label": label, "key": key, "historical": None, "current": value,
                     "status": "kun Work", "changed": False, "editable": True,
                     "references": None})
    edits = _raw_events(root, uid, source["sha256"]) if source else {}
    for path, row in items.items():
        linked = raw_links.get(path)
        event = edits.get(path)
        value = (str(current.get(linked) or "") if linked else
                 event["new_value"] if event else row["source_value"])
        state = (comparisons.get(linked, "uten kilde") if linked else
                 "endret" if event and value != row["source_value"] else "lik")
        rows.append({"id": "xml:" + path, "kind": "xml", "group": row["group"],
                     "label": row["label"] + (" (rediger via 47-feltlisten)" if linked else ""),
                     "key": path, "historical": row["source_value"],
                     "current": value, "status": state, "linked_to": linked,
                     "changed": state in ("ulik", "endret", "endret i Work"),
                     "editable": row["editable"] and not bool(linked) and
                                 not technical_read_only(path)})
    extended = extended_mets_rows(xml_root, rows, raw_links)
    return {"model": MODEL, "work": str(root), "job_uid": uid, "job_id": alias,
            "metadata_sha256": fingerprint, "sources": sources, "selected_source": source,
            "source_type": kind, "rows": rows,
            "extended_rows": extended, "field_references": references,
            "paired_sources": {key: {"sha256": value["source"]["sha256"],
                                     "original_name": value["source"].get("original_name"),
                                     "kind": key}
                               for key, value in reference_evidence.items()},
            "canonical_count": len(FIELD_ROWS),
            "depot_field_count": len(DEPOT_ROWS),
            "xml_field_count": len(items),
            "paired_differences": sum(int(r.get("source_conflict", False)) for r in rows),
            "changed": sum(int(r["changed"]) for r in rows
                if not (r["kind"] == "xml" and r.get("linked_to"))),
            "source_original_preserved": bool(source),
            "notes": "Ulikt innhold krever faglig vurdering – ingen automatisk godkjenning."}


def _require_editor(author: dict, comment: str, current: str, new_value: str) -> None:
    if not isinstance(author, dict) or not str(author.get("user_id") or "").strip():
        raise MetadataA16Error("Registrert DWM-brukerprofil kreves")
    if not comment.strip() or len(comment) > 1500:
        raise MetadataA16Error("Oppgi en begrunnelse (maks 1500 tegn)")
    if len(new_value) > MAX_FIELD_VALUE or "\x00" in new_value:
        raise MetadataA16Error("Ugyldig eller for lang metadataverdi")
    if current == new_value:
        raise MetadataA16Error("Ingen endring å lagre")


def save_field(work: str | Path, *, source_sha256: str | None, row_id: str,
               previous_value: str, new_value: str, comment: str, author: dict,
               expected_metadata_sha256: str | None = None) -> dict:
    """Save an intentional correction; do not change either original METS file."""
    current = load_metadata(work, source_sha256)
    row = next((x for x in current["rows"] if x["id"] == row_id), None)
    if row is None or not row["editable"]:
        raise MetadataA16Error("Ukjent eller ikke-redigerbart metadatafelt")
    if row["current"] != previous_value:
        raise MetadataA16Error("Metadataverdien er endret av en annen operasjon. Oppdater visningen.")
    _require_editor(author, comment, previous_value, new_value)
    root = Path(work).resolve(strict=True)
    event = {"model": MODEL, "event_id": str(uuid4()),
             "created_utc": datetime.now(timezone.utc).isoformat(timespec="microseconds"),
             "job_uid": current["job_uid"], "source_sha256": source_sha256,
             "path": row["key"], "kind": row["kind"],
             "old_value": previous_value, "new_value": new_value,
             "reason": comment.strip(), "author": author}
    if row["kind"] in ("canonical", "depot"):
        if expected_metadata_sha256 != current["metadata_sha256"]:
            raise MetadataA16Error("Work-metadata er endret; oppdater før lagring")
        meta, _ = _work_metadata(root, current["job_id"])
        if not isinstance(meta.get("review") or {}, dict):
            raise MetadataA16Error("Ugyldig historikk")
        review = meta.setdefault("review", {})
        history = review.setdefault("history", [])
        if not isinstance(history, list) or len(history) >= 10000:
            raise MetadataA16Error("Ugyldig eller full metadataversjonshistorikk")
        history.append(event)
        meta.setdefault("current", {})[row["key"]] = new_value
        meta["updated_at"] = event["created_utc"]
        _write_json(_work_path(root, WORK_META), meta)
    else:
        if source_sha256 is None or current["selected_source"] is None:
            raise MetadataA16Error("XML-kilden må være valgt og SHA-verifisert")
        event["event_sha256"] = _sha(_canonical_json(event))
        folder = _work_path(root, EVENT_DIR)
        if not folder.exists():
            folder.mkdir(parents=True, exist_ok=True)
        if folder.is_symlink() or len(list(folder.iterdir())) >= MAX_EVENTS:
            raise MetadataA16Error("Endringskatalog kan ikke brukes")
        path = folder / (event["event_id"] + ".json")
        data = json.dumps(event, ensure_ascii=False, indent=2).encode("utf-8") + b"\n"
        with path.open("xb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
    return event


def import_inner_mets(work: str | Path, candidate: str | Path) -> dict:
    """Import either METS type as immutable, SHA-verified Work evidence.

    The source path is read only. This supplements existing info.xml imports and
    never guesses that an inner DIAS document exists in an unpacked extraction.
    """
    root = Path(work).resolve(strict=True)
    uid, alias = _identity(root)
    _work_metadata(root, alias)  # validate job-bound metadata before writing
    src = Path(candidate)
    if not src.is_file() or src.is_symlink() or src.stat().st_size > MAX_XML:
        raise MetadataA16Error("Velg en vanlig METS XML-fil på høyst 32 MiB")
    data = src.read_bytes()
    doc, kind = _xml_tree(data)
    _inventory(doc)  # reject structures that cannot be fully indexed
    sha = _sha(data)
    index_path = _work_path(root, INNER_INDEX)
    old = _read_json(index_path) if index_path.exists() else {"model": MODEL, "job_uid": uid, "sources": []}
    if old.get("job_uid") != uid or not isinstance(old.get("sources"), list):
        raise MetadataA16Error("METS-kilderegister tilhører feil jobb")
    for entry in old["sources"]:
        if entry.get("sha256") == sha:
            _read_source(root, entry)  # verify existing immutable copy
            return entry
    folder = _work_path(root, "metadata/source_evidence")
    if not folder.exists():
        folder.mkdir(parents=True, exist_ok=True)
    evidence = _work_path(root, "metadata/source_evidence/a16-" + sha[:20])
    if not evidence.exists():
        evidence.mkdir()
    destination = _work_path(root, "metadata/source_evidence/a16-" + sha[:20] + "/imported-mets.xml")
    if destination.exists():
        if _sha(destination.read_bytes()) != sha:
            raise MetadataA16Error("Bevart kildefil er endret")
    else:
        with destination.open("xb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
    entry = {"source": "manuelt bevart METS", "path": destination.relative_to(root).as_posix(),
             "sha256": sha, "original_name": src.name, "kind": kind,
             "imported_utc": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    old["sources"].append(entry)
    if len(old["sources"]) > 100:
        raise MetadataA16Error("For mange METS-kilder")
    _write_json(index_path, old)
    # Keep the existing 47-field metadata editor aware of manually imported
    # *outer* info.xml. Inner DIAS-METS uses a different namespace and cannot
    # be passed to the old LOC-only importer as though it were outer METS.
    if kind == "ytre info.xml":
        meta, _ = _work_metadata(root, alias)
        imports = meta.setdefault("source_imports", [])
        if not any(isinstance(x, dict) and str(x.get("sha256") or "").lower() == sha
                   for x in imports):
            imports.append({"kind": "dias-mets", "path": str(src),
                            "sha256": sha, "preserved_file": entry["path"],
                            "fields": _canonical_source(doc),
                            "fields_mapper": "arkade5-dias-v3",
                            "imported_at": entry["imported_utc"]})
            _write_json(_work_path(root, WORK_META), meta)
    return entry
