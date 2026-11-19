"""A13: full KS/depot export, source identity, recipient selection, atomicity.

Loads the A12 fixtures in isolation, and stubs only the pre-existing append-only
review reader / destination safety entrypoint unavailable in the local sandbox.
Windows full-suite tests use the real implementations unchanged.
"""
from __future__ import annotations

import csv
from hashlib import sha256
import importlib.util
import json
import os
from pathlib import Path
import sys
from types import ModuleType
from unittest.mock import patch
import unittest

from noark5_workflow.reporting.qa_complete_report_v023_a13 import (
    CompleteReportError, MODEL, _csv_cell, _event_revision, _review_fields,
    export_complete_reports, preview_complete_summary,
)
from noark5_workflow.reporting.qa_paged_review_v023_a12 import (
    build_paged_index, review_page,
)

ROOT = Path(__file__).resolve().parents[1]
A12_TEST = ROOT.parent / 'dwm_a12/tests/test_v023_a12_paged_review.py'
# In the user's repository the A12 test resides in the same tests/ directory.
if not A12_TEST.is_file():
    A12_TEST = ROOT / 'tests/test_v023_a12_paged_review.py'


def _a12_fixture():
    spec = importlib.util.spec_from_file_location('_a13_test_fixture_a12', A12_TEST)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    fixture = module.PagedReviewTests(methodName='test_all_DWM_and_arkade_findings_are_present_beyond_preview')
    fixture.setUp()
    return fixture


def _old_api_modules(events):
    review = ModuleType('noark5_workflow.reporting.qa_review_v021_a13')
    review._read_events = lambda _work: list(events)
    destination = ModuleType('noark5_workflow.reporting.qa_decision_v021_a13')
    def check(target, work, job, jobs):
        if target.exists() or target.is_symlink():
            raise FileExistsError(str(target))
        if not target.parent.is_dir() or target.parent.is_symlink():
            raise ValueError('Utrygg overordnet målmappe')
        if target == work or target.is_relative_to(work) or work.is_relative_to(target):
            raise ValueError('Målmappe kan ikke være Work')
        for k in ('source_extraction','source_root','source_unzipped','output_root','archive_root'):
            raw = (job.get('job') or {}).get(k)
            if raw and Path(raw).is_absolute():
                p=Path(raw).resolve(strict=False)
                if target == p or target.is_relative_to(p):
                    raise ValueError('Målmappe kan ikke være Source')
    destination._safe_destination = check
    return {review.__name__: review, destination.__name__: destination}


