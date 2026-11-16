"""a16.1: presentation-only METS field references and non-duplicating views.

One editable 47-field Arkade catalogue; source instances are separate evidence.
Both source references are kept even when the other METS is not imported.
Raw ordinal XML inventory belongs to a dedicated technical view.
"""
from __future__ import annotations

from typing import Any
from xml.etree import ElementTree as ET

_ALT_FIELDS = {
    "archive_description": "DELIVERYSPECIFICATION",
    "submission_agreement": "SUBMISSIONAGREEMENT",
    "delivery_type": "DELIVERYTYPE",
    "project_name": "PROJECTNAME",
    "package_number": "PACKAGENUMBER",
    "reference_code": "REFERENCECODE",
    "period_start": "STARTDATE",
    "period_end": "ENDDATE",
}
_ROLES = {
    "archivist": ("ARCHIVIST", ""),
    "submitter": ("OTHER", "SUBMITTER"),
    "producer": ("OTHER", "PRODUCER"),
    "owner": ("IPOWNER", ""),
    "creator": ("CREATOR", ""),
}
_CONTACTS = {"address": "Address", "phone": "Telephone", "email": "Email"}
_SOFTWARE = {
    "mets_creator_software": ("CREATOR", "", "mets_creator_software"),
    "system": ("ARCHIVIST", "", "system"),
    "extraction_system": ("OTHER", "PRODUCER", "extraction_system"),
}


def _agent_clause(role: str, otherrole: str, typ: str, *, software: bool = False) -> str:
    parts = [f"@ROLE='{role}'", f"@TYPE='{typ}'"]
    if otherrole:
        parts.append(f"@OTHERROLE='{otherrole}'")
    if software:
        parts.append("@OTHERTYPE='SOFTWARE'")
    return "[" + " and ".join(parts) + "]"


def expected_references(field: str) -> dict[str, dict[str, str | None]]:
    """Declared *placement* (not a claim of occurrence or of regulatory status).

    The 'note' placement is descriptive: Arkade uses notescontent: for the
    meaning of positional notes, not a generic METS XPath predicate.
    Actual, ordinal, source-specific paths are obtained separately.
    """
    suffix = ""
    note = ""
    if field == "label":
        suffix = "/@LABEL"
    elif field == "record_status":
        suffix = "/{ns}:metsHdr/@RECORDSTATUS"
    elif field in _ALT_FIELDS:
        suffix = "/{ns}:metsHdr/{ns}:altRecordID[@TYPE='" + _ALT_FIELDS[field] + "']"
        if field == "project_name":
            note = "Arkade 5 skriver normalt PROJECTNAME bare i indre DIAS METS; faktisk funn kontrolleres per kilde."
    elif field == "recipient":
        suffix = "/{ns}:metsHdr/{ns}:agent" + _agent_clause("PRESERVATION", "", "ORGANIZATION") + "/{ns}:name"
    elif field == "mets_creator_software_version":
        suffix = ("/{ns}:metsHdr/{ns}:agent" + _agent_clause("CREATOR", "", "OTHER", software=True)
                  + "/{ns}:note (Arkade notescontent:Version)")
    elif field in _SOFTWARE:
        role, otherrole, _ = _SOFTWARE[field]
        suffix = "/{ns}:metsHdr/{ns}:agent" + _agent_clause(role, otherrole, "OTHER", software=True) + "/{ns}:name"
    elif field.startswith(("system_", "extraction_system_")):
        if field.startswith("extraction_system_"):
            role, otherrole = "OTHER", "PRODUCER"
            end = field[len("extraction_system_"):]
        else:
            role, otherrole = "ARCHIVIST", ""
            end = field[len("system_"):]
        names = {"version": "Version", "type": "Type", "type_version": "TypeVersion"}
        if end in names:
            suffix = ("/{ns}:metsHdr/{ns}:agent" + _agent_clause(role, otherrole, "OTHER", software=True)
                      + "/{ns}:note (Arkade notescontent:" + names[end] + ")")
    else:
        for prefix, (role, otherrole) in _ROLES.items():
            if field == prefix + "_org":
                suffix = "/{ns}:metsHdr/{ns}:agent" + _agent_clause(role, otherrole, "ORGANIZATION") + "/{ns}:name"
                break
            if field == prefix + "_person":
                suffix = "/{ns}:metsHdr/{ns}:agent" + _agent_clause(role, otherrole, "INDIVIDUAL") + "/{ns}:name"
                break
            if field.startswith(prefix + "_"):
                end = field[len(prefix) + 1:]
                if end in _CONTACTS:
                    suffix = ("/{ns}:metsHdr/{ns}:agent" + _agent_clause(role, otherrole, "INDIVIDUAL")
                              + "/{ns}:note (Arkade notescontent:" + _CONTACTS[end] + ")")
                break

    if field == "extraction_date":
        # Arkade's inner fileGrp ArchiveExtraction may carry VERSDATE, but the
        # equivalence with DWM's editable extraction_date is NOT approved.
        return {
            "outer": {"expected": None, "note": "Uttrekksdato har ingen vedtatt mapping i ytre info.xml."},
            "inner": {"expected": None, "note": (
                "Arkade kan skrive ArchiveExtraction/@VERSDATE i indre DIAS METS. "
                "Kobling til DWM-feltet Uttrekksdato er foreløpig ikke fastsatt.")},
        }
    if not suffix:
        raise ValueError("Ukjent Arkade metadatafelt i referanseregister: " + field)
    return {
        "outer": {"expected": "/mets:mets" + suffix.format(ns="mets"),
                  "note": note + (" Ytre Arkade-eksport utelater normalt dette feltet." if field == "project_name" else "")},
        "inner": {"expected": "/dias:mets" + suffix.format(ns="dias"), "note": note},
    }


