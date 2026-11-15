"""Source-first XSD variant and diagnostic evidence for Noark 5.

This module does NOT certify normative equivalence or approve modified schemas.
It never writes to, or changes, an original Source or a reference XSD.

Internal reference: IKAMR/digital-archive-workflow/docs/kilder/noark/noark5.
Historical XPath test source: IKAMR/KDRS_Query, separate from this module.
"""
from __future__ import annotations

import argparse
from collections import Counter
from difflib import SequenceMatcher
import hashlib
import json
from pathlib import Path
import re
import subprocess
import unicodedata
from typing import Any
from urllib.parse import urlsplit
from lxml import etree

XSD_NAMESPACE = "http://www.w3.org/2001/XMLSchema"
ALLOWED_VERSIONS = frozenset({"3.1", "4.0", "5.0"})
XSD_FILENAMES = frozenset({
    "arkivstruktur.xsd", "endringslogg.xsd", "loependeJournal.xsd",
    "metadatakatalog.xsd", "offentligJournal.xsd",
})
MAX_SCHEMA_BYTES = 8_000_000
MAX_XML_BYTES = 64_000_000  # Small diagnostic exemplars only, not large-source operations.


def _sha(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _raw(path: Path, limit: int) -> bytes:
    if not path.is_file():
        raise ValueError(f"Fil mangler: {path}")
    if path.stat().st_size > limit:
        raise ValueError(f"Fil overskrider avgrensning ({limit} byte): {path}")
    return path.read_bytes()


def _newlines_lf(payload: bytes) -> bytes:
    """Only normalize byte-level line endings. BOM, spaces and XML stay intact."""
    return payload.replace(b"\r\n", b"\n").replace(b"\r", b"\n")


def _newline_style(data: bytes) -> str:
    crlf = data.count(b"\r\n")
    lf = data.count(b"\n") - crlf
    cr = data.count(b"\r") - crlf
    styles = [name for count, name in ((crlf, "CRLF"), (lf, "LF"), (cr, "CR")) if count]
    return "+".join(styles) if styles else "none"


def _schema_root(payload: bytes) -> tuple[str | None, str]:
    parser = etree.XMLParser(resolve_entities=False, load_dtd=False, no_network=True)
    root = etree.fromstring(payload, parser=parser)
    if root.tag != f"{{{XSD_NAMESPACE}}}schema":
        raise ValueError("Ikke et XML Schema-dokument")
    ns = str(root.get("targetNamespace") or "")
    if "/noark5/" not in ns.lower():
        raise ValueError("Ikke Noark 5 namespace")
    return root.get("version"), ns


def fingerprint(path: str | Path) -> dict[str, Any]:
    """Exact and EOL-insensitive digests; neither implies normative validity."""
    p = Path(path).resolve()
    data = _raw(p, MAX_SCHEMA_BYTES)
    version, ns = _schema_root(data)
    return {
        "filename": p.name,
        "sha256": _sha(data),
        "sha256_lf_normalized": _sha(_newlines_lf(data)),
        "size_bytes": len(data),
        "newline_style": _newline_style(data),
        "schema_version_declared": version,
        "target_namespace": ns,
    }


def compare_variant(
    observed_path: str | Path,
    reference_path: str | Path,
    *,
    source_commit: str | None = None,
    parent_path: str | Path | None = None,
    declared_purpose: str | None = None,
) -> dict[str, Any]:
    """Match known reference by exact/EOL digest, or flag changed content.

    No mutation, no unverified equivalence claims, no cross-version fallback.
    """
    obs, ref = fingerprint(observed_path), fingerprint(reference_path)
    if obs["filename"] != ref["filename"]:
        raise ValueError("Sammenlign samme XSD-filnavn")
    if obs["schema_version_declared"] != ref["schema_version_declared"]:
        status = "declared_version_conflict"
    elif obs["target_namespace"] != ref["target_namespace"]:
        status = "namespace_conflict"
    elif obs["sha256"] == ref["sha256"]:
        status = "exact_reference_bytes"
    elif obs["sha256_lf_normalized"] == ref["sha256_lf_normalized"]:
        status = "line_endings_only"
    else:
        status = "content_variant_requires_qa"
    result: dict[str, Any] = {
        "reference_repository": "IKAMR/digital-archive-workflow",
        "reference_commit": source_commit,
        "status": status,
        "observed": obs,
        "reference": ref,
        "exact_reference_byte_identity": status == "exact_reference_bytes",
        "normative_compliance_approved": False,
        "source_data_modified": False,
        "warning": "EOL-ekvivalens viser identisk XML-tekst etter linjeskiftnormalisering; annen variant må QA-vurderes.",
    }
    if parent_path is not None:
        result["parent"] = fingerprint(parent_path)
        result["declared_purpose"] = declared_purpose or "not_specified"
        result["qa_status"] = "operator_review_required"
    return result



def metadata_type_facets(schema_path: str | Path, metadata_id: str) -> dict[str, Any] | None:
    """Read exact M-ID annotated type and primitive facets from our local XSD.

    Does not establish obligation, object-level occurrence or semantic custom
    value permission (those may be in the PDF/DOCX source specification).
    """
    if not re.fullmatch(r"M\d{3}", metadata_id):
        raise ValueError("Ugyldig metadata-ID")
    path = Path(schema_path).resolve()
    data = _raw(path, MAX_SCHEMA_BYTES)
    version, ns = _schema_root(data)
    parser = etree.XMLParser(resolve_entities=False, load_dtd=False, no_network=True)
    root = etree.fromstring(data, parser=parser)
    xs = f"{{{XSD_NAMESPACE}}}"
    for typ in root:
        if typ.tag not in {xs + "simpleType", xs + "complexType"} or not typ.get("name"):
            continue
        ann = typ.find(xs + "annotation")
        if ann is None:
            continue
        ids = ["".join(n.itertext()).strip() for n in ann.findall(xs + "documentation")]
        if metadata_id not in ids:
            continue
        facets = [x for x in typ.iter() if x.tag in {xs + "restriction", xs + "extension"}]
        base = facets[0].get("base") if facets else None
        enums = [str(el.get("value")) for el in typ.iter(xs + "enumeration")]
        minima = [el.get("value") for el in typ.iter(xs + "minLength")]
        return {
            "metadata_id": metadata_id,
            "name": typ.get("name"),
            "schema_version": version,
            "source_schema_sha256": _sha(data),
            "restriction_base": base,
            "enumeration": enums,
            "min_length": int(minima[0]) if minima else None,
            "xsd_constraint": "enumeration" if enums else ("min_length" if minima else "other"),
            "custom_values_permitted_by_standard_text": "requires_separate_specification_qa",
        }
    return None


def reference_metadata_overview(reference_root: str | Path,
                                metadata_ids: tuple[str, ...] = ("M300", "M619")) -> dict[str, Any]:
    """Compare version-specific XSD restrictions; never extrapolate to other versions."""
    root = Path(reference_root).resolve()
    out = {}
    for version in ("3.1", "4.0", "5.0"):
        path = (root / "docs" / "kilder" / "noark" / "noark5"
                / f"v{version}" / "schemas" / "metadatakatalog.xsd")
        if not path.is_file():
            out[version] = {"status": "reference_schema_missing", "expected": str(path)}
            continue
        out[version] = {"status": "checked", "source_file": str(path),
                        "metadata": {m: metadata_type_facets(path, m) for m in metadata_ids}}
    return {"source_repository": "IKAMR/digital-archive-workflow",
            "status": "technical_xsd_facet_comparison_not_full_specification_qa",
            "versions": out}



def compare_dwm_value_sets(reference_root: str | Path,
                           dwm_value_registry: str | Path) -> dict[str, Any]:
    """Literal XSD enumeration crosswalk, not a normative acceptance matrix."""
    raw = json.loads(Path(dwm_value_registry).read_text(encoding="utf-8"))
    results: dict[str, Any] = {}
    for version in ("3.1", "4.0", "5.0"):
        xsd = (Path(reference_root).resolve() / "docs" / "kilder" / "noark" / "noark5" /
               f"v{version}" / "schemas" / "metadatakatalog.xsd")
        if not xsd.is_file():
            results[version] = {"status": "source_xsd_missing"}
            continue
        data = _raw(xsd, MAX_SCHEMA_BYTES)
        root = etree.fromstring(data, parser=etree.XMLParser(
            resolve_entities=False, load_dtd=False, no_network=True))
        xs = f"{{{XSD_NAMESPACE}}}"
        xsd_enums: dict[str, dict[str, Any]] = {}
        for typ in root:
            if typ.tag not in {xs + "simpleType", xs + "complexType"}:
                continue
            ann = typ.find(xs + "annotation")
            if ann is None:
                continue
            ids = ["".join(n.itertext()).strip() for n in ann.findall(xs + "documentation")]
            ids = [mid for mid in ids if re.fullmatch(r"M\d{3}", mid)]
            enums = [str(n.get("value")) for n in typ.iter(xs + "enumeration")]
            if ids and enums:
                xsd_enums[ids[0]] = {"metadata_id": ids[0],
                                      "type_name": typ.get("name"), "values": enums}
        registered = raw.get("versions", {}).get(version, {}).get("value_sets", {})
        ref_by_id = {x.get("metadata_id"): {"value_set_id": key, **x}
                     for key, x in registered.items() if isinstance(x, dict) and x.get("metadata_id")}
        gaps = [rec for mid, rec in sorted(xsd_enums.items()) if mid not in ref_by_id]
        diffs = []
        for mid, rec in sorted(xsd_enums.items()):
            if mid not in ref_by_id:
                continue
            source = set(rec["values"])
            current = set(ref_by_id[mid].get("values", []))
            if source != current:
                diffs.append({"metadata_id": mid,
                              "xsd_only": sorted(source - current),
                              "dwm_only": sorted(current - source),
                              "status": "operator_qa_required_no_auto_repair"})
        results[version] = {
            "status": "checked",
            "source_schema_sha256": _sha(data),
            "xsd_enumerated_metadata_count": len(xsd_enums),
            "dwm_registered_value_set_count": len(registered),
            "xsd_enumerations_registered_in_dwm": sum(mid in ref_by_id for mid in xsd_enums),
            "xsd_enumerations_not_registered": gaps,
            "literal_value_differences": diffs,
            "warning": "v5 standardverdier i DWM er ikke en XSD enumeration når XSD har friteksttype",
        }
    return {"audit_type": "literal_xsd_enumeration_crosswalk_not_normative_qa",
            "versions": results}


def _schema_dependencies(path: Path) -> dict[str, str]:
    """Keep schema graph local; refuse external or parent-traversal references."""
    visited: dict[str, str] = {}

    def visit(candidate: Path) -> None:
        candidate = candidate.resolve()
        if candidate.parent != path.resolve().parent:
            raise ValueError("XSD-avhengighet utenfor valgt skjemamappe er ikke tillatt")
        if candidate.name in visited:
            return
        data = _raw(candidate, MAX_SCHEMA_BYTES)
        parser = etree.XMLParser(resolve_entities=False, load_dtd=False, no_network=True)
        root = etree.fromstring(data, parser=parser)
        if root.tag != f"{{{XSD_NAMESPACE}}}schema":
            raise ValueError("XSD-avhengighet har ugyldig rot")
        visited[candidate.name] = _sha(data)
        for element in root:
            if element.tag not in {f"{{{XSD_NAMESPACE}}}include", f"{{{XSD_NAMESPACE}}}import", f"{{{XSD_NAMESPACE}}}redefine"}:
                continue
            loc = element.get("schemaLocation")
            if not loc:
                continue
            if urlsplit(loc).scheme or "\\" in loc or Path(loc).name != loc:
                raise ValueError(f"Ekstern/relativ XSD-avhengighet er ikke tillatt: {loc}")
            visit(candidate.parent / loc)

    visit(path)
    return dict(sorted(visited.items()))


def _error_rows(log: Any) -> list[dict[str, Any]]:
    return [{
        "line": row.line, "column": row.column, "path": row.path,
        "domain": row.domain_name, "type": row.type_name,
        "level": row.level_name, "message": row.message,
    } for row in log]


def _diagnostic_validation(xml_path: Path, xsd_path: Path) -> dict[str, Any]:
    # Check/record all local XSD dependencies before parser accesses them.
    deps = _schema_dependencies(xsd_path)
    parser = etree.XMLParser(resolve_entities=False, load_dtd=False, no_network=True)
    schema = etree.XMLSchema(etree.parse(str(xsd_path), parser=parser))
    xml_parser = etree.XMLParser(resolve_entities=False, load_dtd=False, no_network=True, huge_tree=False)
    tree = etree.parse(str(xml_path), parser=xml_parser)
    valid = bool(schema.validate(tree))
    return {"valid": valid, "errors": _error_rows(schema.error_log), "schema_graph_sha256": deps}


def _error_key(row: dict[str, Any]) -> str:
    # Stable within the same lxml/XSD setup. Raw messages retained as evidence.
    return json.dumps([row.get("line"), row.get("column"), row.get("path"),
                       row.get("domain"), row.get("type"), row.get("message")], ensure_ascii=False)


def diagnostic_comparison(xml: str | Path, original_schema: str | Path,
                          diagnostic_schema: str | Path) -> dict[str, Any]:
    """Compare original and explicitly modified XSD against unchanged XML.

    No normative acceptance: even 0 remaining errors is a *diagnostic* result.
    """
    xml_path = Path(xml).resolve()
    before_path = Path(original_schema).resolve()
    after_path = Path(diagnostic_schema).resolve()
    if before_path == after_path:
        raise ValueError("Original og diagnostisk XSD må være separate filer")
    if before_path.name != after_path.name:
        raise ValueError("Begge XSD-filer må ha samme navn i adskilte mapper")
    xml_data = _raw(xml_path, MAX_XML_BYTES)
    xml_hash = _sha(xml_data)
    original = _diagnostic_validation(xml_path, before_path)
    diagnostic = _diagnostic_validation(xml_path, after_path)
    if _sha(_raw(xml_path, MAX_XML_BYTES)) != xml_hash:
        raise RuntimeError("Kilde-XML endret seg under sammenligningen")
    if (_schema_dependencies(before_path) != original["schema_graph_sha256"] or
            _schema_dependencies(after_path) != diagnostic["schema_graph_sha256"]):
        raise RuntimeError("XSD-avhengighetene endret seg under sammenligningen")
    bc = Counter(_error_key(x) for x in original["errors"])
    ac = Counter(_error_key(x) for x in diagnostic["errors"])
    removed = bc - ac
    introduced = ac - bc
    return {
        "analysis_type": "diagnostic_xsd_comparison_not_normative_acceptance",
        "xml_sha256": xml_hash,
        "xml_file": str(xml_path),
        "original_schema_file": str(before_path),
        "diagnostic_schema_file": str(after_path),
        "original": original,
        "diagnostic": diagnostic,
        "original_error_count": len(original["errors"]),
        "diagnostic_error_count": len(diagnostic["errors"]),
        "error_occurrences_removed": sum(removed.values()),
        "error_occurrences_introduced": sum(introduced.values()),
        "error_occurrences_unchanged": sum((bc & ac).values()),
        "removed_fingerprints": [{"key": k, "count": v} for k, v in sorted(removed.items())],
        "introduced_fingerprints": [{"key": k, "count": v} for k, v in sorted(introduced.items())],
        "original_xsd_failure_preserved": not original["valid"],
        "normative_approval": "not_assessed",
    }


def _value_key(s: str) -> str:
    return " ".join(unicodedata.normalize("NFC", s).split()).casefold()


def value_candidate(observed: str, reference_values: list[str],
                    *, approved_aliases: dict[str, str] | None = None) -> dict[str, Any]:
    """Preserve observed literal value. Suggestions are never auto-accepted."""
    if not isinstance(observed, str):
        raise TypeError("observed må være tekst")
    exact = list(dict.fromkeys(reference_values))
    result: dict[str, Any] = {
        "observed_raw": observed, "status": "unknown_needs_qa", "candidate": None,
        "normative_compliance_approved": False,
    }
    if observed in exact:
        result.update(status="exact_reference_value", candidate=observed,
                      literal_reference_match=True)
        return result
    if approved_aliases and observed in approved_aliases:
        target = approved_aliases[observed]
        if target not in exact:
            raise ValueError("Godkjent alias peker ikke til gyldig referanseverdi")
        result.update(status="operator_approved_alias", candidate=target,
                      normative_compliance_approved=False,
                      note="Bare faglig sammenligning; original XSD krever fortsatt eksakt literal")
        return result
    same_format = [v for v in exact if _value_key(v) == _value_key(observed)]
    if len(same_format) == 1:
        result.update(status="formatting_candidate_needs_qa", candidate=same_format[0])
        return result
    ranked = sorted(((SequenceMatcher(None, _value_key(observed), _value_key(v)).ratio(), v)
                     for v in exact), key=lambda x: (-x[0], x[1]))
    if ranked and ranked[0][0] >= 0.86:
        result.update(status="similar_text_candidate_needs_qa", candidate=ranked[0][1],
                      similarity=round(ranked[0][0], 4),
                      ambiguous_candidates=[v for score, v in ranked if score >= ranked[0][0] - 0.02])
    return result



def source_checkout_commit(path: str | Path) -> str | None:
    """Return immutable HEAD when reference repo is a real local Git checkout."""
    try:
        proc = subprocess.run(["git", "rev-parse", "HEAD"], cwd=Path(path),
                              capture_output=True, text=True, check=False, timeout=5)
        commit = proc.stdout.strip()
        if proc.returncode == 0 and re.fullmatch(r"[0-9a-f]{40}", commit):
            return commit
    except (FileNotFoundError, OSError, subprocess.TimeoutExpired):
        pass
    return None


def build_schema_variant_inventory(reference_root: str | Path, candidates: list[str | Path],
                                   *, source_commit: str | None = None) -> dict[str, Any]:
    root = Path(reference_root).resolve()
    current_commit = source_checkout_commit(root)
    if current_commit and source_commit and source_commit != current_commit:
        raise ValueError("Angitt kildecommit samsvarer ikke med lokal utsjekking")
    source_commit = current_commit or source_commit
    records = []
    for candidate in candidates:
        observed = Path(candidate).resolve()
        if observed.name not in XSD_FILENAMES:
            raise ValueError(f"Ukjent Noark XSD-navn: {observed.name}")
        fp = fingerprint(observed)
        version = fp["schema_version_declared"]
        if version not in ALLOWED_VERSIONS:
            records.append({"status": "unknown_schema_version_needs_qa", "observed": fp})
            continue
        ref = root / "docs" / "kilder" / "noark" / "noark5" / f"v{version}" / "schemas" / observed.name
        if not ref.is_file():
            records.append({"status": "authoritative_reference_missing", "observed": fp,
                            "expected_reference_path": str(ref)})
            continue
        records.append(compare_variant(observed, ref, source_commit=source_commit))
    return {"report_format_version": 1,
            "source_repository": "IKAMR/digital-archive-workflow",
            "source_commit": source_commit,
            "source_commit_verified_from_checkout": current_commit is not None,
            "read_only": True,
            "records": records}



def aggregate_existing_work_ledgers(work_areas: list[str | Path]) -> dict[str, Any]:
    """Read explicit per-job Work ledgers from the preexisting a6 mechanism.

    Does not walk drives, read XML payloads, or copy any depot content into Git.
    """
    merged: dict[str, dict[str, Any]] = {}
    sources_reviewed = []
    for work_path in work_areas:
        work = Path(work_path).resolve()
        ledger = work / "noark5_evidence" / "xsd_variants.json"
        if not ledger.is_file():
            sources_reviewed.append({"work_area": str(work), "status": "ledger_not_found"})
            continue
        if ledger.stat().st_size > 5_000_000:
            raise ValueError("Work-ledger overskrider størrelsesgrensen")
        data = json.loads(ledger.read_text(encoding="utf-8"))
        if data.get("schema_version") != "1.0" or not isinstance(data.get("variants"), list):
            raise ValueError("Ukjent Work-ledgerformat")
        obs = data.get("observations", [])
        if not isinstance(obs, list):
            raise ValueError("Ukjent observasjonsliste")
        counts = Counter(o.get("variant_id") for o in obs if isinstance(o, dict))
        for entry in data["variants"]:
            digest = entry.get("sha256")
            if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
                raise ValueError("Ugyldig SHA-256 i Work-ledger")
            record = merged.setdefault(digest, {
                "sha256": digest, "filenames": set(), "declared_versions": set(),
                "jobs_seen": 0, "observation_count": 0,
                "source_file_content_checked": False,
                "provenance": "local_work_observation_not_normative_reference",
            })
            record["filenames"].add(entry.get("filename") or "")
            version = entry.get("schema_version_declared")
            if version:
                record["declared_versions"].add(version)
            record["jobs_seen"] += 1
            record["observation_count"] += counts.get(entry.get("variant_id"), 0)
        sources_reviewed.append({"work_area": str(work), "status": "loaded",
                                 "variants": len(data["variants"]), "observations": len(obs)})
    return {
        "report_format_version": 1, "read_only": True,
        "unique_raw_sha256_variants": len(merged),
        "variant_observations": [{**row,
            "filenames": sorted(row["filenames"]),
            "declared_versions": sorted(row["declared_versions"])}
            for _, row in sorted(merged.items())],
        "work_ledgers": sources_reviewed,
        "note": "Samlet Work-evidens er ikke et normativt XSD-register og gir ikke EOL-ekvivalens uten filbytes.",
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--reference-root", type=Path, required=True,
                   help="Lokal utsjekking av IKAMR/digital-archive-workflow")
    p.add_argument("--schema", action="append", type=Path, required=True,
                   help="Eksakt XSD-fil fra uttrekk eller diagnostisk kopi; kan gjentas")
    p.add_argument("--source-commit", default=None)
    p.add_argument("--dwm-root", type=Path, default=Path(__file__).resolve().parents[1],
                   help="DWM-reporot med versjonert standardverdiregister")
    p.add_argument("--work-ledger", action="append", type=Path, default=[],
                   help="Eksakt jobb-Work med noark5_evidence/xsd_variants.json; kan gjentas")
    p.add_argument("--diagnostic-xml", type=Path, default=None,
                   help="Den uendrede XML-filen brukt i før/etter-sammenligning")
    p.add_argument("--diagnostic-original-schema", type=Path, default=None,
                   help="Original XSD, med lokale avhengigheter i samme mappe")
    p.add_argument("--diagnostic-modified-schema", type=Path, default=None,
                   help="Diagnostisk modifisert XSD i separat mappe")
    p.add_argument("--work-root", type=Path, required=True,
                   help="Eksisterende, eksplisitt Work-område, adskilt fra kildene")
    p.add_argument("--output", type=Path, required=True,
                   help="JSON-evidensfil innenfor Work-området")
    args = p.parse_args(argv)
    output = args.output.resolve()
    work = args.work_root.resolve()
    forbidden = [args.reference_root.resolve(), *(s.resolve().parent for s in args.schema)]
    if not work.is_dir() or work not in output.parents:
        p.error("Utdatarapporten må ligge innenfor et eksisterende Work-område")
    if any(work == x or x in work.parents or work in x.parents for x in forbidden):
        p.error("Work må være adskilt fra kilde- og XSD-mapper")
    result = build_schema_variant_inventory(args.reference_root, args.schema,
                                            source_commit=args.source_commit)
    result["reference_metadata_M300_M619"] = reference_metadata_overview(args.reference_root)
    registry_path = (args.dwm_root / "config/noark5/standards/noark5_standard_values.json")
    if registry_path.is_file():
        result["dwm_value_set_crosswalk"] = compare_dwm_value_sets(args.reference_root, registry_path)
    if args.work_ledger:
        result["existing_work_variant_aggregation"] = aggregate_existing_work_ledgers(args.work_ledger)
    diagnostic_args = [args.diagnostic_xml, args.diagnostic_original_schema,
                       args.diagnostic_modified_schema]
    if any(x is not None for x in diagnostic_args):
        if any(x is None for x in diagnostic_args):
            p.error("Diagnostisk XSD-sammenligning krever alle tre filargumentene")
        result["diagnostic_comparison"] = diagnostic_comparison(*diagnostic_args)
    if output.exists():
        p.error("Rapportfilen finnes allerede; velg nytt filnavn for å bevare tidligere QA-evidens")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"XSD-inventar: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
