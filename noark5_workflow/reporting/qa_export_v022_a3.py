"""v0.2.2-a3: atomic KS/depot/technical report bundle with an issue register.

Uses the existing a12 recipient renderers and the a20 technical report writer.
Every report is a DRAFT. This module never records a formal depot decision.
"""
from __future__ import annotations

import csv
from hashlib import sha256
from html import escape
from io import StringIO
import json
from pathlib import Path
import shutil
import tempfile
from typing import Any, Iterable

from .qa_decision_v021_a12 import _csv_cell, _json, publish as publish_a12, ReportInputError
from .qa_decision_v021_a13 import _safe_destination, _validate_a20_job
from .qa_review_v021_a13 import finding_key, latest_reviews, STATUSES
from .qa_workflow_v022_a3 import build_review_snapshot_v022_a3, finding_summary

BUNDLE_MODEL = "ikamr.dwm.noark5.qa-decision-bundle.a3.v1"


def _sha(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def register_rows(snapshot: dict, work: str | Path) -> list[dict]:
    """All source observations + source-bound review status, no hidden PASS."""
    all_reviews = latest_reviews(work, snapshot)["current"]
    selected = {e["finding_key"]: e for e in snapshot.get("a13_review_rows") or []}
    result = []
    for finding in snapshot.get("findings") or []:
        key = finding_key(finding)
        latest = all_reviews.get(key)
        shared = selected.get(key)
        result.append({
            "finding_key": key,
            "source": finding["source"],
            "test_id": finding["test_id"],
            "severity": finding["severity"],
            "message": finding["message"],
            "context": finding.get("context") or "",
            "file": finding.get("file") or "",
            "lines": list(finding.get("lines") or []),
            "source_ref": finding.get("source_ref") or "",
            "requires_review": bool(finding.get("requires_review")),
            "professional_status": (
                STATUSES.get(shared["status"], shared["status"]) if shared else
                "Vurdert internt (ikke valgt til eksport)" if latest else "Ikke vurdert"
            ),
            "comment": shared["comment"] if shared else "",
            "include_in_ks": bool(shared and shared["include_in_ks"]),
            "include_in_depot": bool(shared and shared["include_in_depot"]),
            "manual": bool(finding.get("manual_event_id")),
            "automatic_approval": False,
        })
    return result


def _render_register(rows: list[dict], snapshot: dict, summary: dict) -> str:
    identity = snapshot["work_identity"]
    header = (
        "<!doctype html><html lang='no'><head><meta charset='utf-8'>"
        "<title>Avviks- og vurderingsregister – DWM</title>"
        "<style>body{font:15px/1.5 Segoe UI,Arial,sans-serif;max-width:1250px;"
        "margin:32px auto;padding:0 25px;color:#1c2b3a}"
        "table{border-collapse:collapse;width:100%;font-size:13px}"
        "th,td{padding:8px;border:1px solid #d2dce4;vertical-align:top;text-align:left}"
        "th{background:#edf3f9;position:sticky;top:0}tr:nth-child(even){background:#f8fafc}"
        ".scroll{overflow-x:auto}.wrap{overflow-wrap:anywhere}.note{background:#f3f6fb;padding:12px}"
        "</style></head><body><h1>Avviks- og vurderingsregister – UTKAST</h1>"
        "<p><b>Uttrekk:</b> " + escape(str(identity.get("extraction_label") or "Ukjent")) +
        " · <b>Jobb:</b> " + escape(str(identity.get("job_id") or "")) + "</p>"
        "<p class='note'>Dette registeret viser alle funn fra valgt rapportgrunnlag, "
        "inkludert ubehandlede punkter. Teknisk status, historisk RAF-klassifisering "
        "og faglige kommentarer er atskilt. Manuelle observasjoner er ikke "
        "maskinelle testfeil. En kommentar betyr ikke godkjenning. "
        "Kommentarer som ikke er valgt til eksport, gjengis ikke her.</p>"
        "<p><b>Funn:</b> " + str(summary["total"]) + " · <b>Faglig vurdert:</b> " +
        str(summary["reviewed"]) + " · <b>Åpne:</b> " + str(summary["unreviewed"]) +
        " · <b>Feil:</b> " + str(summary["errors"]) + " · <b>Advarsler:</b> " +
        str(summary["warnings"]) + " · <b>Manuelle:</b> " + str(summary["manual"]) + "</p>"
        "<p>Kildegrunnlag: <code>rapporter/rapportgrunnlag.json</code> og "
        "<code>rapporter/evidensmanifest.json</code>. Originale data er uendret.</p>"
        "<div class='scroll'><table><thead><tr><th>Nivå</th><th>Kilde / test</th>"
        "<th>Funn / kontekst</th><th>Kildereferanse</th><th>Faglig status</th>"
        "<th>Kommentar valgt til eksport</th><th>KS</th><th>Depot</th></tr></thead><tbody>"
    )
    html_rows = []
    for row in rows:
        def h(value: Any) -> str:
            return escape(str(value or ""), quote=True)
        evidence = str(row["source_ref"]) + (" · " + str(row["file"]) if row["file"] else "")
        if row["lines"]:
            evidence += " · linjer " + ", ".join(str(n) for n in row["lines"])
        cells = (
            row["severity"], row["source"] + " / " + row["test_id"],
            row["message"] + (" · " + row["context"] if row["context"] else ""),
            evidence, row["professional_status"], row["comment"],
            "Ja" if row["include_in_ks"] else "Nei",
            "Ja" if row["include_in_depot"] else "Nei",
        )
        html_rows.append("<tr>" + "".join("<td class='wrap'>" + h(c) + "</td>" for c in cells) + "</tr>")
    return header + "".join(html_rows) + "</tbody></table></div></body></html>\n"


def _register_csv(rows: list[dict]) -> bytes:
    buffer = StringIO(newline="")
    writer = csv.writer(buffer, delimiter=";", lineterminator="\r\n")
    writer.writerow(("Kilde", "Test-ID", "Nivå", "Funn", "Kontekst", "Kildefil", "Kildereferanse",
                     "Faglig status", "Valgt kommentar", "KS", "Depot"))
    for row in rows:
        cells = (row["source"], row["test_id"], row["severity"], row["message"],
                 row["context"], row["file"], row["source_ref"], row["professional_status"],
                 row["comment"], "Ja" if row["include_in_ks"] else "Nei",
                 "Ja" if row["include_in_depot"] else "Nei")
        writer.writerow([_csv_cell(v) for v in cells])
    return ("\ufeff" + buffer.getvalue()).encode("utf-8")


def _index(snapshot: dict, a20: bool, count: int) -> str:
    label = escape(str(snapshot["work_identity"].get("extraction_label") or "Ukjent"), quote=True)
    links = [
        ("avviksregister.html", "Avviksregister – " + str(count) + " funn og vurderingsstatus"),
        ("rapporter/01-kvalitetssikring-arkivskaper.html", "Kvalitetssikringsrapport til arkivskaper (UTKAST)"),
        ("rapporter/02-depot-godkjenning-ferdigstilling.html", "Godkjennings-/beslutningsrapport til depotet (UTKAST)"),
    ]
    if a20:
        links.append(("teknisk-detaljrapport/index.html", "DWM Full-rapport med vedlegg A–D"))
    return ("<!doctype html><html lang='no'><meta charset='utf-8'>"
            "<title>DWM – KS og godkjenning</title><body style='font:17px/1.6 Segoe UI,Arial,sans-serif;"
            "max-width:860px;margin:45px auto;padding:0 20px'>"
            "<h1>KS, avvik og godkjenning – rapportpakke</h1><p>Uttrekk: " + label +
            "</p><p><strong>UTKAST – INGEN AUTOMATISK GODKJENNING.</strong> "
            "Arkivskapers svar, restavvik, beslutningsmyndighet, dato og journalreferanse "
            "må vurderes og dokumenteres i depotets beslutningsprosess.</p><ol>" +
            "".join("<li><a href='" + escape(path) + "'>" + escape(title) + "</a></li>"
                    for path, title in links) +
            "</ol><p>Originale Work-/Source-filer er uendret. "
            "<a href='rapportpakke-manifest.json'>Manifest og SHA-256</a></p></body></html>\n")


def export_review_bundle_v022_a3(*, work: str | Path, output_dir: str | Path,
                                  report_jobs: Iterable[Any] = (),
                                  depot_report: str | None = None,
                                  kdrs_qa: str | Path | None = None,
                                  arkade_evidence: str | None = None,
                                  a20_formats: tuple[str, ...] = ("html", "json", "csv"),
                                  _a20_writer=None) -> dict:
    """One new, atomically published folder. Never overwrites existing output."""
    work = Path(work).resolve(strict=True)
    target = Path(output_dir).resolve(strict=False)
    jobs = tuple(report_jobs)
    snapshot = build_review_snapshot_v022_a3(
        work=work, depot_report=depot_report, kdrs_qa=kdrs_qa,
        arkade_evidence=arkade_evidence)
    # a8: the legacy HTML/CSV builders enumerate only snapshot["findings"].
    # A bounded preview must NEVER be published as a complete issue register.
    # A260 continues to publish full source-bound CSV/JSONL independently.
    if snapshot.get("findings_complete") is False:
        raise ReportInputError(
            "KS-utkastet inneholder bare en forhåndsvisning av Arkade-funn. "
            "Bruk komplett A260 CSV/JSONL-eksport, eller fullfør sidevis KS-eksport "
            "før publisering. Ingen ufullstendig avviksrapport er skrevet.")
    _safe_destination(target, work, _json(work / "job.json"), jobs)
    _validate_a20_job(jobs, work, snapshot)
    formats = tuple(dict.fromkeys(str(f).lower() for f in a20_formats))
    if "html" not in formats or any(f not in ("html", "json", "csv", "pdf") for f in formats):
        raise ReportInputError("HTML må være valgt; ukjent eksportformat")
    summary = finding_summary(work, snapshot)
    rows = register_rows(snapshot, work)
    stage = Path(tempfile.mkdtemp(prefix=".dwm-a3-", dir=target.parent))
    published = False
    try:
        publish_a12(snapshot, stage / "rapporter", work=work)
        if jobs:
            from .job_summary_a16 import ReportOptions
            from .report_service_a20 import write_report_package
            writer = _a20_writer or write_report_package
            technical = stage / "teknisk-detaljrapport"
            technical.mkdir()
            writer(technical, jobs, ReportOptions("Full", (), True, True),
                   formats=formats, overwrite=False)
            if not (technical / "index.html").is_file():
                raise ReportInputError("Full-rapporten mangler index.html")
        (stage / "avviksregister.html").write_text(_render_register(rows, snapshot, summary), encoding="utf-8")
        (stage / "avviksregister.json").write_text(
            json.dumps({"model_id": "ikamr.dwm.qa-issue-register.a3.v1",
                        "work_job_uid": snapshot["work_identity"]["job_uid"],
                        "depot_source": snapshot["dwm_report_source"],
                        "summary": summary, "findings": rows,
                        "approval": "DRAFT_REVIEW_REQUIRED"},
                       ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        (stage / "avviksregister.csv").write_bytes(_register_csv(rows))
        (stage / "index.html").write_text(_index(snapshot, bool(jobs), len(rows)), encoding="utf-8")
        hashes = {p.relative_to(stage).as_posix(): _sha(p) for p in sorted(stage.rglob("*")) if p.is_file()}
        manifest = {"model_id": BUNDLE_MODEL,
                    "work_job_uid": snapshot["work_identity"]["job_uid"],
                    "depot_report_source": snapshot["dwm_report_source"],
                    "a20_included": bool(jobs), "a20_formats": list(formats) if jobs else [],
                    "finding_summary": summary,
                    "automatic_approval": False,
                    "source_families_separate": True, "files": hashes}
        (stage / "rapportpakke-manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        if target.exists():
            raise FileExistsError("Rapportmappen ble opprettet av en annen prosess")
        stage.rename(target)
        published = True
    finally:
        if not published:
            shutil.rmtree(stage, ignore_errors=True)
    return {"directory": target, "index": target / "index.html", "manifest": manifest,
            "summary": summary, "technical_a20_included": bool(jobs)}
