from pathlib import Path

from noark5_workflow.core.job import Job, JobStatus
from noark5_workflow.reporting import (
    build_job_overview_report,
    render_job_overview_html,
    write_job_overview_html,
)


def _job() -> Job:
    return Job(
        job_id="JOB-007",
        name="ePhorte <HIST>",
        profile_id="noark5",
        source_root=Path("C:/source"),
        source_extraction=Path("C:/source/extraction"),
        work_root=Path("D:/work"),
        work_operations=Path("D:/work/operations"),
        archive_root=Path("E:/archive"),
        output_root=Path("E:/archive"),
        workflow_ids=["analyse", "validate"],
        status=JobStatus.OK,
        progress=1.0,
        message="Workflow fullført & kontrollert",
    )


def test_build_job_overview_report_uses_existing_job_state_only() -> None:
    report = build_job_overview_report([_job()], generated_at="2026-10-06T22:00:00+02:00")

    assert report.generated_at == "2026-10-06T22:00:00+02:00"
    assert len(report.jobs) == 1
    row = report.jobs[0]
    assert row.job_id == "JOB-007"
    assert row.profile_id == "noark5"
    assert row.status == "Ferdig"
    assert row.progress_percent == 100
    assert row.source_extraction == "C:/source/extraction"
    assert row.workflow_ids == ("analyse", "validate")


def test_render_job_overview_html_is_self_contained_and_escapes_values() -> None:
    report = build_job_overview_report([_job()], generated_at="2026-10-06T22:00:00+02:00")
    html = render_job_overview_html(report)

    assert "<!doctype html>" in html.lower()
    assert '<meta charset="utf-8">' in html
    assert "Tilstand og omfang - Noark 5" in html
    assert "ePhorte &lt;HIST&gt;" in html
    assert "Workflow fullført &amp; kontrollert" in html
    assert "C:/source/extraction" in html
    assert "analyse<br>validate" in html


def test_write_job_overview_html_adds_extension_and_writes_utf8(tmp_path: Path) -> None:
    written = write_job_overview_html(tmp_path / "rapport", [_job()])

    assert written == tmp_path / "rapport.html"
    assert written.is_file()
    text = written.read_text(encoding="utf-8")
    assert "JOB-007" in text
    assert "1 jobb" in text
