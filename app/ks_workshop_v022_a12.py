"""Workshop-oriented UI projection of the existing a3/a13 Noark 5 KS records.

No extra validator, no second assessment ledger and NO automatic approval.
Only reads from a selected Work directory. Saves via the established append-only
review/manual-finding API; delegates package export to the established a3 API.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
from html import escape
import json
import os
from pathlib import Path, PureWindowsPath
import shutil
import tempfile
from typing import Any, Iterable


SECTIONS = (
    ("summary", "Oppsummering og beslutningsutkast"),
    ("findings", "Funn med faglige vurderinger"),
    ("parts", "Arkivdeler og perioder"),
    ("tests", "Tekniske tester"),
    ("sources", "Kilder og evidensreferanser"),
)
SECTION_IDS = frozenset(k for k, _ in SECTIONS)
RECOMMENDATIONS = {
    "pending": "Ingen innstilling registrert",
    "clarify": "Krever videre avklaring",
    "accept": "Foreslås godkjent (ikke vedtak)",
    "conditional": "Foreslås godkjent med merknader (ikke vedtak)",
    "followup": "Krever oppfølging/korrigert uttrekk",
    "reject": "Foreslås ikke godkjent (ikke vedtak)",
}
MAX_JSON = 24 * 1024 * 1024
MAX_DISPLAY_ROWS = 4000


class WorkshopError(ValueError):
    """Work-binding, selection, or report-generation error."""


@dataclass(frozen=True)
class ReviewActor:
    """Adapt the existing DWM per-user profile to legacy a13's author contract."""
    user_id: str
    display_name: str
    username: str
    email: str

    def as_dict(self) -> dict[str, str]:
        return {"user_id": self.user_id, "display_name": self.display_name,
                "username": self.username, "email": self.email}


def actor_from_profile(profile: Any) -> ReviewActor:
    if (profile is None or not getattr(profile, "user_id", "")
            or not getattr(profile, "is_complete", False)):
        raise WorkshopError("En fullstendig registrert DWM-brukerprofil kreves for faglig vurdering")
    return ReviewActor(str(profile.user_id), str(profile.name),
                       str(profile.username), str(profile.email))


def _work_root(work: str | Path) -> Path:
    root = Path(work).resolve(strict=True)
    if not root.is_dir() or not (root / "job.json").is_file():
        raise WorkshopError("Velg en eksisterende Work-mappe med job.json")
    if (root / "job.json").is_symlink():
        raise WorkshopError("Work-jobbidentiteten kan ikke være en symbolsk lenke")
    return root


def work_file(work: str | Path, relative: str) -> Path:
    """Confine evidence links to regular files in selected Work; never Source."""
    root = _work_root(work)
    raw = str(relative or "").replace("\\", "/")
    parts = raw.split("/")
    if (not raw or raw.startswith("/") or PureWindowsPath(raw).drive
            or any(p in ("", ".", "..") for p in parts)):
        raise WorkshopError("Ugyldig eller absolutt evidensreferanse")
    item = root
    for name in parts:
        item = item / name
        if item.is_symlink():
            raise WorkshopError("Symbolske lenker er ikke tillatt i evidensstien")
    if not item.is_file() or not item.resolve(strict=True).is_relative_to(root):
        raise WorkshopError("Evidensfilen mangler eller ligger utenfor Work")
    return item


def _load_json(work: str | Path, relative: str, *, max_bytes: int = MAX_JSON) -> dict:
    path = work_file(work, relative)
    if path.stat().st_size > max_bytes:
        raise WorkshopError("Evidensfil overskrider sikker lesestørrelse: " + relative)
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise WorkshopError("Ugyldig evidens-JSON: " + relative) from exc
    if not isinstance(data, dict):
        raise WorkshopError("Evidens-JSON skal være et objekt: " + relative)
    return data


