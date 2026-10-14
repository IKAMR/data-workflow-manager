import json
from pathlib import Path
from types import SimpleNamespace
from noark5_workflow.reporting.job_summary_a16 import ReportOptions, render_selected_jobs_report


def test_real_report_identity_and_archive_annex(tmp_path):
    root = tmp_path / 'dwm' / 'noark5_reports' / 'depot_validation' / 'JOB-001__RUN-test'
    root.mkdir(parents=True)
    fixture = {'summary': {'archive_part_count': 1, 'folder_count':48}, 'period_reconciliation':{'declared_period':{'start_year':'2004','end_year':'2005','start_date':'2004-01-13','end_date':'2005-04-13'}}, 'archive_parts':[{'archive_part':{'title':'Barn og Familie'}, 'yearly_volume':{'folder':{'2004':42,'2005':6}}}], 'external_validation':{'arkade5':{'summary':{'imports':1, 'arkade_errors':2}, 'imports':[{'source_version':'2.13.1'}]}}}
    (root / 'depot_validation_report.json').write_text(json.dumps(fixture), encoding='utf-8')
    job = SimpleNamespace(job_id='JOB-001', name='bf-2023-08-22_562',
        source_extraction=r'G:\arkiv-noark5-1502\1502\1502_029_ephorte-hist-bf_noark5\content\sip\content\bf-2023-08-22_562\avleveringspakke',
        work_operations=tmp_path / 'dwm', status=SimpleNamespace(value='Ferdig'), progress=1)
    html = render_selected_jobs_report([job], ReportOptions('Full', (), True, True))
    assert '1502_029 ephorte hist bf (oppgitt 2004–2005)' in html
    assert 'Barn og Familie' in html
    assert 'Omfang per år' in html
    assert '2004' in html and '2005' in html
    assert 'Samlet omfang' in html
    assert 'Arkade-versjon' in html
    assert '&quot;arkade5&quot;' not in html
    assert '2.13.1' in html
