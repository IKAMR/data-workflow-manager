"""v0.2.3-a1: read-only, source-bound inspection of stored Arkade 5 findings.

A reported Arkade error can contain source XML line references.  Display those
references *as evidence*, not as invented or re-run tests.  Source XML is read
on demand from the current job's configured Source, never copied into Work.
"""
from __future__ import annotations

from collections import deque
from hashlib import sha256
import json
from pathlib import Path
import re
from typing import Any, Callable

from app.ks_workshop_v022_a12 import WorkshopError, _load_json, _work_root, work_file

MAX_ANCHORS = 12000
MAX_XML_LINE = 20_000_000
MAX_EXCERPT_LINE_BYTES = 256 * 1024
MAX_SCAN_BYTES = 768 * 1024 * 1024
_ARCHIVE_PART = re.compile(r"Arkivdel \(systemID, tittel\):\s*([^,]+),\s*(.*)")
_XML_FIELDS = {
    "N5.15": ("saksstatus", "mappe"),
    "N5.22": ("journalstatus", "registrering"),
    "N5.25": ("dokumentstatus", "dokumentbeskrivelse"),
}


def _check_cancel(cancel: Callable[[], bool] | None) -> None:
    if cancel is not None and cancel():
        raise WorkshopError("XML-inspeksjonen ble avbrutt")


def _evidence_reference(snapshot: dict, relative: str) -> str:
    """The reference must be included in this exact job's QA evidence manifest."""
    candidates = [e for e in snapshot.get("evidence_manifest") or ()
                  if isinstance(e, dict) and e.get("path") == relative]
    if len(candidates) != 1:
        raise WorkshopError("Arkade-kilden er ikke entydig bundet til valgt KS-grunnlag")
    expected = str(candidates[0].get("sha256") or "").lower()
    if len(expected) != 64 or any(c not in "0123456789abcdef" for c in expected):
        raise WorkshopError("Arkade-kilden mangler gyldig SHA-256-binding")
    return expected


