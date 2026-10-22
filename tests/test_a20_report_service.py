"""Regression gates for v0.1.7-a20 central report/export service.

Fixtures intentionally emulate the established report_package_a16 JSON contract.
They do not assert that any production archive has passed an actual test.
"""
from __future__ import annotations

import copy
import csv
import io
import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import Mock

from noark5_workflow.reporting.report_model_a20 import build_snapshot
from noark5_workflow.reporting.report_service_a20 import write_report_package
from noark5_workflow.reporting.report_views_a20 import enrich_html, csv_for_page


METRIC_COUNTS={'archive_part_count':2,'folder_count':7,'registration_count':11,
               'journalpost_count':9,'document_description_count':13,'document_object_count':15}


def make_payload(n=1, *, missing=set(), name_prefix='1502', parts=2):
    entries=[]
    periods=[]
    for i in range(1,n+1):
        jid=f'JOB-{i:03d}'
        did=f'{name_prefix}_{i+22:03d}'
        data={} if i in missing else {
            'summary':{**METRIC_COUNTS,'archive_part_count':parts,'folder_count':0 if i == 1 else 7},
            'archive_parts':[{'archive_part':{'system_id':f'PART-{i}-{k}',
                                              'title':f'Arkivdel {k}'},
                              'folder_count':0 if k == 1 else 12,
                              'registration_count':None,'journalpost_count':2,
                              'document_description_count':0,'document_object_count':6}
                             for k in range(1,parts+1)],
            'external_validation':{'arkade5':{'imports':[]}},
        }
        entries.append({'job_id':jid,'extraction':did + ' ephorte',
                        'source_file':None if i in missing else f'/reports/{did}/{jid}/depot_validation_report.json',
                        'diagnostic':'Depotrapport ikke funnet' if i in missing else '',
                        'depot_report':data})
        periods.append({'job_id':jid,'dwm_observed_years':None,
                        'dwm_declared_years':[1993,2099],
                        'assessment_status':'godkjent' if i==2 else 'ikke_vurdert',
                        'approved_years':[2005,2019] if i==2 else None,
                        'selected_years':[2005,2019] if i==2 else None,
                        'comment':'Verifisert periode' if i==2 else '',
                        'archive_parts':[{'system_id':f'PART-{i}-{k}',
                                          'status':'godkjent' if k==1 else 'undersokes',
                                          'approved_years':[2005,2015] if k==1 else None,
                                          'selected_years':[2005,2015] if k==1 else None,
                                          'comment':'Faglig begrunnet' if k==1 else 'Undersøkes'}
                                         for k in range(1,parts+1)],
                        'kdrs_runs':[{'import_id':f'KDRS-{i}','report_type':'standard',
                                      'source_files':[f'kdrs_{did}.txt'],
                                      'scopes':[{'scope_id':'whole','period_observed_years':[1899,2099],
                                                 'series':{},'conflicts':[]}]}]
                        if i in missing or i==1 else [],
                        'kdrs_diagnostics':[]})
    return {'schema':'ikamr.noark5.selected_report.v1',
            'jobs':entries,'period_source_evidence':{'jobs':periods},
            'main_count_overview':{},'source_comparison':{}}


def selected_jobs(payload):
    return tuple(SimpleNamespace(job_id=j['job_id']) for j in payload['jobs'])


def opts(*, full=True, archive_parts=True):
    return SimpleNamespace(level='Full' if full else 'Medium',
                           enabled=('overview','totals','technical','external','period','sources') if full else ('overview','technical'),
                           extraction_appendix=True,archive_part_appendix=archive_parts)