def _bounded_glob(work: Path, pattern: str, limit: int = 24) -> tuple[str, ...]:
    matches = sorted(work.glob(pattern))
    if len(matches) > limit:
        raise WorkshopError("For mange resultatfiler; gjør søket mer spesifikt")
    result = []
    for path in matches:
        rel = path.relative_to(work).as_posix()
        if path.is_file() and not path.is_symlink():
            # Explicit work_file also checks parent components for symlinks.
            work_file(work, rel)
            result.append(rel)
    return tuple(result)


def build_workspace(work: str | Path) -> dict:
    """Never reconstruct source findings; reuse the established bound snapshot."""
    root = _work_root(work)
    from noark5_workflow.reporting.qa_workflow_v022_a3 import build_review_snapshot_v022_a3
    snapshot = build_review_snapshot_v022_a3(work=root)
    identity = snapshot.get("work_identity") or {}
    job = _load_json(root, "job.json")
    if (str(identity.get("job_uid") or "") != str(job.get("job_uid") or "")
            or snapshot.get("model_id") != "ikamr.dwm.noark5.qa-decision.a12.v1"):
        raise WorkshopError("KS-grunnlaget er ikke bundet til valgt Work-jobb")
    return snapshot


def findings_with_reviews(work: str | Path, snapshot: dict) -> tuple[dict, ...]:
    from noark5_workflow.reporting.qa_review_v021_a13 import finding_key, latest_reviews
    reviews = latest_reviews(work, snapshot)["current"]
    result = []
    for finding in snapshot.get("findings") or ():
        key = finding_key(finding)
        event = reviews.get(key)
        row = dict(finding)
        row["finding_key"] = key
        row["review_status"] = str(event.get("status") or "") if event else ""
        row["review_comment"] = str(event.get("comment") or "") if event else ""
        row["include_in_ks"] = bool(event.get("include_in_ks")) if event else True
        row["include_in_depot"] = bool(event.get("include_in_depot")) if event else True
        row["reviewed_by"] = str((event.get("author") or {}).get("display_name") or "") if event else ""
        result.append(row)
    return tuple(result)


def filter_findings(rows: Iterable[dict], *, severity: str = "", source: str = "",
                    review: str = "", search: str = "") -> tuple[dict, ...]:
    query = search.strip().casefold()
    selected = []
    for row in rows:
        if severity and str(row.get("severity", "")).upper() != severity.upper():
            continue
        if source and str(row.get("source") or "") != source:
            continue
        if review == "pending" and row.get("review_status"):
            continue
        if review == "reviewed" and not row.get("review_status"):
            continue
        haystack = " ".join(str(row.get(k) or "") for k in
                            ("source", "test_id", "severity", "message", "context",
                             "file", "review_comment", "review_status"))
        if query and query not in haystack.casefold():
            continue
        selected.append(row)
    return tuple(selected)


def save_review(work: str | Path, snapshot: dict, finding: dict, *,
                status: str, comment: str, user: ReviewActor,
                include_in_ks: bool = True, include_in_depot: bool = True) -> dict:
    from noark5_workflow.reporting.qa_review_v021_a13 import record_review
    return record_review(work, snapshot, finding, status=status, comment=comment,
                         user=user, include_in_ks=include_in_ks,
                         include_in_depot=include_in_depot)


def save_observation(work: str | Path, snapshot: dict, *,
                     severity: str, message: str, context: str,
                     user: ReviewActor, file: str = "") -> dict:
    from noark5_workflow.reporting.qa_workflow_v022_a3 import record_manual_finding
    return record_manual_finding(work, snapshot, severity=severity, message=message,
                                 context=context, file=file, user=user)


def _test_row(engine: str, test_id: str, name: str, state: str,
              relative: str, note: str = "") -> dict:
    return {"engine": engine, "test_id": str(test_id), "name": str(name),
            "status": str(state), "source_ref": str(relative), "note": str(note)}


