"""A260 a6: deterministic full-export, no silent preview truncation.

For 100k findings additionally run:
    set DWM_A260_STRESS=1
    py -m unittest tests.test_v023_a6_a260_large -v
"""
from __future__ import annotations

import csv
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from noark5_workflow.reporting.qa_a260_v023_a6 import (
    A260CapacityError, FindingWriter, _csv_cell, _finding_key, _html,
    _secure_work_file, iter_arkade_findings,
)


def event_stream(count: int, *, late_header: bool = False, test_id: str = 'N5.22'):
    """Produce ijson.parse-style event tuples without allocating source JSON."""
    yield '', 'start_map', None
    yield 'format_version', 'number', 2
    yield 'source_system', 'string', 'Arkade 5'
    yield 'tests', 'start_array', None
    yield 'tests.item', 'start_map', None
    if not late_header:
        yield 'tests.item.test_id', 'string', test_id
        yield 'tests.item.source_status', 'string', 'error' if count else 'ok'
        yield 'tests.item.number_of_errors', 'number', count
    yield 'tests.item.results', 'start_array', None
    for i in range(count):
        yield 'tests.item.results.item', 'start_map', None
        yield 'tests.item.results.item.result_type', 'string', 'Error'
        yield 'tests.item.results.item.message', 'string', 'Feilstatus ' + str(i)
        yield 'tests.item.results.item.result_set_path', 'start_array', None
        yield 'tests.item.results.item.result_set_path.item', 'string', 'Arkivdel: 123'
        yield 'tests.item.results.item.result_set_path', 'end_array', None
        yield 'tests.item.results.item.location', 'start_map', None
        yield 'tests.item.results.item.location.file_name', 'string', 'arkivstruktur.xml'
        yield 'tests.item.results.item.location.line_numbers', 'start_array', None
        yield 'tests.item.results.item.location.line_numbers.item', 'number', i + 1
        yield 'tests.item.results.item.location.line_numbers', 'end_array', None
        yield 'tests.item.results.item.location', 'end_map', None
        yield 'tests.item.results.item', 'end_map', None
    yield 'tests.item.results', 'end_array', None
    if late_header:
        yield 'tests.item.test_id', 'string', test_id
        yield 'tests.item.source_status', 'string', 'error' if count else 'ok'
        yield 'tests.item.number_of_errors', 'number', count
    yield 'tests.item', 'end_map', None
    yield 'tests', 'end_array', None
    yield '', 'end_map', None


def export_case(count: int, *, late_header: bool = False, message=''):
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        writer = FindingWriter(root/'funn.jsonl', root/'funn.csv')
        try:
            for row in iter_arkade_findings(event_stream(count, late_header=late_header),
                                            source_ref='external_evidence/arkade5/a/normalized/arkade5_results.json',
                                            source_sha='a'*64):
                writer.add(row)
            summary = writer.summary()
            preview = writer.preview
        finally:
            writer.close()
        lines = (root/'funn.jsonl').read_text(encoding='utf-8').splitlines()
        with (root/'funn.csv').open('r',encoding='utf-8-sig',newline='') as handle:
            csv_lines = list(csv.DictReader(handle,delimiter=';'))
        html = _html(summary, preview, 'JOB-001', 'a260_exports_v023_a6/abcd')
        return summary, lines, csv_lines, preview, html