def fake_legacy(payload):
    def generate(directory,jobs,options,*,prefix,formats):
        assert formats == ('html','json')
        assert len(jobs) == len(payload['jobs'])
        names=['index.html','vedlegg-a-uttrekk.html','vedlegg-c-teknisk-evidens.html']
        if options.archive_part_appendix:names.append('vedlegg-b-arkivdeler.html')
        if 'period' in options.enabled:names.append('vedlegg-d-periodevurdering.html')
        table='<table class="job-overview"><thead><tr><th>Jobb</th><th>Uttrekk</th><th>Arkivdel</th><th>Periodevurdering</th></tr></thead><tbody>'
        for entry in payload['jobs']:
            table+=f'<tr><td>{entry["job_id"]}</td><td>{entry["extraction"]}</td><td>Arkivdel</td><td>Kan ikke vurderes</td></tr>'
        table+='</tbody></table>'
        for name in names:
            body=(table+'<h2>Åpne periodevurderinger</h2><p>Kan ikke vurderes</p>'+
                  '<h2>Grupperte vurderingspunkter</h2><p>Kildegrunnlag</p>') if name=='index.html' else '<p>Gammel rapportdel</p>'
            html=f'<!doctype html><html><body><h1>{name}</h1>'+body+'</body></html>'
            (Path(directory)/(prefix+name)).write_text(html,encoding='utf8')
            (Path(directory)/(prefix+Path(name).stem+'.json')).write_text(json.dumps(payload),encoding='utf8')
        return Path(directory)/(prefix+'index.html')
    return generate


class A20ReportModelTest(unittest.TestCase):
    def test_kdrs_allows_professional_review_without_xpath(self):
        snapshot=build_snapshot(make_payload(1,missing={1}))
        record=snapshot['jobs'][0]
        self.assertFalse(record['has_depot_report'])
        self.assertIn('KDRS Query tilgjengelig',record['professional_period_status'])
        self.assertIsNone(record['counts']['folder_count'])
        self.assertEqual(snapshot['totals']['folder_count']['missing_dwm_value'],1)

    def test_approved_whole_period_and_separate_parts(self):
        snapshot=build_snapshot(make_payload(2))
        self.assertEqual(snapshot['jobs'][1]['approved_years'],[2005,2019])
        self.assertEqual(snapshot['jobs'][1]['professional_period_status'],'Godkjent – faglig vurdert')
        self.assertEqual(snapshot['jobs'][0]['archive_parts'][0]['approved_years'],[2005,2015])
        self.assertEqual(snapshot['jobs'][0]['archive_parts'][1]['professional_status'],'Under undersøkelse')
        self.assertEqual(snapshot['jobs'][0]['approved_years'],None)

    def test_unknown_is_not_zero_in_totals_and_parts(self):
        snapshot=build_snapshot(make_payload(3,missing={3}))
        self.assertEqual(snapshot['totals']['folder_count']['dwm_sum'],7)
        self.assertEqual(snapshot['totals']['folder_count']['with_dwm_value'],2)
        self.assertEqual(snapshot['totals']['folder_count']['missing_dwm_value'],1)
        self.assertEqual(snapshot['jobs'][0]['archive_parts'][0]['counts']['folder_count'],0)
        self.assertIsNone(snapshot['jobs'][0]['archive_parts'][0]['counts']['registration_count'])

    def test_kdrs_part_index_is_not_native_part_identity(self):
        base=make_payload(1)
        base['period_source_evidence']['jobs'][0]['kdrs_runs']=[{
            'report_type':'u02','import_id':'external','source_files':['u2.txt'],
            'scopes':[{'scope_id':'u2:1:Arkivdel 1','period_observed_years':[1900,2099]}]}]
        model=build_snapshot(base)
        self.assertIn('uten entydig årsgrunnlag',model['jobs'][0]['professional_period_status'])
        self.assertNotIn('kdrs',model['jobs'][0]['archive_parts'][0]['counts'])

    def test_scale_six_and_twenty_eight_and_mixed(self):
        for n,prefix in ((6,'1502'),(28,'1502'),(9,'1543')):
            with self.subTest(n=n):
                model=build_snapshot(make_payload(n,name_prefix=prefix))
                self.assertEqual(model['number_distinct'],n)
                self.assertEqual(model['archive_part_rows'],2*n)
                self.assertEqual(len(model['jobs']),n)

    def test_bad_period_identity_is_not_silently_assigned(self):
        p=make_payload(2)
        p['period_source_evidence']['jobs'][0]['job_id']='OTHER-JOB'
        model=build_snapshot(p)
        self.assertTrue(any('Kildeidentitet' in x for x in model['warnings']))
        self.assertNotIn('KDRS Query tilgjengelig',model['jobs'][0]['professional_period_status'])

    def test_html_period_correction_preserves_other_details(self):
        payload=make_payload(2)
        original = (
            '<html><body><h1>Rapport</h1>'
            '<table class="job-overview"><thead><tr><th>J</th></tr></thead><tbody>'
            '<tr><td>JOB-001</td><td>A</td><td>B</td><td>Kan ikke vurderes</td></tr>'
            '<tr><td>JOB-002</td><td>A</td><td>B</td><td>Kan ikke vurderes</td></tr></tbody></table>'
            '<h2>Åpne periodevurderinger</h2><p>Kan ikke vurderes</p>'
            '<h2>Grupperte vurderingspunkter</h2><p>Behold</p></body></html>'
        )
        result=enrich_html(original,'index.html',build_snapshot(payload))
        self.assertIn('KDRS Query tilgjengelig',result)
        self.assertIn('Godkjent – faglig vurdert',result)
        self.assertIn('<p>Behold</p>',result)
        self.assertNotIn('<td>Kan ikke vurderes</td>',result)
        self.assertNotIn('Åpne periodevurderinger',result)

    def test_csv_has_one_row_per_part_zero_and_safe_excel_labels(self):
        p=make_payload(1,parts=43)
        p['jobs'][0]['depot_report']['archive_parts'][0]['archive_part']['title']='=IMPORTXML("evil")'
        snapshot=build_snapshot(p)
        b=csv_for_page('vedlegg-b-arkivdeler.html',snapshot,p)
        self.assertTrue(b.startswith(b'\xef\xbb\xbf'))
        rows=list(csv.reader(io.StringIO(b.decode('utf-8-sig')),delimiter=';'))
        self.assertEqual(len(rows),44)
        self.assertTrue(rows[1][4].startswith("'="))
        self.assertEqual(rows[1][5],'0')
        self.assertEqual(rows[1][6],'')  # missing means unknown


