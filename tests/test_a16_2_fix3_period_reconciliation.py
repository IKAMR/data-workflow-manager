import json
from types import SimpleNamespace
from noark5_workflow.reporting.job_summary_a16 import ReportOptions, render_selected_jobs_report


def test_declared_and_observed_periods_are_distinct(tmp_path):
    path = tmp_path / 'dwm/noark5_reports/depot_validation/JOB-001__RUN-test'
    path.mkdir(parents=True)
    data = {
        'period_reconciliation': {
            'declared_period': {'start_date': '1999-01-01', 'end_date': '2099-12-31', 'start_year': '1999', 'end_year': '2099'},
            'observed_series': {
                'folder_created': {'span': {'first_year':'2000', 'last_year':'2002'}},
                'registration_created': {'span': {'first_year':'2000', 'last_year':'2003'}},
                'journal_date_archive_structure': {'span': {'first_year':'2001','last_year':'2003'}},
                'document_description_created': {'span': {'first_year':'2000','last_year':'2003'}},
                'document_object_parent_created': {'span': {'first_year':'2002','last_year':'2003'}},
                'change_log': {'span': {'first_year':'2022','last_year':'2022'}},
            },
            'archive_parts': [{'archive_part': {'system_id':'abc'}, 'observed_period': {'first_year':'2000','last_year':'2003'}, 'metrics': {'folder_created': {'span': {'first_year':'2000','last_year':'2002'}}}}],
        },
        'archive_parts': [{'archive_part': {'system_id':'abc', 'title':'Testarkivdel'}, 'folder_count': 1}]
    }
    (path/'depot_validation_report.json').write_text(json.dumps(data),encoding='utf-8')
    job = SimpleNamespace(job_id='JOB-001',name='Test',work_operations=tmp_path/'dwm',status=SimpleNamespace(value='Ferdig'),progress=1)
    html = render_selected_jobs_report([job], ReportOptions('Full',(),True,True))
    assert '1999-01-01 – 2099-12-31' in html
    assert '2000–2002' in html and '2001–2003' in html
    assert 'Endringslogg (ikke arkivperiode)' in html and '2022' in html
    assert 'XPath-ytterår for arkivdelen' in html
    assert 'Dok.obj. (forelders dato)' in html


def test_unknown_xpath_does_not_inherit_declared_years(tmp_path):
    path = tmp_path/'dwm/noark5_reports/depot_validation/JOB-001__RUN-test'
    path.mkdir(parents=True)
    (path/'depot_validation_report.json').write_text(json.dumps({'period_reconciliation':{'declared_period':{'start_date':'1999-01-01','end_date':'2099-12-31'}}}),encoding='utf-8')
    job=SimpleNamespace(job_id='JOB-001',name='Test',work_operations=tmp_path/'dwm',status=SimpleNamespace(value='Ferdig'),progress=1)
    html=render_selected_jobs_report([job],ReportOptions('Full'))
    assert '<td>1999-01-01 – 2099-12-31</td><td>Ikke tilgjengelig</td><td>Kan ikke avstemmes</td><td>–</td>' in html


def test_2099_only_remains_in_declared_period(tmp_path):
    path=tmp_path/'dwm/noark5_reports/depot_validation/JOB-019__RUN-test'
    path.mkdir(parents=True)
    report={'period_reconciliation':{'declared_period':{'start_year':'1999','end_year':'2099','start_date':'1999-04-26','end_date':'2099-12-31'},'observed_series':{'folder_created':{'span':{'first_year':'1999','last_year':'2004'}},'registration_created':{'span':{'first_year':'1999','last_year':'2006'}},'change_log':{'span':{'first_year':'2022','last_year':'2022'}}}},'archive_parts':[{'archive_part':{'title':'Møteserie','system_id':'x'}}]}
    (path/'depot_validation_report.json').write_text(json.dumps(report),encoding='utf-8')
    job=SimpleNamespace(job_id='JOB-019',name='mote',source_extraction=r'G:\arkiv-noark5-1502\1502\1502_047_ephorte-hist-mote_noark5\content',work_operations=tmp_path/'dwm',status=SimpleNamespace(value='Ferdig'),progress=1)
    html=render_selected_jobs_report([job],ReportOptions('Full',(),True,False))
    assert '1502_047 ephorte hist mote (oppgitt 1999–2099; krever vurdering)' in html
    assert '1502_047 ephorte hist mote (1999–2099)' not in html
    assert '1999-04-26 – 2099-12-31' in html
    assert 'Periodevurdering' in html and 'Krever vurdering' in html
    assert 'Endringslogg (ikke arkivperiode)' in html