class A260CompleteExportTests(unittest.TestCase):
    def test_000_zero_findings(self):
        summary, lines, csv_rows, preview, html = export_case(0)
        self.assertEqual((summary['total'], len(lines), len(csv_rows),len(preview)), (0,0,0,0))
        self.assertIn('Ingen funn', html)

    def test_300_boundary(self):
        summary, lines, csv_rows, preview, html = export_case(300)
        self.assertEqual((summary['total'],len(lines),len(csv_rows)),(300,300,300))
        self.assertEqual(len(preview),250)
        self.assertIn('Viser de første 250 av 300 funn', html)

    def test_301_no_failure_and_immutable_full_count(self):
        summary, lines, csv_rows, preview, html = export_case(301)
        self.assertEqual((summary['total'],summary['errors']), (301,301))
        self.assertEqual((len(lines),len(csv_rows)), (301,301))
        self.assertEqual(csv_rows[-1]['message'],'Feilstatus 300')
        self.assertIn('301', html)
        self.assertIn('CSV (alle funn)', html)
        self.assertIn('JSONL (alle funn)', html)
        self.assertEqual(json.loads(lines[300])['lines'],[301])

    def test_10k_full_export(self):
        summary, lines, csv_rows, preview, html = export_case(10000)
        self.assertEqual((summary['total'],len(lines),len(csv_rows)),(10000,10000,10000))
        self.assertEqual(summary['by_test'], {'N5.22':10000})
        self.assertEqual(summary['by_arkade_test'], {'N5.22':10000})
        self.assertEqual(len(preview),250)
        self.assertIn('Viser de første 250 av 10000 funn', html)

    @unittest.skipUnless(os.environ.get('DWM_A260_STRESS') == '1',
                         'Sett DWM_A260_STRESS=1 for 100 000-funn-kapasitetstest')
    def test_100k_full_export_stress(self):
        import tracemalloc
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            writer=FindingWriter(root/'funn.jsonl', root/'funn.csv')
            tracemalloc.start()
            try:
                for row in iter_arkade_findings(event_stream(100000),
                                                source_ref='arkade/normalized/arkade5_results.json',
                                                source_sha='a'*64):
                    writer.add(row)
                peak=tracemalloc.get_traced_memory()[1]
                summary=writer.summary()
            finally:
                tracemalloc.stop()
                writer.close()
            self.assertEqual(summary['total'],100000)
            self.assertLess(peak,64*1024*1024)
            with (root/'funn.jsonl').open(encoding='utf-8') as inp:
                self.assertEqual(sum(1 for _ in inp),100000)
            with (root/'funn.csv').open(encoding='utf-8-sig') as inp:
                self.assertEqual(sum(1 for _ in inp),100001)

    def test_metadata_order_after_results_keeps_all_rows(self):
        summary, lines, _, _, _ = export_case(7,late_header=True)
        self.assertEqual(summary['total'],7)
        self.assertEqual(json.loads(lines[0])['test_id'],'N5.22')

    def test_missing_source_envelope_is_rejected(self):
        events = [('','start_map',None),('tests','start_array',None),
                  ('tests','end_array',None),('','end_map',None)]
        with self.assertRaises(A260CapacityError):
            list(iter_arkade_findings(events,source_ref='path',source_sha='a'*64))

    def test_source_status_without_details_is_one_aggregate_not_invented_occurrences(self):
        events = iter(event_stream(0))
        def changed():
            for pre,kind,val in events:
                if pre == 'tests.item.source_status':
                    val='error'
                if pre == 'tests.item.number_of_errors':
                    val=12
                yield pre,kind,val
        rows=list(iter_arkade_findings(changed(),source_ref='path',source_sha='a'*64))
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]['lines'],[])
        self.assertIn('check its original source report',rows[0]['message'])

    def test_identical_findings_have_unique_occurrence_id(self):
        events=list(event_stream(2))
        for i, item in enumerate(events):
            if item[0]=='tests.item.results.item.message':
                events[i]=(item[0],item[1],'Identisk feiltekst')
            elif item[0]=='tests.item.results.item.location.line_numbers.item':
                events[i]=(item[0],item[1],7)
        rows=list(iter_arkade_findings(events,source_ref='path',source_sha='a'*64))
        self.assertEqual(rows[0]['finding_key'],rows[1]['finding_key'])
        self.assertNotEqual(rows[0]['finding_uid'],rows[1]['finding_uid'])

    def test_csv_spreadsheet_formula_safety_without_modifying_jsonl(self):
        self.assertEqual(_csv_cell('=cmd!A0'),"'=cmd!A0")
        self.assertEqual(_csv_cell('normal'),'normal')
        self.assertEqual(_csv_cell('  +99'),"'  +99")
        self.assertEqual(_csv_cell('=cmd!A0'),"'=cmd!A0")

    def test_exact_review_fingerprint(self):
        row={'source':'Arkade 5','test_id':'N5.15','severity':'ERROR',
             'message':'avvik','context':'kontekst','file':'arkivstruktur.xml',
             'lines':[21],'source_ref':'proof'}
        try:
            from noark5_workflow.reporting.qa_review_v021_a13 import finding_key
        except ImportError:
            self.skipTest('Krever fullstendig DWM-repo (ikke bare delta ZIP)')
        self.assertEqual(_finding_key(row), finding_key(row))

    def test_symlink_outside_work_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            (root/'ok.json').write_text('{}')
            self.assertEqual(_secure_work_file(root,'ok.json'),root/'ok.json')
            with self.assertRaises(A260CapacityError):
                _secure_work_file(root,'../etc/passwd')
            link = root/'shortcut.json'
            try:
                link.symlink_to(root/'ok.json')
            except OSError as exc:
                if getattr(exc, 'winerror', None) != 1314:
                    raise
                # Windows without Developer Mode/symlink privilege: keep the
                # security assertion, rather than failing test setup or
                # requiring the user to run test.bat as Administrator.
                with patch.object(Path, 'is_symlink', autospec=True,
                                  side_effect=lambda candidate: candidate == link):
                    with self.assertRaisesRegex(A260CapacityError, 'Symbolsk lenke'):
                        _secure_work_file(root,'shortcut.json')
            else:
                with self.assertRaisesRegex(A260CapacityError, 'Symbolsk lenke'):
                    _secure_work_file(root,'shortcut.json')

    def test_symlink_windows_1314_fallback_still_rejects(self):
        # Exercise the Windows fallback deterministically on every OS.
        denied = OSError('Windows symlink privilege unavailable')
        denied.winerror = 1314
        with patch.object(Path, 'symlink_to', side_effect=denied):
            self.test_symlink_outside_work_rejected()

    def test_symlink_unexpected_oserror_is_not_masked(self):
        with patch.object(Path, 'symlink_to', side_effect=OSError('Other I/O error')):
            with self.assertRaisesRegex(OSError, 'Other I/O error'):
                self.test_symlink_outside_work_rejected()




