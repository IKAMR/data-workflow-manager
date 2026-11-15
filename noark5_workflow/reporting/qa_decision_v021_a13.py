"""v0.2.1-a13: one report export that reuses a12 and the established a20 engine.

This module *orchestrates* existing report writers. It does not reimplement
archive-part diagrams, KDRS/Arkade reports, a20 annexes, or normative rules.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
from html import escape
import json
import os
from pathlib import Path
import shutil
import tempfile
from typing import Any, Callable, Iterable

from .qa_decision_v021_a12 import (
    ReportInputError, _json, build_snapshot, publish as publish_a12,
)
from .qa_review_v021_a13 import latest_reviews, with_selected_reviews

BUNDLE_MODEL = "ikamr.dwm.noark5.qa-decision-bundle.a13.v1"


def build_review_snapshot(*, work: str | Path, depot_report: str | None = None,
                          kdrs_qa: str | Path | None = None,
                          arkade_evidence: str | None = None) -> dict:
    base = build_snapshot(work=Path(work), depot_report=depot_report,
                          kdrs_qa=Path(kdrs_qa) if kdrs_qa else None,
                          arkade_evidence=arkade_evidence)
    return with_selected_reviews(work, base)


def _safe_destination(destination: Path, work: Path, job: dict, jobs: tuple) -> None:
    """Check all target protections before creating even a staging directory."""
    destination = destination.resolve(strict=False)
    work = work.resolve(strict=True)
    if destination.exists():
        raise FileExistsError("Rapportmappen finnes allerede: " + str(destination))
    if not destination.parent.is_dir() or destination.parent.is_symlink():
        raise ReportInputError("Målmappens overordnede katalog må finnes og være en vanlig mappe")
    if destination == work or destination.is_relative_to(work) or work.is_relative_to(destination):
        raise ReportInputError("Rapportmappen må være atskilt fra Work og eksisterende evidens")
    if destination.is_symlink():
        raise ReportInputError("Målmappen kan ikke være symbolsk lenke")
    sources = []
    props = job.get("job") or {}
    for name in ("source_root", "source_extraction", "source_unzipped", "output_root", "archive_root"):
        value = props.get(name)
        if isinstance(value, str) and value.strip():
            sources.append(value)
    for selected in jobs:
        for name in ("active_extraction_root", "archive_root", "output_root"):
            raw = getattr(selected, name, None)
            if raw:
                sources.append(str(raw))
    for raw in sources:
        path = Path(raw)
        if not path.is_absolute():
            continue
        protected = path.resolve(strict=False)
        if destination == protected or destination.is_relative_to(protected):
            raise ReportInputError("Rapportmappen kan ikke ligge under Source eller AIP: " + str(protected))


def _validate_a20_job(jobs: tuple, work: Path, snapshot: dict) -> None:
    if not jobs:
        return
    if len(jobs) != 1:
        raise ReportInputError("a13-eksport gjelder nøyaktig én jobb; bruk a20 for samlerapporter")
    job = jobs[0]
    identity = snapshot["work_identity"]
    if str(getattr(job, "job_id", "")) != identity["job_id"]:
        raise ReportInputError("a20-jobbens lokale ID stemmer ikke med a12-rapportgrunnlaget")
    uid = str(getattr(job, "job_uid", "") or "")
    if uid and uid != identity["job_uid"]:
        raise ReportInputError("a20-jobbens varige identitet stemmer ikke med valgt Work")
    location = (getattr(job, "effective_work_operations", None)
                or getattr(job, "_effective_work_operations", None)
                or getattr(job, "work_operations", None))
    if not location:
        raise ReportInputError("Ingen Work-sti for a20-jobben")
    try:
        same = Path(location).samefile(work)
    except (OSError, ValueError) as exc:
        raise ReportInputError("Kan ikke bekrefte identisk Work for a20 og a12") from exc
    if not same:
        raise ReportInputError("a20-jobben peker på en annen Work-katalog")


def _index(snapshot: dict, *, technical: bool) -> str:
    label = escape(str(snapshot["work_identity"]["extraction_label"]), quote=True)
    other = ("<li><a href='teknisk-detaljrapport/index.html'>Eksisterende DWM a20 Full-rapport "
             "og vedlegg A-D</a></li>" if technical else
             "<li>Eksisterende a20-rapport er ikke eksportert i denne CLI-pakken.</li>")
    return ("<!doctype html><html lang='no'><head><meta charset='utf-8'>"
            "<title>DWM a13 – rapportpakke</title><style>body{font:16px/1.55 "
            "Segoe UI,Arial,sans-serif;max-width:860px;margin:45px auto;padding:0 22px;" 
            "color:#24313c}a{color:#17628b}li{margin:16px 0}h1{color:#17384a}</style>"
            "</head><body><h1>Noark 5 – samlet rapportpakke</h1><p>Uttrekk: " + label +
            "</p><p><b>UTKAST:</b> Ingen arkivskaperaksept eller depotgodkjenning "
            "er registrert av a13. Tekniske kontroller, faglige merknader og "
            "formelle beslutninger er separate.</p><ol>"
            "<li><a href='rapporter/01-kvalitetssikring-arkivskaper.html'>"
            "Kvalitetssikringsrapport til arkivskaper</a></li>"
            "<li><a href='rapporter/02-depot-godkjenning-ferdigstilling.html'>"
            "Depotets godkjennings-/ferdigstillingsutkast</a></li>" + other +
            "</ol><p>Faglige kommentarer som er valgt til rapportering, vises "
            "i de respektive rapportene. Kildegrunnlag og SHA-256 ligger i "
            "<a href='rapporter/evidensmanifest.json'>evidensmanifestet</a>.</p>"
            "</body></html>\n")


def _digest(path: Path) -> str:
    result = sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            result.update(block)
    return result.hexdigest()


def export_review_bundle(*, work: str | Path, output_dir: str | Path,
                         report_jobs: Iterable[Any] = (),
                         depot_report: str | None = None,
                         kdrs_qa: str | Path | None = None,
                         arkade_evidence: str | None = None,
                         a20_formats: tuple[str, ...] = ("html", "json", "csv"),
                         _a20_writer: Callable | None = None) -> dict:
    """All-or-nothing new directory: a12 audience reports plus original a20 Full.

    If report_jobs is empty (CLI), explicitly omit the a20 technical annex;
    the GUI passes the job from the established DWM report API.
    """
    work = Path(work).resolve(strict=True)
    target = Path(output_dir).resolve(strict=False)
    jobs = tuple(report_jobs)
    snapshot = build_review_snapshot(work=work, depot_report=depot_report,
                                     kdrs_qa=kdrs_qa, arkade_evidence=arkade_evidence)
    job = _json(work / "job.json")
    _safe_destination(target, work, job, jobs)
    _validate_a20_job(jobs, work, snapshot)
    formats = tuple(dict.fromkeys(str(fmt).lower() for fmt in a20_formats))
    if not formats or any(fmt not in ("html", "json", "csv", "pdf") for fmt in formats):
        raise ReportInputError("Ukjent a20-eksportformat")
    if "html" not in formats:
        raise ReportInputError("a13 krever HTML for navigering til a20-rapporten")

    stage = Path(tempfile.mkdtemp(prefix=".a13-rapport-", dir=target.parent))
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
                raise ReportInputError("a20-rapportmotoren mangler index.html")
        (stage / "index.html").write_text(_index(snapshot, technical=bool(jobs)), encoding="utf-8")
        file_hashes = {}
        for file in sorted(stage.rglob("*")):
            if file.is_file():
                file_hashes[file.relative_to(stage).as_posix()] = _digest(file)
        manifest = {
            "model_id": BUNDLE_MODEL,
            "work_job_uid": snapshot["work_identity"]["job_uid"],
            "depot_report_source": snapshot["dwm_report_source"],
            "a20_included": bool(jobs),
            "a20_formats": list(formats) if jobs else [],
            "a13_review_summary": snapshot["a13_review_summary"],
            "source_families_separate": True,
            "automatic_approval": False,
            "files": file_hashes,
        }
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
            "reviewed": snapshot["a13_review_summary"]["reviewed_findings"],
            "technical_a20_included": bool(jobs)}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="DWM a13: faglige merknader og KS/depot-utkast, med valgfri a20 GUI-rapport")
    parser.add_argument("--work", required=True)
    parser.add_argument("--depot-report", help="Work-relativ original depot_validation_report.json")
    parser.add_argument("--kdrs-qa", help="Valgfri kildebundet a11 QA JSON")
    parser.add_argument("--arkade-evidence", help="Valgfri Work-relativ Arkade-evidens")
    parser.add_argument("--output-dir", help="Ny, ikke eksisterende målmappe")
    parser.add_argument("--preflight", action="store_true")
    args = parser.parse_args(argv)
    try:
        snapshot = build_snapshot(work=Path(args.work), depot_report=args.depot_report,
                                  kdrs_qa=Path(args.kdrs_qa) if args.kdrs_qa else None,
                                  arkade_evidence=args.arkade_evidence)
        review = latest_reviews(args.work, snapshot)
        info = {"status": "DRAFT_REVIEW_REQUIRED",
                "job_uid": snapshot["work_identity"]["job_uid"],
                "findings": len(snapshot["findings"]),
                "faglig_vurderte": len(review["current"]),
                "eldre_kildeversjoner": review["older_or_changed"],
                "a20_included_via_cli": False,
                "formell_depotgodkjenning": False}
        if args.preflight:
            print(json.dumps(info, ensure_ascii=False, indent=2))
            return 0
        if not args.output_dir:
            parser.error("--output-dir må velges (eller bruk --preflight)")
        result = export_review_bundle(work=args.work, output_dir=args.output_dir,
                                      depot_report=args.depot_report, kdrs_qa=args.kdrs_qa,
                                      arkade_evidence=args.arkade_evidence)
        print("a13-rapportpakke: " + str(result["index"]))
        print(json.dumps(info, ensure_ascii=False, indent=2))
        return 0
    except (ReportInputError, ValueError, OSError, FileExistsError) as exc:
        parser.error(str(exc))
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
