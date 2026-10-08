from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

METS_NS = "http://www.loc.gov/METS/"
XLINK_NS = "http://www.w3.org/1999/xlink"
XSI_NS = "http://www.w3.org/2001/XMLSchema-instance"
EARD_PROFILE = "http://xml.ra.se/METS/RA_METS_eARD.xml"
SUBMISSION_DESCRIPTION_XSD = "https://schema.arkivverket.no/INFOFIL/latest/submissionDescription.xsd"
DIAS_METS_XSD = "https://schema.arkivverket.no/INFOFIL/latest/DIAS_METS.xsd"

# Canonical editable DIAS metadata, ordered exactly like rows 1-47 in
# 0000-metadata-arkade.xlsx / the Arkade 5 metadata GUI.
DIAS_METADATA_FIELDS = (
    "archive_description",       # 1  DELIVERYSPECIFICATION
    "submission_agreement",      # 2  SUBMISSIONAGREEMENT
    "record_status",             # 3  metsHdr/@RECORDSTATUS
    "delivery_type",             # 4  DELIVERYTYPE
    "project_name",              # 5  PROJECTNAME (legacy/inner creator supports it)
    "package_number",            # 6  PACKAGENUMBER
    "reference_code",            # 7  REFERENCECODE
    "archivist_org",             # 8  ARCHIVIST / ORGANIZATION
    "archivist_person",          # 9  ARCHIVIST / INDIVIDUAL
    "archivist_address",         # 10 note
    "archivist_phone",           # 11 note
    "archivist_email",           # 12 note
    "submitter_org",             # 13 OTHER/SUBMITTER / ORGANIZATION
    "submitter_person",          # 14 OTHER/SUBMITTER / INDIVIDUAL
    "submitter_address",         # 15 note
    "submitter_phone",           # 16 note
    "submitter_email",           # 17 note
    "producer_org",              # 18 OTHER/PRODUCER / ORGANIZATION
    "producer_person",           # 19 OTHER/PRODUCER / INDIVIDUAL
    "producer_address",          # 20 note
    "producer_phone",            # 21 note
    "producer_email",            # 22 note
    "owner_org",                 # 23 IPOWNER / ORGANIZATION
    "owner_person",              # 24 IPOWNER / INDIVIDUAL
    "owner_address",             # 25 note
    "owner_phone",               # 26 note
    "owner_email",               # 27 note
    "creator_org",               # 28 CREATOR / ORGANIZATION (creator of metadata)
    "creator_person",            # 29 CREATOR / INDIVIDUAL
    "creator_address",           # 30 note
    "creator_phone",             # 31 note
    "creator_email",             # 32 note
    "mets_creator_software",     # 33 CREATOR / OTHER / SOFTWARE
    "mets_creator_software_version", # 34 note Version
    "recipient",                 # 35 PRESERVATION / ORGANIZATION
    "system",                    # 36 ARCHIVIST / OTHER / SOFTWARE
    "system_version",            # 37 note Version
    "system_type",               # 38 note Type
    "system_type_version",       # 39 note TypeVersion
    "extraction_system",         # 40 OTHER/PRODUCER / OTHER / SOFTWARE
    "extraction_system_version", # 41 note Version
    "extraction_system_type",    # 42 note Type
    "extraction_system_type_version", # 43 note TypeVersion
    "period_start",              # 44 STARTDATE
    "period_end",                # 45 ENDDATE
    "extraction_date",           # 46 depot field; XML location not yet approved
    "label",                     # 47 mets/@LABEL
)

# Previous DWM a1/a2 keys kept as compatibility aliases.  The canonical
# metadata model above is authoritative from v0.1.7-a2 onward.
LEGACY_TO_CANONICAL = {
    "creator": "creator_org",
    "preserver": "recipient",
    "archivist_type": "system_type",
    "producer_software": "extraction_system",
}
CANONICAL_TO_LEGACY = {value: key for key, value in LEGACY_TO_CANONICAL.items()}


def _tag(local: str) -> str:
    return f"{{{METS_NS}}}{local}"


