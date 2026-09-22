from __future__ import annotations

import html
import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable

from app.workspace import run_log_dir


@dataclass(frozen=True)
class ValidationOverviewFiles:
    json_path: Path
    html_path: Path


def _status_text(job) -> str:
    status = getattr(job, "status", "")
    value = getattr(status, "value", None)
    return str(value if value is not None else status)


def _effective_work_operations(job) -> Path | None:
    value = (
        getattr(job, "_effective_work_operations", None)
        or getattr(job, "work_operations", None)
    )
    return Path(value) if value else None


def _read_manifest(path: Path) -> dict | None:
    manifest = path / "artifact_manifest.json"
    if not manifest.is_file():
        return None
    try:
        return json.loads(manifest.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _manifest_matches(path: Path, job, *, run_id: str | None = None) -> bool:
    data = _read_manifest(path)
    if run_id:
        if not data:
            return False
        if str(data.get("run_id", "") or "") != str(run_id):
            return False

    if not data:
        return True

    expected_job = str(getattr(job, "job_id", "") or "")
    actual_job = str(data.get("job_id", "") or "")
    if expected_job and actual_job and expected_job != actual_job:
        return False

    expected_source = str(getattr(job, "active_extraction_root", "") or "")
    actual_source = str(data.get("source_extraction", "") or "")
    return (
        not expected_source
        or not actual_source
        or Path(actual_source) == Path(expected_source)
    )


def latest_depot_report(job, *, run_id: str | None = None) -> tuple[Path, dict] | None:
    work = _effective_work_operations(job)
    if work is None:
        return None

    report_root = work / "noark5_reports" / "depot_validation"
    if not report_root.is_dir():
        return None

    candidates: list[tuple[Path, Path]] = []
    for folder in report_root.iterdir():
        if not folder.is_dir():
            continue
        if not _manifest_matches(folder, job, run_id=run_id):
            continue
        report = folder / "depot_validation_report.json"
        if report.is_file():
            candidates.append((folder, report))

    if not candidates:
        return None

    _, path = max(candidates, key=lambda item: item[0].name)
    try:
        model = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return path, model


def _control_status(model: dict | None) -> tuple[str, str]:
    if not model:
        return "MANGLER", "Ingen depotvalideringsrapport for denne RUN-en."

    technical = model.get("technical_validation") or {}
    technical_status = str(technical.get("status", "") or "")
    deviations = list(model.get("deviations") or [])

    serious = [
        item for item in deviations
        if str(item.get("severity", "")).casefold() == "serious"
    ]
    review = [item for item in deviations if bool(item.get("requires_review"))]

    if technical_status == "error" or serious:
        return "FEIL", "Teknisk feil eller alvorlig avvik krever behandling."
    if review:
        return "VURDER", "Teknisk kjøring er fullført, men vurderingspunkter finnes."
    if technical_status == "ok":
        return "OK", "Ingen automatiske tekniske feil eller vurderingspunkter registrert."
    return "UKJENT", "Rapport finnes, men kontrollstatus kunne ikke klassifiseres."


def _review_findings(model: dict | None) -> tuple[int, int, dict[str, int]]:
    if not model:
        return 0, 0, {}

    deviations = [
        item for item in list(model.get("deviations") or [])
        if bool(item.get("requires_review"))
    ]
    cases = len(deviations)

    technical = model.get("technical_validation") or {}
    tech_summary = technical.get("summary") or {}
    reconciliation = technical.get("reconciliation") or {}
    std = ((model.get("standard_values") or {}).get("summary") or {})
    std_counts = std.get("status_counts") or {}

    breakdown: dict[str, int] = {}
    for item in deviations:
        category = str(item.get("category", "") or "other")
        if category == "additional_observed_values":
            count = int(std_counts.get("additional_observed_values", 0) or 0)
        elif category == "reconciliation_mismatch":
            count = int(reconciliation.get("mismatch", 0) or 0)
        elif category == "technical_error":
            count = int(tech_summary.get("error", 0) or 0)
        else:
            count = 1
        breakdown[category] = max(1, count)

    return cases, sum(breakdown.values()), breakdown


def _summary_value(model: dict | None, key: str) -> int | None:
    value = ((model or {}).get("summary") or {}).get(key)
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _job_row(job, *, run_id: str) -> dict:
    found = latest_depot_report(job, run_id=run_id)
    report_path = found[0] if found else None
    model = found[1] if found else None
    control_status, control_message = _control_status(model)

    technical = (model or {}).get("technical_validation") or {}
    tech_summary = technical.get("summary") or {}
    reconciliation = technical.get("reconciliation") or {}
    assessment = (model or {}).get("assessment") or {}

    review_cases, review_findings, review_breakdown = _review_findings(model)

    html_report = (
        report_path.with_name("depot_validation_report.html")
        if report_path is not None
        else None
    )
    if html_report is not None and not html_report.is_file():
        html_report = None

    return {
        "job_id": str(getattr(job, "job_id", "") or ""),
        "name": str(getattr(job, "name", "") or ""),
        "profile_id": str(getattr(job, "profile_id", "") or ""),
        "job_status": _status_text(job),
        "source_extraction": str(getattr(job, "active_extraction_root", "") or ""),
        "work_operations_effective": str(_effective_work_operations(job) or ""),
        "control_status": control_status,
        "control_message": control_message,
        "technical_status": str(technical.get("status", "") or ""),
        "tests_ok": int(tech_summary.get("ok", 0) or 0),
        "tests_error": int(tech_summary.get("error", 0) or 0),
        "tests_legacy_disabled": int(tech_summary.get("legacy_disabled", 0) or 0),
        "tests_other": int(tech_summary.get("other", 0) or 0),
        "reconciliation_mismatch": int(reconciliation.get("mismatch", 0) or 0),
        "review_cases": review_cases,
        "review_findings": review_findings,
        "review_findings_breakdown": review_breakdown,
        "review_points": review_cases,
        "assessment_status": str(assessment.get("status", "") or ""),
        "archive_part_count": _summary_value(model, "archive_part_count"),
        "folder_count": _summary_value(model, "folder_count"),
        "registration_count": _summary_value(model, "registration_count"),
        "document_description_count": _summary_value(model, "document_description_count"),
        "document_object_count": _summary_value(model, "document_object_count"),
        "report_json": str(report_path or ""),
        "report_html": str(html_report or ""),
    }


def build_validation_overview(
    jobs: Iterable,
    *,
    run_id: str,
    job_list_path: str | Path | None,
    app_version: str,
) -> dict:
    rows = [_job_row(job, run_id=run_id) for job in jobs]
    counts = {
        key: sum(row["control_status"] == key for row in rows)
        for key in ("OK", "VURDER", "FEIL", "MANGLER", "UKJENT")
    }

    return {
        "format_version": 2,
        "report_type": "noark5_batch_validation_overview",
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "run_id": str(run_id or ""),
        "app_version": str(app_version),
        "job_list_path": str(job_list_path or ""),
        "principle": (
            "Oversikten bruker kun depotvalideringsrapporter som kan knyttes til "
            "denne eksakte RUN-en. Den kjører ingen ny XML/XPath-analyse og gjør "
            "ingen automatisk faglig godkjenning av uttrekk."
        ),
        "counts": counts,
        "jobs": rows,
    }


def _file_uri(value: str) -> str:
    if not value:
        return ""
    try:
        return Path(value).resolve().as_uri()
    except (OSError, ValueError):
        return ""


def _count(value) -> str:
    return "–" if value is None else str(value)


def write_validation_overview(
    settings: dict,
    overview: dict,
) -> ValidationOverviewFiles:
    root = run_log_dir(settings)
    root.mkdir(parents=True, exist_ok=True)

    run_id = str(overview.get("run_id", "") or "RUN-unknown")
    base = f"{run_id}_NOARK5_KONTROLLOVERSIKT"
    json_path = root / f"{base}.json"
    html_path = root / f"{base}.html"

    json_path.write_text(
        json.dumps(overview, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    rows_html = []
    for row in overview["jobs"]:
        report_uri = _file_uri(row.get("report_html", ""))
        report_link = (
            f'<a href="{html.escape(report_uri)}">Åpne rapport</a>'
            if report_uri
            else "–"
        )
        searchable = " ".join([
            row.get("job_id", ""),
            row.get("name", ""),
            row.get("source_extraction", ""),
            row.get("control_status", ""),
            row.get("assessment_status", ""),
        ]).casefold()

        rows_html.append(
            f'<tr class="job-row" data-status="{html.escape(row["control_status"])}" '
            f'data-search="{html.escape(searchable)}">'
            f"<td>{html.escape(row['job_id'])}</td>"
            f"<td>{html.escape(row['name'])}</td>"
            f"<td>{html.escape(row['job_status'])}</td>"
            f"<td><strong>{html.escape(row['control_status'])}</strong></td>"
            f"<td>{_count(row['archive_part_count'])}</td>"
            f"<td>{row['tests_ok']}</td>"
            f"<td>{row['tests_error']}</td>"
            f"<td>{row['reconciliation_mismatch']}</td>"
            f"<td>{row['review_cases']}</td>"
            f"<td>{row['review_findings']}</td>"
            f"<td>{html.escape(row['assessment_status'])}</td>"
            f"<td>{report_link}</td>"
            "</tr>"
            f'<tr class="detail-row" data-status="{html.escape(row["control_status"])}" '
            f'data-search="{html.escape(searchable)}">'
            "<td></td>"
            f"<td colspan='11'><strong>Kilde:</strong> "
            f"{html.escape(row['source_extraction'])}<br>"
            f"<strong>Work:</strong> {html.escape(row['work_operations_effective'])}<br>"
            f"<strong>Mapper:</strong> {_count(row['folder_count'])} | "
            f"<strong>Registreringer:</strong> {_count(row['registration_count'])} | "
            f"<strong>Dokumentbeskrivelser:</strong> {_count(row['document_description_count'])} | "
            f"<strong>Dokumentobjekter:</strong> {_count(row['document_object_count'])}<br>"
            f"{html.escape(row['control_message'])}</td>"
            "</tr>"
        )

    counts = overview["counts"]
    html_doc = f"""<!doctype html>
<html lang="no">
<head>
<meta charset="utf-8">
<title>Noark 5 kontrolloversikt</title>
<style>
body {{ font-family: Arial, sans-serif; max-width: 1700px; margin: 2rem auto; line-height: 1.4; }}
table {{ border-collapse: collapse; width: 100%; }}
th, td {{ border: 1px solid #bbb; padding: .45rem; text-align: left; vertical-align: top; }}
th {{ background: #eee; position: sticky; top: 0; }}
.detail-row td {{ background: #fafafa; font-size: .9rem; color: #333; }}
.note {{ border-left: 4px solid #777; padding: .8rem 1rem; background: #f7f7f7; }}
.summary {{ margin: 1rem 0; font-size: 1.05rem; }}
.controls {{ display: flex; gap: .75rem; margin: 1rem 0; align-items: center; flex-wrap: wrap; }}
.controls input, .controls select {{ padding: .45rem .6rem; font-size: 1rem; }}
.legend {{ font-size: .9rem; color: #444; margin: .5rem 0 1rem; }}
.hidden {{ display: none; }}
</style>
</head>
<body>
<h1>Noark 5 kontrolloversikt</h1>
<div class="note">{html.escape(overview["principle"])}</div>
<p><strong>RUN:</strong> {html.escape(overview["run_id"])}</p>
<p><strong>Jobbliste:</strong> {html.escape(overview["job_list_path"])}</p>
<p><strong>Generert:</strong> {html.escape(overview["generated_at"])}</p>
<p class="summary">
<strong>OK:</strong> {counts["OK"]} |
<strong>Vurder:</strong> {counts["VURDER"]} |
<strong>Feil:</strong> {counts["FEIL"]} |
<strong>Mangler rapport:</strong> {counts["MANGLER"]} |
<strong>Ukjent:</strong> {counts["UKJENT"]}
</p>
<div class="controls">
<label>Søk <input id="searchBox" type="search" placeholder="jobb, navn, kilde..."></label>
<label>Status
<select id="statusFilter">
<option value="">Alle</option>
<option>FEIL</option>
<option>VURDER</option>
<option>MANGLER</option>
<option>UKJENT</option>
<option>OK</option>
</select>
</label>
</div>
<p class="legend">
<strong>Vurderingssaker</strong> = antall registrerte vurderingskategorier/saker.
<strong>Funn</strong> = underliggende funn i disse sakene. Én sak kan derfor inneholde flere funn.
</p>
<table>
<thead>
<tr>
<th>Jobb</th><th>Navn</th><th>Jobbstatus</th><th>Kontrollstatus</th>
<th>Arkivdeler</th><th>Tester OK</th><th>Testfeil</th><th>Mismatch</th>
<th>Vurderingssaker</th><th>Funn</th><th>Depotvurdering</th><th>Rapport</th>
</tr>
</thead>
<tbody>
{''.join(rows_html)}
</tbody>
</table>
<script>
(function() {{
  const q = document.getElementById('searchBox');
  const s = document.getElementById('statusFilter');
  function apply() {{
    const needle = (q.value || '').toLowerCase().trim();
    const status = s.value || '';
    const rows = Array.from(document.querySelectorAll('tr.job-row'));
    rows.forEach((row) => {{
      const detail = row.nextElementSibling;
      const matchesText = !needle || (row.dataset.search || '').includes(needle);
      const matchesStatus = !status || row.dataset.status === status;
      const show = matchesText && matchesStatus;
      row.classList.toggle('hidden', !show);
      if (detail && detail.classList.contains('detail-row')) {{
        detail.classList.toggle('hidden', !show);
      }}
    }});
  }}
  q.addEventListener('input', apply);
  s.addEventListener('change', apply);
}})();
</script>
</body>
</html>
"""
    html_path.write_text(html_doc, encoding="utf-8")
    return ValidationOverviewFiles(json_path=json_path, html_path=html_path)


def latest_validation_overview(settings: dict) -> Path | None:
    root = run_log_dir(settings)
    if not root.is_dir():
        return None
    files = list(root.glob("RUN-*_NOARK5_KONTROLLOVERSIKT.html"))
    return max(files, key=lambda path: path.stat().st_mtime) if files else None
