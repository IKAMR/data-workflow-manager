"""v0.2.1-a14: read-only interpretation and METS provenance for a13 findings.

This is *not* a new Noark validation engine, an accepted deviation catalogue,
or an automated recommendation/approval service. It reads existing Work
metadata without rewriting source, technical evidence, reviews, or a20 pages.
Only N5.22 has a verified, explicitly documented explanatory requirement here.
"""
from __future__ import annotations

from copy import deepcopy
from html import escape
from pathlib import Path
import re
from typing import Any

from .qa_decision_v021_a12 import ReportInputError, _json, _rel, _source

METADATA_FILE = "metadata/depot_metadata.json"
STANDARD_VALUES_FILE = "config/noark5/standards/noark5_standard_values.json"
SUPPORTED_NOARK5 = ("3.1", "4.0", "5.0")
METADATA_FIELDS = (
    ("archive_description", "Beskrivelse av arkivuttrekket"),
    ("archivist_org", "Arkivansvarlig virksomhet (METS ARCHIVIST)"),
    ("archive_creators", "Oppgitte arkivskapere i Work (ikke bekreftet)"),
    ("owner_org", "Oppgitt arkiveier (METS OWNER)"),
    ("creator_org", "METS CREATOR (ikke automatisk arkivskaper)"),
    ("submitter_org", "Innsender (METS SUBMITTER)"),
    ("producer_org", "Pakkeprodusent (METS PRODUCER)"),
    ("recipient", "Oppgitt mottaker"),
    ("system", "Arkivsystem oppgitt i Work"),
    ("system_version", "Arkivsystemversjon"),
    ("extraction_system", "Uttrekksverktøy"),
    ("extraction_system_version", "Uttrekksverktøyversjon"),
    ("system_type", "Systemtype oppgitt"),
    ("system_type_version", "Noark-versjon for system, oppgitt"),
    ("extraction_system_type", "Uttrekkets systemtype, oppgitt"),
    ("extraction_system_type_version", "Noark-versjon for uttrekk, oppgitt"),
    ("period_start", "Oppgitt startdato"),
    ("period_end", "Oppgitt sluttdato"),
    ("submission_agreement", "Oppgitt avtale-/saksreferanse"),
    ("package_number", "Oppgitt pakkenummer"),
)


def _version_text(value: Any) -> str | None:
    raw = str(value or "").strip()
    if raw.startswith("v"):
        raw = raw[1:]
    return raw if raw in SUPPORTED_NOARK5 else None


def _noark5_type(value: Any) -> bool:
    return str(value or "").casefold().replace(" ", "").replace("-", "") == "noark5"


def _declared_version(fields: dict, canonical: Any) -> dict:
    """Keep conflicting Noark version declarations visible; never guess one."""
    declared: list[tuple[str, str]] = []
    for type_field, ver_field in (("system_type", "system_type_version"),
                                  ("extraction_system_type", "extraction_system_type_version")):
        if _noark5_type(fields.get(type_field)):
            raw = str(fields.get(ver_field) or "").strip()
            if raw:
                declared.append((ver_field, raw))
    c_raw = str(canonical or "").strip()
    values = {raw for _, raw in declared}
    if c_raw:
        values.add(c_raw)
    known = {_version_text(raw) for raw in values}
    if any(v is None for v in known):
        status = "unrecognized"
        version = None
    elif len(known) > 1:
        status = "conflict"
        version = None
    elif not known:
        status = "not_documented"
        version = None
    else:
        version = known.pop()
        status = "canonical_plus_work" if c_raw and declared else (
            "canonical" if c_raw else "work_mets_only")
    return {"version": version, "status": status,
            "canonical_version": c_raw or None,
            "work_declarations": [{"field": key, "version": raw} for key, raw in declared],
            "source_note": "Work/METS er en registrert opplysning, ikke en bekreftet normativ uttrekksversjon."}


