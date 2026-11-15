"""v0.2.1-a12: two audience-specific, evidence-bound draft reports.

Read-only adapter over existing Work canonical result, depot validation and
Arkade models, plus an explicitly selected a11 practical KDRS QA package.
No extraction, validator, approval or journal operation is performed here.
"""
from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
from hashlib import sha256
from html import escape
from io import StringIO
import json
import os
from pathlib import Path, PureWindowsPath
import re
import shutil
import sys
import tempfile
from typing import Any

from version import VERSION

MODEL = "ikamr.dwm.noark5.qa-decision.a12.v1"
FILES = (
    "index.html",
    "01-kvalitetssikring-arkivskaper.html",
    "02-depot-godkjenning-ferdigstilling.html",
    "rapportgrunnlag.json",
    "funn.csv",
    "evidensmanifest.json",
)
MAX_JSON = 20 * 1024 * 1024
MAX_DEPO = 24 * 1024 * 1024
MAX_TEXT = 3000
MAX_ISSUES = 300


class ReportInputError(ValueError):
    """Evidence cannot safely be joined into an identified snapshot."""


def _hash(path: Path) -> str:
    h = sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _json(path: Path, limit: int = MAX_JSON) -> dict:
    if not path.is_file() or path.is_symlink() or path.stat().st_size > limit:
        raise ReportInputError("Manglende, for stor eller utrygg rapportfil: " + str(path))
    try:
        doc = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError) as e:
        raise ReportInputError("Ugyldig JSON: " + str(path)) from e
    if not isinstance(doc, dict):
        raise ReportInputError("JSON-roten er ikke et objekt: " + str(path))
    return doc


def _rel(work: Path, relative: str) -> Path:
    """Only relative paths inside Work. Reject symlinked evidence paths."""
    if not isinstance(relative, str) or not relative or "\\" in relative:
        raise ReportInputError("Forventet Work-relativ sti med /: " + str(relative))
    candidate = Path(relative)
    if candidate.is_absolute() or any(part in ("..", ".") for part in candidate.parts):
        raise ReportInputError("Utrygg Work-relativ sti: " + relative)
    actual = work
    for part in candidate.parts:
        actual = actual / part
        if actual.is_symlink():
            raise ReportInputError("Symbolsk lenke i evidenssti: " + relative)
    if not actual.resolve(strict=False).is_relative_to(work.resolve(strict=True)):
        raise ReportInputError("Evidens utenfor valgt Work: " + relative)
    return actual


def _source(work: Path, relative: str, expected_hash: str | None = None,
            *, required: bool = True, limit: int = MAX_JSON) -> dict:
    path = _rel(work, relative)
    if not path.is_file():
        if required:
            raise ReportInputError("Evidensfil mangler: " + relative)
        return {"path": relative, "state": "missing", "sha256": None}
    if path.stat().st_size > limit:
        raise ReportInputError("Evidensfil er for stor: " + relative)
    digest = _hash(path)
    if expected_hash and digest != expected_hash:
        raise ReportInputError("SHA-256-avvik for evidens: " + relative)
    return {"path": relative, "state": "sha256_verified" if expected_hash else "hashed_now",
            "sha256": digest, "bytes": path.stat().st_size}


def _h(value: Any) -> str:
    return escape(str(value if value is not None else "Ikke dokumentert")[:MAX_TEXT], quote=True)


def _count(value: Any) -> int | None:
    return value if type(value) is int and value >= 0 else None


def _number(value: Any) -> str:
    return "Ikke dokumentert" if value is None else str(value)


def _table(headers: tuple[str, ...], rows: list[tuple[Any, ...]], *, empty: str) -> str:
    head = "".join("<th scope='col'>" + _h(x) + "</th>" for x in headers)
    body = "".join("<tr>" + "".join("<td>" + _h(x) + "</td>" for x in row) + "</tr>" for row in rows)
    if not rows:
        body = "<tr><td colspan='" + str(len(headers)) + "'>" + _h(empty) + "</td></tr>"
    return "<div class='table-wrap'><table><thead><tr>" + head + "</tr></thead><tbody>" + body + "</tbody></table></div>"


