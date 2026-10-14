import json
from types import SimpleNamespace
from noark5_workflow.reporting.report_package_a16 import write_report_package
from noark5_workflow.reporting.job_summary_a16 import ReportOptions


def _job(tmp_path):
    folder=tmp_path/'dwm/noark5_reports/depot_validation/JOB-019__RUN-test'
    folder.mkdir(parents=True)
    content={
        'summary': {'archive_part_count':1,'folder_count':3,'registration_count':4,'document_description_count':5,'document_object_count':6},
        'period_reconciliation':{'declared_period':{'start_year':1999,'end_year':2099},'observed_series':{'folder_created':{'span':{'first_year':1999,'last_year':2099}},'registration_created':{'span':{'first_year':1999,'last_year':2099}},'document_description_created':{'span':{'first_year':1999,'last_year':2005}},'document_object_parent_created':{'span':{'first_year':1999,'last_year':2005}}}},
        'archive_parts':[{'archive_part':{'title':'Møteserie','system_id':'x'},'folder_count':3}],
        'technical_validation':{'summary':{'ok':50,'error':0}},
        'deviations':[{'category':'period_source_divergence','summary':'Avvik mellom kilder'}],
    }
    (folder/'depot_validation_report.json').write_text(json.dumps(content),encoding='utf-8')
    return SimpleNamespace(job_id='JOB-019',work_operations=tmp_path/'dwm',name='mote',source_extraction='1502_047_ephorte-hist-mote_noark5',status=SimpleNamespace(value='Ferdig'),progress=1)


def test_separate_package_links_and_review(tmp_path):
    job=_job(tmp_path)
    output=tmp_path/'out'
    path=write_report_package(output,[job],ReportOptions('Full',(),True,True))
    assert path==output/'index.html'
    assert len(list(output.glob('*.html')))==5
    main=path.read_text(encoding='utf-8')
    assert 'Krever vurdering' in main and 'JOB-019' in main
    assert 'Jobboversikt – alle uttrekk' in main
    assert '1502_047 ephorte hist mote (1999–2005, foreslått)' in main
    assert '2099 er fiktivt oppgitt sluttår' in main
    assert 'Møteserie' in main
    assert 'vedlegg-d-periodevurdering.html' in main
    assert 'Avvik mellom kilder' not in main  # grouped category only
    assert '1999–2099' in (output/'vedlegg-d-periodevurdering.html').read_text(encoding='utf-8')
    assert 'Møteserie' in (output/'vedlegg-b-arkivdeler.html').read_text(encoding='utf-8')
    assert not (tmp_path/'dwm/noark5_reports/period_assessments/JOB-019.json').exists()


def test_optional_appendices(tmp_path):
    path=write_report_package(tmp_path/'out',[_job(tmp_path)],ReportOptions('Enkel',(),False,False))
    assert path.is_file()
    assert sorted(x.name for x in path.parent.iterdir())==['index.html','vedlegg-c-teknisk-evidens.html']


def test_main_overview_lists_every_job(tmp_path):
    from types import SimpleNamespace
    first = _job(tmp_path/'one')
    second = _job(tmp_path/'two')
    second.job_id='JOB-020'
    folder=tmp_path/'two'/'dwm/noark5_reports/depot_validation/JOB-019__RUN-test'
    folder.rename(folder.parent/'JOB-020__RUN-test')
    second.source_extraction='1502_048_ephorte-hist-mu_noark5'
    path=write_report_package(tmp_path/'out',[first,second],ReportOptions('Full',(),False,False))
    main=path.read_text(encoding='utf-8')
    assert '<td>JOB-019</td>' in main and '<td>JOB-020</td>' in main
    assert main.count('Møteserie') >= 2