def document_events(obj, prefix=''):
    """Small deterministic stand-in for ijson.parse for full-output integration."""
    if isinstance(obj, dict):
        yield prefix, 'start_map', None
        for key, value in obj.items():
            yield prefix, 'map_key', key
            yield from document_events(value, prefix + '.' + key if prefix else key)
        yield prefix, 'end_map', None
    elif isinstance(obj, list):
        yield prefix, 'start_array', None
        for value in obj:
            yield from document_events(value, prefix + '.item')
        yield prefix, 'end_array', None
    else:
        kind = ('null' if obj is None else 'boolean' if isinstance(obj, bool) else
                'number' if isinstance(obj, (int, float)) else 'string')
        yield prefix, kind, obj


class A260OperationIntegrationTests(unittest.TestCase):
    def test_301_finds_plus_one_dwm_and_verifies_sources_and_manifest(self):
        import hashlib
        import sys
        import types
        from noark5_workflow.reporting import qa_a260_v023_a6 as a6
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            work = root/'work'
            evidence = work/'noark5_evidence'
            evidence.mkdir(parents=True)
            relative = 'external_evidence/arkade5/one/normalized/arkade5_results.json'
            source = work/relative
            source.parent.mkdir(parents=True)
            normalized = {'format_version': 2, 'source_system': 'Arkade 5',
                          'tests': [{'test_id': 'N5.22', 'source_status': 'error',
                                     'number_of_errors': 301,
                                     'results': [{'result_type': 'Error',
                                                  'message': 'Test '+str(i),
                                                  'location': {'file_name':'arkivstruktur.xml',
                                                               'line_numbers':[i+10]},
                                                  'result_set_path':['Arkivdel 1']}
                                                 for i in range(301)]}]}
            source.write_text(json.dumps(normalized),encoding='utf-8')
            source_hash = hashlib.sha256(source.read_bytes()).hexdigest()
            uid = 'test-job-uid'
            (evidence/'evidence-audit.json').write_text(json.dumps({'job_uid':uid}),encoding='utf-8')
            (evidence/'canonical-results.json').write_text(json.dumps({
                'extraction': {'stable_id':uid},
                'a7_evidence_sources': {'arkade_noark': {'file':relative,'sha256':source_hash}}
            }),encoding='utf-8')
            depotrel = 'noark5_reports/depot_validation/JOB-001__RUN/depot_validation_report.json'
            depot = work/depotrel
            depot.parent.mkdir(parents=True)
            depot.write_text(json.dumps({'report_type':'noark5_depot_validation'}),encoding='utf-8')
            operation = types.ModuleType('noark5_workflow.operations.canonical_evidence_v022_a7')
            operation.ROOT_NAME = 'noark5_evidence'
            operation._work_identity = lambda path,job: (path, {'job_uid':uid,'job_id':'JOB-001'})
            operation._read = lambda path: json.loads(path.read_text(encoding='utf-8'))
            workflow = types.ModuleType('noark5_workflow.reporting.qa_workflow_v022_a3')
            def fails(**kwargs):
                raise ValueError('Too many Arkade findings for this report')
            workflow.build_review_snapshot_v022_a3 = fails
            decision = types.ModuleType('noark5_workflow.reporting.qa_decision_v021_a12')
            decision._find_depot = lambda root,chosen: (depot,depotrel)
            decision._json = lambda path,limit: json.loads(path.read_text(encoding='utf-8'))
            decision.MAX_DEPO = 24*1024*1024
            fake_ijson = types.ModuleType('ijson')
            fake_ijson.parse = lambda file: document_events(json.load(file))
            def extra(*args,**kwargs):
                yield {'source':'DWM depotvalidering','test_id':'C01',
                       'severity':'REVIEW','message':'DWM avvik',
                       'context':'','file':'','lines':[],
                       'source_ref':depotrel,'requires_review':True}
            with patch.dict(sys.modules, {
                'noark5_workflow.operations.canonical_evidence_v022_a7': operation,
                'noark5_workflow.reporting.qa_workflow_v022_a3': workflow,
                'noark5_workflow.reporting.qa_decision_v021_a12': decision,
                'ijson': fake_ijson,
            }), patch.object(a6,'_reviews',return_value={}), patch.object(a6,'_manual_and_depot_findings', side_effect=extra):
                result = a6.build_qa_basis_a6(work)
                self.assertEqual(result['summary']['total'],302)
                self.assertEqual(result['summary']['errors'],301)
                self.assertEqual(result['summary']['review_points'],1)
                doc = json.loads(Path(result['path']).read_text(encoding='utf-8'))
                self.assertFalse(doc['automatic_approval'])
                self.assertEqual(doc['dependency_no'],260)
                self.assertEqual(doc['source_arkade_sha256'],source_hash)
                export = work/doc['exports']['jsonl']
                lines = export.read_text(encoding='utf-8').splitlines()
                self.assertEqual(len(lines),302)
                self.assertEqual(json.loads(lines[-1])['source'],'DWM depotvalidering')
                manifest = json.loads((export.parent/'manifest.json').read_text(encoding='utf-8'))
                self.assertEqual(manifest['files']['funn.jsonl']['sha256'],
                                 hashlib.sha256(export.read_bytes()).hexdigest())
                html = Path(result['html']).read_text(encoding='utf-8')
                self.assertIn('Viser de første 250 av 302 funn',html)
                self.assertIn('ikke uavhengig verifisert',html)
                self.assertIn('funn.csv',html)
                self.assertEqual(source_hash,hashlib.sha256(source.read_bytes()).hexdigest())