def technical_tests(work: str | Path, snapshot: dict | None = None) -> tuple[dict, ...]:
    """Read real persisted tests from this Work, without rerunning any engine.

    Existing QA findings remain authoritative. These are browsing rows only;
    a single file-format observation is NOT a new Noark compliance test.
    """
    root = _work_root(work)
    canonical = root / "noark5_evidence/canonical-results.json"
    data = (_load_json(root, "noark5_evidence/canonical-results.json")
            if canonical.is_file() else {"sources": []})
    job_uid = str(_load_json(root, "job.json").get("job_uid") or "")
    if canonical.is_file() and (
            data.get("model_id") != "noark5.canonical-results.v1" or
            str((data.get("extraction") or {}).get("stable_id") or "") != job_uid):
        raise WorkshopError("Kanoniske testresultater gjelder en annen jobb")
    rows: list[dict] = []
    for src in data.get("sources") or ():
        if not isinstance(src, dict) or src.get("source_kind") != "dwm_master":
            continue
        ref = src.get("reference") or {}
        relative = str(ref.get("work_relative_path") or "")
        path = work_file(root, relative)
        if path.stat().st_size > MAX_JSON:
            raise WorkshopError("DWM-masterfilen er for stor til sikker lesing")
        expected = str(ref.get("sha256") or "")
        if not expected or sha256(path.read_bytes()).hexdigest() != expected:
            raise WorkshopError("SHA-256 stemmer ikke for DWM-masterresultatet")
        master = _load_json(root, relative)
        for t in master.get("tests") or ():
            if not isinstance(t, dict):
                continue
            name = str(t.get("name") or t.get("test_id") or "Ukjent")
            rows.append(_test_row("DWM XPath", t.get("test_id"), name,
                                  t.get("status") or t.get("availability") or "ukjent",
                                  relative, str(t.get("test_point") or "")))
    for relative in _bounded_glob(root, "noark5_tests/xpath_regression/*/index.json"):
        index = _load_json(root, relative)
        folder = Path(relative).parent
        definitions_rel = (folder / "definitions.json").as_posix()
        try:
            definitions = _load_json(root, definitions_rel)
        except (OSError, WorkshopError):
            definitions = {"tests": []}
        names = {str(t.get("test_id")): str(t.get("name") or t.get("test_id"))
                 for t in definitions.get("tests") or () if isinstance(t, dict)}
        for t in index.get("tests") or ():
            if not isinstance(t, dict):
                continue
            ident = str(t.get("test_id") or "")
            result_rel = relative
            if t.get("file"):
                suggestion = (folder / str(t["file"])).as_posix()
                try:
                    work_file(root, suggestion)
                    result_rel = suggestion
                except (OSError, WorkshopError):
                    pass
            rows.append(_test_row("DWM XPath-regresjon", ident,
                                  names.get(ident) or ident,
                                  t.get("status") or "ukjent",
                                  result_rel, str(t.get("test_point") or "")))
    # The native U1 and archive-part projections are output artifacts, not
    # individual microtests: represent them as reports, not invented PASSes.
    for pattern, ident, label in (
        ("noark5_tests/native/noark5-u1-total.json", "native.u1", "Samlede U1-kontroller"),
        ("noark5_tests/native/noark5-analysis-arkiv-arkivdel.json", "native.archive", "Arkiv- og arkivdelanalyse"),
    ):
        for relative in _bounded_glob(root, pattern):
            rows.append(_test_row("DWM native", ident, label, "Rapportert", relative,
                                  "Se individuelle verdier i resultatfilen"))
    arkade = _bounded_glob(root, "arkade5_v*/noark5/arkade-testrapporter_*/*-testrapport*.json")
    for relative in arkade:
        report = _load_json(root, relative)
        for t in report.get("TestsResults") or ():
            if not isinstance(t, dict):
                continue
            count = t.get("NumberOfErrors")
            errors = int(count) if str(count).isdigit() else None
            status = ("FEIL" if errors else "OK" if errors == 0 else "Ukjent")
            rows.append(_test_row("Arkade 5 Noark", t.get("TestId"),
                                  t.get("TestName") or t.get("TestId"), status,
                                  relative, (str(errors) + " rapporterte feil")
                                  if errors is not None else "Antall feil ikke oppgitt"))
    for relative in _bounded_glob(root, "noark5_tests/schema/*/xml-validation-arkivstruktur.json"):
        doc = _load_json(root, relative)
        rows.append(_test_row("DWM XML/XSD", "xml.xsd", "Valider arkivstruktur.xml",
                              "OK" if doc.get("valid") is True else
                              "FEIL" if doc.get("valid") is False else "Ukjent",
                              relative, str(len(doc.get("errors") or [])) + " XSD-funn"))
    # Additional source families are linked as summaries, never silently
    # promoted to a pass/fail verdict for individual microtests.
    for relative in _bounded_glob(root, "external_evidence/siegfried/*/pronom_statistics.json"):
        doc = _load_json(root, relative)
        rows.append(_test_row("Siegfried PRONOM", "pronom.statistics",
                              "Filformatidentifikasjon (statistikk)", "Rapportert",
                              relative, "Detaljer i kildefilen"))
    for relative in _bounded_glob(root, "arkade5_v*/pronom/filformatinfo-statistikk.csv"):
        rows.append(_test_row("Arkade 5 PRONOM", "pronom.statistics",
                              "Filformatidentifikasjon (statistikk)", "Rapportert",
                              relative, "Detaljer i kildefilen"))
    if len(rows) > MAX_DISPLAY_ROWS:
        raise WorkshopError("For mange tekniske tester til én visning")
    return tuple(rows)


