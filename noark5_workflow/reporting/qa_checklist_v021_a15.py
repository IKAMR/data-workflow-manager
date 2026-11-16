"""v0.2.1-a15: source-traceable, manual depot checklist on top of a12/a14 Work.

The two bundled checklists are drafts, NOT additional binding legal rules.
A single METS-based point registry avoids two competing approval workflows.
No item is completed automatically; Work/METS only supplies read-only context.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from hashlib import sha256
from html import escape
import json
import os
from pathlib import Path
import time
from typing import Any
from uuid import uuid4
from xml.etree import ElementTree as ET

from .qa_decision_v021_a12 import _hash, _json, _rel, ReportInputError
from .qa_review_v021_a13 import _binding, _check_work_and_source

MODEL = "ikamr.dwm.noark5.depot-checklist.a15.v1"
EVENT_MODEL = "ikamr.dwm.noark5.depot-checklist-event.a15.v1"
EVENT_DIR = "noark5_evidence/depot_checklist_events_v021_a15"
DOC_MET = "docs/reference-material/checklists/sjekkliste-mets.docx"
DOC_BASE = "docs/reference-material/checklists/sjekkliste.docx"
DOC_GIT_BLOB_SHA1 = {  # Git blob identifiers of the two exact reference drafts
    DOC_MET: "f3e80f63ea98ff9999965c226fb60ee9f99a0168",  # Git blob SHA-1 (not SHA-256)
    DOC_BASE: "8740cefa2b11ee13112d3b68aac9981c4605a7c2",
}
MAX_EVENTS = 6000
MAX_EVENT_BYTES = 20000
MAX_COMMENT = 5000
STATUSES = {"yes": "Ja", "no": "Nei", "not_applicable": "Ikke relevant"}

# Phrases are taken from the preliminary METS checklist; references are labels
# used by that template, never statements of directly binding municipal law.
GROUPS = (
    ("opplysninger", "Opplysninger ved innlevering", "Faglig referanse § 23", (
        "opphavet til dokumentasjonen",
        "sammenhengen dokumentasjonen ble til i og var en del av",
        "hvilken informasjon dokumentasjonen inneholder",
        "tidsperioden dokumentasjonen omfatter",
        "hvordan dokumentasjonen er strukturert",
        "hvilke formater dokumentasjonen har",
        "kassasjon, sletting eller kjent ufullstendighet",
        "personopplysninger og særlige kategorier av personopplysninger",
        "taushetsplikt og informasjonssikkerhet",
        "informasjonssystemet dokumentasjonen har vært lagret i",
        "eventuell konvertering fra analogt til digitalt format",
    )),
    ("arkivpakke", "Arkivpakkens innhold", "Faglig referanse § 26", (
        "uttrekk av dokumentasjonen som skal innleveres",
        "dokumentasjon av kontrollert, systematisk og etterprøvbar produksjon",
        "opplysninger om dokumentasjonen",
        "teknisk beskrivelse av uttrekket",
        "tekniske metadata om datafiler, inkludert sjekksummer og filplasseringer",
        "samsvar med avtalt omfang og innleveringsavtale",
    )),
    ("avklaring", "Godkjenning og behov for korrigert pakke", "Faglig referanse § 27", (
        "avtalt dokumentasjon er med",
        "feil/mangler skyldes ikke ukontrollert eller feilaktig uttrekksproduksjon",
        "teknisk beskrivelse er tilstrekkelig og korrekt",
        "beskrivelse av dokumentasjonen er tilstrekkelig og korrekt",
        "andre avtalte krav er oppfylt",
    )),
    ("database", "Strukturerte databaser og SIARD", "Faglig referanse § 29", (
        "uttrekksformat er identifisert og avtalt",
        "tabeller/felter og relasjoner kan forstås",
        "LOB-er / eksterne filer er håndtert og koblinger bevart",
        "SIARD-validering er gjennomført der SIARD brukes",
        "teknisk beskrivelse er tilstrekkelig for framtidig tolkning",
    )),
    ("format", "Filformat og konvertering", "Faglig referanse § 30", (
        "filformater er identifisert",
        "formatinformasjon følger innleveringen",
        "eventuell konvertering er dokumentert",
        "informasjon og metadata er ikke vesentlig svekket ved konvertering",
    )),
    ("tegnsett", "Tegnsett", "Faglig referanse § 31", (
        "tegnsett er identifisert",
        "tegnsett kan leses korrekt",
        "eventuelle avvik eller konverteringer er dokumentert",
    )),
    ("teknisk", "Teknisk beskrivelse", "Faglig referanse § 32", (
        "indre struktur og sammenhenger mellom datafiler og innhold er beskrevet",
        "tolkning og presentasjon av data er beskrevet",
        "filformatene er beskrevet",
        "beskrivelsen er maskinleselig der det er relevant",
        "beskrivelsen er forståelig for mennesker",
    )),
    ("koblinger", "Koblinger og filstier", "Faglig referanse § 33", (
        "nødvendige referanser og koblinger er intakte",
        "filstier/referanser er oppdatert ved endringer",
        "relative filstier brukes der dette er relevant",
    )),
    ("kryptering", "Kryptering og passordvern", "Faglig referanse § 34", (
        "filer er ikke utilgjengelig kryptert",
        "filer er ikke passordbeskyttet, eller særskilt håndtering er avtalt",
    )),
    ("andre", "Andre sjekkpunkter", "Sjekkliste – øvrige", (
        "endringer/korrigeringer under uttrekksproduksjonen er dokumentert",
        "sjekksummer og integritetskontroll er gjennomført",
        "virus/skadevarekontroll er gjennomført etter depotets rutine",
        "omfang og filantall er konsistent med avtale og dokumentasjon",
        "kjente mangler og avvik er registrert",
    )),
)
NOTES = (
    ("historikk", "System- og leverandørhistorikk", "Kort om systemet, driftsperioden og innleveringen"),
    ("metode", "Beskrivelse av uttrekksmetode", "Kort om systemet, driftsperioden og innleveringen"),
    ("periode", "Driftsperiode og uttrekksperiode", "Kort om systemet, driftsperioden og innleveringen"),
    ("kjente_avvik", "Kjente avvik / merknader", "Kort om systemet, driftsperioden og innleveringen"),
    ("noark5_funn", "Noark 5-avvik / vurderingspunkter", "Faglig referanse § 28"),
    ("noark5_oppsummering", "Depotets samlede vurdering av Noark 5-funn", "Faglig referanse § 28"),
    ("testing", "Testing av innleveringen", "Testing av innleveringen"),
    ("samlet", "Samlet depotfaglig vurdering (ikke vedtak)", "Oppsummering og godkjenning (utkast)"),
)
POINTS = tuple(
    {"id": f"{section}.{i:02d}", "section": section, "section_title": title,
     "source_ref": reference, "label": label, "kind": "control"}
    for section, title, reference, labels in GROUPS
    for i, label in enumerate(labels, 1)
) + tuple(
    {"id": "notat." + key, "section": "notat", "section_title": "Faglige tekstfelter",
     "source_ref": reference, "label": label, "kind": "note"}
    for key, label, reference in NOTES
)
POINT_BY_ID = {point["id"]: point for point in POINTS}
CATALOG_SHA256 = sha256(json.dumps(POINTS, ensure_ascii=False, sort_keys=True,
                                  separators=(",", ":")).encode("utf-8")).hexdigest()

# Two distinct sources are shown as separate columns, never silently merged.
HEADER_FIELDS = (
    ("label", "METS LABEL", "label"),
    ("delivery_spec", "Innleveringsspesifikasjon", "archive_description"),
    ("archivist", "Arkivansvarlig (METS ARCHIVIST)", "archivist_org"),
    ("owner", "Arkiveier (METS IPOWNER)", "owner_org"),
    ("system", "System", "system"),
    ("system_version", "Systemversjon", "system_version"),
    ("system_noark_version", "Oppgitt Noark-versjon for system (METS TypeVersion)", "system_type_version"),
    ("extraction_tool", "Uttrekks-/produksjonsverktøy", "extraction_system"),
    ("extraction_version", "Uttrekksverktøyversjon", "extraction_system_version"),
    ("extraction_noark_version", "Oppgitt Noark-versjon for uttrekk (METS TypeVersion)", "extraction_system_type_version"),
    ("submitter", "Innleverer", "submitter_org"),
    ("delivery_type", "Leveringstype", "delivery_type"),
    ("period_start", "Oppgitt startdato", "period_start"),
    ("period_end", "Oppgitt sluttdato", "period_end"),
    ("agreement", "Innleveringsavtale", "submission_agreement"),
    ("package_number", "Pakkenummer", "package_number"),
    ("objid", "METS OBJID / pakke-ID", ""),
    ("created", "METS CREATEDATE", ""),
    ("preservation", "Depot (METS PRESERVATION)", "recipient"),
    ("mets_creator", "METS CREATOR (ikke arkivskaper)", "creator_org"),
    ("mets_creator_software", "METS CREATOR SOFTWARE (pakkeverktøy)", "mets_creator_software"),
)


class ChecklistError(ValueError):
    """Invalid or stale professional checklist input; do not write partial data."""


def _event_digest(payload: dict) -> str:
    return sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True,
                             separators=(",", ":")).encode("utf-8")).hexdigest()


def _scope(snapshot: dict, scope: str, native_id: str) -> tuple[str, str]:
    if scope not in ("uttrekk", "arkivdel"):
        raise ChecklistError("Ukjent vurderingsomfang")
    native_id = str(native_id or "").strip()
    if scope == "uttrekk":
        if native_id:
            raise ChecklistError("Uttrekksnivå kan ikke ha arkivdel-ID")
        return scope, ""
    matches = sum(str(p.get("system_id") or "") == native_id
                  for p in snapshot.get("archive_parts") or [])
    if not native_id or matches != 1:
        raise ChecklistError("Arkivdel mangler entydig system-ID i valgt originalrapport")
    return scope, native_id


def _events_dir(work: Path, *, create: bool = False) -> Path:
    root = Path(work).resolve(strict=True)
    path = _rel(root, EVENT_DIR)
    if path.exists() and (not path.is_dir() or path.is_symlink()):
        raise ChecklistError("Ugyldig eller lenket hendelseskatalog for sjekklisten")
    if create:
        if not path.parent.is_dir() or path.parent.is_symlink():
            raise ChecklistError("Mangler sikker Work/evidenskatalog")
        path.mkdir(exist_ok=True)
    return path


def _read_events(work: Path) -> list[dict]:
    folder = _events_dir(work)
    if not folder.exists():
        return []
    files = list(folder.iterdir())
    if len(files) > MAX_EVENTS:
        raise ChecklistError("For mange sjekklistehendelser")
    events = []
    for path in files:
        if path.suffix != ".json" or not path.is_file() or path.is_symlink():
            raise ChecklistError("Ukjent fil i sjekklistehistorikken")
        if path.stat().st_size > MAX_EVENT_BYTES:
            raise ChecklistError("Sjekklistehendelse er for stor")
        entry = _json(path, MAX_EVENT_BYTES)
        fingerprint = entry.get("event_sha256")
        unsigned = {k: v for k, v in entry.items() if k != "event_sha256"}
        if (entry.get("model_id") != EVENT_MODEL
                or path.stem != entry.get("event_id")
                or _event_digest(unsigned) != fingerprint
                or type(entry.get("recorded_ns")) is not int
                or entry.get("point_id") not in POINT_BY_ID
                or entry.get("scope") not in ("uttrekk", "arkivdel")
                or not isinstance(entry.get("native_id"), str)
                or not isinstance(entry.get("comment"), str)
                or type(entry.get("include_in_ks")) is not bool
                or type(entry.get("include_in_depot")) is not bool):
            raise ChecklistError("Ugyldig eller manipulert sjekklistehendelse")
        point = POINT_BY_ID[entry["point_id"]]
        if (entry.get("status") not in (STATUSES if point["kind"] == "control" else ("note",))
                or len(entry["comment"]) > MAX_COMMENT
                or (point["kind"] == "note" and not entry["comment"].strip())
                or (entry["status"] in ("no", "not_applicable") and not entry["comment"].strip())):
            raise ChecklistError("Ugyldig status eller manglende faglig begrunnelse i hendelse")
        events.append(entry)
    events.sort(key=lambda row: (row["recorded_ns"], row["event_id"]))
    return events


def latest_checklist(work: str | Path, snapshot: dict, *, scope: str = "uttrekk",
                     native_id: str = "") -> dict:
    """Only events for exact job, current depot report, catalogue and scope."""
    scope, native_id = _scope(snapshot, scope, native_id)
    job_uid, source_sha, _ = _binding(snapshot)
    current, old, other = {}, 0, 0
    for entry in _read_events(Path(work)):
        if entry.get("job_uid") != job_uid:
            other += 1
        elif (entry.get("depot_report_sha256") != source_sha
              or entry.get("catalog_sha256") != CATALOG_SHA256):
            old += 1
        elif (entry["scope"], entry["native_id"]) == (scope, native_id):
            current[entry["point_id"]] = entry
    return {"current": current, "older_or_changed": old, "other_job": other}


def record_checklist(work: str | Path, snapshot: dict, point_id: str, *,
                     scope: str, native_id: str = "", status: str,
                     comment: str, user: Any,
                     include_in_ks: bool = False, include_in_depot: bool = True) -> dict:
    """Explicit manual append-only event. Source & existing outcomes are immutable."""
    point = POINT_BY_ID.get(point_id)
    if point is None:
        raise ChecklistError("Ukjent sjekkpunkt-ID")
    allowed = STATUSES if point["kind"] == "control" else ("note",)
    if status not in allowed:
        raise ChecklistError("Ugyldig svar for valgt kontrollpunkt")
    comment = str(comment or "").strip()
    if len(comment) > MAX_COMMENT:
        raise ChecklistError("Kommentar overstiger 5000 tegn")
    if (point["kind"] == "note" or status in ("no", "not_applicable")) and not comment:
        raise ChecklistError("Dette svaret krever faglig begrunnelse")
    if type(include_in_ks) is not bool or type(include_in_depot) is not bool:
        raise ChecklistError("Ugyldig valg av rapportmottaker")
    if not hasattr(user, "as_dict") or not callable(user.as_dict) or not getattr(user, "user_id", None):
        raise ChecklistError("Registrert brukerprofil kreves for å lagre sjekklistevurdering")
    author = user.as_dict()
    if not isinstance(author, dict) or not author.get("user_id"):
        raise ChecklistError("Ugyldig brukerprofil")
    scope, native_id = _scope(snapshot, scope, native_id)
    root, job_uid, source_sha = _check_work_and_source(Path(work), snapshot)
    event_id = str(uuid4())
    entry = {"model_id": EVENT_MODEL, "event_id": event_id,
             "created_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
             "recorded_ns": time.time_ns(), "job_uid": job_uid,
             "depot_report_sha256": source_sha, "catalog_sha256": CATALOG_SHA256,
             "scope": scope, "native_id": native_id, "point_id": point_id,
             "status": status, "comment": comment,
             "include_in_ks": include_in_ks, "include_in_depot": include_in_depot,
             "author": author}
    entry["event_sha256"] = _event_digest(entry)
    folder = _events_dir(root, create=True)
    if len(list(folder.iterdir())) >= MAX_EVENTS:
        raise ChecklistError("For mange sjekklistehendelser")
    path = folder / (event_id + ".json")
    serialized = json.dumps(entry, ensure_ascii=False, indent=2) + "\n"
    if len(serialized.encode("utf-8")) > MAX_EVENT_BYTES:
        raise ChecklistError("Sjekklistehendelsen overstiger størrelsesgrensen")
    with path.open("x", encoding="utf-8") as handle:
        handle.write(serialized)
        handle.flush()
        os.fsync(handle.fileno())
    return entry


def _all_current(work: Path, snapshot: dict) -> tuple[dict, int]:
    job_uid, source_sha, _ = _binding(snapshot)
    ids = {str(row.get("system_id") or "") for row in snapshot.get("archive_parts") or []}
    current, stale = {}, 0
    for entry in _read_events(work):
        if entry.get("job_uid") != job_uid or entry.get("depot_report_sha256") != source_sha or entry.get("catalog_sha256") != CATALOG_SHA256:
            stale += 1
            continue
        if entry["scope"] == "arkivdel" and entry["native_id"] not in ids:
            stale += 1
            continue
        if entry["scope"] == "uttrekk" and entry["native_id"]:
            stale += 1
            continue
        current[(entry["scope"], entry["native_id"], entry["point_id"])] = entry
    return current, stale


def attach_checklist(work: str | Path, snapshot: dict) -> dict:
    """Report adapter: include only explicitly selected comments; no new engine."""
    current, stale = _all_current(Path(work), snapshot)
    rows = []
    for (scope, native_id, point_id), entry in sorted(current.items()):
        point = POINT_BY_ID[point_id]
        if not entry["include_in_ks"] and not entry["include_in_depot"]:
            continue
        rows.append({"scope": scope, "native_id": native_id, "point_id": point_id,
                     "section": point["section_title"], "reference": point["source_ref"],
                     "label": point["label"], "kind": point["kind"],
                     "status": entry["status"], "comment": entry["comment"],
                     "author": entry["author"], "created_utc": entry["created_utc"],
                     "include_in_ks": entry["include_in_ks"],
                     "include_in_depot": entry["include_in_depot"],
                     "event_id": entry["event_id"]})
    controls = [p for p in POINTS if p["kind"] == "control"]
    job_controls = {point_id for (scope, _, point_id) in current
                    if scope == "uttrekk" and POINT_BY_ID[point_id]["kind"] == "control"}
    result = deepcopy(snapshot)
    result["a15_checklist"] = {"model_id": MODEL,
                               "catalog_sha256": CATALOG_SHA256,
                               "source_template": DOC_MET,
                               "other_source_template": DOC_BASE,
                               "source_template_git_blobs": dict(DOC_GIT_BLOB_SHA1),
                               "draft_only": True,
                               "automatic_approval": False,
                               "selected_rows": rows,
                               "summary": {"total_controls": len(controls),
                                           "job_controls_manually_reviewed": len(job_controls),
                                           "all_scope_responses": len(current),
                                           "historical_or_changed_events": stale,
                                           "selected_ks": sum(r["include_in_ks"] for r in rows),
                                           "selected_depot": sum(r["include_in_depot"] for r in rows)}}
    return result


def checklist_html(snapshot: dict, *, depot: bool) -> str:
    """HTML fragment appended to existing a12/a13/a14 report body, not a new report."""
    context = snapshot.get("a15_checklist")
    if not context:
        return ""
    summary = context["summary"]
    chosen = [r for r in context["selected_rows"] if r["include_in_depot" if depot else "include_in_ks"]]
    title = "12. Depotets sjekkliste (arbeidsutkast)" if depot else "12. Utvalgte sjekkpunkter til arkivskaper"
    content = ["<h2>" + escape(title) + "</h2>",
               "<p>Basert på lokale arbeidsutkast til sjekklister, særlig METS-utgaven. "
               "Referanser til arkivforskrifta er faglige referanser, ikke automatisk "
               "bindende kommunale avleveringskrav. Svarene er manuelle og er "
               "ikke depotvedtak eller endringer av tekniske kontrollresultater.</p>"]
    if depot:
        content.append("<p>Uttrekksnivå: " + str(summary["job_controls_manually_reviewed"]) +
                       " av " + str(summary["total_controls"]) + " kontrollpunkter vurdert manuelt. "
                       "Ikke vurdert betyr ikke bestått.</p>")
    if not chosen:
        content.append("<p>Ingen sjekklistevurderinger valgt til denne rapporten.</p>")
    else:
        content.append("<div class='table-wrap'><table><thead><tr><th>Omfang</th><th>Kontrollpunkt</th>"
                       "<th>Faglig svar</th><th>Merknad</th><th>Registrert</th></tr></thead><tbody>")
        for row in chosen:
            scope = "Hele uttrekket" if row["scope"] == "uttrekk" else "Arkivdel " + row["native_id"]
            status = STATUSES.get(row["status"], "Faglig notat")
            author = row.get("author") or {}
            name = author.get("name") or author.get("display_name") or author.get("username") or author.get("user_id") or "Ukjent"
            content.append("<tr><td>" + escape(scope) + "</td><td>" + escape(row["section"]) +
                           ": " + escape(row["label"]) + "<br><small>" + escape(row["reference"]) +
                           "</small></td><td>" + escape(status) + "</td><td>" +
                           escape(row["comment"]).replace("\n", "<br>") + "</td><td>" +
                           escape(str(name)) + " · " + escape(row["created_utc"]) + "</td></tr>")
        content.append("</tbody></table></div>")
    return "\n".join(content)


def mets_header(work: str | Path, snapshot: dict) -> dict:
    """Read-only Work/METS header, preserving the difference from original XML.

    Original values come only from a SHA-verified preserved info.xml copy.
    Never read the external original Source path or silently choose one value.
    """
    root = Path(work).resolve(strict=True)
    context = (snapshot.get("a14_context") or {}).get("mets") or {}
    fields = dict(context.get("fields") or {})
    metadata = _rel(root, "metadata/depot_metadata.json")
    if metadata.is_file():
        registered = _json(metadata, limit=3 * 1024 * 1024).get("current") or {}
        if not isinstance(registered, dict):
            raise ChecklistError("Ugyldig Work-metadata")
        # a14 already verifies identity, import hash and path before use.
        for key in ("label", "delivery_type", "mets_creator_software"):
            if isinstance(registered.get(key), str):
                fields[key] = registered[key].strip()[:2000]
    original = {}
    original_path = None
    for origin in context.get("sources") or []:
        if origin.get("verification") != "preserved_copy_hash_matches":
            continue
        rel = origin.get("preserved_file")
        if not rel:
            continue
        path = _rel(root, rel)
        raw = path.read_bytes()
        if len(raw) > 3 * 1024 * 1024:
            raise ChecklistError("Bevart METS-kopi er for stor")
        if sha256(raw).hexdigest() != origin.get("recorded_sha256"):
            raise ChecklistError("Bevart METS-kopi er endret")
        if b"<!DOCTYPE" in raw.upper() or b"<!ENTITY" in raw.upper():
            raise ChecklistError("DTD/enheter tillates ikke i bevart METS-kopi")
        try:
            doc = ET.fromstring(raw)
        except ET.ParseError as exc:
            raise ChecklistError("Kan ikke lese bevart METS-kopi") from exc
        ns = {"mets": "http://www.loc.gov/METS/"}
        hdr = doc.find("mets:metsHdr", ns)
        original["label"] = doc.attrib.get("LABEL", "")
        original["objid"] = doc.attrib.get("OBJID", "")
        if hdr is not None:
            original["created"] = hdr.attrib.get("CREATEDATE", "")
            typemap = {"DELIVERYSPECIFICATION": "delivery_spec", "DELIVERYTYPE": "delivery_type",
                       "STARTDATE": "period_start", "ENDDATE": "period_end",
                       "SUBMISSIONAGREEMENT": "agreement", "PACKAGENUMBER": "package_number"}
            for element in hdr.findall("mets:altRecordID", ns):
                key = typemap.get(element.attrib.get("TYPE"))
                if key:
                    original[key] = (element.text or "").strip()
            for agent in hdr.findall("mets:agent", ns):
                role = agent.attrib.get("OTHERROLE") if agent.attrib.get("ROLE") == "OTHER" else agent.attrib.get("ROLE")
                name = (agent.findtext("mets:name", default="", namespaces=ns) or "").strip()
                if agent.attrib.get("TYPE") == "ORGANIZATION":
                    k = {"ARCHIVIST": "archivist", "IPOWNER": "owner", "SUBMITTER": "submitter",
                         "PRESERVATION": "preservation", "CREATOR": "mets_creator"}.get(role)
                    if k:
                        original[k] = name
                elif (agent.attrib.get("TYPE") == "OTHER"
                      and agent.attrib.get("OTHERTYPE") == "SOFTWARE"):
                    notes = [(node.text or "").strip() for node in agent.findall("mets:note", ns)]
                    # Use only the positional notes documented by the actual
                    # METS profile; the final notescontent marker is metadata.
                    if role == "ARCHIVIST":
                        original["system"] = name
                        if notes:
                            original["system_version"] = notes[0]
                        if len(notes) >= 3:
                            original["system_noark_version"] = notes[2]
                    elif role == "PRODUCER":
                        original["extraction_tool"] = name
                        if notes:
                            original["extraction_version"] = notes[0]
                        if len(notes) >= 3:
                            original["extraction_noark_version"] = notes[2]
                    elif role == "CREATOR":
                        original["mets_creator_software"] = name
        original_path = {"path": rel, "sha256": origin["recorded_sha256"]}
        break
    rows = []
    for key, title, work_key in HEADER_FIELDS:
        work_val = str(fields.get(work_key) or "") if work_key else ""
        source_val = str(original.get(key) or "")
        different = bool(work_val and source_val and work_val != source_val)
        rows.append({"id": key, "label": title, "work_value": work_val or None,
                     "original_value": source_val or None,
                     "conflict": different,
                     "source_note": "Arbeidskopi i Work er ikke automatisk verifisert mot arkivskaper."})
    return {"rows": rows, "preserved_source": original_path,
            "work_source": "metadata/depot_metadata.json" if metadata.is_file() else None,
            "status": "read_only_no_auto_completion"}