def _text(node: ET.Element | None) -> str:
    return (node.text or "").strip() if node is not None else ""


def _name(agent: ET.Element) -> str:
    return _text(agent.find(_tag("name")))


def _notes(agent: ET.Element) -> list[str]:
    return [_text(node) for node in agent.findall(_tag("note")) if _text(node)]


def _parse_notes(notes: list[str], *, system: bool = False) -> dict[str, str]:
    """Parse Arkade 5 HdrAgentNotesWriter/Loader note conventions.

    Arkade 5 writes ordinary notes followed by a marker such as
    ``notescontent:Version,Type,TypeVersion``.  Older files can lack that
    marker, so bounded content heuristics are retained as a fallback.
    """
    marker = next((n for n in notes if n.startswith("notescontent:")), "")
    content = [n for n in notes if n != marker]
    result: dict[str, str] = {}

    if marker:
        fields = [part.strip() for part in marker[len("notescontent:"):].split(",") if part.strip()]
        if len(fields) == len(content):
            for field, value in zip(fields, content):
                key = {
                    "Address": "address",
                    "Telephone": "phone",
                    "Email": "email",
                    "Version": "version",
                    "Type": "type",
                    "TypeVersion": "type_version",
                }.get(field)
                if key and value:
                    result[key] = value
            return result

    if system:
        if content:
            result["version"] = content[0]
        if len(content) > 1:
            result["type"] = content[1]
        if len(content) > 2:
            result["type_version"] = content[2]
        return result

    for value in content:
        if "@" in value and "email" not in result:
            result["email"] = value
        elif re.fullmatch(r"\+?(?:[\d .()/-]*\d)", value) and "phone" not in result:
            result["phone"] = value
        elif "address" not in result:
            result["address"] = value
    return result


def _set_entity(fields: dict[str, str], prefix: str, org: ET.Element | None, person: ET.Element | None) -> None:
    if org is not None:
        fields[f"{prefix}_org"] = _name(org)
    if person is not None:
        fields[f"{prefix}_person"] = _name(person)
        notes = _parse_notes(_notes(person))
        for suffix in ("address", "phone", "email"):
            value = notes.get(suffix, "")
            if value:
                fields[f"{prefix}_{suffix}"] = value


def _find_agents(hdr: ET.Element, *, role: str, type_: str | None = None, otherrole: str | None = None, othertype: str | None = None) -> list[ET.Element]:
    result: list[ET.Element] = []
    for agent in hdr.findall(_tag("agent")):
        if (agent.get("ROLE") or "").upper() != role:
            continue
        if type_ is not None and (agent.get("TYPE") or "").upper() != type_:
            continue
        if otherrole is not None and (agent.get("OTHERROLE") or "").upper() != otherrole:
            continue
        if othertype is not None and (agent.get("OTHERTYPE") or "").upper() != othertype:
            continue
        result.append(agent)
    return result


def _first(items: list[ET.Element]) -> ET.Element | None:
    return items[0] if items else None


def _with_legacy_aliases(fields: dict[str, str]) -> dict[str, str]:
    result = dict(fields)
    for old, new in LEGACY_TO_CANONICAL.items():
        value = result.get(new, "")
        if value and not result.get(old):
            result[old] = value
    return result


