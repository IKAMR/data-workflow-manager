"""a7: source-bound automatic canonical evidence and postprocessing safety."""
from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
import sys
import tempfile
from types import ModuleType
import unittest
from unittest.mock import patch
from uuid import uuid4

from noark5_workflow.operations.canonical_evidence_v022_a7 import (
    EvidenceError, build_evidence, analyze_external, audit_evidence, build_qa_basis,
    _dwm_siegfried_statistics,
)
from noark5_workflow.analysis import canonical_external_import_v0115_a10 as real_external
from noark5_workflow.analysis.canonical_matrix_v0115_a11 import load_external_status
from noark5_workflow.core.context import OperationContext
from noark5_workflow.operations.canonical_evidence_v022_a7 import AnalyzeNoark5ExternalEvidenceOperation


def write_json(path: Path, doc: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, ensure_ascii=False), encoding='utf-8')


class EvidenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.work = Path(self.temp.name)/'work'
        self.work.mkdir()
        self.job_uid = str(uuid4())
        self.job_id = 'JOB-002'
        self.source = str(Path(self.temp.name)/'source')
        self.work_job = {
            'file_type': 'dwm-work-job', 'format_version': 1,
            'job_uid': self.job_uid, 'job': {
                'job_id': self.job_id, 'source_extraction': self.source,
                'workflow_ids': ['run_noark5_xpath_tests_2026',
                                 'arkade5_noark5_test', 'arkade5_pronom_analysis',
                                 'siegfried_pronom_identification'],
            },
        }
        write_json(self.work/'job.json', self.work_job)
        self.run = self.work/'noark5_tests/xpath/JOB-002__RUN001'
        write_json(self.run/'master-results.json', {
            'format_version': 1, 'source': {'execution_profile':'normal'},
            'tests': [{'test_id': 'T1'}, {'test_id':'T2'}],
        })
        write_json(self.run/'artifact_manifest.json', {
            'operation_id': 'run_noark5_xpath_tests_2026',
            'job_id': self.job_id, 'job_uid': self.job_uid,
            'source_extraction': self.source, 'run_id': 'RUN001',
        })
        self.ark = self.work/'external_evidence/arkade5/one'
        original = self.ark/'source/arkade.json'
        write_json(original, {'original':True})
        write_json(self.ark/'normalized/arkade5_results.json',
                   {'source_system':'Arkade 5', 'tests':[{'test_id':'N5.01'}]})
        write_json(self.ark/'normalized/pronom_statistics.json',
                   {'source_system':'Arkade 5', 'evidence_type':'arkade5_pronom_format_statistics'})
        write_json(self.ark/'manifest.json', {
            'imported_by': {'job_id': self.job_id},
            'source': {'sha256': sha256(original.read_bytes()).hexdigest(),
                       'preserved_file':'external_evidence/arkade5/one/source/arkade.json'},
            'normalized_file':'external_evidence/arkade5/one/normalized/arkade5_results.json',
            'pronom_evidence': {'statistics': {'normalized_file':
                'external_evidence/arkade5/one/normalized/pronom_statistics.json'}},
        })
        self.sf = self.work/'external_evidence/siegfried/run1'
        write_json(self.sf/'pronom_statistics.json', {'files_total': 7})
        write_json(self.sf/'manifest.json', {
            'job_id': self.job_id, 'job_uid': self.job_uid,
            'source_root': self.source, 'created_at':'2026-11-17T20:05:00Z',
        })
        canonical = ModuleType('noark5_workflow.analysis.canonical_results')
        def validate_work(work):
            return Path(work), {'job_id':self.job_id,'job_uid':self.job_uid}
        def make_canonical(work, *, master_paths=(), write=False):
            self.assertFalse(write)
            self.assertEqual(len(master_paths), 1)
            return {
                'model_id':'noark5.canonical-results.v1',
                'extraction':{'stable_id':self.job_uid},
                'sources':[{'source_kind':'dwm_master', 'reference':{
                    'work_relative_path': Path(master_paths[0]).relative_to(work).as_posix()}}],
                'observations':[{'test_id':'T1'},{'test_id':'T2'}], 'limitations':[],
            }
        canonical._validate_work=validate_work
        canonical.build_canonical_results=make_canonical
        external=ModuleType('noark5_workflow.analysis.canonical_external_import_v0115_a10')
        external.MAX_ANALYSIS_OUTPUT=128 * 1024 * 1024
        external.MAX_SOURCE_NORMALIZED=48 * 1024 * 1024
        def make_external(work, selected_files=(), write=False):
            self.assertFalse(write)
            sources=[]
            for p in selected_files:
                analysis={}
                if p.endswith('siegfried/run1/pronom_statistics.json'):
                    analysis=_dwm_siegfried_statistics(json.loads((work/p).read_text())) or {}
                sources.append({'evidence':{'work_relative_path':p}, 'analysis':analysis})
            return {'model_id':'noark5.external-analysis.v1',
                    'extraction_stable_id':self.job_uid,
                    'canonical_reference':{'sha256':sha256((work/'noark5_evidence/canonical-results.json').read_bytes()).hexdigest()},
                    'sources':sources,
                    'summary':{'unparsed_files':0}}
        external.analyze_external_results=make_external
        qa=ModuleType('noark5_workflow.reporting.qa_workflow_v022_a3')
        qa.build_review_snapshot_v022_a3=lambda **kwargs: {
            'dwm_report_source':'noark5_reports/depot_validation/d.json',
            'findings':[{'test_id':'N5.29','message':'Needs review', 'severity':'ERROR'}],
        }
        qa.finding_summary=lambda work,snapshot: {'total':1,'reviewed':0,'unreviewed':1}
        patcher=patch.dict(sys.modules,{
            'noark5_workflow.analysis.canonical_results':canonical,
            'noark5_workflow.analysis.canonical_external_import_v0115_a10':external,
            'noark5_workflow.reporting.qa_workflow_v022_a3':qa,
        })
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_build_links_one_master_and_three_external_families(self):
        result=build_evidence(self.work,job_id=self.job_id,run_id='RUN001')
        self.assertEqual(result['observations'],2)
        self.assertEqual(set(result['external_sources']),
                         {'arkade_noark','arkade_pronom','siegfried_pronom'})
        doc=json.loads((self.work/'noark5_evidence/canonical-results.json').read_text())
        self.assertFalse(doc['a7_source_coverage']['fully_verified_noark5'])
        self.assertIsNone(doc['a7_source_coverage']['approval'])

    def test_external_analysis_is_bound_to_canonical_sha(self):
        build_evidence(self.work,job_id=self.job_id)
        result=analyze_external(self.work,job_id=self.job_id)
        self.assertEqual(result['sources'],3)
        self.assertEqual(result['unparsed'],0)
        self.assertTrue((self.work/'noark5_evidence/canonical-external-analysis.json').is_file())

    def test_dwm_siegfried_pronom_statistics_are_read_as_format_evidence(self):
        write_json(self.sf/'pronom_statistics.json', {
            'source_system':'DWM / Siegfried',
            'evidence_type':'dwm_siegfried_pronom_identification',
            'format_version':1, 'run_id':'run1',
            'files_total':7,'identified':6,'unidentified':1,'ambiguous':0,
            'format_groups':[{'puid':'fmt/354','format':'PDF/A','version':'1b','count':6}],
        })
        build_evidence(self.work,job_id=self.job_id)
        result=analyze_external(self.work,job_id=self.job_id)
        self.assertEqual(result['sources'],3)
        doc=json.loads((self.work/'noark5_evidence/canonical-external-analysis.json').read_text())
        stat=next(src['analysis'] for src in doc['sources'] if
                  src['evidence']['work_relative_path'].endswith('siegfried/run1/pronom_statistics.json'))
        self.assertEqual(stat['source_format'],'dwm_siegfried_pronom_statistics_v1')
        self.assertEqual(stat['reported_total_files'],7)
        self.assertIsNone(stat['depot_approval'])
        self.assertFalse(stat['technical_validation_verified'])

    def test_a220_links_large_arkade_and_downstream_status(self):
        normalized=self.ark/'normalized/arkade5_results.json'
        with normalized.open('w',encoding='utf-8') as stream:
            stream.write('{"source_system":"Arkade 5","format_version":2,'
                         '"evidence_type":"external_validation_report","tests":[')
            for index in range(100_000):
                if index:
                    stream.write(',')
                stream.write(json.dumps({'test_id':str(index)+'x'*100,
                    'source_status':'WARNING','results':[],'number_of_errors':0,
                    'unused':'x'*250}))
            stream.write(']}')
        self.assertGreater(normalized.stat().st_size,30_000_000)
        original_hash=sha256(normalized.read_bytes()).hexdigest()
        build_evidence(self.work,job_id=self.job_id)
        with patch.dict(sys.modules, {
            'noark5_workflow.analysis.canonical_external_import_v0115_a10':real_external,
        }):
            result=analyze_external(self.work,job_id=self.job_id)
            linked=load_external_status(self.work)
            audit=audit_evidence(self.work,job_id=self.job_id)
        self.assertEqual(result['sources'],3)
        self.assertGreater((self.work/'noark5_evidence/canonical-external-analysis.json').stat().st_size,
                           64*1024*1024)
        self.assertEqual(audit['linked'],3)
        self.assertEqual(linked['state'],'linked')
        relative=normalized.relative_to(self.work).as_posix()
        self.assertEqual(linked['sources'][relative],'analyzed')
        source=next(item for item in linked['analysis']['sources'] if
                    item['evidence']['work_relative_path']==relative)
        self.assertEqual(source['evidence']['sha256'],original_hash)
        self.assertEqual(source['evidence']['bytes'],normalized.stat().st_size)
        self.assertEqual(source['analysis']['record_count'],100_000)
        self.assertEqual(source['analysis']['records'][0]['reported_status'],'WARNING')
        self.assertIsNone(linked['analysis']['summary']['depot_approval'])

    def test_a220_streams_arkade_above_reported_failure_size(self):
        import tracemalloc
        from noark5_workflow.reporting.qa_decision_v021_a12 import _external
        normalized=self.ark/'normalized/arkade5_results.json'
        with normalized.open('w',encoding='utf-8') as stream:
            stream.write('{"format_version":2,"evidence_type":"external_validation_report",'
                         '"source_system":"Arkade 5","summary":{"number_of_tests_run":1},'
                         '"tests":[{"test_id":"N5.01","source_status":"warning",'
                         '"number_of_errors":0,"results":[{"result_type":"Warning",'
                         '"message":"Kildeadvarsel","result_set_path":["Arkivdel"],'
                         '"location":{"file_name":"arkiv.xml"}}')
            padding=',{"result_type":"Success","message":"ok","source_raw":{"Message":"'+'x'*4000+'"}}'
            for index in range(25_000):
                stream.write(padding)
            stream.write(']}]}')
        original_size=normalized.stat().st_size
        self.assertGreater(original_size,95_287_457)
        original_hash=sha256()
        with normalized.open('rb') as stream:
            for block in iter(lambda: stream.read(1024*1024),b''):
                original_hash.update(block)
        build_evidence(self.work,job_id=self.job_id)
        tracemalloc.start()
        try:
            with patch.dict(sys.modules, {
                'noark5_workflow.analysis.canonical_external_import_v0115_a10':real_external,
            }):
                result=analyze_external(self.work,job_id=self.job_id)
                audit=audit_evidence(self.work,job_id=self.job_id)
                linked=load_external_status(self.work)
                qa=_external(self.work,linked['analysis'],[],None)
            _,peak=tracemalloc.get_traced_memory()
        finally:
            tracemalloc.stop()
        self.assertLess(peak,100*1024*1024)
        self.assertEqual(result['sources'],3)
        self.assertEqual(audit['linked'],3)
        self.assertEqual(linked['state'],'linked')
        relative=normalized.relative_to(self.work).as_posix()
        self.assertEqual(linked['sources'][relative],'analyzed')
        source=next(item for item in linked['analysis']['sources'] if
                    item['evidence']['work_relative_path']==relative)
        self.assertEqual(source['evidence']['bytes'],original_size)
        self.assertEqual(source['evidence']['sha256'],original_hash.hexdigest())
        self.assertEqual(source['analysis']['record_count'],1)
        self.assertEqual(source['analysis']['records'][0]['reported_status'],'warning')
        self.assertEqual(source['analysis']['records'][0]['reported_result_counts']['Success'],25_000)
        self.assertEqual(qa['findings'][0]['message'],'Kildeadvarsel')
        self.assertIsNone(linked['analysis']['summary']['depot_approval'])

    def test_a220_over_limit_returns_failure_without_publishing(self):
        build_evidence(self.work,job_id=self.job_id)
        with patch.dict(sys.modules, {
            'noark5_workflow.analysis.canonical_external_import_v0115_a10':real_external,
        }), patch.object(real_external,'MAX_SOURCE_ARKADE',10):
            context=OperationContext(extraction_root=self.work,work_operations=self.work,
                                     metadata={'job_id':self.job_id})
            result=AnalyzeNoark5ExternalEvidenceOperation().run(context)
        self.assertFalse(result.ok)
        self.assertIn('external_evidence/arkade5/one/normalized/arkade5_results.json',result.message)
        self.assertIn('bytes',result.message)
        self.assertFalse((self.work/'noark5_evidence/canonical-external-analysis.json').exists())

    def test_a220_rejects_mutated_selected_evidence(self):
        build_evidence(self.work,job_id=self.job_id)
        normalized=self.ark/'normalized/arkade5_results.json'
        normalized.write_text('{"source_system":"Arkade 5","tests":[]}',encoding='utf-8')
        with self.assertRaisesRegex(EvidenceError,'endret siden kanonisering'):
            analyze_external(self.work,job_id=self.job_id)
        self.assertFalse((self.work/'noark5_evidence/canonical-external-analysis.json').exists())

    def test_conflicting_siegfried_statistics_cannot_be_published(self):
        write_json(self.sf/'pronom_statistics.json', {
            'source_system':'DWM / Siegfried',
            'evidence_type':'dwm_siegfried_pronom_identification',
            'format_version':1, 'files_total':7,'identified':8,
            'unidentified':0,'ambiguous':0, 'format_groups':[],
        })
        build_evidence(self.work,job_id=self.job_id)
        with self.assertRaisesRegex(EvidenceError,'selvmotsigende'):
            analyze_external(self.work,job_id=self.job_id)
        self.assertFalse((self.work/'noark5_evidence/canonical-external-analysis.json').exists())

    def test_audit_requires_source_hashes_and_no_auto_approval(self):
        build_evidence(self.work,job_id=self.job_id)
        analyze_external(self.work,job_id=self.job_id)
        result=audit_evidence(self.work,job_id=self.job_id)
        self.assertEqual(result['linked'],3)
        self.assertFalse(result['missing'])
        report=json.loads((self.work/'noark5_evidence/evidence-audit.json').read_text())
        self.assertIsNone(report['depot_approval'])
        self.assertIsNone(report['technical_approval'])

    def test_source_modified_after_snapshot_is_rejected(self):
        build_evidence(self.work,job_id=self.job_id)
        analyze_external(self.work,job_id=self.job_id)
        (self.sf/'pronom_statistics.json').write_text('{}',encoding='utf-8')
        with self.assertRaisesRegex(EvidenceError,'endret'):
            audit_evidence(self.work,job_id=self.job_id)

    def test_wrong_job_id_never_reads_another_job(self):
        with self.assertRaisesRegex(EvidenceError,'jobb'):
            build_evidence(self.work,job_id='JOB-001')

    def test_wrong_master_job_uid_is_not_used(self):
        manifest=self.run/'artifact_manifest.json'
        doc=json.loads(manifest.read_text())
        doc['job_uid']=str(uuid4())
        write_json(manifest,doc)
        with self.assertRaisesRegex(EvidenceError,'XPath-master'):
            build_evidence(self.work,job_id=self.job_id)

    def test_wrong_master_source_is_rejected(self):
        manifest=self.run/'artifact_manifest.json'
        doc=json.loads(manifest.read_text())
        doc['source_extraction']='/elsewhere'
        write_json(manifest,doc)
        with self.assertRaisesRegex(EvidenceError,'annen Source'):
            build_evidence(self.work,job_id=self.job_id)

    def test_tampered_original_arkade_is_rejected(self):
        (self.ark/'source/arkade.json').write_text('tampered',encoding='utf-8')
        with self.assertRaisesRegex(EvidenceError,'Arkade-kildehash'):
            build_evidence(self.work,job_id=self.job_id)

    def test_wrong_siegfried_uid_is_rejected(self):
        p=self.sf/'manifest.json';d=json.loads(p.read_text());d['job_uid']=str(uuid4());write_json(p,d)
        with self.assertRaisesRegex(EvidenceError,'varig jobb-ID'):
            build_evidence(self.work,job_id=self.job_id)

    def test_ambiguous_master_runs_are_not_merged(self):
        other=self.work/'noark5_tests/xpath/JOB-002__RUN002'
        write_json(other/'master-results.json',json.loads((self.run/'master-results.json').read_text()))
        doc=json.loads((self.run/'artifact_manifest.json').read_text());doc['run_id']='RUN002'
        write_json(other/'artifact_manifest.json',doc)
        with self.assertRaisesRegex(EvidenceError,'Flere ordinare'):
            build_evidence(self.work,job_id=self.job_id)

    def test_missing_external_families_are_recorded_not_zero(self):
        import shutil
        shutil.rmtree(self.work/'external_evidence')
        result=build_evidence(self.work,job_id=self.job_id)
        self.assertEqual(result['external_sources'],[])
        self.assertEqual(analyze_external(self.work,job_id=self.job_id)['sources'],0)
        report=audit_evidence(self.work,job_id=self.job_id)
        self.assertEqual(len(report['missing']),3)

    def test_qa_draft_is_never_automatic_approval(self):
        build_evidence(self.work,job_id=self.job_id)
        analyze_external(self.work,job_id=self.job_id)
        audit_evidence(self.work,job_id=self.job_id)
        result=build_qa_basis(self.work,job_id=self.job_id)
        self.assertEqual(result['summary']['unreviewed'],1)
        self.assertFalse(result['automatic_approval'])
        self.assertIn('UTKAST',Path(result['html']).read_text(encoding='utf-8'))
        self.assertIn('N5.29',Path(result['html']).read_text(encoding='utf-8'))

    def test_previous_canonical_version_is_preserved(self):
        build_evidence(self.work,job_id=self.job_id)
        target=self.work/'noark5_evidence/canonical-results.json'
        before=target.read_bytes()
        p=self.ark/'normalized/arkade5_results.json'
        write_json(p,{'source_system':'Arkade 5','tests':[{'test_id':'N5.88'}]})
        build_evidence(self.work,job_id=self.job_id)
        self.assertNotEqual(before,target.read_bytes())
        archived=list((self.work/'noark5_evidence/history').glob('canonical-results-*.json'))
        self.assertEqual(len(archived),1)
        self.assertEqual(archived[0].read_bytes(),before)


if __name__=='__main__':
    unittest.main()
