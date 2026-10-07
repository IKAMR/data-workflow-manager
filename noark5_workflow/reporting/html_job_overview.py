from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from html import escape
from pathlib import Path
from typing import Iterable

from noark5_workflow.core.job import Job
from .depot_metadata import load_depot_metadata


@dataclass(frozen=True)
class JobOverviewRow:
    job_id: str
    name: str
    profile_id: str
    status: str
    progress_percent: int
    source_extraction: str
    source_root: str
    work_root: str
    work_operations: str
    archive_root: str
    output_root: str
    workflow_ids: tuple[str, ...]
    message: str
    metadata: dict[str, str]
    metadata_source: str


@dataclass(frozen=True)
class JobOverviewReport:
    title: str
    generated_at: str
    jobs: tuple[JobOverviewRow, ...]


def _path_text(value: Path | None) -> str:
    return str(value) if value is not None else ""


def _metadata_for(job: Job) -> tuple[dict[str, str], str]:
    payload = load_depot_metadata(job)
    current = {
        str(key): str(value or "")
        for key, value in payload.get("current", {}).items()
    }
    imports = payload.get("source_imports", [])
    source = ""
    if imports and isinstance(imports[-1], dict):
        source = str(imports[-1].get("path", "") or "")
    return current, source


def build_job_overview_report(
    jobs: Iterable[Job],
    *,
    title: str = "Tilstand og omfang - Noark 5",
    generated_at: str | None = None,
) -> JobOverviewReport:
    """Build report data from jobs plus the separate depot-metadata sidecar."""
    rows: list[JobOverviewRow] = []
    for job in jobs:
        active_source = job.active_extraction_root
        metadata, metadata_source = _metadata_for(job)
        rows.append(
            JobOverviewRow(
                job_id=str(job.job_id),
                name=str(job.name or job.job_id),
                profile_id=str(job.profile_id or ""),
                status=str(job.status.value),
                progress_percent=max(0, min(100, round(float(job.progress or 0.0) * 100))),
                source_extraction=_path_text(active_source),
                source_root=_path_text(job.source_root),
                work_root=_path_text(job.work_root),
                work_operations=_path_text(job.work_operations),
                archive_root=_path_text(job.archive_root),
                output_root=_path_text(job.output_root),
                workflow_ids=tuple(str(value) for value in job.workflow_ids),
                message=str(job.message or ""),
                metadata=metadata,
                metadata_source=metadata_source,
            )
        )

    timestamp = generated_at or datetime.now().astimezone().isoformat(timespec="seconds")
    return JobOverviewReport(title=title, generated_at=timestamp, jobs=tuple(rows))


def _text(value: str, *, empty: str = "-") -> str:
    return escape(value, quote=True) if value else empty


def _workflow_text(workflow_ids: tuple[str, ...]) -> str:
    if not workflow_ids:
        return "-"
    return "<br>".join(escape(value, quote=True) for value in workflow_ids)


def _unique_values(report: JobOverviewReport, key: str, fallback: str = "") -> list[str]:
    values: list[str] = []
    for row in report.jobs:
        value = str(row.metadata.get(key, "") or "").strip()
        if not value and fallback:
            value = str(row.metadata.get(fallback, "") or "").strip()
        if value and value not in values:
            values.append(value)
    return values


def _joined(values: list[str]) -> str:
    return " · ".join(values)


def _report_header(report: JobOverviewReport) -> str:
    systems = _unique_values(report, "system")
    owners = _unique_values(report, "owner_municipalities", "owner_org")
    creators = _unique_values(report, "archive_creators", "creator")
    regions = _unique_values(report, "system_region")
    starts = sorted(v for v in _unique_values(report, "period_start") if v)
    ends = sorted(v for v in _unique_values(report, "period_end") if v)
    period = ""
    if starts or ends:
        period = f"{starts[0] if starts else '?'} – {ends[-1] if ends else '?'}"

    count = len(report.jobs)
    rows = []
    if systems:
        rows.append(("System", _joined(systems)))
    if owners:
        rows.append(("Eierkommune" if len(owners) == 1 else "Eierkommuner", _joined(owners)))
    if creators:
        rows.append(("Arkivskapere / kommuner", _joined(creators)))
    if regions:
        rows.append(("IT-/systemregion", _joined(regions)))
    if period:
        rows.append(("Samlet periode", period))
    rows.append(("Rapportgrunnlag", f"{count} uttrekk"))
    rows.append(("Rapport generert", report.generated_at))

    system_line = f'<p class="system-title">{_text(_joined(systems))}</p>' if systems else ""
    detail = "".join(
        f"<dt>{_text(label)}</dt><dd>{_text(value)}</dd>" for label, value in rows
    )
    return f"<h1>{_text(report.title)}</h1>{system_line}<dl class=\"report-meta\">{detail}</dl>"


