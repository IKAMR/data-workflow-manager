import json
from pathlib import Path
from types import SimpleNamespace

from noark5_workflow.reporting.job_summary_a16 import _latest_report, render_selected_jobs_report, ReportOptions


def _job(work, effective=None):
    return SimpleNamespace(job_id='JOB-001', name='Uttrekk A', status=SimpleNamespace(value='Ferdig'),
                           progress=1.0, work_operations=work, _effective_work_operations=effective)


def test_report_under_dwm_when_job_points_to_parent(tmp_path):
    report = tmp_path/'repository_operations'/'dwm'/'noark5_reports'/'depot_validation'/'JOB-001__RUN-a'/'depot_validation_report.json'
    report.parent.mkdir(parents=True)
    report.write_text(json.dumps({'summary': {'archive_part_count': 4, 'registration_count': 467},
                                  'technical_validation': {'status': 'ok', 'summary': {'ok': 58}}}), encoding='utf-8')
    job = _job(tmp_path/'repository_operations')
    content = render_selected_jobs_report([job], ReportOptions('Full'))
    assert '<td>4</td>' in content
    assert '<td>467</td>' in content
    assert '<td>58</td>' in content
    assert 'Ingen depotrapport funnet' not in content
    assert job.progress == 1.0


def test_effective_work_directory_and_broken_report(tmp_path):
    effective = tmp_path/'custom'/'dwm'
    p = effective/'noark5_reports'/'depot_validation'/'JOB-001__RUN-b'/'depot_validation_report.json'
    p.parent.mkdir(parents=True)
    p.write_text('{invalid', encoding='utf-8')
    job = _job(tmp_path/'repository_operations', effective)
    value, path, diagnostic = _latest_report(job)
    assert value is None and path is None
    assert str(p) in diagnostic and 'Kunne ikke lese' in diagnostic


def test_report_from_direct_work_and_not_other_job(tmp_path):
    base = tmp_path/'dwm'
    for job_id in ('JOB-001', 'JOB-002'):
        p = base/'noark5_reports'/'depot_validation'/f'{job_id}__RUN-test'/'depot_validation_report.json'
        p.parent.mkdir(parents=True)
        p.write_text(json.dumps({'summary': {'archive_part_count': 1 if job_id == 'JOB-001' else 99}}), encoding='utf-8')
    data, _, diagnostic = _latest_report(_job(base))
    assert data['summary']['archive_part_count'] == 1 and not diagnostic
