"""A14 regression: >2,000 immutable reviews, deterministic order and full reports.

No Source writes and no second decision ledger. Historical events use the
original a13 schema/checksum; all tests use temporary Work directories only.
"""
from __future__ import annotations

from hashlib import sha256
import importlib.util
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from uuid import uuid4

from noark5_workflow.reporting.qa_review_v021_a13 import (
    EVENT_MODEL, REVIEW_DIR, ReviewError, _iter_events, _read_events,
    finding_key, latest_reviews, record_review, with_selected_reviews,
)
from noark5_workflow.reporting.qa_paged_review_v023_a12 import (
    build_paged_index, load_review_events, review_page, save_review_for_page,
)
from noark5_workflow.reporting.qa_a260_v023_a6 import _reviews as a260_reviews
from noark5_workflow.reporting.qa_complete_report_v023_a13 import export_complete_reports

ROOT = Path(__file__).resolve().parents[1]
A12_FIXTURE = ROOT / 'tests/test_v023_a12_paged_review.py'
if not A12_FIXTURE.is_file():
    A12_FIXTURE = ROOT.parent / 'dwm_a12/tests/test_v023_a12_paged_review.py'


def _signed_event(folder: Path, *, uid: str, revision: str, key: str,
                  ns: int, comment: str, ks: bool = True, depot: bool = False) -> Path:
    """Make a real-shaped, checksum-valid legacy JSON event (no production writes)."""
    event_id = str(uuid4())
    doc = {
        'model_id': EVENT_MODEL, 'event_id': event_id,
        'created_utc': '2026-11-19T20:00:00+00:00', 'recorded_ns': ns,
        'job_uid': uid, 'depot_report_sha256': revision,
        'finding_key': key, 'finding_source': 'DWM avleveringskontroll',
        'test_id': 'DWM-AVLEVERING-M052', 'status': 'context_documented',
        'comment': comment, 'include_in_ks': ks, 'include_in_depot': depot,
        'author': {'user_id': 'reviewer', 'display_name': 'KS-saksbehandler'},
    }
    doc['event_sha256'] = sha256(json.dumps(doc, ensure_ascii=False, sort_keys=True,
                                            separators=(',', ':')).encode()).hexdigest()
    path = folder / (event_id + '.json')
    path.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return path