def _html(title: str, sub: str, body: str, *, status: str = "UTKAST") -> str:
    style = """<style>
@page{size:A4;margin:16mm}*{box-sizing:border-box}body{font:14px/1.52 system-ui,'Segoe UI',Arial,sans-serif;color:#202831;max-width:1110px;margin:30px auto;padding:0 25px;background:#fff}
h1{font-size:25px;line-height:1.2;margin:10px 0 9px;color:#17384a}h2{font-size:18px;margin:27px 0 9px;color:#17384a}h3{font-size:15px;margin:18px 0 8px}
p{margin:8px 0 13px}.overline{font-size:12px;color:#556776;text-transform:uppercase;letter-spacing:1px}.meta{color:#50606c}.draft{border-left:4px solid #a77822;background:#fff7e4;padding:12px 16px;margin:18px 0}
.table-wrap{overflow-x:auto;margin:10px 0 20px}table{width:100%;border-collapse:collapse;font-size:12px}th{background:#ecf1f4;font-weight:650;white-space:nowrap}th,td{padding:8px 9px;vertical-align:top;border-bottom:1px solid #d6e0e4;overflow-wrap:anywhere;text-align:left}
code{font:12px/1.4 Consolas,monospace;overflow-wrap:anywhere}ul,ol{padding-left:24px}li{margin:6px 0}.small{font-size:12px;color:#596a76}.signature{height:35px;border-bottom:1px solid #7a8790;margin:18px 0 7px}
a{color:#12618a}@media print{body{margin:0;padding:0;max-width:none;font-size:11px}.draft{background:none}.table-wrap{overflow:visible}tr{break-inside:avoid}h2{break-after:avoid}a{color:#202831;text-decoration:none}}
</style>"""
    return ("<!doctype html><html lang='no'><head><meta charset='utf-8'>"
            "<meta name='viewport' content='width=device-width,initial-scale=1'>"
            "<title>" + _h(title) + "</title>" + style + "</head><body>"
            "<div class='overline'>IKAMR · Data Workflow Manager " + _h(VERSION) + "</div>"
            "<h1>" + _h(title) + "</h1><p class='meta'>" + _h(sub) + "</p>"
            "<div class='draft'><b>" + _h(status) + "</b> – rapporten er dokumentasjonsgrunnlag, ikke automatisk godkjenning eller journalføring.</div>"
            + body + "</body></html>\n")


def _find_depot(work: Path, supplied: str | None) -> tuple[Path, str]:
    root = work / "noark5_reports" / "depot_validation"
    if supplied:
        path = _rel(work, supplied)
    else:
        if not root.is_dir() or root.is_symlink():
            raise ReportInputError("Ingen depotrapport i valgt Work; bruk --depot-report")
        candidates = []
        for d in root.iterdir():
            if d.is_dir() and not d.is_symlink():
                p = d / "depot_validation_report.json"
                if p.is_file() and not p.is_symlink():
                    candidates.append(p)
        if len(candidates) != 1:
            raise ReportInputError("Forventet nøyaktig én depotrapport (fant " + str(len(candidates)) + "); oppgi --depot-report")
        path = candidates[0]
    rel = path.relative_to(work).as_posix()
    if path.name != "depot_validation_report.json" or "depot_validation" not in path.parts:
        raise ReportInputError("--depot-report må peke til original depot_validation_report.json")
    return path, rel


def _date(value: str | None) -> str:
    if value is None:
        return datetime.now(timezone.utc).isoformat(timespec="seconds")
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as e:
        raise ReportInputError("--at må være ISO-8601 med tidssone") from e
    if dt.tzinfo is None:
        raise ReportInputError("--at mangler tidssone")
    return dt.isoformat(timespec="seconds")


def _parts(depot: dict) -> list[dict]:
    out = []
    seen = set()
    for idx, item in enumerate(depot.get("archive_parts") or [], 1):
        if not isinstance(item, dict):
            raise ReportInputError("Ugyldig arkivdelsrad")
        a = item.get("archive_part") or {}
        sid = str(a.get("system_id") or "")
        if not sid or sid in seen:
            raise ReportInputError("Manglende eller duplisert arkivdel system-ID")
        seen.add(sid)
        out.append({"index": idx, "system_id": sid, "title": str(a.get("title") or "Ikke angitt"),
                    "status": str(a.get("status") or "Ikke angitt"),
                    "document_medium": a.get("document_medium"),
                    "created_date": a.get("created_date"), "closed_date": a.get("closed_date"),
                    "period_start": a.get("archive_period_start_date"),
                    "period_end": a.get("archive_period_end_date"),
                    "folder_count": _count(item.get("folder_count")),
                    "registration_count": _count(item.get("registration_count")),
                    "document_object_count": _count(item.get("document_object_count"))})
    return out