def render_job_overview_html(report: JobOverviewReport) -> str:
    """Render a self-contained report; metadata is separate from validation results."""
    summary_rows = []
    details = []
    for row in report.jobs:
        meta = row.metadata
        label = str(meta.get("label", "") or "").strip()
        display_name = label or row.name
        period_start = str(meta.get("period_start", "") or "").strip()
        period_end = str(meta.get("period_end", "") or "").strip()
        period = " – ".join(value for value in (period_start, period_end) if value)
        owner = str(meta.get("owner_municipalities", "") or meta.get("owner_org", "") or "").strip()
        creator = str(meta.get("archive_creators", "") or meta.get("creator", "") or "").strip()

        summary_rows.append(
            "<tr>"
            f"<td><strong>{_text(display_name)}</strong><br><span class=\"muted\">{_text(row.job_id)}</span></td>"
            f"<td>{_text(meta.get('system', ''))}</td>"
            f"<td>{_text(owner)}</td>"
            f"<td>{_text(creator)}</td>"
            f"<td>{_text(period)}</td>"
            f"<td>{_text(row.status)}</td>"
            "</tr>"
        )
        details.append(
            f"<section class=\"job\"><h2>{_text(display_name)} "
            f"<span class=\"muted\">({_text(row.job_id)})</span></h2>"
            "<dl>"
            f"<dt>LABEL</dt><dd>{_text(label)}</dd>"
            f"<dt>System</dt><dd>{_text(meta.get('system', ''))}</dd>"
            f"<dt>Systemversjon</dt><dd>{_text(meta.get('system_version', ''))}</dd>"
            f"<dt>Eierkommune(r)</dt><dd>{_text(owner)}</dd>"
            f"<dt>Arkivskapere / kommuner</dt><dd>{_text(creator)}</dd>"
            f"<dt>IT-/systemregion</dt><dd>{_text(meta.get('system_region', ''))}</dd>"
            f"<dt>Periode</dt><dd>{_text(period)}</dd>"
            f"<dt>Submission Agreement</dt><dd>{_text(meta.get('submission_agreement', ''))}</dd>"
            f"<dt>Informasjon om innleveringen</dt><dd class=\"pre\">{_text(meta.get('delivery_information', ''))}</dd>"
            f"<dt>Metadata importert fra</dt><dd>{_text(row.metadata_source)}</dd>"
            f"<dt>Status</dt><dd>{_text(row.status)} - {row.progress_percent}%</dd>"
            f"<dt>Aktivt uttrekk</dt><dd>{_text(row.source_extraction)}</dd>"
            f"<dt>Source root</dt><dd>{_text(row.source_root)}</dd>"
            f"<dt>Work/operations</dt><dd>{_text(row.work_operations)}</dd>"
            f"<dt>Workflow</dt><dd>{_workflow_text(row.workflow_ids)}</dd>"
            "</dl></section>"
        )

    return f"""<!doctype html>
<html lang=\"no\">
<head>
<meta charset=\"utf-8\">
<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">
<title>{_text(report.title)}</title>
<style>
:root {{ color-scheme: light; font-family: Inter, Segoe UI, Arial, sans-serif; }}
body {{ margin: 0; background: #f4f6f8; color: #17202a; }}
main {{ max-width: 1320px; margin: 0 auto; padding: 34px; }}
h1 {{ margin: 0 0 4px; font-size: 2rem; }}
h2 {{ margin-top: 0; font-size: 1.2rem; }}
.system-title {{ margin: 2px 0 16px; font-size: 1.25rem; font-weight: 650; color: #344054; }}
.muted {{ color: #667085; font-weight: 400; }}
.panel, .job {{ background: white; border: 1px solid #dfe3e8; border-radius: 10px; padding: 20px; margin: 18px 0; }}
table {{ width: 100%; border-collapse: collapse; font-size: 0.92rem; }}
th, td {{ text-align: left; vertical-align: top; border-bottom: 1px solid #e8ebef; padding: 9px 10px; }}
th {{ background: #f8fafc; }}
dl {{ display: grid; grid-template-columns: minmax(170px, 230px) 1fr; gap: 7px 18px; margin: 0; }}
dl.report-meta {{ max-width: 900px; margin: 18px 0 26px; }}
dt {{ font-weight: 600; }}
dd {{ margin: 0; overflow-wrap: anywhere; }}
dd.pre {{ white-space: pre-wrap; }}
@media (max-width: 800px) {{ main {{ padding: 16px; }} .panel {{ overflow-x: auto; }} dl {{ grid-template-columns: 1fr; }} dd {{ margin-bottom: 8px; }} }}
</style>
</head>
<body>
<main>
{_report_header(report)}
<section class=\"panel\">
<h2>Uttrekk</h2>
<table>
<thead><tr><th>LABEL / uttrekk</th><th>System</th><th>Eier</th><th>Arkivskaper</th><th>Periode</th><th>Tilstand</th></tr></thead>
<tbody>{''.join(summary_rows)}</tbody>
</table>
</section>
{''.join(details)}
</main>
</body>
</html>
"""


def write_job_overview_html(
    path: Path,
    jobs: Iterable[Job],
    *,
    title: str = "Tilstand og omfang - Noark 5",
) -> Path:
    path = Path(path)
    if path.suffix.lower() != ".html":
        path = path.with_suffix(".html")
    path.parent.mkdir(parents=True, exist_ok=True)
    report = build_job_overview_report(jobs, title=title)
    path.write_text(render_job_overview_html(report), encoding="utf-8")
    return path
