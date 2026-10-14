from pathlib import Path
from types import SimpleNamespace
from noark5_workflow.reporting.job_summary_a16 import ReportOptions, render_selected_jobs_report, write_selected_jobs_report


def test_report_with_appendices(tmp_path):
    base=tmp_path/'dwm'/'noark5_reports'/'depot_validation'/'JOB-001__RUN-foo'
    base.mkdir(parents=True)
    (base/'depot_validation_report.json').write_text('{"summary":{"archive_part_count":2,"folder_count":4},"technical_validation":{"status":"ok","summary":{"ok":58,"error":0}},"archive_parts":[{"archive_part":{"title":"Arkivdel Alfa"},"folder_count":4}]}',encoding='utf-8')
    job=SimpleNamespace(job_id='JOB-001',name='Test uttrekk',status=SimpleNamespace(value="Ferdig"),progress=1,work_operations=tmp_path/'dwm')
    content=render_selected_jobs_report([job],ReportOptions('Full',(),True,True))
    assert 'Arkivdel Alfa' in content
    assert 'Test uttrekk' in content
    assert '58' in content
    p=write_selected_jobs_report(tmp_path/'report', [job],ReportOptions('Enkel'))
    assert p.exists() and p.suffix=='.html'
    assert 'Vedlegg – arkivdel:' not in p.read_text(encoding='utf-8')
    assert job.status.value == "Ferdig" and job.progress == 1