def source_catalog(work: str | Path, snapshot: dict) -> tuple[dict, ...]:
    root = _work_root(work)
    result: list[dict] = []
    seen: set[str] = set()
    for e in snapshot.get("evidence_manifest") or ():
        raw = str(e.get("path") or "")
        if raw in seen:
            continue
        seen.add(raw)
        try:
            file = work_file(root, raw)
        except (OSError, WorkshopError):
            result.append({"type": str(e.get("kind") or ""), "path": raw,
                           "sha256": str(e.get("sha256") or ""),
                           "exists": False, "integrity": "Mangler / utilgjengelig"})
        else:
            expected = str(e.get("sha256") or "").lower()
            if len(expected) == 64 and all(c in "0123456789abcdef" for c in expected):
                # Hash the same Work-local file represented by the manifest.
                actual = sha256(file.read_bytes()).hexdigest()
                integrity = "SHA-256 OK" if actual == expected else "ENDRET – SHA-256 AVVIK"
            else:
                integrity = "Ikke kontrollert / ingen SHA"
            result.append({"type": str(e.get("kind") or ""), "path": raw,
                           "sha256": str(e.get("sha256") or ""),
                           "exists": True, "integrity": integrity})
    for relative in ("noark5_evidence/qa-basis-draft.json",
                     "noark5_evidence/evidence-audit.json",
                     "noark5_evidence/canonical-results.json"):
        if relative in seen:
            continue
        try:
            file = work_file(root, relative)
        except (OSError, WorkshopError):
            continue
        result.append({"type": "Work KS/evidens", "path": relative,
                       "sha256": sha256(file.read_bytes()).hexdigest(), "exists": True,
                       "integrity": "Lokal hash – ikke i manifest"})
    return tuple(result)


def _h(value: Any) -> str:
    return escape(str(value if value is not None else ""), quote=True)


def _table(headers: tuple[str, ...], rows: Iterable[tuple[Any, ...]], *, empty: str) -> str:
    body = "".join("<tr>" + "".join("<td>" + _h(v) + "</td>" for v in row) + "</tr>" for row in rows)
    if not body:
        body = '<tr><td colspan="' + str(len(headers)) + '">' + _h(empty) + "</td></tr>"
    return "<table><thead><tr>" + "".join("<th>"+_h(c)+"</th>" for c in headers) + "</tr></thead><tbody>" + body + "</tbody></table>"


