"""a20.1 saved Noark 5 content profiles: no XPath reruns, source-safe scope."""
from __future__ import annotations

import csv
import io
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest

from noark5_workflow.reporting.report_content_a201 import (
    build_job_content_profile, find_normal_xpath_run, _distribution,
)
from noark5_workflow.reporting.report_content_views_a201 import augment_content_html, content_csv
from noark5_workflow.reporting.report_model_a20 import build_snapshot
from noark5_workflow.reporting.report_service_a20 import write_report_package
from test_a20_report_service import make_payload, fake_legacy, opts


def _job(home: Path, jid='JOB-001'):
    return SimpleNamespace(job_id=jid, work_operations=home)


def _run(home: Path, jid='JOB-001', token='RUN-20261019-100000-abcdef'):
    root=home/'dwm'/'noark5_tests'/'xpath'/(jid+'__'+token)
    (root/'results').mkdir(parents=True,exist_ok=True)
    (root/'artifact_manifest.json').write_text(json.dumps({'job_id':jid}),encoding='utf8')
    return root


def _result(run: Path, test_id: str, whole: dict, part_data=None, *, status='ok'):
    values=dict(whole)
    if part_data is not None:
        values['_archive_parts']=[{'archive_part':{'system_id':sid,'title':sid},'values':v}
                                  for sid,v in part_data.items()]
    (run/'results'/(test_id.replace('.','_')+'.json')).write_text(json.dumps({
        'test_id':test_id, 'status':status, 'values':values}),encoding='utf8')


def _index(run: Path, test_ids, *, profile='normal'):
    (run/'index.json').write_text(json.dumps({
        'execution_profile':profile,
        'tests':[{'test_id':t,'status':'ok',
                  'file':'results/'+t.replace('.','_')+'.json'} for t in test_ids],
    }),encoding='utf8')


def _data(run: Path):
    value={
        'kdrs.c08': ({'folder_type_counts':{'Saksmappe':7,'moetemappe':0}},
                     {'NATIVE-1':{'folder_type_counts':{'Saksmappe':3}},
                      'NATIVE-2':{'folder_type_counts':{'Saksmappe':4}}}),
        'kdrs.c13': ({'status_counts':{'Under behandling':2,'Avsluttet':5}},
                      {'NATIVE-1':{'status_counts':{'Avsluttet':1}},
                       'NATIVE-2':{'status_counts':{'Avsluttet':4}}}),
        'kdrs.c14': ({'type_counts':{'journalpost':9,'arkivnotat':1}},
                     {'NATIVE-1':{'type_counts':{'journalpost':3}},
                      'NATIVE-2':{'type_counts':{'journalpost':6}}}),
        'kdrs.c15': ({'journalpost_type_counts':{
                          'Inngående dokument':4,'Utgående dokument':3,
                          'Organinternt dokument for oppfølging':2},
                      'journal_status_counts':{'Journalført':9},
                      'main_document_count':8},
                     {'NATIVE-1':{'journalpost_type_counts':{'Inngående dokument':2},
                                  'main_document_count':2},
                      'NATIVE-2':{'journalpost_type_counts':{'Utgående dokument':3,
                                      'Organinternt dokument for oppfølging':2},
                                  'main_document_count':6}}),
        'kdrs.c21': ({'document_type_counts':{'Brev':12}},
                     {'NATIVE-1':{'document_type_counts':{'Brev':3}}}),
        'kdrs.c23': ({'status_counts':{'Dokumentet er ferdigstilt':9}},
                     {'NATIVE-1':{'status_counts':{'Dokumentet er ferdigstilt':3}}}),
        'kdrs.c24': ({'variant_format_counts':{'Arkivformat':10},
                      'format_counts':{'application/pdf':10}},
                     {'NATIVE-1':{'variant_format_counts':{'Arkivformat':4}}}),
        'kdrs.f05': ({'correspondence_party_count':17,
                      'correspondence_party_type_counts':{'Avsender':10,'Mottaker':7}},
                     {'NATIVE-1':{'correspondence_party_count':7}}),
        'kdrs.f06': ({'writeoff_method_count':5,'method_counts':{'TE':5}},
                     {'NATIVE-1':{'method_counts':{'TE':2}}}),
        'kdrs.f08': ({'screening_count':2,'access_restriction_counts':{'UO':2}},
                     {'NATIVE-1':{'screening_count':0}}),
        'kdrs.f13': ({'deletion_count':0,'deletion_type_counts':{}},None),
    }
    for tid,(whole,parts) in value.items():
        _result(run,tid,whole,parts)
    _index(run,value)