class A20ReportServiceTest(unittest.TestCase):
    def test_exports_all_formats_and_appendices(self):
        p=make_payload(6,missing={3})
        baseline=copy.deepcopy(p)
        with tempfile.TemporaryDirectory() as tmp:
            dest=Path(tmp)/'out'
            result=write_report_package(dest,selected_jobs(p),opts(),prefix='test',
                    formats=('html','json','csv','pdf'),
                    _legacy_export=fake_legacy(p),
                    _pdf_renderer=lambda text:(b'%PDF-STUB\n'+text.encode('utf8')))
            self.assertEqual(result,dest/'test_index.html')
            self.assertEqual(len(list(dest.iterdir())),20)
            html=(dest/'test_index.html').read_text(encoding='utf8')
            self.assertIn('KDRS Query tilgjengelig',html)
            self.assertIn('Grupperte vurderingspunkter',html)
            self.assertIn('Godkjent – faglig vurdert',(dest/'test_index.pdf').read_bytes().decode('utf8'))
            self.assertIn('Arkivdeler – kompakt indeks',
                          (dest/'test_vedlegg-b-arkivdeler.html').read_text(encoding='utf8'))
            loaded=json.loads((dest/'test_index.json').read_text(encoding='utf8'))
            self.assertEqual(loaded['schema'],p['schema'])
            self.assertEqual(loaded['a20_report_snapshot']['number_distinct'],6)
            self.assertEqual(loaded['a20_report_snapshot']['archive_part_rows'],10)
            self.assertEqual(baseline,p) # DWM inputs left untouched

    def test_twenty_eight_jobs_and_all_part_rows_exported(self):
        p=make_payload(28,parts=3)
        writer=Mock(side_effect=fake_legacy(p))
        with tempfile.TemporaryDirectory() as tmp:
            out=write_report_package(tmp,selected_jobs(p),opts(),
                                     formats=('html','json','csv'),_legacy_export=writer)
            self.assertTrue(out.is_file())
            writer.assert_called_once()
            data=json.loads((Path(tmp)/'index.json').read_text('utf8'))
            self.assertEqual(data['a20_report_snapshot']['number_distinct'],28)
            self.assertEqual(data['a20_report_snapshot']['archive_part_rows'],84)
            part_csv=(Path(tmp)/'vedlegg-b-arkivdeler.csv').read_text(encoding='utf-8-sig')
            self.assertEqual(len(list(csv.reader(io.StringIO(part_csv),delimiter=';'))),85)

    def test_selected_sections_do_not_inject_long_period_index(self):
        p=make_payload(1)
        with tempfile.TemporaryDirectory() as tmp:
            write_report_package(tmp,selected_jobs(p),opts(full=False),
                                 formats=('html',),_legacy_export=fake_legacy(p))
            main=(Path(tmp)/'index.html').read_text('utf8')
            self.assertNotIn('a20-period-index',main)
            self.assertNotIn('Åpne periodevurderinger',main)
            self.assertIn('KDRS Query tilgjengelig',main) # overview status still corrected

    def test_professional_json_status_and_legacy_dwm_status_separate(self):
        p=make_payload(1,missing={1})
        p['jobs'][0]['period_status']='Kan ikke vurderes'
        with tempfile.TemporaryDirectory() as tmp:
            write_report_package(tmp,selected_jobs(p),opts(),formats=('json',),
                                 _legacy_export=fake_legacy(p))
            data=json.loads((Path(tmp)/'index.json').read_text('utf8'))
            job=data['jobs'][0]
            self.assertEqual(job['dwm_xpath_period_status'],'Kan ikke vurderes')
            self.assertIn('KDRS Query tilgjengelig',job['period_status'])
            self.assertEqual(job['period_status'],job['professional_period_status'])

    def test_pdf_failure_does_not_block_other_formats(self):
        p=make_payload(1)
        with tempfile.TemporaryDirectory() as tmp:
            warnings=[]
            result=write_report_package(tmp,selected_jobs(p),opts(),
                    formats=('html','json','csv','pdf'),
                    _legacy_export=fake_legacy(p),
                    _pdf_renderer=lambda html:1/0,on_warning=warnings.append)
            self.assertEqual(result.suffix,'.html')
            self.assertEqual(len(list(Path(tmp).glob('*.pdf'))),0)
            self.assertTrue(any('PDF ble ikke eksportert' in msg for msg in warnings))
            self.assertTrue((Path(tmp)/'index.csv').is_file())

    def test_pdf_only_failure_has_no_output(self):
        p=make_payload(1)
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(RuntimeError):
                write_report_package(tmp,selected_jobs(p),opts(),formats=('pdf',),
                    _legacy_export=fake_legacy(p),_pdf_renderer=lambda html:1/0)
            self.assertEqual(list(Path(tmp).iterdir()),[])

    def test_pdf_only_and_csv_only(self):
        p=make_payload(1)
        for format,expected in [('pdf',b'%PDF-TEST'),('csv',b'JOB;')]:
            with self.subTest(format=format), tempfile.TemporaryDirectory() as tmp:
                out=write_report_package(tmp,selected_jobs(p),opts(full=False,archive_parts=False),
                    formats=(format,),_legacy_export=fake_legacy(p),
                    _pdf_renderer=lambda html:b'%PDF-TEST')
                self.assertEqual(out.suffix,'.'+format)
                self.assertTrue(out.read_bytes().startswith(expected) if format=='pdf'
                                else b'JOB;' in out.read_bytes())

    def test_conflicts_are_detected_before_any_export(self):
        p=make_payload(1)
        writer=Mock(side_effect=fake_legacy(p))
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp)/'index.html').write_text('older report')
            with self.assertRaises(FileExistsError):
                write_report_package(tmp,selected_jobs(p),opts(),formats=('html',),
                                     _legacy_export=writer)
            writer.assert_not_called()
            self.assertEqual((Path(tmp)/'index.html').read_text(),'older report')

    def test_repeated_local_job_id_is_rejected_before_legacy(self):
        p=make_payload(2)
        jobs=(SimpleNamespace(job_id='JOB-001'),SimpleNamespace(job_id='JOB-001'))
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError,'Samme JOB-ID'):
                write_report_package(tmp,jobs,opts(),_legacy_export=fake_legacy(p))
            self.assertEqual(list(Path(tmp).iterdir()),[])

    def test_prefix_validation_blocks_path_escape(self):
        p=make_payload(1)
        with tempfile.TemporaryDirectory() as tmp:
            for prefix in ('../a','a\\b','x/y','a?b'):
                with self.assertRaises(ValueError):
                    write_report_package(tmp,selected_jobs(p),opts(),prefix=prefix,
                                         _legacy_export=fake_legacy(p))


if __name__=='__main__':
    unittest.main()