def _external(work: Path, external: dict, manifest: list[dict], selection: str | None) -> dict:
    sources = external.get("sources") or []
    if not isinstance(sources, list):
        raise ReportInputError("Ugyldige eksterne kilder")
    arkade = []
    for src in sources:
        if not isinstance(src, dict):
            continue
        ev = src.get("evidence") or {}
        relative = ev.get("work_relative_path")
        if not relative:
            continue
        declared_hash = ev.get("sha256")
        if not isinstance(declared_hash, str) or not re.fullmatch(r"[a-fA-F0-9]{64}", declared_hash):
            raise ReportInputError("Ekstern evidens mangler kildebelagt SHA-256: " + relative)
        record = _source(work, relative, declared_hash)
        manifest.append({"kind": "external", **record})
        if (src.get("analysis") or {}).get("source_format") == "arkade_normalized_v2":
            arkade.append((relative, src.get("analysis") or {}))
    if selection:
        arkade = [item for item in arkade if item[0] == selection]
        if not arkade:
            raise ReportInputError("Valgt --arkade-evidence er ikke verifisert i kanonisk analyse")
    if len(arkade) > 1:
        raise ReportInputError("Flere Arkade-kjøringer: velg én med --arkade-evidence for å unngå dobbelttelling")
    if not arkade:
        return {"status": "not_available", "source": None, "summary": {}, "findings": [], "test_count": None}
    rel, data = arkade[0]
    results = []
    tests = data.get("records") or []
    if not isinstance(tests, list):
        raise ReportInputError("Ugyldig Arkade-kontrolliste")
    for test in tests:
        if not isinstance(test, dict):
            continue
        severity = str(test.get("reported_status") or "").lower()
        raw = test.get("reported_issues") or []
        if severity not in ("error", "warning") and not raw:
            continue
        for issue in raw if raw else [{}]:
            if not isinstance(issue, dict):
                continue
            typ = issue.get("result_type") or severity
            if str(typ).lower() not in ("error", "warning"):
                continue
            loc = issue.get("location") or {}
            lines = loc.get("line_numbers") or []
            if not isinstance(lines, list):
                lines = []
            results.append({"source": "Arkade 5", "test_id": str(test.get("external_test_id") or "Ukjent"),
                            "severity": str(typ).upper(),
                            "message": str(issue.get("message") or "Arkade rapporterer feil/advarsel uten detaljmelding"),
                            "context": " / ".join(str(x) for x in (issue.get("result_set_path") or [])),
                            "file": str(loc.get("file_name") or "Ikke oppgitt"),
                            "lines": [x for x in lines if type(x) is int and x > 0],
                            "source_ref": rel})
    if len(results) > MAX_ISSUES:
        raise ReportInputError("Flere Arkade-funn enn sikker rapportgrense; velg detaljrapport")
    return {"status": "reported_unverified", "source": rel,
            "summary": data.get("reported_summary") or {}, "test_count": len(tests),
            "findings": results}


def _kdrs(work: Path, depot: dict, qa_path: Path | None, manifest: list[dict]) -> dict:
    if qa_path is None:
        return {"status": "not_selected", "summary": None, "source": None}
    qa_path = Path(qa_path)
    report = _json(qa_path)
    if report.get("report_type") != "noark5_a11_practical_kdrs_qa_not_full_parity":
        raise ReportInputError("Valgt KDRS QA er ikke fra a11 praktisk QA")
    run = (depot.get("evidence") or {}).get("source_xpath_run")
    if not run:
        raise ReportInputError("Depotrapport mangler XPath-kjørereferanse for KDRS-tilknytning")
    # Work might have been relocated; trust the observed run folder basename,
    # not the historical drive letter (or its apparent parent on another PC).
    leaf = PureWindowsPath(str(run)).name
    if not re.fullmatch(r"JOB-[0-9]+__[-A-Za-z0-9]+", leaf):
        raise ReportInputError("Ugyldig XPath-kjøringsidentifikasjon")
    index_rel = "noark5_tests/xpath/" + leaf + "/index.json"
    evidence = _source(work, index_rel, str(report.get("preflight", {}).get("dwm_index_sha256") or ""))
    manifest.append({"kind": "a11_index", **evidence})
    declared = report.get("preflight", {}).get("dwm_index_sha256")
    if not declared or evidence["sha256"] != declared:
        raise ReportInputError("KDRS QA gjelder ikke valgte DWM XPath-indeks")
    summary = report.get("comparison_summary") or {}
    if (not isinstance(summary, dict) or summary.get("rows") is None
            or summary.get("provisional_matches") is None):
        raise ReportInputError("Ugyldig KDRS-sammendrag")
    manifest.append({"kind": "a11_qa", "path": qa_path.name, "sha256": _hash(qa_path),
                     "state": "external_selected_and_hashed", "bytes": qa_path.stat().st_size})
    return {"status": "partial_provisional", "source": qa_path.name,
            "summary": {k: summary.get(k) for k in ("rows", "provisional_matches", "provisional_mismatches", "not_comparable", "by_profile")},
            "historical_execution_attested": bool(report.get("historical_execution_time_xml_sha256_attested", False)),
            "whole_parity_verified": False}


def _assessments(work: Path, depot_path: Path, manifest: list[dict]) -> dict:
    """Version-bound existing human depot assessment is evidence, not a12 approval."""
    rel = depot_path.parent.relative_to(work).as_posix() + "/depot_assessment.json"
    p = _rel(work, rel)
    if not p.exists():
        return {"status": "not_registered", "current": None}
    data = _json(p)
    if (data.get("report") or {}).get("sha256") != _hash(depot_path):
        raise ReportInputError("Depotvurdering gjelder annen versjon av depotrapporten")
    manifest.append({"kind": "existing_depot_assessment", **_source(work, rel)})
    current = data.get("current") or None
    if current is not None and not isinstance(current, dict):
        raise ReportInputError("Ugyldig lagret depotvurdering")
    return {"status": "existing_assessment_read_only" if current else "not_registered", "current": current,
            "history_count": len(data.get("history") or [])}


def _extraction_label(job_props: dict) -> str:
    """Use a recognizable extraction folder, never a generic sip/content leaf.

    This is a label from the saved DWM job path, not a verified archive creator
    or a normalized identity for different deliveries.
    """
    raw = str(job_props.get("source_extraction") or job_props.get("source_root") or "")
    components = PureWindowsPath(raw).parts
    labels = [part for part in components
              if re.fullmatch(r"[0-9]{4}_[0-9]{3}_[A-Za-z0-9][A-Za-z0-9_.-]*", part)]
    if labels:
        return labels[-1]
    name = str(job_props.get("name") or "").strip()
    if name and name.casefold() not in ("content", "sip", "source", "job"):
        return name
    return "Ikke dokumentert"