class A201SourceTests(unittest.TestCase):
    def test_native_journalpost_and_other_distributions_without_rerun(self):
        with TemporaryDirectory() as temp:
            home=Path(temp)
            run=_run(home)
            _data(run)
            report={'evidence':{'source_xpath_run':str(run)}}
            profile=build_job_content_profile(_job(home),report)
            self.assertEqual(profile['status'],'available')
            self.assertIn('kdrs.c15',profile['tests_read'])
            self.assertEqual(profile['distributions']['journalpost_type']['value']['Inngående dokument'],4)
            self.assertEqual(profile['distributions']['journalpost_type']['value']['Utgående dokument'],3)
            self.assertEqual(profile['archive_parts']['NATIVE-1']['distributions']['journalpost_type']['value']['Inngående dokument'],2)
            self.assertEqual(profile['archive_parts']['NATIVE-2']['distributions']['journalpost_type']['value']['Utgående dokument'],3)
            self.assertEqual(profile['scalars']['main_document_links']['value'],8)
            self.assertEqual(profile['scalars']['deletions']['value'],0)
            self.assertEqual(profile['distributions']['document_format']['value']['application/pdf'],10)

    def test_moved_drive_relinks_only_same_run_name(self):
        with TemporaryDirectory() as temp:
            home=Path(temp)
            run=_run(home);_data(run)
            old='K:\\old-disk\\repository_operations\\dwm\\noark5_tests\\xpath\\'+run.name
            path,why=find_normal_xpath_run(_job(home),{'evidence':{'source_xpath_run':old}})
            self.assertEqual(path,run)
            self.assertEqual(why,'')
            missing={'evidence':{'source_xpath_run':'X:\\other\\JOB-001__RUN-unknown'}}
            path,why=find_normal_xpath_run(_job(home),missing)
            self.assertIsNone(path)
            self.assertIn('finnes ikke',why)

    def test_missing_and_failing_test_are_unknown_not_zero(self):
        with TemporaryDirectory() as temp:
            home=Path(temp);run=_run(home)
            _result(run,'kdrs.c15',{'journalpost_type_counts':{'':0}},status='error')
            _index(run,['kdrs.c15'])
            p=build_job_content_profile(_job(home),{'evidence':{'source_xpath_run':str(run)}})
            self.assertNotIn('journalpost_type',p['distributions'])
            self.assertEqual(p['status'],'not_available')
            self.assertIsNone(_distribution({'x':-1}))

    def test_wrong_job_manifest_does_not_attach(self):
        with TemporaryDirectory() as temp:
            home=Path(temp);run=_run(home)
            _data(run)
            (run/'artifact_manifest.json').write_text(json.dumps({'job_id':'JOB-999'}),'utf8')
            p=build_job_content_profile(_job(home),{'evidence':{'source_xpath_run':str(run)}})
            self.assertEqual(p['status'],'not_available')

    def test_regression_run_is_not_a_master_source(self):
        with TemporaryDirectory() as temp:
            home=Path(temp);run=_run(home);_data(run)
            _index(run,['kdrs.c15'],profile='regression')
            p=build_job_content_profile(_job(home),{'evidence':{'source_xpath_run':str(run)}})
            self.assertEqual(p['status'],'not_available')


