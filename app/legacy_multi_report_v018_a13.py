"""Qt-independent bridge for the *existing* a6 multi-extraction report engine.

Unlike the historic CLI/GUI scanner, this adapter receives explicit,
independent Work snapshots and their known report paths. It never reads an
original SIP or relies on a v4 .n5jobs. The legacy renderer, coverage, Arkade
comparisons, evidence and GO/avklaring logic stay authoritative.
"""
from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Iterable
from threading import Event

from app.result_evidence_v018_a13 import WorkSnapshot, safe_json


class LegacyExportStopped(Exception):
    """The operator cancelled before a report was published."""


def _check_cancel(cancelled: Event | None):
    if cancelled is not None and cancelled.is_set():
        raise LegacyExportStopped("Eksport avbrutt før publisering.")


def _validated_target(snapshots: tuple[WorkSnapshot, ...], output: Path) -> Path:
    target = output.resolve(strict=False)
    for shot in snapshots:
        jobdef = (safe_json(shot.job.work, "job.json") or {}).get("job") or {}
        for prop in ("source_root", "source_extraction", "archive_root", "output_root"):
            original = jobdef.get(prop)
            if not original:
                continue
            directory = Path(str(original)).resolve(strict=False)
            if target == directory or target.is_relative_to(directory):
                raise ValueError("Samlerapporten kan ikke eksporteres inne i Source eller AIP.")
    return target


def render_legacy_multi(snapshots: Iterable[WorkSnapshot], *, profile="detaljert",
                        layout="single", sections=None, cancelled: Event | None = None):
    """Return (HTML, full JSON export model, optional per-extraction HTML).

    The caller is responsible for choosing/publishing an output destination.
    This intentionally delegates every assessment and coverage calculation
    to tools.noark5_batch_overview_a6 (legacy), not to Qt.
    """
    shots = tuple(snapshots)
    if not shots:
        raise ValueError("Velg minst ett uttrekk.")
    if layout not in ("single", "attachments"):
        raise ValueError("Ukjent rapportstruktur")
    if len({shot.job.job_uid for shot in shots}) != len(shots):
        raise ValueError("Samme Work-jobb er valgt flere ganger.")
    if any(shot.depot is None or shot.results.depot_report_path is None for shot in shots):
        raise ValueError("Alle valgte uttrekk må ha en lesbar depotrapport for den klassiske samlerapporten.")
    from tools.noark5_batch_overview_a6 import (
        extract, build_report_metrics, render, filter_report_html, coverage_rows,
        selected_report_sections, render_extraction_attachment,
    )
    choices = selected_report_sections(profile, sections)
    items = []
    for shot in shots:
        _check_cancel(cancelled)
        item = extract(shot.results.depot_report_path)
        item["job"] = shot.job.job_id
        item["name"] = shot.job.name
        item["extraction"] = str(shot.job.work.parent)
        item["job_uid"] = shot.job.job_uid
        item["work_operations"] = str(shot.job.work)
        item["report_metrics"] = build_report_metrics(item)
        items.append(item)
    stamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    _check_cancel(cancelled)
    html = filter_report_html(render(items, stamp), profile, choices)
    attachments = []
    if layout == "attachments":
        for index, item in enumerate(items, 1):
            filename = f"vedlegg-{index:03d}-{item['job']}.html"
            # The original a6 attachment renderer uses the same presentation
            # filter as its main report. With profile='oversikt' and no optional
            # sections, that filter removes the entire <section class="page">.
            # An attachment must still contain a meaningful extraction summary:
            # preserve the original introductory status/source paragraphs and
            # the existing data-coverage table, without enabling other optional
            # evidence sections or changing the user's main-report profile.
            attachment_profile = "standard" if profile == "oversikt" and not choices else profile
            attachment_sections = {"coverage"} if profile == "oversikt" and not choices else choices
            document = render_extraction_attachment(
                item, stamp, attachment_profile, attachment_sections
            )
            attachments.append({"filename": filename, "job_uid": item["job_uid"],
                                "html": document})
        html = filter_report_html(render(items, stamp), "oversikt", set())
        from html import escape
        links = "<h2>Vedlegg per uttrekk</h2><ol>" + "".join(
            f"<li>{escape(row['job_uid'])}: "
            f"<a href='noark5-uttrekksoversikt-vedlegg/{escape(row['filename'])}'>"
            f"{escape(row['filename'])}</a></li>" for row in attachments) + "</ol>"
        html = html.replace("</body></html>", links + "</body></html>")
    payload = {"generated": stamp, "items": items, "coverage": coverage_rows(items),
               "missing_jobs": [], "attachments": [
                   {"filename": item["filename"], "job_uid": item["job_uid"]}
                   for item in attachments],
               "report_presentation": {"profile": profile, "sections": sorted(choices),
                                       "layout": layout, "engine": "tools.noark5_batch_overview_a6"},
               "principle": "Kun allerede lagrede rapporter fra separate Work-områder; ingen automatisk faglig godkjenning."}
    return html, payload, tuple(attachments)