def read_meta_from_mets(mets_path: str | Path) -> dict[str, str]:
    """Read DIAS/Arkade metadata from package-level or inner METS XML.

    This follows the current Arkade 5 ArchiveMetadata mapping rather than the
    earlier DWM approximation.  The same metadata model is shared by the outer
    submission description (commonly info.xml) and the inner dias-mets.xml.
    """
    try:
        root = ET.parse(str(mets_path)).getroot()
    except ET.ParseError as exc:
        raise ValueError(f"Ugyldig XML: {exc}") from exc
    except OSError as exc:
        raise ValueError(f"Kunne ikke lese filen: {exc}") from exc

    if root.tag != _tag("mets"):
        raise ValueError("Filen er ikke en METS-fil (forventet mets:mets som rotelement).")

    fields: dict[str, str] = {}
    label = (root.get("LABEL") or "").strip()
    if label:
        fields["label"] = label

    hdr = root.find(_tag("metsHdr"))
    if hdr is None:
        return _with_legacy_aliases(fields)

    record_status = (hdr.get("RECORDSTATUS") or "").strip()
    if record_status:
        fields["record_status"] = record_status

    alt_map = {
        "DELIVERYSPECIFICATION": "archive_description",
        "SUBMISSIONAGREEMENT": "submission_agreement",
        "DELIVERYTYPE": "delivery_type",
        "PROJECTNAME": "project_name",
        "PACKAGENUMBER": "package_number",
        "REFERENCECODE": "reference_code",
        "STARTDATE": "period_start",
        "ENDDATE": "period_end",
    }
    for alt in hdr.findall(_tag("altRecordID")):
        kind = (alt.get("TYPE") or "").upper()
        key = alt_map.get(kind)
        value = _text(alt)
        if key and value:
            fields[key] = value

    # Entity roles: Arkade 5 groups an organization agent followed by a matching
    # individual agent containing contact notes.
    role_specs = {
        "archivist": ("ARCHIVIST", None),
        "submitter": ("OTHER", "SUBMITTER"),
        "producer": ("OTHER", "PRODUCER"),
        "owner": ("IPOWNER", None),
        "creator": ("CREATOR", None),
    }
    for prefix, (role, otherrole) in role_specs.items():
        orgs = _find_agents(hdr, role=role, type_="ORGANIZATION", otherrole=otherrole)
        people = _find_agents(hdr, role=role, type_="INDIVIDUAL", otherrole=otherrole)
        _set_entity(fields, prefix, _first(orgs), _first(people))

    # Software creator of the METS document itself.
    sw_creator = _first(_find_agents(hdr, role="CREATOR", type_="OTHER", othertype="SOFTWARE"))
    if sw_creator is not None:
        fields["mets_creator_software"] = _name(sw_creator)
        notes = _parse_notes(_notes(sw_creator), system=True)
        if notes.get("version"):
            fields["mets_creator_software_version"] = notes["version"]

    recipient = _first(_find_agents(hdr, role="PRESERVATION", type_="ORGANIZATION"))
    if recipient is not None:
        fields["recipient"] = _name(recipient)

    system_agents = _find_agents(hdr, role="ARCHIVIST", type_="OTHER", othertype="SOFTWARE")
    system_agent = _first(system_agents)
    if system_agent is not None:
        fields["system"] = _name(system_agent)
        notes = _parse_notes(_notes(system_agent), system=True)
        for source, target in (("version", "system_version"), ("type", "system_type"), ("type_version", "system_type_version")):
            if notes.get(source):
                fields[target] = notes[source]

        # Compatibility with DWM <= v0.1.7-a1 and other legacy METS files that
        # represented system name, version and type as three separate SOFTWARE /
        # ARCHIVIST agents instead of Arkade 5's single agent + notescontent.
        # Prefer the standards-correct Arkade note bundle above; only use the
        # positional legacy names for fields that are still missing.
        legacy_names = [_name(agent) for agent in system_agents if _name(agent)]
        if not fields.get("system_version") and len(legacy_names) > 1:
            fields["system_version"] = legacy_names[1]
        if not fields.get("system_type") and len(legacy_names) > 2:
            fields["system_type"] = legacy_names[2]

    extraction_agent = _first(_find_agents(hdr, role="OTHER", type_="OTHER", otherrole="PRODUCER", othertype="SOFTWARE"))
    if extraction_agent is not None:
        fields["extraction_system"] = _name(extraction_agent)
        notes = _parse_notes(_notes(extraction_agent), system=True)
        for source, target in (("version", "extraction_system_version"), ("type", "extraction_system_type"), ("type_version", "extraction_system_type_version")):
            if notes.get(source):
                fields[target] = notes[source]

    # Extraction date exists on the inner DIAS METS ArchiveExtraction fileGrp.
    for file_grp in root.findall(f".//{_tag('fileGrp')}"):
        if (file_grp.get("USE") or "").casefold() == "archiveextraction":
            value = (file_grp.get("VERSDATE") or "").strip()
            if value:
                fields["extraction_date"] = value
                break

    return _with_legacy_aliases(fields)