def build_snapshot(*, work: Path, depot_report: str | None = None,
                   kdrs_qa: Path | None = None, arkade_evidence: str | None = None,
                   created_at: str | None = None) -> dict:
    work = Path(work).resolve(strict=True)
    if not work.is_dir():
        raise ReportInputError("--work må være en DWM-jobbs Work-katalog")
    manifest = []
    job = _json(_rel(work, "job.json"))
    canonical_path = "noark5_evidence/canonical-results.json"
    canonical = _json(_rel(work, canonical_path))
    if job.get("file_type") != "dwm-work-job" or not job.get("job_uid"):
        raise ReportInputError("Mangler kanonisk DWM-jobbidentitet i Work")
    uid = str(job["job_uid"])
    if (canonical.get("model_id") != "noark5.canonical-results.v1"
            or (canonical.get("extraction") or {}).get("stable_id") != uid):
        raise ReportInputError("Kanonisk resultatmodell tilhører annen jobb")
    for path in ("job.json", canonical_path):
        manifest.append({"kind": "work_canonical", **_source(work, path)})
    for source in canonical.get("sources") or []:
        if not isinstance(source, dict) or source.get("source_kind") != "dwm_master":
            continue
        reference = source.get("reference") or {}
        if not reference.get("work_relative_path") or not reference.get("sha256"):
            raise ReportInputError("DWM-master mangler kildeversjonsbinding")
        manifest.append({"kind":"dwm_master", **_source(work, reference["work_relative_path"], reference["sha256"])})
    depot_path, depot_rel = _find_depot(work, depot_report)
    job_id = str((job.get("job") or {}).get("job_id") or "")
    if not job_id or not depot_path.parent.name.startswith(job_id + "__"):
        raise ReportInputError("Depotrapportens jobb-ID samsvarer ikke med Work-jobben")
    masters = [x.get("reference", {}).get("work_relative_path", "")
               for x in (canonical.get("sources") or []) if isinstance(x, dict)
               and x.get("source_kind") == "dwm_master"]
    if masters and not any(depot_path.parent.name in x for x in masters):
        raise ReportInputError("Depotrapport og kanonisk DWM-master gjelder ulike kjøringer")
    depot = _json(depot_path, MAX_DEPO)
    if depot.get("report_type") != "noark5_depot_validation":
        raise ReportInputError("Ikke en DWM-depotvalideringsrapport")
    manifest.append({"kind": "dwm_depot", **_source(work, depot_rel, limit=MAX_DEPO)})
    runref = str((depot.get("evidence") or {}).get("source_xpath_run") or "")
    if runref and PureWindowsPath(runref).name != depot_path.parent.name:
        raise ReportInputError("Depotrapportens XPath-kjøring stemmer ikke med rapportversjonen")
    ext_rel = "noark5_evidence/canonical-external-analysis.json"
    ext_path = _rel(work, ext_rel)
    external = _json(ext_path) if ext_path.is_file() else None
    if external:
        if external.get("extraction_stable_id") != uid:
            raise ReportInputError("Ekstern analyse gjelder annen jobb")
        canonical_ref = external.get("canonical_reference") or {}
        if not canonical_ref.get("sha256"):
            raise ReportInputError("Ekstern analyse mangler versjonsbinding til kanonisk resultat")
        _source(work, canonical_path, canonical_ref.get("sha256"))
        manifest.append({"kind": "external_analysis", **_source(work, ext_rel)})
    arkade = _external(work, external or {"sources": []}, manifest, arkade_evidence)
    if not external and arkade_evidence:
        raise ReportInputError("Ingen kanonisk Arkade-analyse å velge fra")
    parts = _parts(depot)
    counts = {k: _count(v) for k, v in (depot.get("summary") or {}).items()}
    if counts.get("archive_part_count") is not None and counts["archive_part_count"] != len(parts):
        raise ReportInputError("Ulike arkivdelstall i depotrapportens hovedtall og arkivdelstabell")
    audit = _kdrs(work, depot, kdrs_qa, manifest)
    human = _assessments(work, depot_path, manifest)
    technical = depot.get("technical_validation") or {}
    if not isinstance(technical, dict):
        technical = {}
    dwm_deviations = [d for d in depot.get("deviations") or [] if isinstance(d, dict)]
    issues = [{"source": "DWM depotvalidering", "test_id": str(d.get("category") or ""),
               "severity": str(d.get("severity") or "review").upper(),
               "message": str(d.get("summary") or ""), "context": "", "file": "", "lines": [],
               "source_ref": depot_rel, "requires_review": bool(d.get("requires_review"))}
              for d in dwm_deviations]
    issues.extend(dict(i, requires_review=True) for i in arkade["findings"])
    for part in parts:
        if "aktiv" in part["status"].casefold():
            issues.append({"source":"DWM arkivdelstatus", "test_id":"arkivdel.active_period",
                           "severity":"REVIEW", "message":"Arkivdel er oppført med aktiv periode ved levering; be om faglig avklaring, ikke automatisk avvik.",
                           "context":part["title"]+" ("+part["system_id"]+")", "file":"", "lines":[],
                           "source_ref":depot_rel, "requires_review":True})
    # Human evaluations are *not* adopted as corrections to machine findings.
    context_rel = "noark5_evidence/canonical-context.json"
    human_notes = []
    context_path = _rel(work, context_rel)
    if context_path.is_file():
        context = _json(context_path)
        if context.get("extraction_stable_id") != uid:
            raise ReportInputError("Faglig vurderingskontekst gjelder annen jobb")
        cref = context.get("canonical_reference") or {}
        _source(work, canonical_path, cref.get("sha256"))
        manifest.append({"kind": "manual_context", **_source(work, context_rel)})
        for event in context.get("assessments") or []:
            if isinstance(event, dict):
                human_notes.append({k: event.get(k) for k in ("event_id", "test_id", "metadata_id", "decision", "note", "recorded_at", "evidence_verification", "human_verification")})
    archived = canonical.get("extraction") or {}
    job_props = job.get("job") or {}
    if job_props.get("job_uid") and job_props["job_uid"] != uid:
        raise ReportInputError("Motstridende job_uid i jobbdefinisjon")
    return {
        "model_id": MODEL, "created_utc": _date(created_at), "report_status": "DRAFT_REVIEW_REQUIRED",
        "work_identity": {"job_uid": uid, "job_id": str(job_props.get("job_id") or ""),
                          "job_name": str(job_props.get("name") or ""),
                          "extraction_label": _extraction_label(job_props),
                          "canonical_identity_scope": archived.get("identity_scope")},
        "reported_identity": {"system_from_arkade_not_verified": arkade["summary"].get("system_name"),
                              "period_from_arkade_not_verified": arkade["summary"].get("archival_period"),
                              "archive_creators_from_canonical": archived.get("archive_creators"),
                              "archive_owner_from_canonical": archived.get("archive_owner"),
                              "noark_version_from_canonical": archived.get("noark_version")},
        "dwm_summary": counts, "dwm_technical": {"status": technical.get("status"),
                            "summary": technical.get("summary") or {},
                            "reconciliation": technical.get("reconciliation") or {}},
        "archive_parts": parts, "dwm_report_source": depot_rel,
        "arkade": arkade, "kdrs_qa": audit, "human_context_events": human_notes,
        "existing_depot_assessment": human, "findings": issues,
        "review_required": True,
        "acceptance_from_archive_creator_registered": False,
        "depot_formal_decision_registered_by_a12": False,
        "journal_reference_registered_by_a12": False,
        "aip_produced_by_a12": False,
        "evidence_manifest": manifest,
        "limitations": ["DWM ok er ikke normativ Noark-godkjenning.",
                        "Arkade-funn er eksterne observasjoner og endrer ikke DWM-status.",
                        "U1/U2 er ikke full Saxon/lxml-paritet uten separat dokumentasjon.",
                        "Arkivskapers identitet, innhold og proveniens må bekreftes.",
                        "Tidligere faglig vurdering erstatter ikke dokumentert arkivskapersvar, beslutning og journalreferanse."]}