def _registry_context(root: Path | None = None) -> dict:
    """Show differences across Noark 5 releases; never validate a source value."""
    registry = (root or Path(__file__).resolve().parents[2]) / STANDARD_VALUES_FILE
    if not registry.is_file() or registry.is_symlink():
        return {"status": "not_available", "metadata_id": "M053", "versions": {}}
    data = _json(registry, limit=2 * 1024 * 1024)
    versions = data.get("versions") or {}
    if not isinstance(versions, dict):
        raise ReportInputError("Versjonsregisteret for Noark 5 har ugyldig struktur")
    result = {}
    for version in SUPPORTED_NOARK5:
        group = (versions.get(version) or {}).get("value_sets") or {}
        candidates = [v for v in group.values() if isinstance(v, dict) and v.get("metadata_id") == "M053"]
        if len(candidates) > 1:
            raise ReportInputError("Flere M053-definisjoner i versjonsregisteret for " + version)
        if candidates:
            values = candidates[0].get("values")
            if not isinstance(values, list) or any(not isinstance(v, str) for v in values):
                raise ReportInputError("Ugyldige M053-verdier i versjonsregisteret")
            result[version] = list(values)
    return {"status": "read_only_reference" if result else "not_available",
            "metadata_id": "M053", "versions": result,
            "source": STANDARD_VALUES_FILE}


def _metadata_context(work: Path, snapshot: dict) -> tuple[dict, list[dict]]:
    meta_path = _rel(work, METADATA_FILE)
    empty = {"status": "not_available", "fields": {}, "sources": [],
             "version": _declared_version({}, (snapshot.get("reported_identity") or {}).get("noark_version_from_canonical"))}
    if not meta_path.exists():
        return empty, []
    metadata = _json(meta_path, limit=3 * 1024 * 1024)
    if metadata.get("file_type") != "dwm-depot-metadata":
        raise ReportInputError("Ukjent Work-metadataformat: " + METADATA_FILE)
    uid = str((snapshot.get("work_identity") or {}).get("job_id") or "")
    if metadata.get("job_id") and str(metadata["job_id"]) != uid:
        raise ReportInputError("DIAS/METS Work-metadata tilhører en annen jobb")
    current = metadata.get("current") or {}
    if not isinstance(current, dict):
        raise ReportInputError("Work-metadata har ugyldig current-felt")
    fields = {}
    for key, _name in METADATA_FIELDS:
        value = current.get(key)
        if isinstance(value, str) and value.strip():
            fields[key] = value.strip()[:2000]
    sources = []
    evidence = [{"kind": "a14_work_mets_metadata", **_source(work, METADATA_FILE)}]
    imports = metadata.get("source_imports") or []
    if not isinstance(imports, list) or len(imports) > 32:
        raise ReportInputError("Ugyldig antall DIAS/METS-importer i Work")
    for item in imports:
        if not isinstance(item, dict) or item.get("kind") != "dias-mets":
            continue
        original = str(item.get("preserved_file") or "").replace("\\", "/")
        sha = str(item.get("sha256") or "")
        origin = {"kind": "dias-mets", "preserved_file": original or None,
                  "recorded_sha256": sha or None, "verification": "not_available"}
        if original:
            path = _rel(work, original)
            if path.is_file():
                if not re.fullmatch(r"[a-fA-F0-9]{64}", sha):
                    raise ReportInputError("Bevart DIAS/METS-kopi mangler dokumentert SHA-256")
                rec = _source(work, original, expected_hash=sha, limit=3 * 1024 * 1024)
                evidence.append({"kind": "a14_original_mets_copy", **rec})
                origin["verification"] = "preserved_copy_hash_matches"
        sources.append(origin)
    version = _declared_version(fields, (snapshot.get("reported_identity") or {}).get("noark_version_from_canonical"))
    return {"status": "work_recorded_unverified_identity", "fields": fields,
            "sources": sources, "version": version,
            "identity_warning": "Opplysninger fra DIAS/METS registrert i Work er ikke automatisk bekreftet av arkivskaper; endringshistorikk i Work kan avvike fra opprinnelig info.xml."}, evidence


