"""A12 bounded-memory, source-bound page and review regression tests.

Fixtures create Work and fake *original-shaped* source artefacts, not test
monkeypatches of production modules. No UI display/GUI runtime is required.
"""
from __future__ import annotations

from hashlib import sha256
import json
import os
from pathlib import Path
import sqlite3
import sys
from tempfile import TemporaryDirectory
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import patch

from noark5_workflow.reporting.qa_paged_review_v023_a12 import (
    MODEL, PagedReviewError, build_paged_index, finding_key,
    review_page, save_review_for_page, _sha,
)
from noark5_workflow.reporting.qa_paged_v023_a8 import INDEX_MODEL


class PagedReviewTests(unittest.TestCase):
    def setUp(self):
        temp = TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.work = self.root / 'Work'
        self.work.mkdir()
        self.uid = 'A12-JOB-UID'
        self.work.joinpath('job.json').write_text(json.dumps({
            'file_type': 'dwm-work-job', 'format_version': 1,
            'job_uid': self.uid, 'job': {'job_id': 'JOB-001'}}), encoding='utf-8')
        self.rel = 'noark5_reports/depot_validation/JOB-001__RUN-12/depot_validation_report.json'
        self.depot = self.work / self.rel
        self.depot.parent.mkdir(parents=True)
        self.find_rel = self.rel.rsplit('/', 1)[0] + '/delivery-funn.jsonl'
        self.csv_rel = self.rel.rsplit('/', 1)[0] + '/delivery-funn.csv'
        self.arch_ref = 'external_evidence/arkade5/IMP/normalized/arkade5_results.json'
        self.arc_src = self.work / self.arch_ref
        self.arc_src.parent.mkdir(parents=True)
        self.arc_src.write_bytes(b'normalized')
        self.original_ref = 'external_evidence/arkade5/IMP/original/source.zip'
        self.arc_original = self.work / self.original_ref
        self.arc_original.parent.mkdir(parents=True)
        self.arc_original.write_bytes(b'original')
        self.arc_db = self.work / 'noark5_evidence/qa_index_v023_a8/one.sqlite'
        self.arc_db.parent.mkdir(parents=True)
        self.arc_rows = []
        self.dwm_rows = []
        self.snapshot = None

    def create(self, dwm=301, arkade=301):
        self.dwm_rows = []
        for n in range(dwm):
            uid = sha256(('dwm'+str(n)).encode()).hexdigest()
            self.dwm_rows.append({
                'source': 'DWM avleveringskontroll', 'test_id': 'DWM-AVLEVERING-M052',
                'severity': 'ERROR', 'message': f'Feil avleveringsverdi {n:04d}',
                'context': 'saksstatus: Under behandling', 'file': 'arkivstruktur.xml',
                'lines': [n+10], 'source_ref': self.find_rel, 'finding_uid': uid,
                'metadata_id': 'M052', 'xpath': f'/arkiv[1]/mappe[{n+1}]/saksstatus[1]',
                'object_id': f'S-{n}', 'archive_part_id': 'AD-1',
                'requires_review': True, 'delivery_value': False, 'standard_value': True,
            })
        # The A11 projector enriches context with an occurrence-specific UID.
        from noark5_workflow.reporting.qa_delivery_v023_a11 import _project
        info = {'jsonl_relative': self.find_rel, 'source_counts': {
            'M051': 0, 'M052': dwm, 'M053': 0, 'M054': 0},
            'source_xml_sha256': 'c'*64, 'version': '5.0'}
        self.projected = [_project(item, info) for item in self.dwm_rows]
        lines = b''.join((json.dumps(row,ensure_ascii=False)+'\n').encode('utf-8')
                         for row in self.dwm_rows)
        (self.work / self.find_rel).write_bytes(lines)
        (self.work / self.csv_rel).write_bytes(b'test;source\n')
        d = {'model_id':'dwm.noark5.delivery-validation.a10.v1',
             'status':'completed_with_findings','complete':True,
             'version':'5.0','automatic_approval':False,
             'finding_count':dwm,'delivery_value_findings':dwm,
             'period_review_findings':0,'source_sha256':'c'*64,
             'finding_file_sha256':_sha(self.work / self.find_rel),
             'finding_csv_sha256':_sha(self.work / self.csv_rel),
             'finding_file':'delivery-funn.jsonl', 'finding_csv':'delivery-funn.csv',
             'findings_relative':self.find_rel,
             'rules':[{'metadata_id':m,'delivery_deviations':dwm if m=='M052' else 0}
                      for m in ('M051','M052','M053','M054')]}
        self.depot.write_text(json.dumps({'report_type':'noark5_depot_validation',
                                          'delivery_validation':d}),encoding='utf-8')
        (self.depot.parent / 'artifact_manifest.json').write_text(json.dumps({
            'operation_id':'build_noark5_depot_report','job_uid':self.uid,
        }),encoding='utf-8')
        conn = sqlite3.connect(self.arc_db)
        conn.execute('CREATE TABLE findings (ordinal integer primary key, '
                     'finding_key text, severity text, test_id text, payload text)')
        self.arc_rows = []
        for n in range(arkade):
            row = {'source':'Arkade 5','test_id':'A5-'+str(n % 10),
                   'severity':'ERROR' if n < 200 else 'WARNING',
                   'message':f'Arkade avvik {n:04d}', 'context':'saksmappe',
                   'file':'arkivstruktur.xml','lines':[n+1],
                   'source_ref':self.arch_ref,'requires_review':True}
            row['finding_key'] = finding_key(row)
            self.arc_rows.append(row)
            conn.execute('INSERT INTO findings VALUES(?,?,?,?,?)',
                         (n+1,row['finding_key'],row['severity'],row['test_id'],json.dumps(row)))
        conn.commit()
        conn.close()
        meta = {'model_id':INDEX_MODEL,'complete':True,'job_uid':self.uid,
                'index_relative_path':self.arc_db.relative_to(self.work).as_posix(),
                'index_sha256':_sha(self.arc_db),
                'source_relative_path':self.arch_ref,
                'source_sha256':_sha(self.arc_src),
                'preserved_relative_path':self.original_ref,
                'original_source_sha256':_sha(self.arc_original),
                'finding_count':arkade}
        older = {'source':'DWM XPath','test_id':'XPATH','severity':'REVIEW',
                 'message':'Vurder test','context':'', 'file':'', 'lines':[],
                 'source_ref':self.rel}
        self.snapshot = {'model_id':'ikamr.dwm.noark5.qa-decision.a12.v1',
                         'work_identity':{'job_uid':self.uid,'job_id':'JOB-001'},
                         'evidence_manifest':[{'kind':'dwm_depot','path':self.rel,
                                                'sha256':_sha(self.depot)}],
                         'findings_complete': not (dwm>250 or arkade>250),
                         'full_finding_count':dwm+arkade+1,
                         'a8_paged_index':meta,
                         'arkade':{'a8_paged_index':meta,
                                   'findings_complete':arkade<=250},
                         'delivery_qa':{'status':'completed_with_findings',
                                        'finding_count':dwm,'source':self.find_rel,
                                        'source_sha256':'c'*64},
                         'findings':[older,*self.arc_rows[:250],*self.projected[:250]]}
        return self.snapshot

    def test_all_DWM_and_arkade_findings_are_present_beyond_preview(self):
        shot = self.create()
        self.assertEqual(len(shot['findings']), 501)
        info = build_paged_index(self.work,shot)
        self.assertEqual(info['finding_count'],603)
        self.assertEqual(info['source_counts']['Arkade 5'],301)
        self.assertEqual(info['source_counts']['DWM avleveringskontroll'],301)
        self.assertEqual(info['severity_counts']['WARNING'],101)
        self.assertFalse(info['automatic_approval'])
        page = review_page(self.work,info,page=6,page_size=100)
        self.assertEqual(page['total'],603)
        self.assertEqual(len(page['rows']),3)
        self.assertTrue(page['complete'])
        self.assertEqual(len({finding_key(x) for x in review_page(self.work,info,page=0)['rows']}),100)

    def test_server_side_search_severity_source_and_test_filters(self):
        info=build_paged_index(self.work,self.create())
        page=review_page(self.work,info,severity='WARNING',source='Arkade 5',page_size=100)
        self.assertEqual(page['total'],101)
        page=review_page(self.work,info,test_id='DWM-AVLEVERING-M052',search='0007')
        self.assertEqual(page['total'],1)
        self.assertEqual(page['rows'][0]['object_id'],'S-7')
        page=review_page(self.work,info,search='avvik 0300')
        self.assertEqual(page['total'],1)
        self.assertEqual(page['rows'][0]['source'],'Arkade 5')

    def test_reviews_and_pending_filter_work_outside_preview(self):
        info=build_paged_index(self.work,self.create(500,0))
        row=review_page(self.work,info,severity='ERROR',page=3,page_size=100)['rows'][0]
        self.assertEqual(row['object_id'],'S-300')
        event={'status':'clarification_needed','comment':'Kontrollert oppfølging',
               'include_in_ks':True,'include_in_depot':False}
        reviews={row['finding_key']:event}
        page=review_page(self.work,info,severity='ERROR',reviewed='reviewed',reviews=reviews)
        self.assertEqual(page['total'],1)
        self.assertEqual(page['rows'][0]['review_status'],'clarification_needed')
        self.assertEqual(page['rows'][0]['review_comment'],'Kontrollert oppfølging')
        self.assertFalse(page['rows'][0]['include_in_depot'])
        remaining=review_page(self.work,info,severity='ERROR',reviewed='pending',reviews=reviews)
        self.assertEqual(remaining['total'],499)

    def test_paged_save_uses_original_ledger_and_exact_off_preview_row(self):
        info=build_paged_index(self.work,self.create(501,0))
        row=review_page(self.work,info,page=5,page_size=100)['rows'][0]
        self.assertEqual(row['object_id'],'S-500')
        fake=ModuleType('noark5_workflow.reporting.qa_review_v021_a13')
        evidence=[]
        def persist(root, shot, selected, **kwargs):
            evidence.append((root,shot,selected,kwargs))
            return {'event_id':'EVENT-1','finding_key':finding_key(selected),
                    'status':kwargs['status']}
        fake.record_review=persist
        with patch.dict(sys.modules, {'noark5_workflow.reporting.qa_review_v021_a13':fake}):
            result=save_review_for_page(self.work,self.snapshot,info,row,
                status='clarification_needed',comment='Kontroller arkivdel',
                user=SimpleNamespace(user_id='u',as_dict=lambda:{'user_id':'u'}))
        self.assertEqual(result['finding_key'],finding_key(row))
        self.assertEqual(len(evidence),1)
        self.assertEqual(len(evidence[0][1]['findings']),1)
        self.assertEqual(evidence[0][2]['finding_key'],row['finding_key'])
        self.assertEqual(evidence[0][3]['comment'],'Kontroller arkivdel')
        self.assertEqual(len(self.snapshot['findings']),251) # Original preview untouched.
        tampered=dict(row,message='Forfalsket')
        with self.assertRaises(PagedReviewError):
            save_review_for_page(self.work,self.snapshot,info,tampered,
                status='clarification_needed',comment='bad',user=None)

    def test_index_reuse_is_stable_and_does_not_rewrite_db(self):
        info=build_paged_index(self.work,self.create())
        db=self.work/info['index_relative_path']
        marker=db.stat().st_mtime_ns
        self.assertEqual(build_paged_index(self.work,self.snapshot)['index_sha256'],info['index_sha256'])
        self.assertEqual(db.stat().st_mtime_ns,marker)
        self.assertEqual(len(list((self.work / 'noark5_evidence/qa_review_index_v023_a12').glob('*.sqlite'))),1)

    def test_changed_original_or_bad_sha_or_count_fail_without_complete_index(self):
        shot=self.create()
        self.arc_original.write_bytes(b'CHANGED ORIGINAL')
        with self.assertRaisesRegex(PagedReviewError,'original'):
            build_paged_index(self.work,shot)
        self.assertFalse(list((self.work / 'noark5_evidence/qa_review_index_v023_a12').glob('*.json')))

    def test_silent_gap_in_full_count_fails_closed(self):
        shot=self.create()
        shot['full_finding_count']=shot['full_finding_count']+1
        with self.assertRaisesRegex(PagedReviewError,'Forventet'):
            build_paged_index(self.work,shot)

    def test_wrong_work_and_depot_sha_fail_closed(self):
        shot=self.create(1,0)
        shot['work_identity']['job_uid']='wrong'
        with self.assertRaisesRegex(PagedReviewError,'jobber|identitet'):
            build_paged_index(self.work,shot)
        shot['work_identity']['job_uid']=self.uid
        self.depot.write_text('mutated',encoding='utf-8')
        with self.assertRaisesRegex(PagedReviewError,'endret'):
            build_paged_index(self.work,shot)

    def test_page_input_validation(self):
        info=build_paged_index(self.work,self.create())
        for args in ({'page':-1},{'page_size':251},{'reviewed':'invalid'},
                     {'severity':'SERIOUS'},{'search':'X'*401}):
            with self.subTest(args=args),self.assertRaises(PagedReviewError):
                review_page(self.work,info,**args)

    def test_index_file_mutation_blocks_paged_review_saves(self):
        info=build_paged_index(self.work,self.create(1,0))
        row=review_page(self.work,info)['rows'][0]
        with (self.work/info['index_relative_path']).open('ab') as f:
            f.write(b'altered')
        with self.assertRaisesRegex(PagedReviewError,'endret'):
            save_review_for_page(self.work,self.snapshot,info,row,
                status='clarification_needed',comment='?',user=None)

    def test_changed_source_invalidates_cached_index_and_page(self):
        info=build_paged_index(self.work,self.create(301,301))
        self.arc_src.write_bytes(b'CHANGED normalized bytes')
        with self.assertRaisesRegex(PagedReviewError,'endret|SHA-256'):
            build_paged_index(self.work,self.snapshot)
        with self.assertRaisesRegex(PagedReviewError,'endret'):
            review_page(self.work,info)

    def test_source_is_not_written_by_paging_or_review_validation(self):
        info=build_paged_index(self.work,self.create())
        recorded = {self.arc_src:_sha(self.arc_src),
                    self.arc_original:_sha(self.arc_original),
                    self.work/self.find_rel:_sha(self.work/self.find_rel)}
        review_page(self.work,info,page=5,page_size=100)
        row=review_page(self.work,info)['rows'][0]
        with self.assertRaises(PagedReviewError):
            save_review_for_page(self.work,self.snapshot,info,dict(row,message='changed'),
                                 status='clarification_needed',comment='no',user=None)
        self.assertEqual({p:_sha(p) for p in recorded},recorded)

    @unittest.skipUnless(os.environ.get('DWM_A12_STRESS') == '1',
                         'Set DWM_A12_STRESS=1 to run 100,001-row pagination test')
    def test_100001_finding_index_and_final_page(self):
        info=build_paged_index(self.work,self.create(1,100000))
        self.assertEqual(info['finding_count'],100002) # 1 DWM + 100k Arkade + 1 other
        last=review_page(self.work,info,page=1000,page_size=100)
        self.assertEqual(last['total'],100002)
        self.assertEqual(len(last['rows']),2)
        self.assertEqual(last['total_all'],100002)
        # A nonzero Arkade detail beyond the old 300/250 boundaries remains navigable.
        p=review_page(self.work,info,source='Arkade 5',page=999,page_size=100)
        self.assertEqual(p['total'],100000)
        self.assertEqual(len(p['rows']),100)
        self.assertIn('avvik',p['rows'][0]['message'])

    def test_cancel_creates_no_published_metadata(self):
        shot=self.create()
        with self.assertRaisesRegex(PagedReviewError,'avbrutt'):
            build_paged_index(self.work,shot,cancelled=lambda:True)
        self.assertFalse(list((self.work/'noark5_evidence/qa_review_index_v023_a12').glob('*.json')))


if __name__ == '__main__':
    unittest.main()