def write_legacy_multi_report(output: str | Path, snapshots: Iterable[WorkSnapshot],
                              *, prefix: str = "", profile: str = "detaljert",
                              layout: str = "single", sections=None,
                              overwrite: bool = False,
                              cancelled: Event | None = None) -> tuple[Path, tuple[str, ...]]:
    shots = tuple(snapshots)
    target = _validated_target(shots, Path(output))
    if not target.is_dir():
        raise ValueError("Velg en eksisterende eksportmappe.")
    prefix = str(prefix or "").strip()
    if prefix and (len(prefix) > 100 or prefix in (".", "..") or
                   any(char not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-." for char in prefix)):
        raise ValueError("Ugyldig filnavnprefiks")
    basename = (prefix + "_" if prefix else "") + "noark5-uttrekksoversikt"
    html, model, attachments = render_legacy_multi(shots, profile=profile,
                                                   layout=layout, sections=sections, cancelled=cancelled)
    filenames = [basename + suffix for suffix in (".html", ".json", ".csv")]
    if layout == "attachments":
        filenames += [basename + "-vedlegg/" + item["filename"] for item in attachments]
    collisions = [name for name in filenames if (target / name).exists()]
    if collisions and not overwrite:
        raise FileExistsError("Rapportfiler finnes allerede: " + ", ".join(collisions[:8]))
    _check_cancel(cancelled)
    html = html.replace("noark5-uttrekksoversikt-vedlegg/", basename + "-vedlegg/")
    output_html = target / filenames[0]
    warnings = []
    # Staging is local and temporary. No source or Work data is rewritten.
    with TemporaryDirectory(prefix=".dwm-a13-overview-", dir=target) as tmp:
        staging = Path(tmp)
        (staging / filenames[0]).write_text(html, encoding="utf-8")
        (staging / filenames[1]).write_text(json.dumps(model, ensure_ascii=False, indent=2, default=str) + "\n",
                                          encoding="utf-8")
        with (staging / filenames[2]).open("w", encoding="utf-8-sig", newline="") as fh:
            writer = csv.writer(fh, delimiter=";")
            from tools.noark5_batch_overview_a6 import METRICS
            writer.writerow(["Jobb", "Uttrekk", "Varig Work-jobb-ID"] + [label for _, label in METRICS]
                            + [label + " – kilde" for _, label in METRICS]
                            + ["Teknisk status", "Avvik", "Vurdering"])
            for item in model["items"]:
                writer.writerow([item["job"], item["name"], item["job_uid"]] +
                                [item["report_metrics"][key]["value"] if item["report_metrics"][key]["value"] is not None
                                 else "" for key, _ in METRICS] +
                                [item["report_metrics"][key]["source"] for key, _ in METRICS] +
                                [item["technical_status"], item["deviation_count"], item["assessment_status"]])
        for item in attachments:
            dest = staging / (basename + "-vedlegg") / item["filename"]
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(item["html"], encoding="utf-8")
        # Guard concurrent outputs; never replace an existing file unless the
        # operator explicitly authorized overwrite.
        _check_cancel(cancelled)
        if not overwrite and any((target / name).exists() for name in filenames):
            raise FileExistsError("Rapportfiler ble opprettet av en annen prosess under eksporten")
        for name in filenames:
            dest = target / name
            dest.parent.mkdir(parents=True, exist_ok=True)
            (staging / name).replace(dest)
    # PDF uses the same established conversion as the a6 report engine. A
    # failed optional PDF never masquerades as a newly produced PDF.
    pdf = target / (basename + ".pdf")
    if pdf.exists() and not overwrite:
        warnings.append("PDF finnes allerede og ble ikke erstattet.")
    else:
        try:
            from tools.report_outputs import html_to_pdf
            if pdf.exists():
                pdf.unlink()
            html_to_pdf(output_html, pdf)
        except (OSError, ValueError, RuntimeError, ModuleNotFoundError) as exc:
            pdf.unlink(missing_ok=True)
            warnings.append("PDF ikke laget: " + str(exc))
    return output_html, tuple(warnings)