class A201ReportTests(unittest.TestCase):
    def _payload(self,run):
        p=make_payload(1)
        p['jobs'][0]['depot_report']['evidence']={'source_xpath_run':str(run)}
        for i,row in enumerate(p['jobs'][0]['depot_report']['archive_parts']):
            row['archive_part']['system_id']=f'NATIVE-{i+1}'
        for i,row in enumerate(p['period_source_evidence']['jobs'][0]['archive_parts']):
            row['system_id']=f'NATIVE-{i+1}'
        return p

    def test_four_formats_same_values_and_optional_content_csv(self):
        with TemporaryDirectory() as temp:
            home=Path(temp)/'work';run=_run(home);_data(run)
            package=self._payload(run)
            job=_job(home)
            directory=Path(temp)/'out'
            result=write_report_package(directory,[job],opts(),prefix='1502',
                    formats=('html','pdf','json','csv'),
                    _legacy_export=fake_legacy(package),
                    _pdf_renderer=lambda text:b'%PDF-TEST'+text.encode('utf8'))
            self.assertTrue(result.is_file())
            html=(directory/'1502_index.html').read_text('utf8')
            self.assertIn('Inngående dokument: 4',html)
            self.assertIn('Journalposter etter type',html)
            a=(directory/'1502_vedlegg-a-uttrekk.html').read_text('utf8')
            self.assertIn('Avskrivningsmåte',a)
            b=(directory/'1502_vedlegg-b-arkivdeler.html').read_text('utf8')
            self.assertIn('NATIVE-1',b)
            self.assertIn('Inngående dokument',b)
            self.assertIn('Inngående dokument',
                          (directory/'1502_index.pdf').read_bytes().decode('utf8'))
            snap=json.loads((directory/'1502_index.json').read_text('utf8'))['a20_report_snapshot']
            self.assertEqual(snap['jobs'][0]['content_profile']['distributions']['journalpost_type']['value']['Inngående dokument'],4)
            csv_path=directory/'1502_innholdsprofil.csv'
            self.assertTrue(csv_path.is_file())
            rows=list(csv.reader(io.StringIO(csv_path.read_text('utf-8-sig')),delimiter=';'))
            self.assertTrue(any('NATIVE-1' in row and 'Inngående dokument' in row for row in rows))
            self.assertTrue(any('Journalposter – type' in row for row in rows))
            self.assertTrue(any('0' in row and 'Slettinger' in ' '.join(row) for row in rows))

    def test_medium_shows_types_full_in_appendix_no_false_zero(self):
        with TemporaryDirectory() as temp:
            home=Path(temp)/'work';run=_run(home);_data(run)
            p=self._payload(run)
            snap=build_snapshot(p)
            from noark5_workflow.reporting.report_content_a201 import attach_content_profiles
            snap=attach_content_profiles(snap,[_job(home)],p)
            base='<html><body><h1>Demo</h1><h2>Teknisk kontroll</h2></body></html>'
            out=augment_content_html(base,'index.html',snap,level='Medium',enabled=('totals',))
            self.assertIn('Inngående dokument',out)
            self.assertNotIn('Datadekning for type-',out)
            simple=augment_content_html(base,'index.html',snap,level='Enkel',enabled=('overview',))
            self.assertNotIn('Inngående dokument',simple)
            no_source=make_payload(1,missing={1})
            self.assertEqual(build_snapshot(no_source)['jobs'][0]['counts']['folder_count'],None)

    def test_twenty_eight_job_scoped_xpath_sources_no_mixed_totals(self):
        with TemporaryDirectory() as temp:
            root=Path(temp)
            payload=make_payload(28)
            jobs=[]
            for i,entry in enumerate(payload['jobs'],1):
                home=root/entry['job_id']
                job=_job(home,entry['job_id'])
                jobs.append(job)
                run=_run(home,entry['job_id'])
                _result(run,'kdrs.c15',{'journalpost_type_counts':{'Inngående dokument':i}})
                _index(run,['kdrs.c15'])
                entry['depot_report']['evidence']={'source_xpath_run':str(run)}
            from noark5_workflow.reporting.report_content_a201 import attach_content_profiles
            snap=attach_content_profiles(build_snapshot(payload),jobs,payload)
            self.assertEqual(len(snap['jobs']),28)
            values=[j['content_profile']['distributions']['journalpost_type']['value']['Inngående dokument']
                    for j in snap['jobs']]
            self.assertEqual(values,list(range(1,29)))
            self.assertEqual(sum(values),406)

    def test_same_code_in_six_jobs_is_only_sum_of_available(self):
        with TemporaryDirectory() as temp:
            base=Path(temp)
            p=make_payload(6)
            jobs=[]
            for i,entry in enumerate(p['jobs'],1):
                home=base/str(i)
                job=_job(home,entry['job_id'])
                jobs.append(job)
                if i!=3:
                    run=_run(home,entry['job_id']);_data(run)
                    entry['depot_report']['evidence']={'source_xpath_run':str(run)}
            from noark5_workflow.reporting.report_content_a201 import attach_content_profiles
            snap=attach_content_profiles(build_snapshot(p),jobs,p)
            html=augment_content_html('<body><h2>Teknisk kontroll</h2></body>',
                     'index.html',snap,level='Medium',enabled=('totals',))
            self.assertIn('5/6 uttrekk',html)
            self.assertIn('Inngående dokument',html)
            self.assertIn('20',html)  # 5*4, not 6*4


if __name__ == '__main__':
    unittest.main()