def render_preview(snapshot: dict, review_rows: Iterable[dict], tests: Iterable[dict],
                   sources: Iterable[dict], *, sections: Iterable[str],
                   recommendation: str = "pending", recommendation_note: str = "") -> str:
    """Printable report-preview; presentation selection NEVER deletes findings."""
    wanted = frozenset(sections) & SECTION_IDS
    if not wanted:
        raise WorkshopError("Velg minst én seksjon til rapportutkastet")
    if recommendation not in RECOMMENDATIONS:
        raise WorkshopError("Ukjent forslag til faglig konklusjon")
    findings = tuple(review_rows)
    technical = tuple(tests)
    evidence = tuple(sources)
    ident = snapshot.get("work_identity") or {}
    parts = snapshot.get("archive_parts") or []
    status = {"ERROR": 0, "WARNING": 0, "REVIEW": 0}
    for f in findings:
        level = str(f.get("severity") or "").upper()
        if level in status:
            status[level] += 1
    reviewed = sum(bool(r.get("review_status")) for r in findings)
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    heading = "<header><h1>KS- og godkjenningsrapport – UTKAST</h1><p>" + _h(ident.get("job_id")) + " · " + _h(ident.get("job_name")) + "</p><p>Generert: " + _h(now) + "</p></header>"
    pages = [heading, '<p class="caution"><strong>UTKAST – ingen formell depotgodkjenning.</strong> Teknisk fullført betyr ikke faglig godkjent. Alle originale funn er bevart i rapportpakkens avviksregister.</p>']
    if "summary" in wanted:
        pages += ["<h2>Oppsummering og faglig innstilling</h2>",
                  "<p>Registrerte funn: " + str(len(findings)) + "; vurdert: " + str(reviewed) + "; åpne: " + str(len(findings)-reviewed) +
                  "; feilmarkerte: " + str(status["ERROR"]) + "; advarsler: " + str(status["WARNING"]) + "; vurderingspunkter: " + str(status["REVIEW"]) + ".</p>",
                  "<p><strong>Forslag til beslutning:</strong> " + _h(RECOMMENDATIONS[recommendation]) + "</p>",
                  "<p><strong>Merknad:</strong> " + _h(recommendation_note or "Ikke utfylt") + "</p>"]
    if "findings" in wanted:
        pages += ["<h2>Funn, uklarheter og vurderinger</h2>",
                  _table(("Kilde", "Test", "Alvorlighet", "Funn", "Kontekst", "Vurdering", "Kommentar"),
                         ((f.get("source"), f.get("test_id"), f.get("severity"), f.get("message"),
                           f.get("context"), (f.get("review_status") or "Ikke vurdert")
                          if f.get("include_in_ks", True) else "Vurdert internt – ikke i KS",
                          f.get("review_comment") if f.get("include_in_ks", True) else "")
                          for f in findings), empty="Ingen funn registrert")]
    if "parts" in wanted:
        pages += ["<h2>Arkivdeler og perioder</h2>",
                  _table(("ID", "Arkivdel", "Status", "Start", "Slutt"),
                         ((p.get("system_id") or p.get("id"), p.get("title"), p.get("status"),
                           p.get("period_start") or p.get("archive_period_start_date"),
                           p.get("period_end") or p.get("archive_period_end_date"))
                          for p in parts), empty="Ingen arkivdeler funnet i KS-grunnlaget")]
    if "tests" in wanted:
        pages += ["<h2>Tekniske tester og kildekjøringer</h2>",
                  _table(("Motor", "Test-ID", "Navn", "Status", "Kildenøkkel"),
                         ((t["engine"], t["test_id"], t["name"], t["status"], t["source_ref"])
                          for t in technical), empty="Ingen testresultater tilgjengelig")]
    if "sources" in wanted:
        pages += ["<h2>Evidensreferanser fra Work</h2>",
                  _table(("Kildetype", "Fil i Work", "SHA-256", "Integritet"),
                         ((s.get("type"), s.get("path"), s.get("sha256"), s.get("integrity") or "Ukjent")
                          for s in evidence), empty="Ingen kildereferanser")]
    pages.append("<footer>IKAMR Data Workflow Manager · v0.2.2-a12 · vurderinger er ikke maskintestresultater. Rapporten skal gjennomgås og signeres gjennom organisasjonens formelle rutiner.</footer>")
    style = """<style>body{font:14px/1.5 'Segoe UI',Arial,sans-serif;color:#172434;max-width:1180px;margin:28px auto;padding:0 22px}header{border-bottom:3px solid #1e4f75;padding-bottom:12px}h1{font-size:25px;margin-bottom:4px}h2{margin:28px 0 10px;font-size:19px}table{border-collapse:collapse;width:100%;font-size:12px;word-break:break-word}th,td{border:1px solid #d7e0e8;padding:7px;vertical-align:top;text-align:left}th{background:#eaf1f8}.caution{padding:14px;background:#fff5dc;border-left:4px solid #b9781a}footer{font-size:11px;margin-top:40px;color:#555;border-top:1px solid #ddd;padding-top:12px}@media print{body{margin:12mm;font-size:11pt}table{font-size:8pt;page-break-inside:auto}tr{page-break-inside:avoid}h2{page-break-after:avoid}}</style>"""
    return '<!doctype html><html lang="no"><head><meta charset="utf-8"><title>KS-rapport UTKAST</title>' + style + '</head><body>' + "".join(pages) + '</body></html>'