def _sha256_file(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as inp:
        for chunk in iter(lambda: inp.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _arkade_source(work: str | Path, snapshot: dict, finding: dict | None,
                   test_id: str | None) -> tuple[str, str]:
    if finding is not None:
        if str(finding.get("source")) != "Arkade 5":
            raise WorkshopError("Forekomstvisning støttes for dokumenterte Arkade 5-funn")
        ident = str(finding.get("test_id") or "").strip()
        relative = str(finding.get("source_ref") or "")
    else:
        ident = str(test_id or "").strip()
        references = {str(f.get("source_ref") or "") for f in snapshot.get("findings") or ()
                      if isinstance(f, dict) and f.get("source") == "Arkade 5"
                      and f.get("test_id") == ident}
        if len(references) != 1:
            raise WorkshopError("Velg et bestemt Arkade-funn med entydig lagret kilde")
        relative = references.pop()
    if (not ident or not relative.startswith("external_evidence/arkade5/")
            or not relative.endswith("/normalized/arkade5_results.json")):
        raise WorkshopError("Ingen verifisert, normalisert Arkade-resultatfil er valgt")
    _evidence_reference(snapshot, relative)
    return ident, relative


def arkade_occurrences(work: str | Path, snapshot: dict,
                       finding: dict | None = None, *, test_id: str | None = None) -> dict:
    """Return individual *documented line references* from one saved Arkade import.

    Do not use total counts as row counts when line-level evidence is absent.
    In that case the result explicitly reports an aggregate-only gap.
    """
    ident, relative = _arkade_source(work, snapshot, finding, test_id)
    path = work_file(work, relative)
    if _sha256_file(path) != _evidence_reference(snapshot, relative):
        raise WorkshopError("Arkade-kilden er endret siden den inngikk i KS-grunnlaget")
    doc = _load_json(work, relative)
    if (doc.get("format_version") != 2 or
            str(doc.get("source_system") or "").casefold() != "arkade 5" or
            not isinstance(doc.get("tests"), list)):
        raise WorkshopError("Ukjent format for normalisert Arkade 5-evidens")
    matched_tests = [t for t in doc["tests"] if isinstance(t, dict) and t.get("test_id") == ident]
    if len(matched_tests) != 1:
        raise WorkshopError("Arkade-testen er ikke entydig i valgt kildefil")
    groups, rows = [], []
    for observation in matched_tests[0].get("results") or ():
        if not isinstance(observation, dict):
            continue
        raw_level = str(observation.get("result_type") or "").casefold()
        if raw_level not in ("error", "warning", "warn", "failed", "failure"):
            continue
        message = str(observation.get("message") or "")
        trail = observation.get("result_set_path") or []
        if not isinstance(trail, list):
            trail = []
        context = " / ".join(str(x) for x in trail)
        level = "WARNING" if raw_level in ("warning", "warn") else "ERROR"
        loc = observation.get("location") or {}
        if not isinstance(loc, dict):
            loc = {}
        raw_lines = loc.get("line_numbers") or []
        if not isinstance(raw_lines, list):
            raw_lines = []
        lines = [n for n in raw_lines if type(n) is int and 0 < n <= MAX_XML_LINE]
        if len(raw_lines) != len(lines) or len(rows) + len(lines) > MAX_ANCHORS:
            raise WorkshopError("Arkade-linjereferanser overskrider kontrollert grense")
        if finding is not None:
            if (str(finding.get("message") or "") != message or
                    str(finding.get("context") or "") != context or
                    str(finding.get("severity") or "").upper() != level):
                continue
            if ("lines" in finding and list(finding.get("lines") or ()) != lines):
                continue
        filename = str(loc.get("file_name") or "")
        part_id, part_title = "", ""
        for segment in trail:
            match = _ARCHIVE_PART.search(str(segment))
            if match:
                part_id, part_title = match.group(1).strip(), match.group(2).strip()
                break
        declared = re.search(r"\bAntall:\s*(\d+)\s*$", message)
        count = int(declared.group(1)) if declared else None
        group = {"message": message, "severity": level, "source_file": filename,
                 "archive_part_id": part_id, "archive_part_title": part_title,
                 "reported_count": count, "anchors": len(lines), "result_set_path": tuple(trail),
                 "aggregate_only": not bool(lines),
                 "count_mismatch": count is not None and count != len(lines)}
        groups.append(group)
        for line in lines:
            rows.append({"test_id": ident, "line": line, "file": filename,
                         "message": message, "severity": level,
                         "archive_part_id": part_id, "archive_part_title": part_title,
                         "source_ref": relative,
                         "group_index": len(groups) - 1})
    if finding is not None and not groups:
        raise WorkshopError("Finner ikke valgt avvik som eksakt observasjon i bevart Arkade-kilde")
    return {"test_id": ident, "source_ref": relative, "source_sha256": _sha256_file(path),
            "groups": tuple(groups), "rows": tuple(rows), "has_only_aggregate": bool(groups) and not rows,
            "finding_scoped": finding is not None}


def resolve_source_xml(work: str | Path, filename: str) -> Path | None:
    """Only current Work job's explicit Source, never scan arbitrary directories."""
    if filename.casefold() != "arkivstruktur.xml":
        return None
    root = _work_root(work)
    job = _load_json(root, "job.json", max_bytes=2 * 1024 * 1024)
    properties = job.get("job") or {}
    if job.get("file_type") != "dwm-work-job" or not isinstance(properties, dict):
        raise WorkshopError("Work-identiteten har ugyldig jobbdefinisjon")
    for key in ("source_extraction", "source_unzipped", "source_root"):
        raw = properties.get(key)
        if not isinstance(raw, str) or not raw.strip():
            continue
        source = Path(raw)
        try:
            if source.is_file() and source.name.casefold() == filename.casefold():
                return source.resolve(strict=True)
            base = source.resolve(strict=True)
            if not base.is_dir():
                continue
            candidate = base / filename
            if (candidate.is_file() and not candidate.is_symlink() and
                    candidate.resolve(strict=True).is_relative_to(base)):
                return candidate
        except (OSError, RuntimeError, ValueError):
            continue
    return None


def _line_excerpt(source: Path, line: int, *, before: int = 12, after: int = 12,
                  cancel: Callable[[], bool] | None = None) -> str:
    """Bounded, read-only stream. Never load the whole XML into memory."""
    previous: deque[tuple[int, str]] = deque(maxlen=before)
    picked: list[tuple[int, str]] = []
    total = 0
    with source.open("rb") as fp:
        for number, raw in enumerate(fp, 1):
            if number % 4096 == 0:
                _check_cancel(cancel)
            total += len(raw)
            if total > MAX_SCAN_BYTES:
                raise WorkshopError("XML-kilden er for stor til denne begrensede linjeinspeksjonen")
            if number > line + after:
                break
            if number < line - before:
                continue
            if len(raw) > MAX_EXCERPT_LINE_BYTES:
                rendered = "[XML-linjen overstiger sikker visningsgrense]"
            else:
                rendered = raw.decode("utf-8-sig", errors="replace").rstrip("\r\n")
            if number < line:
                previous.append((number, rendered))
            else:
                picked.append((number, rendered))
    _check_cancel(cancel)
    if not picked or picked[0][0] != line:
        raise WorkshopError(f"XML-filen har ikke dokumentert linje {line}")
    return "\n".join(("> " if n == line else "  ") + f"{n:>9}: {value}"
                     for n, value in (*previous, *picked))


def _xml_metadata(source: Path, line: int, test_id: str, *,
                  cancel: Callable[[], bool] | None = None) -> dict[str, str]:
    """Resolve object identity/XPath with secure streaming XML events when possible.

    No generic fallback system-ID guesses from a nearby different object.
    """
    field, object_tag = _XML_FIELDS.get(test_id, ("", ""))
    if not field:
        return {}
    from lxml import etree
    frames: list[dict] = []
    found: dict[str, str] = {}
    stream = source.open("rb")
    try:
        context = etree.iterparse(stream, events=("start", "end"),
                                  resolve_entities=False, no_network=True,
                                  load_dtd=False, huge_tree=False)
    except BaseException:
        stream.close()
        raise
    events = 0
    try:
        for event, element in context:
            events += 1
            if events % 8192 == 0:
                _check_cancel(cancel)
            if not isinstance(element.tag, str):
                continue
            tag = etree.QName(element).localname
            lineno = int(element.sourceline or 0)
            if event == "start":
                if lineno > line and found:
                    break
                if frames:
                    siblings = frames[-1]["children"]
                    ordinal = siblings.get(tag, 0) + 1
                    siblings[tag] = ordinal
                else:
                    ordinal = 1
                frames.append({"tag": tag, "ordinal": ordinal, "children": {},
                               "system_id": "", "title": "", "start_line": lineno})
                continue
            if not frames:
                continue
            if tag == "systemID" and len(frames) > 1:
                frames[-2]["system_id"] = (element.text or "").strip()[:500]
            if tag in ("tittel", "mappeID", "offentligTittel") and len(frames) > 1:
                if tag == "tittel":
                    frames[-2]["title"] = (element.text or "").strip()[:500]
            if lineno == line and tag == field and not found:
                ancestors = list(frames)
                obj = next((x for x in reversed(ancestors[:-1]) if x["tag"] == object_tag), None)
                if obj is None:
                    obj = next((x for x in reversed(ancestors[:-1]) if x["tag"] in
                                ("mappe", "registrering", "journalpost", "dokumentbeskrivelse")), None)
                found = {"xpath": "/" + "/".join(
                             f"{f['tag']}[{f['ordinal']}]" for f in ancestors),
                         "element": tag, "xml_value": (element.text or "").strip()[:1000],
                         "object_type": str(obj["tag"] if obj else ""),
                         "system_id": str(obj["system_id"] if obj else ""),
                         "title": str(obj["title"] if obj else "")}
                break
            frames.pop()
            element.clear()
            while element.getprevious() is not None:
                del element.getparent()[0]
            if lineno > line + 2048:
                break
    except etree.XMLSyntaxError as exc:
        raise WorkshopError("Kunne ikke tolke original XML: " + str(exc)) from exc
    finally:
        del context
        stream.close()
    return found


def inspect_xml_line(work: str | Path, row: dict, *,
                     cancel: Callable[[], bool] | None = None) -> dict:
    """On-demand read-only original XML inspection, never on test enumeration."""
    line = row.get("line")
    if type(line) is not int or not 1 <= line <= MAX_XML_LINE:
        raise WorkshopError("Ingen gyldig linje fra bevart Arkade-evidens")
    source = resolve_source_xml(work, str(row.get("file") or ""))
    if source is None:
        return {"available": False, "message":
                "Original arkivstruktur.xml er ikke tilgjengelig på jobbens registrerte Source. "
                "Arkades fil-, arkivdel- og linjereferanse beholdes, men kan ikke "
                "kontrolleres mot XML før Source kobles til.", "line": line}
    excerpt = _line_excerpt(source, line, cancel=cancel)
    try:
        metadata = _xml_metadata(source, line, str(row.get("test_id") or ""), cancel=cancel)
    except WorkshopError as exc:
        if cancel is not None and cancel():
            raise
        metadata = {"xml_parse_note": str(exc)}
    return {"available": True, "source_path": str(source), "line": line,
            "excerpt": excerpt, "metadata": metadata,
            "provenance_note": "XML leses nå fra Source. Arkade-linjereferansen er bevart i Work; "
                               "denne visningen attesterer ikke at Source er byte-identisk "
                               "med filen Arkade opprinnelig undersøkte."}
