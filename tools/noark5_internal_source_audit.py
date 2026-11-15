"""Read-only source-first Noark 5 QA inventory for IKAMR/DWM.

The IKAMR/digital-archive-workflow checkout is the internal authoritative
reference collection. Externally observed differences require operator QA.
This script does NOT claim that textual mentions or XPath tokens prove normative
compliance. It never modifies source documents or existing DWM catalogues.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import re
import subprocess
from typing import Any
import xml.etree.ElementTree as ET
from zipfile import ZipFile

VERSIONS = ("3.1", "4.0", "5.0")
XSD_NS = "http://www.w3.org/2001/XMLSchema"
WORD_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
SHEET_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
M_ID = re.compile(r"(?<![A-Za-z0-9])M\d{3}(?![A-Za-z0-9])")
# These are *lexical references*, not independently established requirement IDs.
REQUIREMENT_ID = re.compile(r"\b\d+\.\d+\.\d+\b")
XSD_NAMES = ("arkivstruktur.xsd", "endringslogg.xsd", "loependeJournal.xsd",
             "metadatakatalog.xsd", "offentligJournal.xsd")
KDRS_FILES = (
    "xml-queries_noark5_2026-05-26.txt",
    "xml-queries_noark5_2026-05-26_U1.txt",
    "xml-queries_noark5_2026-05-26_U2.txt",
    "xml-queries_noark5_2026-05-26_no-journal.txt",
    "xml-queries_noark5_2026-05-26_no-offjournal.txt",
)


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _git_commit(repo: Path) -> str | None:
    try:
        proc = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo,
                              capture_output=True, text=True, timeout=8,
                              check=False)
        commit = proc.stdout.strip()
        return commit if proc.returncode == 0 and re.fullmatch("[a-f0-9]{40}", commit) else None
    except (OSError, subprocess.TimeoutExpired):
        return None


def xsd_metadata(path: Path) -> dict[str, dict[str, Any]]:
    """Read M-numbered type declarations, preserving XSD spelling and facets."""
    root = ET.parse(path).getroot()
    xs = f"{{{XSD_NS}}}"
    types: dict[str, dict[str, Any]] = {}
    for typ in root.iter():
        if typ.tag not in {xs + "simpleType", xs + "complexType"}:
            continue
        name = typ.get("name")
        ann = typ.find(xs + "annotation")
        if not name or ann is None:
            continue
        id_match = None
        for doc in ann.findall(xs + "documentation"):
            value = (doc.text or "").strip()
            if re.fullmatch(r"M\d{3}", value):
                id_match = value
                break
        if not id_match:
            continue
        restrictions = [n for n in typ.iter() if n.tag in {xs + "restriction", xs + "extension"}]
        restrict = restrictions[0] if restrictions else None
        enumerations = [n.get("value") for n in typ.iter() if n.tag == xs + "enumeration"]
        minima = [n.get("value") for n in typ.iter() if n.tag == xs + "minLength"]
        types[id_match] = {
            "metadata_id": id_match,
            "xsd_name": name,
            "type_kind": typ.tag.rsplit("}", 1)[-1],
            "base": restrict.get("base") if restrict is not None else None,
            "enumerations": [x for x in enumerations if x is not None],
            "min_length": minima[0] if minima else None,
        }
    return types


def xsd_elements(path: Path) -> dict[str, list[dict[str, Any]]]:
    root = ET.parse(path).getroot()
    xs = f"{{{XSD_NS}}}"
    elements: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for el in root.iter(xs + "element"):
        name = el.get("name")
        if name:
            elements[name].append({"type": el.get("type"),
                                   "min_occurs": el.get("minOccurs", "1"),
                                   "max_occurs": el.get("maxOccurs", "1")})
    return dict(elements)


def manifest_sha_status(raw: bytes, sha256: str | None) -> str:
    if not sha256:
        return "manifest_digest_missing"
    if _sha(raw) == sha256:
        return "identical_bytes"
    # Git can normalize CRLF text to LF, unlike the original SOURCE-MANIFEST.
    if b"\r\n" not in raw and _sha(raw.replace(b"\n", b"\r\n")) == sha256:
        return "matches_original_after_restoring_crlf"
    return "hash_mismatch_qa"


def _docx_sections(path: Path) -> list[tuple[str, str]]:
    sections = []
    with ZipFile(path) as z:
        members = [n for n in z.namelist() if n == "word/document.xml"
                   or re.fullmatch(r"word/(?:footnotes|endnotes|header\d+|footer\d+)\.xml", n)]
        for member in members:
            root = ET.fromstring(z.read(member))
            ptag, ttag = f"{{{WORD_NS}}}p", f"{{{WORD_NS}}}t"
            for i, paragraph in enumerate(root.iter(ptag), 1):
                content = "".join(node.text or "" for node in paragraph.iter(ttag)).strip()
                if content:
                    sections.append((f"{member}:p{i}", content))
    return sections


def _xlsx_sections(path: Path) -> list[tuple[str, str]]:
    sections = []
    ns = f"{{{SHEET_NS}}}"
    with ZipFile(path) as z:
        names = set(z.namelist())
        shared = []
        if "xl/sharedStrings.xml" in names:
            root = ET.fromstring(z.read("xl/sharedStrings.xml"))
            for item in root.iter(ns + "si"):
                shared.append("".join(n.text or "" for n in item.iter(ns + "t")))
        sheets = sorted(n for n in names if re.fullmatch(r"xl/worksheets/sheet\d+\.xml", n))
        for sheet in sheets:
            root = ET.fromstring(z.read(sheet))
            for row in root.iter(ns + "row"):
                values = []
                for cell in row.findall(ns + "c"):
                    value = cell.find(ns + "v")
                    inline = cell.find(ns + "is")
                    if cell.get("t") == "s" and value is not None:
                        try:
                            values.append(shared[int(value.text or "-1")])
                        except (IndexError, ValueError):
                            pass
                    elif inline is not None:
                        values.append("".join(t.text or "" for t in inline.iter(ns + "t")))
                    elif value is not None and value.text:
                        values.append(value.text)
                if values:
                    sections.append((f"{sheet}:row{row.get('r', '?')}", " | ".join(values)))
    return sections


def _pdf_sections(path: Path) -> tuple[list[tuple[str, str]], str]:
    """Extract existing text; no guessed OCR and no silent empty-PDF success."""
    try:
        import fitz  # type: ignore
        with fitz.open(str(path)) as pdf:
            return [(f"page{i + 1}", page.get_text() or "")
                    for i, page in enumerate(pdf)], "pymupdf"
    except ImportError:
        pass
    except Exception as exc:
        return [], f"pdf_parse_error:{type(exc).__name__}"
    try:
        from pypdf import PdfReader  # type: ignore
        pdf = PdfReader(str(path))
        return [(f"page{i + 1}", page.extract_text() or "")
                for i, page in enumerate(pdf.pages)], "pypdf"
    except ImportError:
        return [], "not_read_no_pdf_library"
    except Exception as exc:
        return [], f"pdf_parse_error:{type(exc).__name__}"


def read_source_document(path: Path) -> tuple[list[tuple[str, str]], str]:
    ext = path.suffix.lower()
    try:
        if ext == ".pdf":
            return _pdf_sections(path)
        if ext == ".docx":
            return _docx_sections(path), "docx_xml"
        if ext == ".xlsx":
            return _xlsx_sections(path), "xlsx_xml"
        if ext in {".xml", ".md", ".txt"}:
            text = path.read_text(encoding="utf-8-sig")
            return [(f"line{i}", line) for i, line in enumerate(text.splitlines(), 1)], "plain_text"
        return [], "unsupported_format"
    except (ValueError, KeyError, ET.ParseError, OSError) as exc:
        return [], f"parse_error:{type(exc).__name__}"


def document_inventory(path: Path, root: Path) -> dict:
    sections, parser = read_source_document(path)
    ids = Counter()
    requirements = Counter()
    locations = defaultdict(list)
    nonempty_sections = 0
    for loc, text in sections:
        if not text.strip():
            continue
        nonempty_sections += 1
        found = set(M_ID.findall(text))
        for m in found:
            ids[m] += 1
            if len(locations[m]) < 8:
                locations[m].append(loc)
        for req in set(REQUIREMENT_ID.findall(text)):
            requirements[req] += 1
    return {
        "file": str(path.relative_to(root)).replace("\\", "/"),
        "bytes": path.stat().st_size,
        "sha256": _sha(path.read_bytes()),
        "extractor": parser,
        "sections": len(sections),
        "sections_with_text": nonempty_sections,
        "metadata_lexical_ids": dict(sorted(ids.items())),
        "metadata_lexical_locations": dict(sorted(locations.items())),
        "requirement_number_lexical_count": len(requirements),
        "requirement_number_examples": sorted(requirements)[:30],
        "warning": "Lexical occurrences are not normative verification or extracted requirement meaning.",
    }


def _expressions(test: dict) -> list[str]:
    exe = test.get("execution") or {}
    out: list[str] = []
    for metric in [*(exe.get("metrics") or []), *(exe.get("archive_part_metrics") or [])]:
        if isinstance(metric, dict):
            out.extend(str(metric[key]) for key in ("expression", "select", "value")
                       if isinstance(metric.get(key), str))
            out.extend(x for x in (metric.get("fields") or {}).values() if isinstance(x, str))
    return out


def xpath_mentions_field(expression: str, field: str) -> bool:
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_.-]*", field):
        return False
    # Deliberately conservative: quoted XPath string values are not names.
    code = re.sub(r"'[^']*'|\"[^\"]*\"", " ", expression)
    return re.search(r"(?<![A-Za-z0-9_.:-])" + re.escape(field)
                     + r"(?![A-Za-z0-9_.:-])", code) is not None


def build_audit(dwm_root: Path, sources_root: Path, kdrs_root: Path | None = None) -> dict:
    dwm_root, sources_root = dwm_root.resolve(), sources_root.resolve()
    sources = sources_root / "docs" / "kilder" / "noark"
    if not sources.is_dir() or not (sources / "SOURCE-MANIFEST.json").is_file():
        raise FileNotFoundError("Mangler IKAMR/digital-archive-workflow/docs/kilder/noark/SOURCE-MANIFEST.json")
    manifest = _json(sources / "SOURCE-MANIFEST.json")
    manifests = {row["path"]: row for row in manifest.get("files", [])}
    catalog = _json(dwm_root / "config/noark5/tests/xpath_catalog_2026_05_26.json")
    values = _json(dwm_root / "config/noark5/standards/noark5_standard_values.json")
    report: dict[str, Any] = {
        "report_format_version": 1,
        "authority_for_dwm": "IKAMR/digital-archive-workflow/docs/kilder/noark/noark5",
        "dwm_source_commit": _git_commit(dwm_root),
        "reference_source_commit": _git_commit(sources_root),
        "kdrs_source_commit": _git_commit(kdrs_root) if kdrs_root else None,
        "versions": {},
        "kdrs_reference_matches": [],
        "not_normative_coverage_certification": True,
        "governance": "External discrepancies require QA with repository owner before changing canonical sources or DWM rules.",
    }
    for v in VERSIONS:
        path = sources / "noark5" / f"v{v}"
        if not path.is_dir():
            report["versions"][v] = {"status": "source_version_missing"}
            continue
        xsd_inventory = []
        xsd_meta = {}
        xsd_elements_by_file = {}
        for name in XSD_NAMES:
            xsd = path / "schemas" / name
            if not xsd.is_file():
                xsd_inventory.append({"name": name, "status": "missing"})
                continue
            raw = xsd.read_bytes()
            expected = manifests.get(f"noark5/v{v}/schemas/{name}", {})
            parsed = ET.parse(xsd).getroot()
            xsd_inventory.append({"name": name, "declared_version": parsed.get("version"),
                                  "git_checkout_sha256": _sha(raw),
                                  "manifest_sha256": expected.get("sha256"),
                                  "manifest_integrity": manifest_sha_status(raw, expected.get("sha256")),
                                  "elements_declared": sum(len(x) for x in xsd_elements(xsd).values())})
            xsd_elements_by_file[name] = xsd_elements(xsd)
            if name == "metadatakatalog.xsd":
                xsd_meta = xsd_metadata(xsd)
        metadata_registry = _json(dwm_root / f"config/noark5/standards/metadata/{v}.json")
        req_registry = _json(dwm_root / f"config/noark5/standards/requirements/{v}.json")
        registered = {m["metadata_id"]: m for m in metadata_registry["metadata"]}
        version_tests = [t for t in catalog["tests"] if v in (t.get("noark_versions") or [])]
        links = defaultdict(list)
        for t in version_tests:
            for m_id, spec in xsd_meta.items():
                if any(xpath_mentions_field(x, spec["xsd_name"]) for x in _expressions(t)):
                    links[m_id].append(t["test_id"])
        value_sets = values.get("versions", {}).get(v, {}).get("value_sets", {})
        mismatch = []
        for key, value_set in value_sets.items():
            m_id = value_set.get("metadata_id")
            if m_id not in xsd_meta or not xsd_meta[m_id]["enumerations"]:
                continue
            expected = set(value_set.get("values", []))
            actual = set(xsd_meta[m_id]["enumerations"])
            if actual != expected:
                mismatch.append({"metadata_id": m_id, "value_set": key,
                                 "xsd_only": sorted(actual - expected),
                                 "dwm_only": sorted(expected - actual),
                                 "status": "qa_open_do_not_change_automatically"})
        docs = []
        for path_doc in sorted((path / "spesifikasjoner").iterdir()):
            if path_doc.is_file() and path_doc.suffix.lower() in {".pdf", ".docx", ".xlsx", ".xml"}:
                docs.append(document_inventory(path_doc, sources))
        report["versions"][v] = {
            "status": "inspected",
            "xsd": xsd_inventory,
            "xsd_declared_metadata_count": len(xsd_meta),
            "dwm_metadata_register_count": len(registered),
            "dwm_requirement_register_count": len(req_registry["requirements"]),
            "xpath_tests_applicable_count": len(version_tests),
            "xpath_tests_needing_version_qa": sum("needs_qa" in str(t.get("version_basis", "")) for t in version_tests),
            "xpath_lexical_field_count": len(links),
            "dwm_schema_validation": "arkivstruktur.xml only in config/noark5/xml_schema_validation.json",
            "value_sets_registered_count": len(value_sets),
            "xsd_value_set_mismatches": mismatch,
            "metadata_crosswalk": {
                m_id: {
                    **rec,
                    "dwm_registered_name": registered.get(m_id, {}).get("name"),
                    "dwm_verification_status": registered.get(m_id, {}).get("verification_status"),
                    "dwm_name_equals_xsd": (registered[m_id].get("name") == rec["xsd_name"]
                                                   if m_id in registered else None),
                    "xpath_lexical_candidates": sorted(set(links.get(m_id, []))),
                    "normative_validation_proven": False,
                } for m_id, rec in sorted(xsd_meta.items())
            },
            "xsd_element_inventories": xsd_elements_by_file,
            "specification_documents": docs,
        }
    if kdrs_root is not None:
        for fn in KDRS_FILES:
            a = kdrs_root / "doc" / fn
            b = dwm_root / "docs" / "reference" / "kdrs-query" / fn
            report["kdrs_reference_matches"].append({
                "filename": fn, "source_found": a.is_file(), "dwm_found": b.is_file(),
                "same_sha256": _sha(a.read_bytes()) == _sha(b.read_bytes())
                if a.is_file() and b.is_file() else None,
            })
    return report


def markdown_report(report: dict) -> str:
    lines = ["# Noark 5 – kildeførst-maskinkartlegging", "",
             "Dette er en reproducerbar teknisk kartlegging mot **IKAMR/digital-archive-workflow**.",
             "XSD-definisjoner og teksthenvisninger er ikke i seg selv attestasjon av kravoppfyllelse.",
             "", f"Kildecommit: `{report['reference_source_commit'] or 'ikke tilgjengelig'}`",
             f"DWM-commit: `{report['dwm_source_commit'] or 'ikke tilgjengelig'}`", "",
             "| Versjon | XSD | M-typer i XSD | M i DWM | Krav i DWM | XPath-kandidater (M) | Uavklarte testversjoner |",
             "| --- | ---: | ---: | ---: | ---: | ---: | ---: |"]
    for v, obj in report["versions"].items():
        if obj["status"] != "inspected":
            lines.append(f"| {v} | - | - | - | - | - | Kilde mangler |")
            continue
        lines.append(f"| {v} | {sum(item.get('status') != 'missing' for item in obj['xsd'])} | {obj['xsd_declared_metadata_count']} | "
                     f"{obj['dwm_metadata_register_count']} | {obj['dwm_requirement_register_count']} | "
                     f"{obj['xpath_lexical_field_count']} | {obj['xpath_tests_needing_version_qa']} |")
    lines += ["", "## Avvik som krever manuell QA", ""]
    for v, obj in report["versions"].items():
        for item in obj.get("xsd_value_set_mismatches", []):
            lines.append(f"- {v} / {item['metadata_id']} / {item['value_set']}: "
                         f"XSD `{item['xsd_only']}`; DWM `{item['dwm_only']}`. "
                         "**Ikke automatisk retting.**")
    lines += ["", "## Kildedokumenter og uttrekksstatus", ""]
    for v, obj in report["versions"].items():
        docs = obj.get("specification_documents", [])
        read = sum(d["extractor"] not in {"not_read_no_pdf_library", "unsupported_format"}
                   and not d["extractor"].startswith(("parse_error", "pdf_parse_error"))
                   for d in docs)
        lines.append(f"- Noark 5 v{v}: {len(docs)} dokument-/eksempelfiler; "
                     f"{read} kunne tekstleses. Manglende/OCR-avhengig tekst gir IKKE verifiserte krav.")
    lines += ["", "## Begrensninger", "", "- Registrerte kilder og en tekstforekomst er ikke en kildeverifisert normativ regel.",
              "- Kartlegging av 5 XSD per versjon betyr ikke at DWM validerer alle 5 XML-typene.",
              "- SHA-256 sammenliknes på faktiske bytes og CRLF-rekonstruksjon; sistnevnte rapporteres særskilt.",
              "- Full kravverifikasjon krever QA av kravtekst/kontekst og en testet implementasjon.",
              "- Eksterne avvik skal forelegges bruker før kilderepoet eller DWM endres.", ""]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    repo = Path(__file__).resolve().parents[1]
    parser.add_argument("--dwm-root", type=Path, default=repo)
    parser.add_argument("--source-root", type=Path, default=repo.parent / "digital-archive-workflow")
    parser.add_argument("--kdrs-root", type=Path, default=repo.parent / "KDRS_Query")
    parser.add_argument("--output-dir", type=Path, required=True,
                        help="Choose an explicit report destination outside Source")
    args = parser.parse_args(argv)
    dst = args.output_dir.resolve()
    protected = [
        (args.source_root.resolve(), "autoritativ Source"),
        (args.dwm_root.resolve(), "DWM-repositoriet"),
    ]
    if args.kdrs_root.is_dir():
        protected.append((args.kdrs_root.resolve(), "KDRS-kildene"))
    for root, label in protected:
        if root == dst or root in dst.parents or dst in root.parents:
            parser.error(f"Resultater skal skrives utenfor {label}")
    report = build_audit(args.dwm_root, args.source_root,
                         args.kdrs_root if args.kdrs_root.is_dir() else None)
    dst.mkdir(parents=True, exist_ok=True)
    js = dst / "noark5-source-audit.json"
    md = dst / "noark5-source-audit.md"
    js.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    md.write_text(markdown_report(report), encoding="utf-8")
    print(f"Rapport: {md}\nSporbar detaljmatrise: {js}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