def _report_body(s: dict, *, depot: bool) -> str:
    wi, identity = s["work_identity"], s["reported_identity"]
    d = s["dwm_summary"]
    base = ("<h2>1. Uttrekk og kildeidentitet</h2>"
            "<p><b>Work-jobb:</b> " + _h(wi["job_id"]) + " / " + _h(wi["job_uid"]) +
            "<br><b>Uttrekk (fra DWM-jobbsti, ikke bekreftet):</b> " + _h(wi["extraction_label"]) +
            "<br><b>System (Arkade rapporterer):</b> " + _h(identity["system_from_arkade_not_verified"]) +
            "<br><b>Periode (Arkade rapporterer):</b> " + _h(identity["period_from_arkade_not_verified"]) +
            "<br><b>Noark-versjon (kanonisk kilde):</b> " + _h(identity["noark_version_from_canonical"]) +
            "<br><b>Arkivskaper:</b> " + _h(identity["archive_creators_from_canonical"]) +
            "<br><b>Arkiveier:</b> " + _h(identity["archive_owner_from_canonical"]) + "</p>"
            "<p class='small'>Tomt felt betyr ukjent, aldri 0. System og periode er rapportert av ekstern validator, ikke bekreftet av arkivskaper. DWM-jobbens ID er ikke en verifisert identifikator for kildeuttrekket.</p>")
    metric_labels = (("archive_count", "Arkiv"), ("archive_part_count", "Arkivdeler"),
                     ("classification_system_count", "Klassifikasjonssystemer"),
                     ("class_count", "Klasser"), ("folder_count", "Mapper/saker"),
                     ("registration_count", "Registreringer"), ("journalpost_count", "Journalposter"),
                     ("document_description_count", "Dokumentbeskrivelser"),
                     ("document_object_count", "Dokumentobjekter"))
    base += ("<h2>2. Omfang dokumentert i DWM</h2>" +
             _table(("Måltall", "DWM-observasjon"), [(name, _number(d.get(key))) for key, name in metric_labels], empty="Ingen DWM-tall") +
             "<h3>Arkivdelene</h3>" +
             _table(("Nr.", "Tittel og system-ID", "Status", "Periode opprettet/avsluttet", "Mapper", "Registreringer", "Dokumentobjekter"),
                    [(p["index"], p["title"] + "\n" + p["system_id"], p["status"],
                      str(p["created_date"] or "?")[:10] + " – " + str(p["closed_date"] or "?")[:10],
                      _number(p["folder_count"]), _number(p["registration_count"]), _number(p["document_object_count"]))
                     for p in s["archive_parts"]], empty="Ingen arkivdeler i valgt DWM-rapport"))
    t = s["dwm_technical"]
    a = s["arkade"]
    k = s["kdrs_qa"]
    ksum = k["summary"] or {}
    base += ("<h2>3. Kilder og tekniske kontroller</h2>"
             "<p><b>DWM XPath-kjøring:</b> " + _h(t["status"] or "ikke dokumentert") +
             ", registrert OK: " + _h((t["summary"] or {}).get("ok")) +
             ", interne avvik: " + _h((t["summary"] or {}).get("error")) +
             ". <b>Arkade 5:</b> " + _h(a["summary"].get("number_of_tests_run")) +
             " tester, rapporterte feil: " + _h(a["summary"].get("number_of_errors")) +
             ", advarsler: " + _h(a["summary"].get("number_of_warnings")) +
             ". Dette er separate kilder, ikke en samlet antall godkjente tester.</p>"
             "<p><b>KDRS Query / a11:</b> " +
             ("ikke valgt" if k["status"] == "not_selected" else
              "kartlagte verdier " + _h(ksum.get("rows")) + ", foreløpig like " + _h(ksum.get("provisional_matches")) +
              ", foreløpige avvik " + _h(ksum.get("provisional_mismatches")) +
              ", ikke sammenlignbare " + _h(ksum.get("not_comparable"))) +
             ". KDRS/Saxon-paritet er ikke attestert.</p>")
    ar = s["arkade"]["findings"]
    base += ("<h2>4. Arkade 5 – dokumenterte feil og advarsler</h2>"
             "<p>Disse radene er konkrete kildefunn, ikke depotets egen beslutning. "+_h(len(ar))+" feilmeldings-/advarselsposter vises.</p>"+
             _table(("Test", "Nivå", "Melding", "Arkivdel/kontekst", "Fil og linje"),
                    [(x["test_id"],x["severity"],x["message"],x["context"],
                      x["file"]+": "+", ".join(map(str,x["lines"]))) for x in ar],
                    empty="Ingen rapporterte detaljfeil i valgt Arkade-analyse. Dette er ikke friskmelding."))
    dev = [i for i in s["findings"] if i["source"].startswith("DWM ")]
    base += ("<h2>5. DWM – vurderingspunkter</h2>"+
             _table(("Kategori", "Rapportert nivå", "Beskrivelse", "Krever vurdering"),
                    [(x["test_id"],x["severity"],x["message"],"Ja" if x["requires_review"] else "Nei") for x in dev],
                    empty="Ingen særskilte vurderingspunkter i depotrapporten"))
    notes = s["human_context_events"]
    base += ("<h2>6. Eksisterende faglige merknader</h2>"
             + _table(("Test/metadata", "Registrert vurdering", "Merknad", "Verifisering"),
                      [(str(n.get("test_id") or "")+" / "+str(n.get("metadata_id") or ""),
                        n.get("decision"),n.get("note"),n.get("human_verification")) for n in notes],
                      empty="Ingen registrerte vurderingshendelser i kanonisk kontekst"))
    if not depot:
        base += ("<h2>7. Spørsmål til arkivskaper</h2><ol>"
                 "<li>Bekreft system, arkivskaper/arkiveier, uttrekksomfang, avgrensning og dokumentert proveniens.</li>"
                 "<li>Bekreft arkivperioder og arkivdeler, særlig arkivdel med aktiv status ved levering.</li>"
                 "<li>Gjennomgå N5.15 (saksmappestatus) og N5.22 (journalstatus) med dokumenterte begrunnelser eller rettelser.</li>"
                 "<li>Avklar rapporterte mangler/variasjoner i dokumentkjeden, årstall, metadata og kontrollprofil.</li>"
                 "<li>Bekreft eventuelt korrigert uttrekk, nye kontroller og dokumenterte fil-/sjekksummer.</li></ol>"
                 "<h2>8. Arkivskapers svar – fylles ut utenfor DWM-utkastet</h2>"
                 "<p>Kontaktperson og rolle: _____________________________</p>"
                 "<p>Saks-/journalreferanse: ________________________ Dato: ________________</p>"
                 "<p>Kommentarer og dokumentasjon: ______________________________________________</p>"
                 "<div class='signature'></div><p class='small'>Svar, signatur og aksept er ikke registrert ved å generere denne rapporten.</p>")
    else:
        current = (s["existing_depot_assessment"] or {}).get("current")
        base += ("<h2>7. Beslutningsgrunnlag og åpne krav</h2>"
                 "<p><b>Eksisterende depotvurdering:</b> " +
                 (_h(current.get("status"))+" (eget kildevedtak, må kontrolleres mot rapportversjon)" if current else "ikke registrert") + "</p>"
                 "<ol><li>Arkivskapers dokumenterte svar, bekreftelse og eventuelle rettelser må innhentes og knyttes til journalpost.</li>"
                 "<li>Alle tekniske og faglige avvik må gjennomgås, inkludert aktive arkivdeler og Arkades rapporterte feil.</li>"
                 "<li>Kontrolldekning, gjeldende Noark/XSD-versjon og restavvik må vurderes eksplisitt.</li>"
                 "<li>Beslutning må fattes av autorisert depotansvarlig, med begrunnelse, dato og saks-/journalreferanse.</li>"
                 "<li>Eventuell DIAS AIP-produksjon krever eget dokumentert prosess- og innholdsvalg.</li></ol>"
                 "<h2>8. Depotets beslutningsfelt – ikke utfylt</h2>"
                 "<p>Beslutning (godkjent / med forbehold / retting / avvist): __________________________</p>"
                 "<p>Vilkår, restavvik og begrunnelse: ______________________________________________</p>"
                 "<p>Beslutter og myndighet: ______________________________ Dato: ________________</p>"
                 "<p>Saks-/journalreferanse: ________________________ AIP-referanse (eventuell): __________________</p>"
                 "<div class='signature'></div><p class='small'>Dette HTML-utkastet verken registrerer eller beslutter godkjenning.</p>")
    base += ("<h2>9. Evidens og versjonsbinding</h2>"+
             "<p>Uttrekkets DWM-jobb og depotrapport er bundet gjennom Work og SHA-256."
             " Ekstern Arkade-evidens er kontrollert mot kanonisk filhash."
             " Historiske KDRS-input er ikke attestert med dagens XML-hash alene.</p>"+
             _table(("Kildefamilie", "Work-relativ kilde / valgt fil", "SHA-256", "Tilstand"),
                    [(m["kind"],m["path"],m.get("sha256"),m["state"]) for m in s["evidence_manifest"]],
                    empty="Ingen evidensregistreringer")+
             "<p class='small'>Rapportutkast opprettet UTC: "+_h(s["created_utc"])+". Ingen Source-data eller tidligere DWM-rapporter er endret.</p>")
    return base


