"""Compare all report evidence sources without conflating runs, scopes or statuses."""
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from noark5_workflow.reporting.evidence_comparison_a18 import (
    build_source_comparison, render_source_comparison_annex, render_source_comparison_overview,
)
from noark5_workflow.reporting import job_summary_a16 as summary
from noark5_workflow.reporting import report_package_a16 as package


def job(name='JOB-002'):
    return SimpleNamespace(job_id=name, name=name, work_operations='/not-a-real-job-work-folder',
                           status=SimpleNamespace(value='Ferdig'), progress=1.0)


def native():
    return {'summary': {'folder_count': None, 'registration_count': 90},
            'technical_validation': {'summary': {'ok': 1, 'error': 1},
                                     'tests': [{'test_id': 'kdrs.c08', 'test_point': 'N5.10', 'status': 'other'},
                                               {'test_id': 'kdrs.c14', 'test_point': 'N5.16', 'status': 'ok'}]},
            'archive_parts': [
                {'archive_part': {'system_id': 'a1', 'title': 'Saksarkiv'}, 'folder_count': 4, 'registration_count': None},
                {'archive_part': {'system_id': 'a2', 'title': 'Elevarkiv'}, 'folder_count': 6},
            ]}


def evidence():
    return {'arkade5': {'imports': [
        {'import_id': 'old', 'source_file': 'arkade_old.json', 'source_sha256': 'a'*64,
         'source_version': '2.13.0', 'number_of_errors': 2,
         'tests': [{'test_id': 'N5.47', 'test_name': 'System-ID', 'status': 'error', 'number_of_errors': 2,
                    'dwm_candidates': ['kdrs.c14'], 'source_sha256': 'a'*64, 'results': [{'message': 'error'}]}]},
        {'import_id': 'new', 'source_file': 'arkade_new.json', 'source_sha256': 'b'*64,
         'source_version': '2.13.1', 'number_of_errors': 0,
         'tests': [{'test_id': 'N5.47', 'test_name': 'System-ID', 'status': 'ok', 'number_of_errors': 0,
                    'dwm_candidates': ['kdrs.c14'], 'source_sha256': 'b'*64}]},
    ]}, 'kdrs_query': {'resources': [
        {'report_type': 'standard', 'test_id': 'kdrs.c08', 'source_import_id': 'k1',
         'source_file': 'standard.txt', 'source_sha256': 'c'*64,
         'raw_text': 'N5.10 Mapper pr. type; Alle: 11'},
        {'report_type': 'u02', 'test_id': 'kdrs.u02', 'archive_part_title': 'Saksarkiv',
         'archive_part_index': 1, 'source_import_id': 'k1', 'source_file': 'U02.txt',
         'source_sha256': 'c'*64, 'raw_text': '[.2] Mappe typer: Alle: 4'},
        {'report_type': 'u02', 'test_id': 'kdrs.u02', 'archive_part_title': 'Mangler',
         'archive_part_index': 2, 'source_import_id': 'k1', 'source_file': 'U02.txt',
         'source_sha256': 'c'*64, 'raw_text': '[.2] Mappe typer: Alle: 999'},
    ]}, 'diagnostics': []}


def test_two_arkade_runs_are_independent_and_match_dwm_candidates():
    mod = build_source_comparison([(job(), native(), None, '')], evidence_by_job={'JOB-002': evidence()})
    a = mod['jobs'][0]
    assert [x['import_id'] for x in a['arkade5_runs']] == ['old', 'new']
    assert [x['error_count'] for x in a['arkade5_runs']] == [2, 0]
    c = a['arkade5_control_matrix'][0]
    assert c['control_id'] == 'N5.47'
    assert c['per_run']['old']['status'] == 'error' and c['per_run']['new']['status'] == 'ok'
    assert c['dwm_results'][0]['test_id'] == 'kdrs.c14'
    assert c['mapping_status'] == 'kandidat – ikke likestilt kontroll'
    assert c['per_run']['old']['results'] == [{'message': 'error'}]
    html = render_source_comparison_annex(mod, level='Full')
    assert 'arkade_old.json' in html and 'arkade_new.json' in html
    assert 'N5.47' in html and 'kdrs.c14' in html
    assert 'Arkade 5 – konkrete funn' in html and 'error' in html


