"""a10: selected sources, strict interpretation, no accidental acceptance."""
import importlib.util
import importlib
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import tracemalloc
import types
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'noark5_workflow/analysis/canonical_external_import_v0115_a10.py'
spec = importlib.util.spec_from_file_location('a10_external_test_module', SOURCE)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


class ExternalImportTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.work = self.root / 'work'
        (self.work / 'external_evidence' / 'arkade5' / 'run' / 'normalized').mkdir(parents=True)
        (self.work / 'noark5_evidence').mkdir()
        self.uid = 'test-work-id'
        (self.work / 'noark5_evidence' / 'canonical-results.json').write_text(json.dumps({
            'model_id': 'noark5.canonical-results.v1',
            'extraction': {'stable_id': self.uid}, 'observations': []}), encoding='utf-8')
        self.path = self.work / 'external_evidence/arkade5/run/normalized/arkade5_results.json'
        self.canonical_module = types.ModuleType('noark5_workflow.analysis.canonical_results')
        self.canonical_module._validate_work = lambda p: (self.work, {'job_uid': self.uid})
        self.external_module = types.ModuleType('noark5_workflow.analysis.canonical_external_v0115_a5')
        self.external_module.inspect_external = lambda p: {'format': 'unrecognized', 'interpretation': 'not_parsed'}
        self.external_module.inspect_external_doc = lambda p: {'format': 'unrecognized', 'interpretation': 'not_parsed'}
        self.external_module.MAX_RECORDS = 100_000
        self.external_module.MAX_MATCHES = 1_000_000
        analysis_package = types.ModuleType('noark5_workflow.analysis')
        analysis_package.__path__ = [str(ROOT / 'noark5_workflow/analysis')]
        self.patchers = [patch.dict(sys.modules, {
            'noark5_workflow': types.ModuleType('noark5_workflow'),
            'noark5_workflow.analysis': analysis_package,
            'noark5_workflow.analysis.canonical_results': self.canonical_module,
            'noark5_workflow.analysis.canonical_external_v0115_a5': self.external_module,
        })]
        self.patchers[0].start()
        self.addCleanup(self.patchers[0].stop)

    def test_normalized_arkade_preserves_status_text_not_approval(self):
        self.path.write_text(json.dumps({'results': [
            {'test_id': 'A-1', 'status': 'WARNING'},
            {'id': 'A-2', 'status': 'Passed??'},
        ]}), encoding='utf-8')
        result = mod.analyze_external_results(self.work, (self.path,), write=True)
        record = result['sources'][0]['analysis']
        self.assertEqual(record['interpretation'], 'reported_test_records_unverified')
        self.assertEqual([x['reported_status'] for x in record['records']], ['WARNING', 'Passed??'])
        self.assertTrue(all(x['technical_verification'] == 'not_verified' for x in record['records']))
        self.assertIsNone(result['summary']['depot_approval'])
        self.assertEqual(len(result['sources'][0]['evidence']['sha256']), 64)
        self.assertTrue((self.work / mod.OUT).is_file())

    def test_unknown_arkade_shape_is_not_parsed(self):
        self.path.write_text(json.dumps({'other': {'status': 'OK'}}), encoding='utf-8')
        result = mod.analyze_external_results(self.work, (self.path,), write=False)
        self.assertEqual(result['summary']['unparsed_files'], 1)
        self.assertEqual(result['summary']['reported_external_test_records'], 0)

    def test_malformed_entries_do_not_promote_partial_statuses(self):
        self.path.write_text(json.dumps({'tests': [{'id': 'a', 'status': 'OK'}, {'id': 'b'}]}), encoding='utf-8')
        result = mod.analyze_external_results(self.work, (self.path,), write=False)
        self.assertEqual(result['sources'][0]['analysis']['interpretation'], 'not_parsed')

    def test_siegfried_is_identification_not_validation(self):
        self.path.write_text(json.dumps({'siegfried': '1.11', 'files': []}), encoding='utf-8')
        self.external_module.inspect_external_doc = lambda _: {'format': 'siegfried_json',
            'interpretation': 'format_identification_only', 'file_records': 0}
        result = mod.analyze_external_results(self.work, (self.path,), write=False)
        self.assertEqual(result['summary']['format_identification_files'], 1)
        self.assertFalse(result['summary']['technical_validation_verified'])

    def test_reject_escape_and_duplicate(self):
        self.path.write_text('{}', encoding='utf-8')
        other = self.root / 'outside.json'
        other.write_text('{}', encoding='utf-8')
        with self.assertRaises(mod.ExternalImportError):
            mod.analyze_external_results(self.work, (other,), write=False)
        with self.assertRaises(mod.ExternalImportError):
            mod.analyze_external_results(self.work, (self.path, self.path), write=False)

    def test_reject_wrong_canonical_job(self):
        self.path.write_text('{}', encoding='utf-8')
        canonical = self.work / 'noark5_evidence/canonical-results.json'
        obj = json.loads(canonical.read_text(encoding='utf-8'))
        obj['extraction']['stable_id'] = 'different-job'
        canonical.write_text(json.dumps(obj), encoding='utf-8')
        with self.assertRaises(mod.ExternalImportError):
            mod.analyze_external_results(self.work, (self.path,), write=False)

    def test_discover_nested_sources_without_manual_navigation(self):
        pronom = self.path.with_name('pronom_statistics.json')
        self.path.write_text('{"tests":[]}', encoding='utf-8')
        pronom.write_text('{"csv":{}}', encoding='utf-8')
        candidates = mod.discover_analysis_candidates(self.work)
        names = {Path(c['path']).name for c in candidates}
        self.assertEqual(names, {'arkade5_results.json', 'pronom_statistics.json'})
        self.assertTrue(all(c['selected'] is False for c in candidates))

    def test_two_sources_one_snapshot_and_recalled_selection(self):
        pronom = self.path.with_name('pronom_statistics.json')
        self.path.write_text(json.dumps({'tests': [{'test_id': 'N5.01', 'status': 'ok'}]}), encoding='utf-8')
        pronom.write_text(json.dumps({
            'format_version': 1, 'evidence_type': 'arkade5_pronom_format_statistics',
            'source_system': 'Arkade 5', 'csv': {'rows': [
                {'Format-ID': 'fmt/17', 'Filtype': 'PDF', 'Formatversjon': '1.3',
                 'RAF-220301': 'Ikke gyldig', 'Antall': '2'}]}}), encoding='utf-8')
        result = mod.analyze_external_results(self.work, (self.path, pronom))
        self.assertEqual(result['summary']['selected_files'], 2)
        self.assertEqual(result['summary']['reported_external_test_records'], 1)
        self.assertEqual(result['summary']['unparsed_files'], 0)
        self.assertEqual(result['sources'][1]['analysis']['reported_total_files'], 2)
        candidates = mod.discover_analysis_candidates(self.work)
        self.assertEqual(len(mod.previous_analysis_selection(self.work, candidates)), 2)
        self.assertEqual(result['sources'][0]['analysis']['records'][0]['reported_status'], 'ok')
        self.assertIsNone(result['summary']['depot_approval'])

    def test_discovery_ignores_other_files_and_symlinks(self):
        unknown = self.path.with_name('random_results.json')
        unknown.write_text('{}', encoding='utf-8')
        outside = self.root / 'other.json'
        outside.write_text('{}', encoding='utf-8')
        link = self.path.with_name('pronom_statistics.json')
        try:
            link.symlink_to(outside)
        except (OSError, NotImplementedError):
            pass
        self.assertEqual(mod.discover_analysis_candidates(self.work), [])

    def test_dry_run_does_not_write(self):
        self.path.write_text('{}', encoding='utf-8')
        mod.analyze_external_results(self.work, (self.path,), write=False)
        self.assertFalse((self.work / mod.OUT).exists())

    def test_non_json_remains_opaque(self):
        path = self.work / 'external_evidence/arkade5/report.xml'
        path.write_text('<report/>', encoding='utf-8')
        result = mod.analyze_external_results(self.work, (path,), write=False)
        self.assertEqual(result['summary']['unparsed_files'], 1)

    def test_output_does_not_modify_source(self):
        self.path.write_text('{"data": 1}', encoding='utf-8')
        before = self.path.read_bytes()
        mod.analyze_external_results(self.work, (self.path,), write=True)
        self.assertEqual(self.path.read_bytes(), before)

    def test_source_limit_boundaries_and_context(self):
        with patch.object(mod, 'MAX_SOURCE_ARKADE', 100):
            for size in (99, 100, 101):
                self.path.write_bytes(b'{}' + b' ' * (size - 2))
                if size <= 100:
                    self.assertEqual(mod._inside(self.work, self.path)[1], self.path.relative_to(self.work).as_posix())
                else:
                    with self.assertRaisesRegex(mod.ExternalImportError, r'101 bytes.*100 bytes') as error:
                        mod.analyze_external_results(self.work, (self.path,), write=True)
                    self.assertIn(self.path.relative_to(self.work).as_posix(), str(error.exception))
                    self.assertFalse((self.work / mod.OUT).exists())

    def test_large_native_siegfried_streams_with_bounded_memory(self):
        path = self.work / 'external_evidence/siegfried/run/native.json'
        path.parent.mkdir(parents=True)
        with path.open('w', encoding='utf-8') as stream:
            stream.write('{"siegfried":"1.11","files":[')
            for i in range(90_000):
                if i:
                    stream.write(',')
                stream.write('{"filename":"' + str(i) + 'x' * 350 + '","matches":[{"ns":"pronom","id":"fmt/18"}]}')
            stream.write(']}')
        original_size = path.stat().st_size
        self.assertGreater(original_size, 30_000_000)
        original_hash = hashlib.sha256(path.read_bytes()).hexdigest()
        tracemalloc.start()
        try:
            doc = mod.analyze_external_results(self.work, (path,), write=True)
            _, peak = tracemalloc.get_traced_memory()
        finally:
            tracemalloc.stop()
        self.assertLess(peak, 20 * 1024 * 1024)
        self.assertEqual(doc['sources'][0]['evidence']['bytes'], original_size)
        self.assertEqual(doc['sources'][0]['evidence']['sha256'], original_hash)
        self.assertEqual(doc['sources'][0]['analysis']['file_records'], 90_000)
        self.assertEqual(doc['sources'][0]['analysis']['identifiers'][0]['matches'], 90_000)
        self.assertEqual(path.stat().st_size, original_size)

    def test_large_normalized_arkade_keeps_source_status(self):
        with self.path.open('w', encoding='utf-8') as stream:
            stream.write('{"results":[')
            for i in range(100_000):
                if i:
                    stream.write(',')
                stream.write(json.dumps({'test_id': str(i) + 'x' * 280, 'status': 'WARNING'}))
            stream.write(']}')
        self.assertGreater(self.path.stat().st_size, 30_000_000)
        doc = mod.analyze_external_results(self.work, (self.path,), write=True)
        analysis = doc['sources'][0]['analysis']
        self.assertEqual(analysis['record_count'], 100_000)
        self.assertEqual(analysis['records'][-1]['reported_status'], 'WARNING')
        self.assertIsNone(doc['summary']['depot_approval'])

    def test_large_normalized_pronom_keeps_reported_counts(self):
        path = self.path.with_name('pronom_statistics.json')
        with path.open('w', encoding='utf-8') as stream:
            stream.write('{"format_version":1,"evidence_type":"arkade5_pronom_format_statistics",'
                         '"source_system":"Arkade 5","csv":{"rows":[')
            for i in range(100_000):
                if i:
                    stream.write(',')
                stream.write(json.dumps({'Format-ID':f'fmt/{i}', 'Filtype':'PDF',
                    'Formatversjon':'1', 'RAF-220301':'Uavklart', 'Antall':'1',
                    'unused':'x'*240}))
            stream.write(']}}')
        self.assertGreater(path.stat().st_size, 30_000_000)
        doc = mod.analyze_external_results(self.work, (path,), write=True)
        analysis = doc['sources'][0]['analysis']
        self.assertEqual(analysis['format_rows'], 100_000)
        self.assertEqual(analysis['reported_total_files'], 100_000)
        self.assertEqual(analysis['formats'][0]['reported_raf_220301'], 'Uavklart')
        self.assertIsNone(analysis['depot_approval'])

    def test_streaming_arkade_matches_small_file_semantics(self):
        from noark5_workflow.analysis.streaming_arkade import inspect_arkade_stream
        source = {'format_version': 2, 'evidence_type': 'external_validation_report',
                  'source_system': 'Arkade 5', 'source_version': '2.13',
                  'summary': {'number_of_tests_run': 1, 'number_of_errors': 1,
                              'number_of_warnings': 0, 'archive_type': 'Noark 5',
                              'system_name': 'Test', 'archival_period': '2020-2021'},
                  'tests': [{'test_id': 'N5.01', 'test_name': 'Kontroll',
                             'test_type': 'Noark', 'source_status': 'error',
                             'number_of_errors': 1,
                             'results': [{'result_type': 'Success', 'message': 'ok'},
                                         {'result_type': 'Error', 'message': 'Feil',
                                          'result_set_path': ['Arkivdel'],
                                          'location': {'file_name': 'arkiv.xml'}}],
                             'source_raw': {'duplicate': ['x'] * 100}}]}
        self.path.write_text(json.dumps(source), encoding='utf-8')
        relative = self.path.relative_to(self.work).as_posix()
        expected = mod._arkade_entries(source, relative)
        actual = inspect_arkade_stream(self.path, relative, max_items=mod.MAX_ITEMS,
                                       max_output=mod.MAX_ANALYSIS_OUTPUT)
        self.assertEqual(actual, expected)

    def test_streaming_arkade_rejects_malformed_and_excess_without_output(self):
        from noark5_workflow.analysis import streaming_arkade
        malformed = '{"format_version":2,"evidence_type":"external_validation_report",'
        excessive = json.dumps({'format_version':2,
            'evidence_type':'external_validation_report','source_system':'Arkade 5',
            'tests':[{'test_id':'N5.01','source_status':'warning','number_of_errors':0,
                      'results':[{'result_type':'Warning'},{'result_type':'Success'}]}]})
        long_text = json.dumps({'format_version':2,
            'evidence_type':'external_validation_report','source_system':'Arkade 5',
            'tests':[{'test_id':'N5.01','source_status':'ok','number_of_errors':0,
                      'results':[], 'source_raw':'x'*101}]})
        with patch.object(mod,'MAX_SOURCE_NORMALIZED',0), \
             patch.object(mod,'MAX_ITEMS',1), \
             patch.object(streaming_arkade,'MAX_STRING',100):
            for payload, fragment in ((malformed,'Ugyldig normalisert Arkade JSON'),
                                      (excessive,'Resultatposter per test'),
                                      (long_text,'JSON-teksttoken overstiger')):
                with self.subTest(fragment=fragment):
                    self.path.write_text(payload,encoding='utf-8')
                    with self.assertRaisesRegex(mod.ExternalImportError,fragment) as caught:
                        mod.analyze_external_results(self.work,(self.path,),write=True)
                    self.assertIn(self.path.relative_to(self.work).as_posix(),str(caught.exception))
                    self.assertFalse((self.work/mod.OUT).exists())

    def test_string_preflight_counts_escaped_quotes(self):
        self.path.write_bytes(b'{"v":"a\\\"b"}')
        expected = hashlib.sha256(self.path.read_bytes()).hexdigest()
        self.assertEqual(mod._sha(self.path, max_string_bytes=4), expected)
        with self.assertRaisesRegex(mod.ExternalImportError, 'JSON-teksttoken'):
            mod._sha(self.path, max_string_bytes=3)

    def test_native_malformed_record_and_count_limits_fail_without_output(self):
        path = self.work / 'external_evidence/siegfried/run/native.json'
        path.parent.mkdir(parents=True)
        cases = (
            ('{"siegfried":"1","files":[', 'Malformed JSON'),
            ('{"siegfried":"1","files":[{"matches":[' +
             '{"ns":"pronom","id":"fmt/1"},' * 2 +
             '{"ns":"pronom","id":"fmt/1"}]}]}', 'Matches exceed'),
            ('{"siegfried":"1","files":[{"matches":[]},{"matches":[]}]}', 'File records exceed'),
            ('{"siegfried":"1","files":[{"matches":[],"name":"' +
             'x' * (2 * 1024 * 1024) + '"}]}', 'JSON element exceeds'),
        )
        streaming = importlib.import_module('noark5_workflow.analysis.streaming_siegfried')
        with patch.object(streaming, 'MAX_MATCHES', 2), patch.object(streaming, 'MAX_RECORDS', 1):
            for source, message in cases:
                path.write_text(source, encoding='utf-8')
                with self.subTest(message=message):
                    with self.assertRaisesRegex(mod.ExternalImportError, message) as error:
                        mod.analyze_external_results(self.work, (path,), write=True)
                    self.assertIn(path.relative_to(self.work).as_posix(), str(error.exception))
                    self.assertFalse((self.work / mod.OUT).exists())

    def test_symlink_is_rejected_and_canonical_limit_is_separate(self):
        self.path.write_text('{}', encoding='utf-8')
        link = self.path.with_name('linked.json')
        try:
            link.symlink_to(self.path)
        except (OSError, NotImplementedError):
            self.skipTest('Symlinks unavailable')
        with self.assertRaisesRegex(mod.ExternalImportError, 'Symbolsk lenke'):
            mod.analyze_external_results(self.work, (link,), write=True)
        directory_link = self.work / 'external_evidence/arkade5/linked'
        directory_link.symlink_to(self.path.parent, target_is_directory=True)
        with self.assertRaisesRegex(mod.ExternalImportError, 'Symbolsk lenke'):
            mod.analyze_external_results(self.work, (directory_link / self.path.name,), write=True)
        canonical = self.work / 'noark5_evidence/canonical-results.json'
        with patch.object(mod, 'MAX_CANONICAL_REFERENCE', canonical.stat().st_size - 1):
            with self.assertRaisesRegex(mod.ExternalImportError, 'Kanonisk resultatindeks'):
                mod.analyze_external_results(self.work, (self.path,), write=True)
        self.assertFalse((self.work / mod.OUT).exists())

    def test_generated_output_limit_boundary_is_atomic(self):
        self.path.write_text('{}', encoding='utf-8')
        timestamp = '2026-11-19T00:00:00Z'
        document = mod.analyze_external_results(self.work, (self.path,), write=False,
                                                generated_at=timestamp)
        size = len((json.dumps(document, indent=2, ensure_ascii=False,
                               allow_nan=False) + '\n').encode('utf-8'))
        with patch.object(mod, 'MAX_ANALYSIS_OUTPUT', size - 1):
            with self.assertRaisesRegex(mod.ExternalImportError, 'Generert ekstern analyse') as error:
                mod.analyze_external_results(self.work, (self.path,), write=True,
                                             generated_at=timestamp)
            self.assertIn(self.path.relative_to(self.work).as_posix(), str(error.exception))
            self.assertFalse((self.work / mod.OUT).exists())
        for limit in (size, size + 1):
            with patch.object(mod, 'MAX_ANALYSIS_OUTPUT', limit):
                mod.analyze_external_results(self.work, (self.path,), write=True,
                                             generated_at=timestamp)
                self.assertEqual((self.work / mod.OUT).stat().st_size, size)


if __name__ == '__main__':
    unittest.main()