def _normalise_values(values: dict[str, Any] | None) -> dict[str, str]:
    source = dict(values or {})
    for old, new in LEGACY_TO_CANONICAL.items():
        if not str(source.get(new, "") or "").strip() and str(source.get(old, "") or "").strip():
            source[new] = source[old]
    return {key: str(source.get(key, "") or "").strip() for key in DIAS_METADATA_FIELDS}


def _normalise_date(value: str) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    # Preserve an already valid ISO date/datetime as-is.
    if re.match(r"^\d{4}-\d{2}-\d{2}(?:T.*)?$", text):
        return text
    for fmt in ("%d.%m.%Y", "%d/%m/%Y", "%Y.%m.%d"):
        try:
            return datetime.strptime(text, fmt).date().isoformat()
        except ValueError:
            pass
    return text



def _normalise_datetime(value: str) -> str:
    text = _normalise_date(value)
    if not text:
        return ""
    if "T" in text:
        return text
    if re.match(r"^\d{4}-\d{2}-\d{2}$", text):
        return text + "T00:00:00"
    return text

def _created_at(value: str | None = None) -> str:
    if value:
        return value
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _add_note_bundle(agent: ET.Element, values: list[tuple[str, str]]) -> None:
    present = [(name, str(value or "").strip()) for name, value in values if str(value or "").strip()]
    for _name, value in present:
        ET.SubElement(agent, _tag("note")).text = value
    if present:
        ET.SubElement(agent, _tag("note")).text = "notescontent:" + ",".join(name for name, _value in present)


def _add_entity_agents(hdr: ET.Element, values: dict[str, str], prefix: str, role: str, *, otherrole: str = "") -> int:
    count = 0
    org = values.get(f"{prefix}_org", "")
    person = values.get(f"{prefix}_person", "")
    base = {"ROLE": role}
    if otherrole:
        base["OTHERROLE"] = otherrole
    if org:
        attrs = {**base, "TYPE": "ORGANIZATION"}
        agent = ET.SubElement(hdr, _tag("agent"), attrs)
        ET.SubElement(agent, _tag("name")).text = org
        count += 1
    if person:
        attrs = {**base, "TYPE": "INDIVIDUAL"}
        agent = ET.SubElement(hdr, _tag("agent"), attrs)
        ET.SubElement(agent, _tag("name")).text = person
        _add_note_bundle(
            agent,
            [
                ("Address", values.get(f"{prefix}_address", "")),
                ("Telephone", values.get(f"{prefix}_phone", "")),
                ("Email", values.get(f"{prefix}_email", "")),
            ],
        )
        count += 1
    return count


def _is_noark5_format(value: str) -> bool:
    """Only Noark 5 uses TypeVersion in the current depot mapping."""
    return re.sub(r"[\s_-]+", "", str(value or "")).casefold() == "noark5"


def _add_system_agent(hdr: ET.Element, *, name: str, version: str, type_: str, type_version: str, role: str, otherrole: str = "") -> int:
    name = str(name or "").strip()
    if not name:
        return 0
    attrs = {"ROLE": role, "TYPE": "OTHER", "OTHERTYPE": "SOFTWARE"}
    if otherrole:
        attrs["OTHERROLE"] = otherrole
    agent = ET.SubElement(hdr, _tag("agent"), attrs)
    ET.SubElement(agent, _tag("name")).text = name
    _add_note_bundle(
        agent,
        [
            ("Version", version),
            ("Type", type_),
            ("TypeVersion", type_version if _is_noark5_format(type_) else ""),
        ],
    )
    return 1