def render_reports(snapshot: dict) -> dict[str, str]:
    i = snapshot["work_identity"]
    meta = "Uttrekk: " + str(i["extraction_label"]) + " · DWM jobb " + str(i["job_id"])
    qa_body = _report_body(snapshot, depot=False)
    depot_body = _report_body(snapshot, depot=True)
    if "a13_review_summary" in snapshot:
        # a13 adds only expressly selected professional notes, never approval.
        from .qa_review_v021_a13 import review_html
        qa_body += review_html(snapshot, for_depot=False)
        depot_body += review_html(snapshot, for_depot=True)
    qa = _html("Kvalitetssikringsrapport til arkivskaper", meta, qa_body)
    de = _html("Depotets godkjennings- og ferdigstillingsrapport", meta, depot_body)
    index = _html("Noark 5 – kvalitetssikring og depotvurdering",meta,
                  "<h2>Rapporter</h2><p><a href='01-kvalitetssikring-arkivskaper.html'>1. Kvalitetssikringsrapport til arkivskaper</a></p>"
                  "<p><a href='02-depot-godkjenning-ferdigstilling.html'>2. Depotets godkjennings- og ferdigstillingsrapport</a></p>"
                  "<p>Begge rapporter er utkast. Behandlingsstatus: " + _h(snapshot["report_status"]) + ".</p>"
                  "<p>Strukturert datagrunnlag: <code>rapportgrunnlag.json</code> · Detaljfunn: <code>funn.csv</code></p>")
    return {"index.html":index,"01-kvalitetssikring-arkivskaper.html":qa,
            "02-depot-godkjenning-ferdigstilling.html":de}