def enrich_snapshot(work: str | Path, snapshot: dict, *, registry_root: Path | None = None) -> dict:
    """Add source-labelled read-only context, never altering underlying findings."""
    root = Path(work).resolve(strict=True)
    met, evidence = _metadata_context(root, snapshot)
    result = deepcopy(snapshot)
    result["a14_context"] = {"model_id": "ikamr.dwm.noark5.finding-context.a14.v1",
                             "mets": met, "standard_values": _registry_context(registry_root)}
    result.setdefault("evidence_manifest", []).extend(evidence)
    return result


def explain_finding(finding: dict, context: dict) -> dict:
    """Explain the evidence without changing test severity or suggesting acceptance."""
    severity = str(finding.get("severity") or "Ukjent")
    source = str(finding.get("source") or "Ukjent")
    raw = str(finding.get("message") or "Ingen detaljmelding i original evidens").strip()
    ver = ((context.get("mets") or {}).get("version") or {}).get("version")
    version_status = ((context.get("mets") or {}).get("version") or {}).get("status")
    basis = ("Noark 5 v" + ver + " oppgitt i Work/METS; ikke bekreftet som normativ kontrollversjon."
             if ver and version_status not in ("canonical", "canonical_plus_work") else
             ("Noark 5 v" + ver + " registrert i kanonisk resultatgrunnlag." if ver else
              "Noark 5-versjon er ikke entydig dokumentert for denne rapporten."))
    answer = {"test_id": str(finding.get("test_id") or ""), "severity": severity,
              "source": source, "observed": raw,
              "requirement": "Eksakt standardkrav er ikke knyttet til dette funnet i a14. Se original test og dokumentert Noark-versjon.",
              "distinction": "Et rapportert testutfall er ikke i seg selv et depotvedtak.",
              "version_basis": basis, "metadata_id": None,
              "standard_versions": {}}
    if answer["test_id"] == "N5.22" and source == "Arkade 5":
        match = re.search(r"Journalstatus:\s*(.*?)\s*-\s*Antall:\s*(\d+)\b", raw, flags=re.IGNORECASE)
        if match:
            value = match.group(1).strip()
            count = int(match.group(2))
            answer["observed"] = f"{count} journalposter med status «{value}» (Arkade 5: {severity})."
            answer["metadata_id"] = "M053"
            answer["requirement"] = (
                "Ved uttrekk/avlevering skal journalposter ha «Arkivert» eller «Utgår». "
                "Noark 5 v5.0, vedlegg 1, M053."
                if ver == "5.0" else
                "Arkade N5.22 tester journalstatus ved uttrekk. Noark 5 v5.0 vedlegg 1, M053 angir "
                "«Arkivert» eller «Utgår»; krav for aktuell versjon må bekreftes separat.")
            values = ((context.get("standard_values") or {}).get("versions") or {})
            answer["standard_versions"] = values
            allowed_values = values.get(ver or "", [])
            if value in allowed_values:
                answer["distinction"] = (
                    "«" + value + "» er en registrert M053-standardverdi, men avviker fra "
                    "kravet til journalstatus ved uttrekk. Arkades ERROR beholdes.")
            else:
                answer["distinction"] = (
                    "Statusverdien er ikke bekreftet mot versjonsregisteret. "
                    "Arkades opprinnelige ERROR beholdes; ikke konkluder om verdiens gyldighet automatisk.")
    return answer


def format_explanation(finding: dict, context: dict) -> str:
    """Brief, immediately readable panel; line lists live behind a separate toggle."""
    explanation = explain_finding(finding, context)
    return ("FUNN: " + explanation["observed"] + "\n"
            "KRAV / ÅRSAK: " + explanation["requirement"] + "\n"
            "VIKTIG SKILLE: " + explanation["distinction"] + "\n"
            "VERSJONSKILDE: " + explanation["version_basis"])