def _populate_mets_header(root: ET.Element, values: dict[str, str], *, created_at: str, document_id: str | None, include_project_name: bool = True) -> tuple[ET.Element, int]:
    hdr_attrs = {"CREATEDATE": created_at}
    if values.get("record_status"):
        hdr_attrs["RECORDSTATUS"] = values["record_status"].upper()
    hdr = ET.SubElement(root, _tag("metsHdr"), hdr_attrs)

    agent_count = 0
    agent_count += _add_entity_agents(hdr, values, "archivist", "ARCHIVIST")
    agent_count += _add_entity_agents(hdr, values, "submitter", "OTHER", otherrole="SUBMITTER")
    agent_count += _add_entity_agents(hdr, values, "producer", "OTHER", otherrole="PRODUCER")
    agent_count += _add_entity_agents(hdr, values, "owner", "IPOWNER")
    agent_count += _add_entity_agents(hdr, values, "creator", "CREATOR")

    agent_count += _add_system_agent(
        hdr,
        name=values.get("mets_creator_software", ""),
        version=values.get("mets_creator_software_version", ""),
        type_="",
        type_version="",
        role="CREATOR",
    )

    if values.get("recipient"):
        agent = ET.SubElement(hdr, _tag("agent"), {"ROLE": "PRESERVATION", "TYPE": "ORGANIZATION"})
        ET.SubElement(agent, _tag("name")).text = values["recipient"]
        agent_count += 1

    agent_count += _add_system_agent(
        hdr,
        name=values.get("system", ""),
        version=values.get("system_version", ""),
        type_=values.get("system_type", ""),
        type_version=values.get("system_type_version", ""),
        role="ARCHIVIST",
    )
    agent_count += _add_system_agent(
        hdr,
        name=values.get("extraction_system", ""),
        version=values.get("extraction_system_version", ""),
        type_=values.get("extraction_system_type", ""),
        type_version=values.get("extraction_system_type_version", ""),
        role="OTHER",
        otherrole="PRODUCER",
    )

    alt_pairs = [
        ("DELIVERYSPECIFICATION", "archive_description"),
        ("SUBMISSIONAGREEMENT", "submission_agreement"),
        ("DELIVERYTYPE", "delivery_type"),
    ]
    if include_project_name:
        alt_pairs.append(("PROJECTNAME", "project_name"))
    alt_pairs.extend([
        ("PACKAGENUMBER", "package_number"),
        ("REFERENCECODE", "reference_code"),
        ("STARTDATE", "period_start"),
        ("ENDDATE", "period_end"),
    ])
    for kind, key in alt_pairs:
        value = values.get(key, "")
        if key in {"period_start", "period_end"}:
            value = _normalise_date(value)
        if value:
            ET.SubElement(hdr, _tag("altRecordID"), {"TYPE": kind}).text = value

    if document_id:
        ET.SubElement(hdr, _tag("metsDocumentID")).text = document_id
    return hdr, agent_count


def submission_description_readiness(values: dict[str, Any] | None) -> list[str]:
    """Return human-readable reasons why a package-level METS is not XSD-ready."""
    current = _normalise_values(values)
    missing: list[str] = []
    # submissionDescription.xsd allows LABEL to be absent but requires OBJID,
    # TYPE and PROFILE, which DWM generates. metsHdr requires >=3 agents and at
    # least one altRecordID. Agreement number is the archival business field
    # Arkade uses as the minimum package-level alternate identifier.
    if not current.get("submission_agreement"):
        missing.append("Avtalenr / SUBMISSIONAGREEMENT")

    # DWM itself is the software creator of a newly exported METS document.
    effective = dict(current)
    effective.setdefault("mets_creator_software", "Data Workflow Manager")
    count = 1  # generated DWM software CREATOR
    for prefix in ("archivist", "submitter", "producer", "owner", "creator"):
        if effective.get(f"{prefix}_org"):
            count += 1
        if effective.get(f"{prefix}_person"):
            count += 1
    if effective.get("recipient"):
        count += 1
    if effective.get("system"):
        count += 1
    if effective.get("extraction_system"):
        count += 1
    if count < 3:
        missing.append("minst to metadataaktører i tillegg til DWM (METS krever minst tre agent-elementer)")
    return missing