def _csv_cell(value: Any) -> Any:
    """Prevent imported messages from becoming Excel formulas on CSV open."""
    if isinstance(value, str) and value and value.lstrip().startswith(("=", "+", "-", "@")):
        return "'" + value
    if isinstance(value, str) and value.startswith(("\t", "\r", "\n")):
        return "'" + value
    return value


def _csv(snapshot: dict) -> bytes:
    buf = StringIO(newline="")
    writer = csv.writer(buf,delimiter=";",lineterminator="\r\n")
    reviewed = "a13_review_summary" in snapshot
    columns = ["Kilde","ID/kategori","Nivå","Krever vurdering","Melding","Arkivdel/kontekst","Kildereferanse","XML-fil","Linjer"]
    if reviewed:
        from .qa_review_v021_a13 import finding_key
        # Unselected notes are not exported. The two recipient selections are
        # explicit and separate; a comment does not change the source status.
        selected = {x["finding_key"]: x for x in snapshot.get("a13_review_rows") or []}
        columns += ["Faglig status", "Valgt til KS", "Valgt til depot", "Valgt faglig kommentar"]
    writer.writerow(columns)
    for finding in snapshot["findings"]:
        cells = [finding["source"],finding["test_id"],finding["severity"],
                 "Ja" if finding.get("requires_review") else "Nei",
                 finding["message"],finding["context"],finding["source_ref"],
                 finding["file"],", ".join(str(x) for x in finding["lines"])]
        if reviewed:
            entry = selected.get(finding_key(finding))
            cells += ([entry["status"], "Ja" if entry["include_in_ks"] else "Nei",
                       "Ja" if entry["include_in_depot"] else "Nei", entry["comment"]]
                      if entry else ["", "", "", ""])
        writer.writerow([_csv_cell(x) for x in cells])
    return ("\ufeff"+buf.getvalue()).encode("utf-8")


