"""Self-contained regression for external linkage and control matrix (synthetic Work)."""
import importlib.util
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
# The test is also runnable with an isolated delta (without the entire DWM repo).
import noark5_workflow.analysis as analysis_package
canonical_name = 'noark5_workflow.analysis.canonical_results'
if importlib.util.find_spec(canonical_name) is None:
    fake = types.ModuleType(canonical_name)
    fake._validate_work = lambda p: (p.resolve(), {'job_uid': 'test-uid'})
    sys.modules[canonical_name] = fake
    analysis_package.canonical_results = fake
external_name = 'noark5_workflow.analysis.canonical_external_v0115_a5'
if importlib.util.find_spec(external_name) is None:
    fake = types.ModuleType(external_name)
    fake.inspect_external = lambda path: {'format': 'unrecognized', 'interpretation': 'not_parsed'}
    sys.modules[external_name] = fake
from noark5_workflow.analysis.canonical_matrix_v0115_a11 import (
    evaluate_control_matrix, load_external_status,
)


class MatrixTests(unittest.TestCase):
    def setUp(self):
        from noark5_workflow.analysis import canonical_results
        patcher = patch.object(canonical_results, '_validate_work', side_effect=lambda p: (Path(p).resolve(), {'job_uid': 'test-uid'}))
        patcher.start()
        self.addCleanup(patcher.stop)
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / 'noark5_evidence').mkdir()
        (self.root / 'external_evidence/arkade5/r/normalized').mkdir(parents=True)
        self.canonical = self.root / 'noark5_evidence/canonical-results.json'
        self.canonical.write_text(json.dumps({
            'model_id': 'noark5.canonical-results.v1',
            'extraction': {'stable_id': 'test-uid'},
            'observations': [{'test_id': 'kdrs.c02', 'source_kind': 'dwm_master', 'status': 'ok'}],
        }))
        self.arkade = self.root / 'external_evidence/arkade5/r/normalized/arkade5_results.json'
        self.arkade.write_text('{"test":"N5.22"}')
        self.pronom = self.root / 'external_evidence/arkade5/r/normalized/pronom_statistics.json'
        self.pronom.write_text('{"formats":12}')
        self.analysis_file = self.root / 'noark5_evidence/canonical-external-analysis.json'
        self.profile = ROOT / 'config/noark5/control-profile-dwm-draft-v1.json'
        self.write_analysis()

    def write_analysis(self):
        sources = []
        for file, analysis in ((self.arkade, {
            'source_format': 'arkade_normalized_v2',
            'interpretation': 'reported_test_records_unverified',
            'record_count': 54, 'reported_status_counts': {'ok': 52, 'error': 2},
        }), (self.pronom, {
            'source_format': 'arkade_pronom_statistics_v1',
            'interpretation': 'format_statistics_only', 'format_rows': 12,
        })):
            sources.append({'evidence': {'work_relative_path': file.relative_to(self.root).as_posix(),
                                         'sha256': hashlib.sha256(file.read_bytes()).hexdigest()},
                            'analysis': analysis})
        self.analysis_file.write_text(json.dumps({
            'model_id': 'noark5.external-analysis.v1',
            'extraction_stable_id': 'test-uid',
            'canonical_reference': {'sha256': hashlib.sha256(self.canonical.read_bytes()).hexdigest()},
            'sources': sources,
        }))

    def test_linked_sources_show_as_analyzed(self):
        got = load_external_status(self.root)
        self.assertEqual(got['state'], 'linked')
        self.assertTrue(all(v == 'analyzed' for v in got['sources'].values()))

    def test_matrix_preserves_arkade_errors_and_draft_status(self):
        got = evaluate_control_matrix(self.root, self.profile)
        noark = next(r for r in got['controls'] if r['control_id'] == 'arkade_noark')
        self.assertEqual(noark['external_test_records'], 54)
        self.assertEqual(noark['external_status_counts'], {'error': 2, 'ok': 52})
        self.assertEqual(noark['assessment'], 'reported_errors_require_review')
        self.assertFalse(noark['test_outcomes_verified'])
        self.assertIsNone(noark['requirement_satisfied'])
        self.assertFalse(got['profile_approved'])
        self.assertIsNone(got['summary']['depot_approval'])
        self.assertEqual(next(r for r in got['controls'] if r['control_id'] == 'arkade_pronom')['pronom_format_rows'], 12)

    def test_changed_source_not_marked_analyzed(self):
        self.arkade.write_text('changed')
        got = load_external_status(self.root)
        self.assertEqual(got['sources'][self.arkade.relative_to(self.root).as_posix()], 'source_missing_or_changed')
        matrix = evaluate_control_matrix(self.root, self.profile)
        self.assertEqual(matrix['summary']['reported_arkade_errors'], 0)

    def test_changed_canonical_invalidates_external_link(self):
        self.canonical.write_text(self.canonical.read_text() + ' ')
        got = load_external_status(self.root)
        self.assertEqual(got['state'], 'stale_or_invalid')

    def test_missing_analysis_is_not_failure(self):
        self.analysis_file.unlink()
        got = load_external_status(self.root)
        self.assertEqual(got['state'], 'not_analyzed')
        matrix = evaluate_control_matrix(self.root, self.profile)
        self.assertIsNone(matrix['summary']['coverage_complete'])

    def test_no_duplicate_approval_through_required_coverage(self):
        matrix = evaluate_control_matrix(self.root, self.profile)
        self.assertEqual(matrix['summary']['required_categories'], 2)
        self.assertFalse(matrix['summary']['all_required_tests_verified'])
        self.assertIsNone(matrix['summary']['archive_creator_acceptance'])


if __name__ == '__main__':
    unittest.main()
