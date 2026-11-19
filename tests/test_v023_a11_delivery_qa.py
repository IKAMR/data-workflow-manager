"""v0.2.3-a11: evidence-bound individual DWM delivery findings in KS/A260.

Tests never monkeypatch/reload persistent production modules or touch Source
except their own temporary extraction. Large stress is opt-in.
"""
from __future__ import annotations

import csv
from hashlib import sha256
import json
import os
from pathlib import Path
import sys
import tempfile
from types import ModuleType, SimpleNamespace
import unittest
from unittest import mock

from noark5_workflow.analysis.delivery_validator_v023_a9 import validate_delivery_values
from noark5_workflow.reporting.qa_delivery_v023_a11 import (
    DeliveryQaError, _binding, _hash, _project, attach_delivery_to_snapshot,
    delivery_for_snapshot, iter_verified_delivery, page_delivery_findings,
)
from noark5_workflow.reporting.qa_a260_v023_a6 import FindingWriter, build_qa_basis_a6

NS = 'http://www.arkivverket.no/standarder/noark5/arkivstruktur'
MID = ('M051', 'M052', 'M053', 'M054')


def _xml(n: int = 2, *, journal: str = 'Arkivert', period: bool = False):
    folders = ''.join(
        '<mappe><systemID>S-'+str(i)+'</systemID><saksstatus>Under behandling</saksstatus>'
        '<registrering><systemID>R-'+str(i)+'</systemID>'
        '<journalstatus>'+journal+'</journalstatus><dokumentbeskrivelse>'
        '<systemID>D-'+str(i)+'</systemID>'
        '<dokumentstatus>Dokumentet er ferdigstilt</dokumentstatus>'
        '</dokumentbeskrivelse></registrering></mappe>' for i in range(n))
    dates = ('<arkivperiodeStartDato>2010-01-01</arkivperiodeStartDato>'
             '<arkivperiodeSluttDato>2009-01-01</arkivperiodeSluttDato>') if period else ''
    return ('<arkiv xmlns="'+NS+'"><arkivdel><systemID>AD-1</systemID>'
            '<arkivdelstatus>Avsluttet periode</arkivdelstatus>'+dates+
            '<klassifikasjonssystem><klasse>'+folders+'</klasse></klassifikasjonssystem>'
            '</arkivdel></arkiv>')


def _canonical_key(item):
    fields=('source','test_id','severity','message','context','file','source_ref','lines')
    raw=json.dumps({k:item.get(k) for k in fields},sort_keys=True,
                   ensure_ascii=False,separators=(',',':'))
    return sha256(raw.encode('utf-8')).hexdigest()