def publish(snapshot: dict, directory: str | Path, *, work: str | Path) -> Path:
    out = Path(directory).resolve(strict=False)
    if out.exists():
        raise FileExistsError("Rapportmappen finnes allerede (historikk overskrives aldri): " + str(out))
    work = Path(work).resolve(strict=True)
    # Prevent publishing to Source even if caller passes the historically logged path.
    protected = ("noark5_evidence", "noark5_tests", "noark5_reports/depot_validation",
                 "external_evidence", "preservation_staging", "wf")
    if any(out.is_relative_to(work / rel) for rel in protected):
        raise ReportInputError("Utdata kan ikke skrives i eksisterende evidens- eller testkatalog")
    job = _json(_rel(work, "job.json"))
    for key in ("source_root", "source_extraction", "source_unzipped"):
        raw = (job.get("job") or {}).get(key)
        if isinstance(raw,str) and raw and os.path.isabs(raw):
            source = Path(raw).resolve(strict=False)
            if out == source or out.is_relative_to(source):
                raise ReportInputError("Rapportutdata kan ikke skrives under Source")
    if not out.parent.is_dir() or out.parent.is_symlink():
        raise ReportInputError("Målmappens overordnede katalog må finnes og være en vanlig mappe")
    if out.is_symlink():
        raise ReportInputError("Målmappen er symbolsk lenke")
    stage = Path(tempfile.mkdtemp(prefix=".a12-staging-",dir=out.parent))
    try:
        for name, html in render_reports(snapshot).items():
            (stage/name).write_text(html,encoding="utf-8")
        (stage/"rapportgrunnlag.json").write_text(json.dumps(snapshot,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
        (stage/"funn.csv").write_bytes(_csv(snapshot))
        manifest = {"model_id":MODEL,"job_uid":snapshot["work_identity"]["job_uid"],
                    "source_evidence":snapshot["evidence_manifest"],"published_files":{}}
        for name in FILES:
            if name != "evidensmanifest.json":
                manifest["published_files"][name] = _hash(stage/name)
        (stage/"evidensmanifest.json").write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
        if out.exists():
            raise FileExistsError(str(out))
        stage.rename(out)
    except Exception:
        shutil.rmtree(stage,ignore_errors=True)
        raise
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="DWM a12: to kildebundne Noark 5-rapportutkast uten nye analyser")
    parser.add_argument("--work",required=True,help="Work-rot for nøyaktig én DWM-jobb, med job.json")
    parser.add_argument("--depot-report",help="Work-relativ original depot_validation_report.json; obligatorisk ved flere")
    parser.add_argument("--kdrs-qa",help="Valgfri a11 noark5-a11-practical-qa.json, matches ved SHA mot XPath-index")
    parser.add_argument("--arkade-evidence",help="Valgfri Work-relativ Arkade-fil hvis mer enn én import er koblet")
    parser.add_argument("--output-dir",help="Ny, eksisterer ikke. Omskriver aldri gammel rapport")
    parser.add_argument("--preflight",action="store_true",help="Kontroller og vis oppsummering, uten å skrive")
    parser.add_argument("--at",help=argparse.SUPPRESS)
    args=parser.parse_args(argv)
    try:
        snapshot=build_snapshot(work=Path(args.work),depot_report=args.depot_report,
                                kdrs_qa=Path(args.kdrs_qa) if args.kdrs_qa else None,
                                arkade_evidence=args.arkade_evidence,created_at=args.at)
        info={"status":snapshot["report_status"],"job_uid":snapshot["work_identity"]["job_uid"],
              "parts":len(snapshot["archive_parts"]),"dwm_deviations":sum(x["source"]=="DWM depotvalidering" for x in snapshot["findings"]),
              "arkade_issues":len(snapshot["arkade"]["findings"]),"kdrs":snapshot["kdrs_qa"]["status"],
              "depot_approved_by_a12":False}
        if args.preflight:
            print(json.dumps(info,ensure_ascii=False,indent=2));return 0
        if not args.output_dir:
            parser.error("--output-dir må oppgis hvis --preflight ikke er valgt")
        target=publish(snapshot,args.output_dir,work=args.work)
        print("Opprettet to rapportutkast og seks rapportfiler: "+str(target))
        print(json.dumps(info,ensure_ascii=False,indent=2))
        return 0
    except (ReportInputError, OSError, FileExistsError) as e:
        parser.error(str(e))
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