def field_references(fields: list[str] | tuple[str, ...],
                     source_evidence: dict[str, dict[str, Any]]) -> dict[str, dict[str, dict[str, Any]]]:
    """Two independent references for *every* field, with explicit import state.

    source_evidence values are SHA-verified input with root, inventory, links,
    source descriptor and canonical values. No interpretation from filename.
    """
    output = {}
    for field in fields:
        declared = expected_references(field)
        views = {}
        for role in ("outer", "inner"):
            template = declared[role]
            expected = template["expected"]
            document = source_evidence.get(role)
            entry = {
                "expected": expected, "note": template["note"],
                "status": "ikke kartlagt" if expected is None else
                          "kilde ikke importert" if document is None else "ikke påvist",
                "actual": None, "value": None,
                "source_name": (document.get("source", {}).get("original_name") or "") if document else "",
                "sha256": (document.get("source", {}).get("sha256") or "") if document else "",
            }
            if expected is not None and document:
                # Links can include positions absent in XML (e.g. @RECORDSTATUS);
                # an observed path must actually occur in the *raw* inventory.
                matches = [path for path, key in document["links"].items()
                           if key == field and path in document["items"]]
                if matches:
                    entry["actual"] = matches[0]
                    entry["value"] = document["canonical"].get(field,
                                       document["items"][matches[0]]["source_value"])
                    entry["status"] = "påvist"
            views[role] = entry
        output[field] = views
    return output


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _children(element: ET.Element | None, name: str) -> list[ET.Element]:
    return [child for child in element if _local(child.tag) == name] if element is not None else []


def _path(root: ET.Element, children: list[tuple[ET.Element, int]]) -> str:
    ns = "mets" if root.tag.startswith("{http://www.loc.gov/METS/}") else "dias"
    path = f"/{ns}:mets[1]"
    for child, index in children:
        path += f"/{ns}:{_local(child.tag)}[{index}]"
    return path


def _raw_row(items_by_path: dict[str, dict], path: str, group: str, label: str) -> dict | None:
    raw = items_by_path.get(path)
    if raw is None:
        return None
    result = dict(raw)
    result["group"] = group
    result["label"] = label
    result["view"] = "extended"
    return result