def test_exact_kdrs_whole_and_part_comparison_without_promotion():
    n = native()
    mod = build_source_comparison([(job(), n, None, '')], evidence_by_job={'JOB-002': evidence()})
    comps = mod['jobs'][0]['kdrs_query']['exact_comparisons']
    assert any(r['scope']=='uttrekk' and r['metric_id']=='folder_count' and r['comparison']=='DWM mangler' for r in comps)
    assert any(r['scope']=='arkivdel' and r['archive_part_system_id']=='a1' and r['kdrs_value']==4 and r['comparison']=='samsvar' for r in comps)
    assert any(r['scope']=='ikke_tilordnet' and r['kdrs_value']==999 for r in comps)
    assert n['archive_parts'][0]['folder_count'] == 4 and n['summary']['folder_count'] is None


def test_same_number_is_not_automatically_reported_as_dwm_equivalence():
    e = evidence()
    e['arkade5']['imports'][0]['tests'][0]['dwm_candidates'] = []
    e['arkade5']['imports'][1]['tests'][0]['dwm_candidates'] = []
    a = build_source_comparison([(job(), native(), None, '')], evidence_by_job={'JOB-002': e})['jobs'][0]
    assert not a['arkade5_control_matrix'][0]['dwm_results']


def test_missing_dwm_and_imports_are_not_zero():
    e = {'arkade5': {'imports': []}, 'kdrs_query': {'resources': []}}
    m = build_source_comparison([(job(), None, None, 'Ingen depotrapport')], evidence_by_job={'JOB-002': e})
    text = render_source_comparison_annex(m)
    assert 'Ingen DWM XPath-testresultater' in text
    assert 'Ingen import dokumentert' in text
    assert 'ukjent, ikke null' in text


def test_no_cross_job_collapse():
    a, b = job('JOB-001'), job('JOB-002')
    e = {'JOB-001': evidence(), 'JOB-002': {'arkade5': {'imports': []}, 'kdrs_query': {'resources': []}}}
    m = build_source_comparison([(a,native(),None,''),(b,native(),None,'')], evidence_by_job=e)
    assert len(m['jobs']) == 2
    assert len(m['jobs'][0]['arkade5_runs']) == 2 and len(m['jobs'][1]['arkade5_runs']) == 0
    assert render_source_comparison_overview(m).count('<tr>') >= 3


def test_duplicate_part_titles_are_unassigned():
    d = native()
    d['archive_parts'][1]['archive_part']['title'] = 'Saksarkiv'
    m = build_source_comparison([(job(), d, None, '')], evidence_by_job={'JOB-002': evidence()})
    assert any(r['kdrs_value']==4 and r['comparison']=='ikke_tilordnet'
               for r in m['jobs'][0]['kdrs_query']['exact_comparisons'])


def test_html_escapes_untrusted_source_text():
    e=evidence()
    e['arkade5']['imports'][0]['tests'][0]['test_name']='<script>evil()</script>'
    m=build_source_comparison([(job(),native(),None,'')],evidence_by_job={'JOB-002':e})
    h=render_source_comparison_annex(m,level='Full')
    assert '<script>' not in h and '&lt;script&gt;' in h


def test_report_package_same_model_html_json_pdf(tmp_path):
    j=job()
    n=native()
    e=evidence()
    options=summary.ReportOptions('Full', ('overview','totals','technical','external'), True,True)
    with patch.object(summary, '_latest_report', return_value=(n, None, '')), \
         patch.object(package, '_latest_report', return_value=(n, None, '')), \
         patch.object(package, 'collect_job_evidence', return_value=e):
        package.write_report_package(tmp_path, [j], options, formats=('html','json','pdf'))
    main=(tmp_path/'index.html').read_text(encoding='utf-8')
    annex=(tmp_path/'vedlegg-c-teknisk-evidens.html').read_text(encoding='utf-8')
    payload=json.loads((tmp_path/'index.json').read_text(encoding='utf-8'))
    assert 'DWM XPath / Arkade 5 / KDRS Query' in main
    assert 'arkade_old.json' in annex and 'arkade_new.json' in annex
    assert 'U02.txt' in annex
    assert len(payload['source_comparison']['jobs'][0]['arkade5_runs']) == 2
    assert len(payload['source_comparison']['jobs'][0]['kdrs_query']['exact_comparisons']) >= 2
    assert (tmp_path/'vedlegg-c-teknisk-evidens.pdf').stat().st_size > 1000