def _base_root(values: dict[str, str], *, object_id: str, package_type: str, schema_location: str | None = None) -> ET.Element:
    attrs = {
        "OBJID": object_id,
        "TYPE": package_type,
        "PROFILE": EARD_PROFILE,
    }
    if values.get("label"):
        attrs["LABEL"] = values["label"]
    if schema_location:
        attrs[f"{{{XSI_NS}}}schemaLocation"] = f"{METS_NS} {schema_location}"
    return ET.Element(_tag("mets"), attrs)


def build_submission_description(
    values: dict[str, Any],
    *,
    object_id: str | None = None,
    package_type: str = "SIP",
    created_at: str | None = None,
    software_name: str = "Data Workflow Manager",
    software_version: str = "",
) -> ET.ElementTree:
    """Build the outer DIAS package submission description (commonly info.xml).

    This follows Arkade 5's ``SubmissionDescriptionCreator`` mapping and points
    at the current ``submissionDescription.xsd``.  Package file inventory is
    intentionally omitted here; ``fileSec`` is optional in the schema and is
    added only when the final TAR/dias-mets.xml are known.
    """
    current = _normalise_values(values)
    current["mets_creator_software"] = software_name
    current["mets_creator_software_version"] = software_version
    object_id = object_id or f"UUID:{uuid4()}"

    ET.register_namespace("mets", METS_NS)
    ET.register_namespace("xlink", XLINK_NS)
    ET.register_namespace("xsi", XSI_NS)
    root = _base_root(current, object_id=object_id, package_type=package_type, schema_location=SUBMISSION_DESCRIPTION_XSD)
    _populate_mets_header(root, current, created_at=_created_at(created_at), document_id=None, include_project_name=False)
    struct_map = ET.SubElement(root, _tag("structMap"))
    ET.SubElement(struct_map, _tag("div"))
    return ET.ElementTree(root)


def build_dias_mets_metadata(
    values: dict[str, Any],
    *,
    object_id: str | None = None,
    package_type: str = "SIP",
    created_at: str | None = None,
    software_name: str = "Data Workflow Manager",
    software_version: str = "",
) -> ET.ElementTree:
    """Build an inner DIAS METS metadata shell from canonical values.

    Extraction date remains in depot metadata; XML export location is not yet
    agreed. Final package generation handles PREMIS and file inventory.
    """
    current = _normalise_values(values)
    current["mets_creator_software"] = software_name
    current["mets_creator_software_version"] = software_version
    object_id = object_id or f"UUID:{uuid4()}"

    ET.register_namespace("mets", METS_NS)
    ET.register_namespace("xlink", XLINK_NS)
    ET.register_namespace("xsi", XSI_NS)
    root = _base_root(current, object_id=object_id, package_type=package_type)
    _populate_mets_header(root, current, created_at=_created_at(created_at), document_id="dias-mets.xml", include_project_name=True)
    struct_map = ET.SubElement(root, _tag("structMap"))
    ET.SubElement(struct_map, _tag("div"))
    return ET.ElementTree(root)


def write_xml(tree: ET.ElementTree, target: str | Path) -> Path:
    target_path = Path(target)
    if target_path.suffix.casefold() != ".xml":
        target_path = target_path.with_suffix(".xml")
    target_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        ET.indent(tree, space="  ")
    except AttributeError:
        pass
    tree.write(target_path, encoding="utf-8", xml_declaration=True)
    return target_path


def dias_package_params(values: dict[str, Any]) -> dict[str, str]:
    """Compatibility bridge to the existing DIAS package operation params."""
    current = _normalise_values(values)
    return {
        "submission_agreement": current["submission_agreement"],
        "label": current["label"],
        "system": current["system"],
        "system_version": current["system_version"],
        "archivist_type": current["system_type"],
        "period_start": current["period_start"],
        "period_end": current["period_end"],
        "owner_org": current["owner_org"],
        "archivist_org": current["archivist_org"],
        "submitter_org": current["submitter_org"],
        "submitter_person": current["submitter_person"],
        "producer_org": current["producer_org"],
        "producer_person": current["producer_person"],
        "producer_software": current["extraction_system"],
        "creator": current["creator_org"],
        "preserver": current["recipient"],
    }