class CompleteReportTests(unittest.TestCase):
    def setUp(self):
        self.fixture = _a12_fixture()
        self.addCleanup(self.fixture.doCleanups)
        self.work = self.fixture.work
        self.parent = self.fixture.root / 'rapportmaal'
        self.parent.mkdir()
        self.events=[]
        self.patches = patch.dict(sys.modules, _old_api_modules(self.events))
        self.patches.start()
        self.addCleanup(self.patches.stop)

    def prepare(self, dwm=301, arkade=301):
        self.snapshot = self.fixture.create(dwm, arkade)
        self.index = build_paged_index(self.work, self.snapshot)
        self.target = self.parent / 'UTKAST-A13'
        return self.index

    def report(self, *, page_rows=90, **kwargs):
        return export_complete_reports(self.work, self.snapshot, self.index,
                                       self.target, page_rows=page_rows, **kwargs)

    def test_603_findings_both_reports_and_all_html_pages(self):
        self.prepare()
        result = self.report()
        self.assertEqual(result['finding_count'],603)
        self.assertTrue(result['index'].is_file())
        self.assertTrue(result['ks_html'].is_file())
        self.assertTrue(result['depot_html'].is_file())
        self.assertEqual(len(list(self.target.glob('ks-detaljer/*.html'))),7)
        self.assertEqual(len(list(self.target.glob('depot-detaljer/*.html'))),7)
        for scope in ('ks','depot'):
            lines=(self.target/(scope+'-funn.jsonl')).read_text(encoding='utf-8').splitlines()
            self.assertEqual(len(lines),603)
            objects=[json.loads(s) for s in lines]
            self.assertEqual(sum(x['source']=='DWM avleveringskontroll' for x in objects),301)
            self.assertEqual(sum(x['source']=='Arkade 5' for x in objects),301)
            self.assertEqual(sum(x['source']=='DWM XPath' for x in objects),1)
            with (self.target/(scope+'-funn.csv')).open('r',encoding='utf-8-sig',newline='') as inp:
                self.assertEqual(len(list(csv.DictReader(inp,delimiter=';'))),603)
        summary=json.loads((self.target/'rapportgrunnlag.json').read_text(encoding='utf-8'))
        self.assertEqual(summary['severity_counts']['ERROR'],501)
        self.assertEqual(summary['severity_counts']['WARNING'],101)
        self.assertFalse(summary['automatic_approval'])
        self.assertEqual(summary['report_status'],'UTKAST_IKKE_GODKJENT')
        self.assertIn('IKKE GODKJENT',result['depot_html'].read_text(encoding='utf-8'))

    def test_all_originals_preserved_and_comments_selected_per_recipient(self):
        self.prepare(5,4)
        dwm=review_page(self.work,self.index,source='DWM avleveringskontroll')['rows'][0]
        ark=review_page(self.work,self.index,source='Arkade 5')['rows'][0]
        self.events.extend([
            {'job_uid':self.fixture.uid,'depot_report_sha256':self.index['depot_sha256'],
             'finding_key':dwm['finding_key'],'status':'requires_clarification',
             'comment':'KS <script>alert(1)</script>', 'include_in_ks':True,
             'include_in_depot':False,'author':{'display_name':'Saksbehandler'},
             'created_utc':'2026-11-19T00:00:00Z'},
            {'job_uid':self.fixture.uid,'depot_report_sha256':self.index['depot_sha256'],
             'finding_key':ark['finding_key'],'status':'context_documented',
             'comment':'BARE DEPOT SAK', 'include_in_ks':False,
             'include_in_depot':True,'author':{'display_name':'Arkivar'},
             'created_utc':'2026-11-19T00:00:00Z'},
        ])
        # The fake existing review reader is patched to the same mutable list.
        result=self.report(page_rows=3)
        self.assertEqual(result['reviewed_count'],2)
        self.assertEqual(result['reviews_in_ks'],1)
        self.assertEqual(result['reviews_in_depot'],1)
        ks=''.join(f.read_text(encoding='utf-8') for f in (self.target/'ks-detaljer').glob('*.html'))
        depot=''.join(f.read_text(encoding='utf-8') for f in (self.target/'depot-detaljer').glob('*.html'))
        self.assertIn('KS &lt;script&gt;alert(1)&lt;/script&gt;',ks)
        self.assertNotIn('<script>alert(1)</script>',ks)
        self.assertNotIn('BARE DEPOT SAK',ks)
        self.assertIn('BARE DEPOT SAK',depot)
        self.assertNotIn('KS &lt;script&gt;',depot)
        records=[json.loads(s) for s in (self.target/'ks-funn.jsonl').read_text('utf-8').splitlines()]
        excluded=next(x for x in records if x['finding_key']==ark['finding_key'])
        self.assertEqual(excluded['review_comment'],'')
        self.assertFalse(excluded['review_selected_for_report'])
        self.assertEqual(excluded['severity'],ark['severity'])

    def test_report_csv_formula_protection_without_modifying_jsonl(self):
        self.prepare(0,0)
        # The single historical DWM row has user-provided content.
        self.assertEqual(_csv_cell('  =HYPERLINK(...)'),"'  =HYPERLINK(...)")
        self.assertEqual(_csv_cell('\t=1'),"'\t=1")
        self.assertEqual(_csv_cell(['A','B']), '["A","B"]')
        self.assertEqual(_csv_cell('Arkivført'), 'Arkivført')
        self.report()
        self.assertIn('DWM XPath', (self.target/'ks-funn.csv').read_text('utf-8-sig'))

    def test_invalid_source_hash_blocks_export_without_directory(self):
        self.prepare()
        self.fixture.arc_src.write_bytes(b'modified')
        with self.assertRaises((ValueError,OSError)):
            self.report()
        self.assertFalse(self.target.exists())
        self.assertFalse(list(self.parent.glob('.dwm-a13-*')))

    def test_cancel_before_export_creates_nothing(self):
        self.prepare(100,0)
        with self.assertRaisesRegex(CompleteReportError,'avbrutt'):
            self.report(cancelled=lambda:True)
        self.assertFalse(self.target.exists())
        self.assertFalse(list(self.parent.glob('.dwm-a13-*')))

    def test_cancel_after_opening_stage_discards_all_partial_files(self):
        self.prepare(300,0)
        state={'call':0}
        def cancel():
            state['call']+=1
            return state['call']>65
        with self.assertRaisesRegex(CompleteReportError,'avbrutt'):
            self.report(cancelled=cancel)
        self.assertFalse(self.target.exists())
        self.assertFalse(list(self.parent.glob('.dwm-a13-*')))

    def test_missing_or_foreign_source_job_fails_closed(self):
        self.prepare(10,0)
        self.snapshot['work_identity']['job_uid']='FOREIGN'
        with self.assertRaises((CompleteReportError, ValueError)):
            self.report()
        self.assertFalse(self.target.exists())

    def test_existing_destination_never_overwritten(self):
        self.prepare(10,0)
        self.target.mkdir()
        sentinel=self.target/'sentinel.txt'
        sentinel.write_text('KEEP', encoding='utf-8')
        with self.assertRaises((CompleteReportError, ValueError, OSError)):
            self.report()
        self.assertEqual(sentinel.read_text(encoding='utf-8'),'KEEP')
        self.assertFalse(list(self.parent.glob('.dwm-a13-*')))

    def test_changes_to_review_register_during_export_block_publication(self):
        self.prepare(1100,0)
        row=review_page(self.work,self.index,page=0)['rows'][0]
        review={'job_uid':self.fixture.uid,'depot_report_sha256':self.index['depot_sha256'],
                'finding_key':row['finding_key'],'status':'context_documented',
                'comment':'opprinnelig','include_in_ks':True,'include_in_depot':True}
        self.events.append(review)
        def mutate(n):
            review['comment']='endret mens rapport ble laget'
        with self.assertRaisesRegex(CompleteReportError,'endret'):
            self.report(progress=mutate)
        self.assertFalse(self.target.exists())
        self.assertFalse(list(self.parent.glob('.dwm-a13-*')))

    def test_original_source_mutation_during_export_blocks_publication(self):
        self.prepare(1100,0)
        def mutate(n):
            self.fixture.arc_src.write_bytes(b'CHANGED AFTER EXPORT')
        with self.assertRaisesRegex((CompleteReportError, ValueError),'endret|SHA-256'):
            self.report(progress=mutate)
        self.assertFalse(self.target.exists())
        self.assertFalse(list(self.parent.glob('.dwm-a13-*')))

    def test_manifest_covers_each_published_file_and_input_revision(self):
        self.prepare(311,8)
        result=self.report(page_rows=25)
        m=json.loads(result['manifest'].read_text(encoding='utf-8'))
        self.assertTrue(m['complete'])
        self.assertFalse(m['automatic_approval'])
        self.assertEqual(m['finding_count'],320)
        self.assertEqual(m['a12_index_sha256'],self.index['index_sha256'])
        self.assertEqual(m['depot_report_sha256'],self.index['depot_sha256'])
        self.assertEqual(m['reviewed_finding_count'],0)
        for rel,info in m['published_files'].items():
            file=self.target/rel
            self.assertTrue(file.is_file(),rel)
            self.assertEqual(sha256(file.read_bytes()).hexdigest(),info['sha256'],rel)
        actual={f.relative_to(self.target).as_posix() for f in self.target.rglob('*') if f.is_file()}
        self.assertEqual(actual,set(m['published_files'])|{'evidensmanifest.json'})

    def test_html_and_json_escape_untrusted_content(self):
        shot=self.fixture.create(0,0)
        shot['findings'][0]['message'] = '<script>evil()</script>'
        self.snapshot=shot
        self.index=build_paged_index(self.work,shot)
        self.target=self.parent/'UTKAST-A13'
        self.report()
        pages=''.join(f.read_text('utf-8') for f in (self.target/'ks-detaljer').glob('*.html'))
        self.assertIn('&lt;script&gt;evil()&lt;/script&gt;',pages)
        self.assertNotIn('<script>evil()</script>',pages)
        self.assertIn('<script>evil()</script>',(self.target/'ks-funn.jsonl').read_text('utf-8'))

    def test_preview_is_based_on_full_index_not_snapshot_250(self):
        self.prepare()
        text=preview_complete_summary(self.work,self.snapshot,self.index)
        self.assertIn('603',text)
        self.assertIn('UTKAST',text)
        self.assertNotIn('<tr><td>1</td><td><b>',text)
        self.assertFalse(self.target.exists())

    def test_section_selection_cannot_remove_full_register(self):
        self.prepare(301,0)
        self.report(sections=('summary',))
        self.assertEqual(len((self.target/'ks-funn.jsonl').read_text('utf-8').splitlines()),302)
        self.assertTrue((self.target/'ks-detaljer/side-000001.html').is_file())
        self.assertIn('302', (self.target/'ks-rapport-utkast.html').read_text('utf-8'))

    def test_no_sections_rejected_before_stage(self):
        self.prepare(5,0)
        with self.assertRaisesRegex(CompleteReportError,'utvalg'):
            self.report(sections=())
        self.assertFalse(self.target.exists())

    def test_committed_version_and_distribution_metadata_agree(self):
        import re
        namespace={}
        exec((ROOT/'version.py').read_text('utf-8'),namespace)
        self.assertEqual(namespace['VERSION'],'0.2.3-a13')
        project=(ROOT/'pyproject.toml').read_text('utf-8')
        self.assertRegex(project, r'(?m)^version\s*=\s*"0\.2\.3a13"\s*$')

    def test_selected_csv_formula_comment_protected(self):
        self.prepare(1,0)
        row=review_page(self.work,self.index,source='DWM avleveringskontroll')['rows'][0]
        self.events.append({
            'job_uid':self.fixture.uid,
            'depot_report_sha256':self.index['depot_sha256'],
            'finding_key':row['finding_key'],
            'status':'context_documented','comment':'=HYPERLINK("https://example.org","A")',
            'include_in_ks':True,'include_in_depot':False,
            'author':{'display_name':'=SUM(A1)'},'created_utc':'2026-11-19T00:00:00Z',
        })
        self.report()
        with (self.target/'ks-funn.csv').open('r',encoding='utf-8-sig',newline='') as fp:
            selected=next(r for r in csv.DictReader(fp,delimiter=';')
                          if r['finding_key']==row['finding_key'])
        self.assertTrue(selected['review_comment'].startswith("'="))
        self.assertTrue(selected['reviewed_by'].startswith("'="))
        with (self.target/'depot-funn.csv').open('r',encoding='utf-8-sig',newline='') as fp:
            excluded=next(r for r in csv.DictReader(fp,delimiter=';')
                          if r['finding_key']==row['finding_key'])
        self.assertEqual(excluded['review_comment'],'')
        self.assertEqual(excluded['reviewed_by'],'')
        original=next(json.loads(v) for v in (self.target/'ks-funn.jsonl').read_text('utf-8').splitlines()
                      if json.loads(v)['finding_key']==row['finding_key'])
        self.assertTrue(original['review_comment'].startswith('=HYPERLINK'))

    def test_zero_finding_report_is_complete_and_explicit(self):
        shot=self.fixture.create(0,0)
        shot['findings']=[]
        shot['full_finding_count']=0
        shot['findings_complete']=True
        self.snapshot=shot
        self.index=build_paged_index(self.work,shot)
        self.target=self.parent/'UTKAST-A13'
        result=self.report()
        self.assertEqual(result['finding_count'],0)
        self.assertIn('Ingen registrerte funn',
                      (self.target/'ks-detaljer/side-000001.html').read_text('utf-8'))
        self.assertEqual((self.target/'ks-funn.jsonl').read_text('utf-8'), '')

    def test_original_work_evidence_is_immutable(self):
        self.prepare(10,10)
        files=(self.fixture.arc_src,self.fixture.arc_original,
               self.work/self.fixture.find_rel,self.work/self.fixture.csv_rel,
               self.fixture.depot,self.work/'job.json')
        initial={path:sha256(path.read_bytes()).hexdigest() for path in files}
        self.report(page_rows=4)
        self.assertEqual(initial,{path:sha256(path.read_bytes()).hexdigest() for path in files})

    def test_legacy_review_event_limit_fails_closed(self):
        self.prepare(10,0)
        with patch('noark5_workflow.reporting.qa_complete_report_v023_a13.load_review_events',
                   side_effect=ValueError('For mange vurderingshendelser; gjennomgå historikken')):
            with self.assertRaisesRegex(ValueError,'vurderingshendelser'):
                self.report()
        self.assertFalse(self.target.exists())
        self.assertFalse(list(self.parent.glob('.dwm-a13-*')))

    @unittest.skipUnless(os.environ.get('DWM_A13_STRESS')=='1',
                         'Use DWM_A13_STRESS=1 for 100k finding export')
    def test_100000_arkade_findings_are_streamed_without_preview_limit(self):
        self.prepare(1,100000)
        result=self.report(page_rows=500)
        self.assertEqual(result['finding_count'],100002)
        self.assertEqual(len(list((self.target/'ks-detaljer').glob('*.html'))),201)
        self.assertEqual(len((self.target/'ks-funn.jsonl').read_text('utf-8').splitlines()),100002)


if __name__=='__main__': unittest.main()