def extended_mets_rows(xml_root: ET.Element | None, raw_rows: list[dict],
                       canonical_links: dict[str, str]) -> list[dict]:
    """Human-scale supplementary METS rows, without restating the 47 fields.

    The raw inventory is still available verbatim in its *own* view. The extra
    overview has one row per *file* rather than one per file attribute, one row
    per extra agent rather than its ROLE/TYPE/name/notes XML components, and
    one row for unclaimed/unknown altRecordID values.
    """
    if xml_root is None:
        return []
    raw = {row["key"]: row for row in raw_rows if row.get("kind") == "xml"}
    result: list[dict] = []
    taken_ids: set[str] = set()

    def append(row: dict | None):
        if row and row["id"] not in taken_ids:
            result.append(row)
            taken_ids.add(row["id"])

    base = _path(xml_root, [])
    for attr, name in (("OBJID", "Pakkens OBJID / identitet"),
                       ("TYPE", "Pakketype (SIP/AIP)"),
                       ("PROFILE", "METS-profil"),
                       ("{http://www.w3.org/2001/XMLSchema-instance}schemaLocation", "Skjemareferanse")):
        k = "xsi:schemaLocation" if attr.startswith("{") else attr
        append(_raw_row(raw, base + "/@" + k, "Pakkeidentitet og profil", name))
    hdr = _children(xml_root, "metsHdr")
    if not hdr:
        return result
    header = hdr[0]
    hp = _path(xml_root, [(header, 1)])
    for attr, label in (("CREATEDATE", "METS opprettelsesdato"),
                        ("LASTMODDATE", "METS sist endret"),
                        ("ID", "METS header-ID")):
        append(_raw_row(raw, hp + "/@" + attr, "METS-header", label))
    for attr in header.attrib:
        if attr in ("CREATEDATE", "LASTMODDATE", "ID", "RECORDSTATUS"):
            continue
        append(_raw_row(raw, hp + "/@" + attr, "METS-header", "Tilleggsattributt: " + attr))

    known_alt = frozenset(_ALT_FIELDS.values())
    seen_alt = set()
    for i, alt in enumerate(_children(header, "altRecordID"), 1):
        typ = str(alt.get("TYPE") or "").upper()
        first = typ not in seen_alt
        seen_alt.add(typ)
        if typ in known_alt and first:
            continue
        ap = _path(xml_root, [(header, 1), (alt, i)]) + "/text()"
        append(_raw_row(raw, ap, "Andre pakkereferanser",
                        ("Gjentatt " if typ in known_alt else "Ekstra ") + "altRecordID: " + (typ or "uten TYPE")))

    for i, agent in enumerate(_children(header, "agent"), 1):
        ap = _path(xml_root, [(header, 1), (agent, i)])
        names = _children(agent, "name")
        namepath = ap + "/" + ("mets:name" if base.startswith("/mets:") else "dias:name") + "[1]/text()"
        if namepath in canonical_links:
            continue  # primary organization/person/software already in 47 fields
        role = str(agent.get("OTHERROLE") if agent.get("ROLE") == "OTHER" else agent.get("ROLE") or "ukjent")
        typ = str(agent.get("TYPE") or "ukjent")
        name = (names[0].text or "").strip() if names else "[uten navn]"
        displayed = f"{role} · {typ} · forekomst {i}"
        if namepath in raw:
            append(_raw_row(raw, namepath, "Flere aktører og programvarer", displayed))
        else:
            # A nameless extra agent is still visible, without fabricating a value.
            result.append({"id": "summary:agent:" + ap, "kind": "summary", "group": "Flere aktører og programvarer",
                           "label": displayed, "key": ap, "historical": name, "current": name,
                           "status": "kilde", "changed": False, "editable": False, "view": "extended"})
        # Extra/unknown note values are retained in the full technical view.

    for grp_index, filegrp in enumerate(_children(_children(xml_root, "fileSec")[0], "fileGrp"), 1) if _children(xml_root, "fileSec") else []:
        use = str(filegrp.get("USE") or "uten USE")
        for file_index, file in enumerate(_children(filegrp, "file"), 1):
            filename = (file.get("ID") or f"fil {file_index}").strip()
            locators = _children(file, "FLocat")
            href = (locators[0].get("{http://www.w3.org/1999/xlink}href") or "") if locators else ""
            size = file.get("SIZE") or "ikke oppgitt"
            checksum = file.get("CHECKSUM") or "ikke oppgitt"
            mimetype = file.get("MIMETYPE") or "ikke oppgitt"
            details = (f"Sti: {href or '[ikke oppgitt]'}\nStørrelse: {size}\nFormat: {mimetype}\n"
                       f"Sjekksum ({file.get('CHECKSUMTYPE') or 'ukjent type'}): {checksum}")
            file_path = (base + "/" + ("mets" if base.startswith("/mets:") else "dias") + ":fileSec[1]/" +
                         ("mets" if base.startswith("/mets:") else "dias") + f":fileGrp[{grp_index}]/" +
                         ("mets" if base.startswith("/mets:") else "dias") + f":file[{file_index}]")
            result.append({"id": "summary:file:" + file_path, "kind": "summary",
                           "group": f"Filfortegnelse – {use}", "label": filename,
                           "key": file_path, "historical": details, "current": details,
                           "status": "kilde", "changed": False, "editable": False, "view": "extended"})

    # Unknown values outside the 47 and outside the grouped file inventory:
    # show them once, without listing all XML structure noise as separate rows.
    groups = ("Filfortegnelse", "Aktører / programvare")
    excluded_raw = set(canonical_links)
    for path, row in raw.items():
        if path in excluded_raw or row["id"] in taken_ids or row["group"].startswith(groups):
            continue
        if "/@ROLE" in path or "/@TYPE" in path or "/@OTHERROLE" in path or "/@OTHERTYPE" in path:
            continue
        if row["historical"].startswith("notescontent:") if isinstance(row["historical"], str) else False:
            continue
        # Extra XML attributes/text not captured by curated human-facing groups.
        # Ignore defined root/header attributes and the repeated altRecordID's TYPE.
        if path.startswith(base + "/@") or path.startswith(hp + "/@"):
            continue
        if "/mets:altRecordID[" in path or "/dias:altRecordID[" in path:
            continue
        if ("/mets:agent[" in path or "/dias:agent[" in path):
            continue
        if not row["historical"]:
            continue
        append(_raw_row(raw, path, "Andre METS-opplysninger", row["label"]))
    return result


def technical_read_only(path: str) -> bool:
    """Do not permit Work overrides to impersonate source integrity facts."""
    if "/mets:fileSec" in path or "/dias:fileSec" in path:
        return True
    if path.endswith(("/@OBJID", "/@PROFILE", "/@xsi:schemaLocation", "/@CHECKSUM", "/@CHECKSUMTYPE")):
        return True
    if path.count("/") == 2 and path.endswith("/@TYPE"):
        return True
    return False