class A14LegacyLedgerTests(unittest.TestCase):
    def setUp(self):
        t = tempfile.TemporaryDirectory()
        self.addCleanup(t.cleanup)
        self.work = Path(t.name) / 'Work'
        self.work.mkdir()
        self.uid = 'A14-SOURCE-JOB-001'
        self.depot_rel = 'noark5_reports/depot/report.json'
        self.depot = self.work / self.depot_rel
        self.depot.parent.mkdir(parents=True)
        self.depot.write_text('{"report_type":"noark5_depot_validation"}', encoding='utf-8')
        self.digest = sha256(self.depot.read_bytes()).hexdigest()
        self.finding = {'source':'DWM avleveringskontroll', 'test_id':'DWM-AVLEVERING-M052',
                        'severity':'ERROR', 'message':'Under behandling', 'context':'M052',
                        'file':'arkivstruktur.xml', 'lines':[123], 'source_ref':'report.json'}
        self.key = finding_key(self.finding)
        self.snapshot = {'model_id':'ikamr.dwm.noark5.qa-decision.a12.v1',
                         'work_identity':{'job_uid':self.uid},
                         'evidence_manifest':[{'kind':'dwm_depot','path':self.depot_rel,
                                               'sha256':self.digest}],
                         'findings':[self.finding]}
        (self.work/'job.json').write_text(json.dumps({'file_type':'dwm-work-job',
                                  'job_uid':self.uid,'job':{'job_id':'JOB-001'}}), encoding='utf-8')
        self.folder = self.work/REVIEW_DIR
        self.folder.mkdir(parents=True)
        self.user = SimpleNamespace(user_id='reviewer', as_dict=lambda: {
            'user_id':'reviewer','display_name':'KS-saksbehandler'})

    def make(self, n=3, *, key=None, uid=None, digest=None):
        for k in range(n):
            _signed_event(self.folder, uid=uid or self.uid,
                          revision=digest or self.digest, key=key or self.key,
                          ns=k+1, comment='Historisk ' + str(k))

    def test_new_review_can_be_saved_after_2200_legacy_events(self):
        self.make(2201)
        saved = record_review(self.work, self.snapshot, self.finding,
                              status='requires_clarification', comment='Ny vurdering over gammel grense',
                              user=self.user, include_in_ks=True, include_in_depot=False)
        self.assertEqual(len(list(self.folder.glob('*.json'))), 2202)
        self.assertEqual(saved['model_id'], EVENT_MODEL)
        self.assertTrue((self.folder/(saved['event_id']+'.json')).is_file())
        self.assertEqual(latest_reviews(self.work, self.snapshot)['current'][self.key]['comment'],
                         'Ny vurdering over gammel grense')
        self.assertEqual(with_selected_reviews(self.work, self.snapshot)['a13_review_summary']['reviewed_findings'], 1)

    def test_2301_distinct_findings_keep_individual_review_keys(self):
        findings=[]
        for number in range(2301):
            f=dict(self.finding, message='Avleveringsfunn '+str(number), lines=[number+1])
            findings.append(f)
            _signed_event(self.folder,uid=self.uid,revision=self.digest,
                          key=finding_key(f),ns=number+1,
                          comment='Individuell vurdering '+str(number))
        self.snapshot['findings']=findings
        state=latest_reviews(self.work,self.snapshot)
        self.assertEqual(len(state['current']),2301)
        self.assertEqual(state['current'][finding_key(findings[-1])]['comment'],
                         'Individuell vurdering 2300')
        self.assertEqual(state['older_or_changed'],0)

    def test_latest_chronology_does_not_depend_on_enumeration_order(self):
        for stamp in (9, 2, 14, 5):
            _signed_event(self.folder, uid=self.uid, revision=self.digest, key=self.key,
                          ns=stamp, comment='Tidsstempel ' + str(stamp))
        self.assertEqual(latest_reviews(self.work, self.snapshot)['current'][self.key]['comment'],
                         'Tidsstempel 14')
        self.assertEqual([e['recorded_ns'] for e in _read_events(self.work)], [2,5,9,14])

    def test_old_report_and_different_job_remain_separate(self):
        _signed_event(self.folder, uid=self.uid, revision='a'*64, key=self.key,
                      ns=10, comment='Gammel depotrapport')
        _signed_event(self.folder, uid='OTHER-JOB', revision=self.digest, key=self.key,
                      ns=11, comment='Annen jobb')
        _signed_event(self.folder, uid=self.uid, revision=self.digest, key=self.key,
                      ns=12, comment='Gjeldende')
        state = latest_reviews(self.work, self.snapshot)
        self.assertEqual(state['current'][self.key]['comment'], 'Gjeldende')
        self.assertEqual(state['older_or_changed'], 1)
        self.assertEqual(state['other_job'], 1)

    def test_corrupt_event_even_if_older_blocks_completed_history(self):
        self.make(6)
        item = next(iter(self.folder.glob('*.json')))
        doc = json.loads(item.read_text(encoding='utf-8'))
        doc['comment'] = 'Endret uten ny checksum'
        item.write_text(json.dumps(doc), encoding='utf-8')
        with self.assertRaises(ReviewError):
            latest_reviews(self.work, self.snapshot)

    def test_unknown_file_blocks_full_review_scan(self):
        self.make(1)
        (self.folder/'sneaky.txt').write_text('ikke en vurderingshendelse',encoding='utf-8')
        with self.assertRaises(ReviewError):
            list(_iter_events(self.work))

    def test_legacy_event_format_not_migrated_or_rewritten(self):
        self.make(2)
        before={p.name:sha256(p.read_bytes()).hexdigest() for p in self.folder.glob('*.json')}
        latest_reviews(self.work, self.snapshot)
        self.assertEqual(before,{p.name:sha256(p.read_bytes()).hexdigest()
                                 for p in self.folder.glob('*.json')})


