"""a10: selected sources, strict interpretation, no accidental acceptance."""
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
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
        self.patchers = [patch.dict(sys.modules, {
            'noark5_workflow': types.ModuleType('noark5_workflow'),
            'noark5_workflow.analysis': types.ModuleType('noark5_workflow.analysis'),
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
        self.external_module.inspect_external = lambda _: {'format': 'siegfried_json',
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


if __name__ == '__main__':
    unittest.main()