class A11DeliveryBridgeTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root=Path(temp.name)
        self.work=self.root/'Work';self.work.mkdir()
        self.source=self.root/'Source';self.source.mkdir()
        self.run='JOB-001__RUN-1';self.uid='TEST-JOB-UID-1'
        self.folder=self.work/'noark5_reports'/'depot_validation'/self.run
        self.folder.mkdir(parents=True)
        self.report_rel='noark5_reports/depot_validation/'+self.run+'/depot_validation_report.json'
        self.find_rel=self.report_rel.rsplit('/',1)[0]+'/delivery-funn.jsonl'
        self.manifest=self.folder/'artifact_manifest.json'
        self.manifest.write_text(json.dumps({
            'operation_id':'build_noark5_depot_report','job_uid':self.uid,
            'job_id':'JOB-001'}),encoding='utf-8')
        self.values=self.root/'values.json'
        vals={}
        for version in ('3.1','4.0','5.0'):
            values={
                'M051_arkivdelstatus':['Aktiv periode','Overlappingsperiode','Avsluttet periode','Uaktuelle mapper'],
                'M052_saksstatus':['Under behandling','Avsluttet','Utgår'],
                'M053_journalstatus':(['Journalført','Ferdigstilt fra saksbehandler','Godkjent av leder','Ekspedert','Arkivert','Utgår']
                    if version in ('3.1','4.0') else ['Journalført','Ekspedert','Arkivert','Utgår']),
                'M054_dokumentstatus':['Dokumentet er under redigering','Dokumentet er ferdigstilt'],
            }
            vals[version]={'value_sets':{k:{'metadata_id':k.split('_')[0], 'values':v}
                                          for k,v in values.items()}}
        self.values.write_text(json.dumps({'versions':vals},ensure_ascii=False),encoding='utf-8')
        self.doc={}

    def create(self, n=2, *, version='5.0', journal='Arkivert', period=False):
        (self.source/'arkivstruktur.xml').write_text(_xml(n,journal=journal,period=period),encoding='utf-8')
        evidence=SimpleNamespace(version=version,status='confirmed', schemas=(
            SimpleNamespace(path=Path('arkivstruktur.xsd'),version=version,digest='a'*64),))
        from noark5_workflow.analysis.delivery_validator_v023_a9 import RULES_FILE
        d=validate_delivery_values(self.source,self.folder,source_ref=self.find_rel,
                                   version_evidence=evidence,rules_path=RULES_FILE,
                                   values_path=self.values)
        self.doc={'report_type':'noark5_depot_validation','delivery_validation':d,
                  'deviations':[{'category':'delivery_value_M052','severity':'serious',
                                 'summary':'Aggregert M052-avvik','requires_review':True}]}
        if period:
            self.doc['deviations'].append({'category':'delivery_period_chronology',
                                           'severity':'review','summary':'Aggregert periode'})
        self.write_report()
        return d

    def write_report(self):
        (self.folder/'depot_validation_report.json').write_text(
            json.dumps(self.doc,ensure_ascii=False),encoding='utf-8')

    def snapshot(self):
        return {'work_identity':{'job_uid':self.uid}, 'evidence_manifest':[
            {'kind':'dwm_depot','path':self.report_rel,
             'sha256':_hash(self.folder/'depot_validation_report.json')}],
            'findings':[{'source':'DWM depotvalidering','test_id':'delivery_value_M052',
                         'severity':'SERIOUS','message':'Aggregert M052-avvik',
                         'context':'','file':'','lines':[],
                         'source_ref':self.report_rel,'requires_review':True},
                        {'source':'DWM eldre test','test_id':'XPATH-1','severity':'WARNING',
                         'message':'Eldre kontroll','context':'','file':'','lines':[],
                         'source_ref':self.report_rel,'requires_review':True}],
            'findings_complete':True,'full_finding_count':2,
            'report_status':'DRAFT_REVIEW_REQUIRED'}

    def attach(self, snapshot=None):
        name='noark5_workflow.reporting.qa_review_v021_a13'
        fake=ModuleType(name)
        fake.finding_key=_canonical_key
        with mock.patch.dict(sys.modules,{name:fake}):
            return attach_delivery_to_snapshot(self.work,snapshot or self.snapshot())

    def test_all_individual_findings_are_preserved_and_source_bound(self):
        d=self.create(3,period=True)
        data=delivery_for_snapshot(self.work,self.report_rel,self.doc,job_uid=self.uid)
        self.assertTrue(data['findings_complete'])
        self.assertEqual(data['finding_count'],d['finding_count'])
        self.assertEqual(len(data['findings']),4)
        self.assertEqual({x['source'] for x in data['findings']},
                         {'DWM avleveringskontroll','DWM periodekonsistens'})
        for row in data['findings']:
            self.assertEqual(row['source_ref'],self.find_rel)
            self.assertEqual(row['source_xml_sha256'],d['source_sha256'])
            self.assertIn('Forekomst-ID:',row['context'])
            self.assertIn('XPath:',row['context'])
            self.assertFalse(row.get('automatic_approval',False))
            self.assertIsInstance(row['lines'],list)
        self.assertEqual(len({_canonical_key(x) for x in data['findings']}),4)
        self.assertEqual(len({x['finding_uid'] for x in data['findings']}),4)

    def test_bridge_removes_only_aggregates_and_preserves_other_sources(self):
        self.create(3)
        found=self.attach()
        self.assertEqual(found['full_finding_count'],4) # 1 older + 3 events
        self.assertTrue(found['findings_complete'])
        self.assertEqual(len(found['findings']),4)
        self.assertEqual(found['findings'][0]['source'],'DWM eldre test')
        self.assertEqual(len([r for r in found['findings'] if r['source']=='DWM avleveringskontroll']),3)
        self.assertFalse(any(r['test_id']=='delivery_value_M052' for r in found['findings']))
        self.assertEqual(len([m for m in found['evidence_manifest']
                              if m['kind'].startswith('dwm_delivery_')]),2)

    def test_review_key_is_stable_and_unique_for_identical_values(self):
        self.create(2)
        a=delivery_for_snapshot(self.work,self.report_rel,self.doc)['findings']
        b=delivery_for_snapshot(self.work,self.report_rel,self.doc)['findings']
        self.assertEqual([_canonical_key(x) for x in a],[_canonical_key(x) for x in b])
        self.assertNotEqual(_canonical_key(a[0]),_canonical_key(a[1]))
        self.assertEqual(a[0]['severity'],'ERROR')
        self.assertEqual(a[0]['standard_value'],True)
        self.assertEqual(a[0]['delivery_value'],False)

    def test_all_three_versions_have_their_own_source_identity(self):
        for version in ('3.1','4.0','5.0'):
            with self.subTest(version=version):
                d=self.create(1,version=version)
                data=delivery_for_snapshot(self.work,self.report_rel,self.doc)
                self.assertEqual(data['noark_version'],version)
                self.assertEqual(data['source_sha256'],d['source_sha256'])
                # Reset published Work artifacts for next controlled version.
                for name in ('delivery-funn.jsonl','delivery-funn.csv','delivery-validation.json'):
                    (self.folder/name).unlink()

    def test_unassessed_source_is_not_silently_passed(self):
        self.doc={'report_type':'noark5_depot_validation',
                  'delivery_validation':{'model_id':'dwm.noark5.delivery-validation.a10.v1',
                     'status':'not_assessed','complete':False,
                     'reason':'Ubekreftet XSD','finding_count':None}}
        self.write_report()
        data=delivery_for_snapshot(self.work,self.report_rel,self.doc)
        self.assertEqual(data['status'],'not_assessed')
        self.assertEqual(data['findings'],[])
        self.assertIn('Ubekreftet',self.attach()['delivery_qa']['reason'])

    def test_legacy_without_delivery_model_is_unchanged(self):
        self.doc={'report_type':'noark5_depot_validation'}
        self.write_report()
        before=self.snapshot()
        after=self.attach(before)
        self.assertIs(after,before)
        self.assertEqual(list(iter_verified_delivery(self.work,self.report_rel,self.doc)),[])

    def test_301_and_1250_are_complete_in_stream_but_previewed_in_ks(self):
        for n in (301,1250):
            with self.subTest(count=n):
                if n!=301:
                    for name in ('delivery-funn.jsonl','delivery-funn.csv','delivery-validation.json'):
                        (self.folder/name).unlink()
                self.create(n)
                data=delivery_for_snapshot(self.work,self.report_rel,self.doc,job_uid=self.uid)
                self.assertEqual(data['finding_count'],n)
                self.assertEqual(len(data['findings']),250)
                self.assertFalse(data['findings_complete'])
                p=page_delivery_findings(self.work,self.report_rel,self.doc,
                                          offset=n-3,page_size=20)
                self.assertEqual(p['total'],n)
                self.assertEqual(len(p['rows']),3)
                view=self.attach()
                self.assertFalse(view['findings_complete'])
                self.assertEqual(view['full_finding_count'],n+1)
                self.assertEqual(len(view['findings']),251)
                self.assertIn('PARTIAL_PREVIEW',view['report_status'])

    def test_oversized_requested_page_is_rejected(self):
        self.create(2)
        for args in ({'page_size':1001},{'page_size':0},{'offset':-1},
                     {'severity':'warning'}):
            with self.subTest(args=args), self.assertRaises(DeliveryQaError):
                page_delivery_findings(self.work,self.report_rel,self.doc,**args)

    def test_csv_and_jsonl_hashes_prevent_silent_change(self):
        self.create()
        with (self.folder/'delivery-funn.jsonl').open('ab') as f:
            f.write(b'\n')
        with self.assertRaisesRegex(DeliveryQaError,'JSONL|SHA-256|Ugyldig'):
            list(iter_verified_delivery(self.work,self.report_rel,self.doc))
        (self.folder/'delivery-funn.jsonl').write_bytes(b'')
        with self.assertRaises(DeliveryQaError):
            delivery_for_snapshot(self.work,self.report_rel,self.doc)

    def test_csv_changed_is_rejected_even_when_jsonl_is_intact(self):
        self.create()
        with (self.folder/'delivery-funn.csv').open('ab') as f:
            f.write(b'altered')
        with self.assertRaisesRegex(DeliveryQaError,'CSV-evidens'):
            delivery_for_snapshot(self.work,self.report_rel,self.doc)

    def test_aggregate_counts_must_match_actual_rows(self):
        self.create(2)
        self.doc['delivery_validation']['rules'][1]['delivery_deviations']+=1
        self.doc['delivery_validation']['finding_count']+=1
        self.doc['delivery_validation']['delivery_value_findings']+=1
        self.write_report()
        with self.assertRaisesRegex(DeliveryQaError,'Flere|stemmer|Antall'):
            delivery_for_snapshot(self.work,self.report_rel,self.doc)

    def test_wrong_work_identity_is_rejected(self):
        self.create(1)
        with self.assertRaisesRegex(DeliveryQaError,'annen Work-jobb'):
            delivery_for_snapshot(self.work,self.report_rel,self.doc,job_uid='OTHER-JOB')

    def test_cross_depot_source_reference_is_rejected(self):
        self.create(1)
        self.doc['delivery_validation']['findings_relative']=\
            'noark5_reports/depot_validation/JOB-OTHER/delivery-funn.jsonl'
        with self.assertRaisesRegex(DeliveryQaError,'knyttet'):
            delivery_for_snapshot(self.work,self.report_rel,self.doc)

    def test_wrong_report_revision_fails_closed(self):
        self.create()
        shot=self.snapshot()
        self.doc['deviations'].append({'category':'New','summary':'Mutated'})
        self.write_report()
        with self.assertRaisesRegex(DeliveryQaError,'endret'):
            self.attach(shot)

    def test_unknown_aggregate_model_and_false_approval_are_rejected(self):
        self.create(1)
        self.doc['delivery_validation']['automatic_approval']=True
        with self.assertRaises(DeliveryQaError):
            delivery_for_snapshot(self.work,self.report_rel,self.doc)
        self.doc['delivery_validation']['automatic_approval']=False
        self.doc['delivery_validation']['model_id']='unknown'
        with self.assertRaises(DeliveryQaError):
            delivery_for_snapshot(self.work,self.report_rel,self.doc)

    @unittest.skipUnless(hasattr(os,'symlink'),'No symlink support')
    def test_symlinked_evidence_is_rejected(self):
        self.create(1)
        target=self.folder/'delivery-funn.csv';source=self.root/'original.csv'
        source.write_bytes(target.read_bytes());target.unlink()
        try: target.symlink_to(source)
        except (OSError,NotImplementedError):self.skipTest('No symlink privilege')
        with self.assertRaisesRegex(DeliveryQaError,'Symbolsk lenke'):
            delivery_for_snapshot(self.work,self.report_rel,self.doc)

    def test_a260_writer_preserves_uid_source_severity_and_full_count(self):
        self.create(12,period=True)
        target=self.root/'stage';target.mkdir()
        with context_writer(target/'funn.jsonl', target/'funn.csv') as writer:
            for row in iter_verified_delivery(self.work,self.report_rel,self.doc):
                writer.add(row)
            summary=writer.summary()
        self.assertEqual(summary['total'],13)
        self.assertEqual(summary['errors'],12)
        self.assertEqual(summary['review_points'],1)
        rows=[json.loads(s) for s in (target/'funn.jsonl').read_text(encoding='utf-8').splitlines()]
        self.assertEqual(len(rows),13)
        self.assertTrue(all(row.get('finding_uid') for row in rows))
        self.assertTrue(all(row.get('finding_key')==_canonical_key(row) for row in rows))
        self.assertIn('DWM periodekonsistens',summary['by_source'])
        self.assertIn('DWM avleveringskontroll',summary['by_source'])

    def a260(self, *, partial_snapshot=False):
        """Run the actual A260 builder with only upstream Work services stubbed.

        All stubs are scoped and restored before other unittest modules execute;
        production A260, file verification and writer are real.
        """
        import contextlib
        evidence=self.work/'noark5_evidence'
        evidence.mkdir(exist_ok=True)
        (evidence/'evidence-audit.json').write_text(
            json.dumps({'job_uid':self.uid}),encoding='utf-8')
        (evidence/'canonical-results.json').write_text(
            json.dumps({'extraction':{'stable_id':self.uid},'a7_evidence_sources':{}}),
            encoding='utf-8')
        row=delivery_for_snapshot(self.work,self.report_rel,self.doc)['findings'][0]
        def upstream_snapshot(**kwargs):
            return {'dwm_report_source':self.report_rel,
                    'findings_complete':not partial_snapshot,
                    'findings':[
                        dict(row),
                        {'source':'DWM depotvalidering','test_id':'delivery_value_M052',
                         'severity':'SERIOUS','message':'Aggregert M052',
                         'context':'','file':'','lines':[],
                         'source_ref':self.report_rel,'requires_review':True},
                        {'source':'DWM annen kontroll','test_id':'DWM-XPATH-1',
                         'severity':'REVIEW','message':'Annen kontroll',
                         'context':'','file':'','lines':[],
                         'source_ref':self.report_rel,'requires_review':True},
                    ]}
        def fake_read(path):return json.loads(Path(path).read_text(encoding='utf-8'))
        op=ModuleType('noark5_workflow.operations.canonical_evidence_v022_a7')
        op.ROOT_NAME='noark5_evidence'
        op._read=fake_read
        op._work_identity=lambda work,job_id: (Path(work),{'job_uid':self.uid,'job_id':'JOB-001'})
        op._build_qa_basis_legacy_v022_a7=lambda *a,**k: self.fail('Unexpected legacy A260')
        r=ModuleType('noark5_workflow.reporting.qa_workflow_v022_a3')
        r.build_review_snapshot_v022_a3=upstream_snapshot
        r.manual_findings=lambda *a,**k: []
        r._verified_raf_candidates=lambda *a,**k: []
        d=ModuleType('noark5_workflow.reporting.qa_decision_v021_a12')
        d._find_depot=lambda root,chosen: (self.folder/'depot_validation_report.json',self.report_rel)
        d._json=lambda path,limit=None: json.loads(Path(path).read_text(encoding='utf-8'))
        d.MAX_DEPO=24*1024*1024
        review=ModuleType('noark5_workflow.reporting.qa_review_v021_a13')
        review._read_events=lambda work: []
        with mock.patch.dict(sys.modules,{
            op.__name__:op, r.__name__:r, d.__name__:d, review.__name__:review}):
            return build_qa_basis_a6(self.work,job_id='JOB-001')

    def test_a260_integration_avoids_aggregate_duplicate_for_small_job(self):
        self.create(4,period=True)
        output=self.a260()
        self.assertEqual(output['summary']['by_source']['DWM avleveringskontroll'],4)
        self.assertEqual(output['summary']['by_source']['DWM periodekonsistens'],1)
        self.assertEqual(output['summary']['by_source']['DWM annen kontroll'],1)
        self.assertNotIn('DWM depotvalidering',output['summary']['by_source'])
        path=self.work/output['exports']['jsonl']
        lines=[json.loads(row) for row in path.read_text(encoding='utf-8').splitlines()]
        self.assertEqual(len(lines),6)
        self.assertEqual(len({r['finding_uid'] for r in lines}),6)
        manifest=json.loads(path.with_name('manifest.json').read_text(encoding='utf-8'))
        self.assertEqual(manifest['source_delivery']['finding_count'],5)
        self.assertEqual(manifest['source_delivery']['findings_sha256'],
                         self.doc['delivery_validation']['finding_file_sha256'])

    def test_a260_integration_streams_all_301_when_snapshot_partial(self):
        self.create(301)
        output=self.a260(partial_snapshot=True)
        self.assertEqual(output['summary']['total'],301)
        self.assertEqual(output['summary']['errors'],301)
        self.assertEqual(output['summary']['review_points'],0)
        self.assertNotIn('DWM depotvalidering',output['summary']['by_source'])
        lines=(self.work/output['exports']['jsonl']).read_text(encoding='utf-8').splitlines()
        self.assertEqual(len(lines),301)

    def test_a260_aborts_on_modified_jsonl_without_publishing(self):
        self.create(12)
        with (self.folder/'delivery-funn.jsonl').open('ab') as f:
            f.write(b'\n')
        with self.assertRaises(DeliveryQaError):
            self.a260()
        evidence=self.work/'noark5_evidence'
        self.assertFalse((evidence/'qa-basis-draft.json').exists())
        self.assertFalse((evidence/'qa-basis-draft.html').exists())
        stages=list((evidence/'a260_exports_v023_a6').glob('*'))
        self.assertEqual(stages,[])

    @unittest.skipUnless(os.environ.get('DWM_A11_STRESS')=='1','Set DWM_A11_STRESS=1')
    def test_hundred_thousand_delivery_rows_without_preview_truncation(self):
        self.create(100001)
        data=delivery_for_snapshot(self.work,self.report_rel,self.doc)
        self.assertEqual(data['finding_count'],100001)
        self.assertEqual(len(data['findings']),250)
        self.assertEqual(len(page_delivery_findings(self.work,self.report_rel,self.doc,
                                                    offset=100000)['rows']),1)


class context_writer:
    """Explicit close of existing A260 writer; no production module mutation."""
    def __init__(self,jsonl,csv): self.jsonl,self.csv=jsonl,csv
    def __enter__(self):self.writer=FindingWriter(self.jsonl,self.csv);return self.writer
    def __exit__(self,*args):self.writer.close()


if __name__=='__main__':
    unittest.main()