class A14PagedAndA260Integration(unittest.TestCase):
    def setUp(self):
        # Reuse A12's real, SHA-verified complete Work-index fixture without
        # reloading/replacing any production modules in sys.modules.
        spec=importlib.util.spec_from_file_location('_a14_test_fixture_a12',
                          A12_FIXTURE)
        self.module=importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.module)
        self.fixture=self.module.PagedReviewTests(
              methodName='test_all_DWM_and_arkade_findings_are_present_beyond_preview')
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.work=self.fixture.work
        self.snapshot=self.fixture.create(3,2)
        self.index=build_paged_index(self.work,self.snapshot)
        self.depot_sha=self.index['depot_sha256']
        self.folder=self.work/REVIEW_DIR
        self.folder.mkdir(parents=True)
        self.user=SimpleNamespace(user_id='reviewer', as_dict=lambda: {
            'user_id':'reviewer','display_name':'KS-saksbehandler'})
        self.dwm=review_page(self.work,self.index,source='DWM avleveringskontroll')['rows'][0]
        self.ark=review_page(self.work,self.index,source='Arkade 5')['rows'][0]

    def add_history(self, n=2100):
        for i in range(n):
            _signed_event(self.folder,uid=self.fixture.uid,revision=self.depot_sha,
                          key=self.dwm['finding_key'],ns=i+1,comment='Versjon '+str(i),
                          ks=(i%2==0),depot=(i%2!=0))

    def test_paged_reader_sees_latest_event_beyond_two_thousand(self):
        self.add_history(2025)
        reviews=load_review_events(self.work,self.index)
        self.assertEqual(len(reviews),1)
        self.assertEqual(reviews[self.dwm['finding_key']]['comment'],'Versjon 2024')
        page=review_page(self.work,self.index,source='DWM avleveringskontroll',
                         reviewed='reviewed',reviews=reviews)
        self.assertEqual(page['total'],1)
        self.assertEqual(page['rows'][0]['review_status'],'context_documented')

    def test_paged_save_works_after_two_thousand_events(self):
        self.add_history(2001)
        result=save_review_for_page(self.work,self.snapshot,self.index,self.ark,
                         status='requires_clarification',comment='Nytt funn på side',
                         user=self.user,include_in_ks=False,include_in_depot=True)
        self.assertTrue((self.folder/(result['event_id']+'.json')).is_file())
        reviews=load_review_events(self.work,self.index)
        self.assertEqual(reviews[self.ark['finding_key']]['comment'],'Nytt funn på side')
        self.assertEqual(len(list(self.folder.glob('*.json'))),2002)

    def test_a260_latest_review_and_separate_recipients(self):
        self.add_history(2002)
        result=a260_reviews(self.work,{'job_uid':self.fixture.uid},self.depot_sha)
        self.assertEqual(len(result),1)
        self.assertEqual(result[self.dwm['finding_key']]['comment'],'Versjon 2001')
        self.assertFalse(result[self.dwm['finding_key']]['include_in_ks'])
        self.assertTrue(result[self.dwm['finding_key']]['include_in_depot'])

    def test_complete_ks_depot_export_with_more_than_2000_events(self):
        self.add_history(2003)
        export_parent=self.fixture.root/'complete-report'
        export_parent.mkdir()
        destination=export_parent/'EXPORT-A14'
        result=export_complete_reports(self.work,self.snapshot,self.index,destination,
                                        page_rows=3)
        self.assertEqual(result['finding_count'],6)
        self.assertEqual(result['reviewed_count'],1)
        self.assertEqual(result['reviews_in_ks'],1)
        self.assertEqual(result['reviews_in_depot'],0)
        manifest=json.loads((destination/'evidensmanifest.json').read_text(encoding='utf-8'))
        self.assertNotIn('maksimalt 2000',json.dumps(manifest))
        self.assertEqual(len((destination/'ks-funn.jsonl').read_text('utf-8').splitlines()),6)
        self.assertEqual(len((destination/'depot-funn.jsonl').read_text('utf-8').splitlines()),6)
        self.assertFalse(manifest['automatic_approval'])

    def test_bad_historical_event_prevents_a13_publishing(self):
        self.add_history(5)
        file=next(self.folder.glob('*.json'))
        doc=json.loads(file.read_text(encoding='utf-8'))
        doc['comment']='Tekst endret'
        file.write_text(json.dumps(doc), encoding='utf-8')
        parent=self.fixture.root/'complete-report'
        parent.mkdir()
        destination=parent/'NEVER-PUBLISH'
        with self.assertRaises((ReviewError, ValueError)):
            export_complete_reports(self.work,self.snapshot,self.index,destination)
        self.assertFalse(destination.exists())


if __name__=='__main__':
    unittest.main()