def render_identity_excerpt(snapshot: dict) -> str:
    """Near-top attribution, never silently filling canonical identity fields."""
    context = snapshot.get("a14_context") or {}
    mets = context.get("mets") or {}
    fields = mets.get("fields") or {}
    if not fields:
        return ""
    def show(raw: Any) -> str:
        return escape(str(raw or "Ikke dokumentert"), quote=True)
    version = (mets.get("version") or {}).get("version")
    result = "<br><b>Noark-versjon (Work/METS, ikke bekreftet):</b> " + show(version)
    result += "<br><b>Arkivansvarlig (METS ARCHIVIST, Work):</b> " + show(fields.get("archivist_org"))
    result += "<br><b>Arkiveier (METS OWNER, Work):</b> " + show(fields.get("owner_org"))
    if fields.get("system"):
        result += "<br><b>System (METS/Work):</b> " + show(fields.get("system"))
        if fields.get("system_version"):
            result += " v" + show(fields.get("system_version"))
    return result


def render_context_html(snapshot: dict, *, depot: bool) -> str:
    """Append a small shared *factual* appendix, not human notes or new verdicts."""
    context = snapshot.get("a14_context")
    if not isinstance(context, dict):
        return ""
    mets = context.get("mets") or {}
    fields = mets.get("fields") or {}
    def h(raw: Any) -> str:
        return escape(str(raw if raw is not None else "Ikke dokumentert"), quote=True)
    html = ["<h2>11. DIAS/METS – supplerende Work-opplysninger (a14)</h2>",
            "<p>Disse opplysningene er registrert i Work. De erstatter ikke kanonisk "
            "identitet, bekreftelse fra arkivskaper eller normativ Noark-versjon. "
            "METS CREATOR er ikke automatisk arkivskaper.</p>"]
    if mets.get("status") == "not_available":
        html.append("<p>Ingen DIAS/METS metadata er registrert i valgt Work.</p>")
    else:
        html.append("<div class='table-wrap'><table><thead><tr><th>Opplysning</th><th>Oppgitt verdi</th></tr></thead><tbody>")
        html.extend("<tr><td>" + h(label) + "</td><td>" + h(fields.get(key) or "Ikke dokumentert") + "</td></tr>"
                    for key, label in METADATA_FIELDS)
        html.append("</tbody></table></div>")
        verified = sum(x.get("verification") == "preserved_copy_hash_matches" for x in mets.get("sources") or [])
        html.append("<p>Bevarte DIAS/METS-kopier med samsvarende SHA-256: " + str(verified) + ". "
                    "Metadataens innhold og partenes roller krever fortsatt kildekritisk vurdering.</p>")
    vers = mets.get("version") or {}
    html.append("<p><b>Noark-versjon fra opplysninger:</b> " + h(vers.get("version") or "Ikke entydig dokumentert") +
                " (grunnlag: " + h(vers.get("status")) + "). " + h(vers.get("source_note") or "") + "</p>")
    details = [explain_finding(item, context) for item in snapshot.get("findings") or []
               if item.get("source") == "Arkade 5" and item.get("test_id") == "N5.22"]
    if details:
        html.append("<h3>N5.22 – forklaring av rapportert avvik</h3>")
        html.append("<p>Arkades ERROR beholdes uendret. Forklaringen er ikke en vurdering "
                    "av avvikets aksept eller forslag til retting.</p>")
        html.append("<div class='table-wrap'><table><thead><tr><th>Observert</th><th>Avleveringskrav / kontekst</th>"
                    "<th>Viktig skille</th></tr></thead><tbody>")
        for item in details:
            html.append("<tr><td>" + h(item["observed"]) + "</td><td>" + h(item["requirement"]) +
                        "</td><td>" + h(item["distinction"]) + "</td></tr>")
        html.append("</tbody></table></div>")
        reg = context.get("standard_values") or {}
        if reg.get("status") == "read_only_reference":
            html.append("<h3>M053 – registrerte standardverdier i historiske Noark 5-versjoner</h3>"
                        "<p>Dette er en sammenligning av verdiutvalget, ikke en test av kravene "
                        "ved uttrekk. Noark 5 v4.0 må ikke forveksles med Noark 4.</p>")
            html.append("<div class='table-wrap'><table><thead><tr><th>Versjon</th><th>Verdier</th></tr></thead><tbody>")
            for version, values in reg.get("versions", {}).items():
                html.append("<tr><td>Noark 5 v" + h(version) + "</td><td>" + h(", ".join(values)) + "</td></tr>")
            html.append("</tbody></table></div>")
    return "".join(html)