def export_report(work: str | Path, destination: str | Path, *,
                  sections: Iterable[str], recommendation: str = "pending",
                  recommendation_note: str = "") -> dict:
    """Official a3 export first, then a SHA-labeled optional workshop cover.

    The existing complete issue register cannot be filtered away by section
    choices. Never claim the optional cover is part of the signed a3 manifest.
    """
    from noark5_workflow.reporting.qa_export_v022_a3 import export_review_bundle_v022_a3
    root = _work_root(work)
    snap = build_workspace(root)
    rows = findings_with_reviews(root, snap)
    html_text = render_preview(snap, rows, technical_tests(root, snap),
                               source_catalog(root, snap), sections=sections,
                               recommendation=recommendation,
                               recommendation_note=recommendation_note)
    target = Path(destination)
    # Validate the *final* destination against the same established safety
    # boundary BEFORE any staging folder or file is created.
    from noark5_workflow.reporting.qa_decision_v021_a13 import _safe_destination
    target = target.resolve(strict=False)
    _safe_destination(target, root, _load_json(root, "job.json"), ())
    stage_parent = Path(tempfile.mkdtemp(prefix=".dwm-ks-a12-", dir=target.parent))
    stage_bundle = stage_parent / "rapport"
    published = False
    try:
        result = export_review_bundle_v022_a3(work=root, output_dir=stage_bundle)
        cover = stage_bundle / "workshop-rapport-utkast.html"
        with cover.open("x", encoding="utf-8") as f:
            f.write(html_text)
            f.flush()
            os.fsync(f.fileno())
        meta = {
            "model_id": "dwm.ks-workshop.report-selection.a12.v1",
            "work_job_uid": snap["work_identity"]["job_uid"],
            "report_status": "UTKAST_KREVER_FAGLIG_BESLUTNING",
            "automatic_approval": False,
            "recommendation": recommendation,
            "sections": sorted(frozenset(sections) & SECTION_IDS),
            "workshop_cover": cover.name,
            "cover_sha256": sha256(cover.read_bytes()).hexdigest(),
            "canonical_bundle_manifest": "rapportpakke-manifest.json",
            "canonical_bundle_manifest_sha256": sha256(
                (stage_bundle / "rapportpakke-manifest.json").read_bytes()).hexdigest(),
            "note": "Presentasjonstillegg til original a3-rapportpakke, ikke formell depotgodkjenning",
        }
        with (stage_bundle / "workshop-utvalg.json").open("x", encoding="utf-8") as f:
            f.write(json.dumps(meta, ensure_ascii=False, indent=2) + "\n")
            f.flush()
            os.fsync(f.fileno())
        # Same-volume atomic publication; no report directory is left with
        # half of its evidence if an earlier stage fails.
        stage_bundle.rename(target)
        published = True
        return {**result, "directory": target, "index": target / "index.html",
                "workshop_html": target / cover.name,
                "workshop_metadata": target / "workshop-utvalg.json"}
    finally:
        # Do not remove existing, independently written target directories.
        # Only the private staging directory is ever cleaned up.
        shutil.rmtree(stage_parent, ignore_errors=True)