class A260PronomStreamingTests(unittest.TestCase):
    def test_historical_raf_source_rows_are_separate_and_verified(self):
        from hashlib import sha256
        import sys
        import types
        from noark5_workflow.reporting.qa_a260_v023_a6 import _large_pronom_raf_candidates
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'pronom_statistics.json'
            doc={'evidence_type':'arkade5_pronom_format_statistics',
                 'source':{'original_name':'arkade.csv'},
                 'csv':{'rows':[
                     {'RAF-220301':'Ikke gyldig','Format-ID':'fmt/20','Antall':'12',
                      'Filtype':'PDF','Formatversjon':'1.4'},
                     {'RAF-220301':'Gyldig','Format-ID':'fmt/21','Antall':'2'}]}}
            path.write_text(json.dumps(doc),encoding='utf-8')
            digest=sha256(path.read_bytes()).hexdigest()
            fake=types.ModuleType('ijson')
            fake.parse=lambda stream: document_events(json.load(stream))
            with patch.dict(sys.modules,{'ijson':fake}):
                items=list(_large_pronom_raf_candidates(path,'verified/pronom_statistics.json',digest))
            self.assertEqual(len(items),1)
            self.assertEqual(items[0]['test_id'],'RAF-220301:fmt/20')
            self.assertEqual(items[0]['severity'],'REVIEW')
            self.assertIn('Historisk',items[0]['message'])
            self.assertEqual(items[0]['file'],'arkade.csv')

if __name__ == '__main__':
    unittest.main()
