import json
from pathlib import Path
from types import SimpleNamespace
from noark5_workflow.reporting.period_assessment_a16 import (
    review_candidate, save_assessment, load_assessment, reviewed_years)
from noark5_workflow.reporting.job_summary_a16 import (
    _extraction_label, _review_status, render_selected_jobs_report, ReportOptions)


def job(tmp_path):
    return SimpleNamespace(job_id='JOB-019', work_operations=str(tmp_path),
                           source_extraction=str(tmp_path / '1502_047_ephorte-hist-mote_noark5'),
                           name='Møteserie', status=SimpleNamespace(value='Ferdig'), progress=1)


def data():
    def span(a,b):return {'span':{'first_year':a,'last_year':b}}
    return {'period_reconciliation': {'declared_period':{'start_year':1999,'end_year':2099},
             'observed_series':{
                 'folder_created':span(1999,2099), 'registration_created':span(1999,2099),
                 'document_description_created':span(1999,2005),
                 'document_object_parent_created':span(1999,2005)}}}


def test_job019_is_not_marked_as_approved_or_matching(tmp_path):
    j=job(tmp_path); d=data()
    c=review_candidate(d)
    assert c['observed_years']==[1999,2099]
    assert c['proposed_years']==[1999,2005]
    assert c['needs_review'] and c['conflicting_sources']
    assert _review_status(j,d)=='Krever vurdering'
    assert 'oppgitt 1999–2099; krever vurdering' in _extraction_label(j,d)


def test_saved_assessment_survives_and_changes_display(tmp_path):
    j=job(tmp_path);d=data()
    saved=save_assessment(j,d,status='godkjent',years=[1999,2005],comment='2099 må kontrolleres')
    assert saved.is_file()
    assert reviewed_years(load_assessment(j))==(1999,2005)
    assert '1999–2005, faglig vurdert' in _extraction_label(j,d)
    assert _review_status(j,d)=='Godkjent'
    assert '2099' in json.dumps(load_assessment(j))
    save_assessment(j,d)
    assert reviewed_years(load_assessment(j))==(1999,2005)


def test_report_does_not_write_period_assessment_implicitly(tmp_path,monkeypatch):
    j=job(tmp_path);d=data()
    import noark5_workflow.reporting.job_summary_a16 as report
    monkeypatch.setattr(report,'_latest_report',lambda x:(d,None,''))
    html=render_selected_jobs_report([j],ReportOptions('Full'))
    assert 'Krever vurdering' in html
    assert '1999, 2005' in html
    assert not (tmp_path/'dwm'/'noark5_reports'/'period_assessments'/'JOB-019.json').exists()


def test_invalid_review_rejected(tmp_path):
    j=job(tmp_path)
    import pytest
    with pytest.raises(ValueError):save_assessment(j,data(),status='godkjent',years=[2099,1999])
