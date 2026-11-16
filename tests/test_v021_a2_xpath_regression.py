"""v0.2.1-a2: static KDRS crosswalk, saved U1/U2 evidence and DWM engine parity."""
from __future__ import annotations

import ast
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.noark5_xpath_audit_v021_a1 import load_rows
from app.noark5_xpath_regression_v021_a2 import (
    _fragment_status, _safe_work_index, source_crosswalk,
    discover_saved_regressions, inspect_saved_regression,
    compare_dwm_result_dirs, execute_dwm_engine_parity,
    build_audit, main,
)


class Fixture(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.project = Path(self.temp.name) / 'repo'
        self.project.mkdir()
        path = self.project / 'config/noark5/tests'
        path.mkdir(parents=True)
        self.catalog = path / 'xpath_catalog_2026_05_26.json'
        self.tests = [
            self.make_def('kdrs.c01', 'C01', exprs=[
                'count(//arkiv)', 'count(//arkivskaper)', 'count(//mappe[@type="saksmappe"])']),
            self.make_def('kdrs.c02', 'C02', exprs=['count(//arkivdel)']),
            self.make_def('kdrs.c03', 'C03', exprs=[], source='arkivuttrekk.xml'),
            self.make_def('kdrs.u01', 'U01', exprs=[]),
            self.make_def('kdrs.u02', 'U02', exprs=[]),
            self.make_def('kdrs.extension', 'DWM-AU01', exprs=['count(//foo)']),
        ]
        self.catalog.write_text(json.dumps({'tests': self.tests}), encoding='utf8')
        self.work = self.project / 'work'
        self.work.mkdir()
        self.output = self.work / 'noark5_tests/xpath_regression/JOB-001__test'
        self.output.mkdir(parents=True)

    @staticmethod
    def make_def(testid, jobid, *, exprs, source='arkivstruktur.xml'):
        return {'test_id': testid, 'legacy': {'job_id': jobid},
                'name': jobid, 'source_xml': source, 'scope': 'source_document',
                'noark_versions': ['3.1', '4.0', '5.0'],
                'version_basis': 'master_query_subtype_needs_qa',
                'execution': {'kind': 'metrics', 'metrics': [
                    {'id': f'n{i}', 'type': 'xpath', 'expression': expr}
                    for i, expr in enumerate(exprs)]}}

    def sources(self):
        folder = self.project / 'docs/reference/kdrs-query'
        folder.mkdir(parents=True)
        stem = 'xml-queries_noark5_2026-05-26'
        standard = '''[XML_QUERY]
job_id=C01
source=arkivstruktur.xml
#START#
concat("Archives: ", count( //arkiv ), count(//arkivskaper),
    count(//mappe[@xsi:type="saksmappe"]))
#STOP#
[XML_QUERY]
job_id=C02
source=arkivstruktur.xml
#START#
count(//arkivdel)
#STOP#
[XML_QUERY]
job_id=C03
source=arkivstruktur.xml
#START#
concat("Unsupported", count(//foo))
#STOP#
'''
        (folder / (stem + '.txt')).write_text(standard, encoding='utf8')
        (folder / (stem + '_U1.txt')).write_text(
            '[XML_QUERY]\njob_id=U01\nsource=arkivstruktur.xml\n#START#\ncount(//arkiv)\n#STOP#',
            encoding='utf8')
        (folder / (stem + '_U2.txt')).write_text(
            '[XML_QUERY]\njob_id=U02\nsource=arkivstruktur.xml\n#START#\ncount(//arkivdel)\n#STOP#',
            encoding='utf8')

    def saved(self, *, whole=None, parts=None, summary=None):
        whole = whole if whole is not None else {'a': {'status': 'match', 'legacy': 2, 'canonical': 2}}
        parts = parts if parts is not None else {'P1': {'archive_part': {'system_id': 'P1'},
                                                       'checks': {'b': {'status': 'match', 'legacy': 1, 'canonical': 1}}}}
        check_count = len(whole) + sum(len(v['checks']) for v in parts.values())
        result = {'whole_extraction': whole, 'archive_parts': parts,
                  'summary': summary or {'checks': check_count, 'matches': check_count,
                                         'mismatches': 0, 'not_comparable': 0}}
        name = 'legacy-regression-comparison.json'
        (self.output / name).write_text(json.dumps(result), encoding='utf8')
        index = {'execution_profile': 'regression', 'tests': [{'test_id': 'kdrs.u01'}],
                 'legacy_regression_comparison': {'file': name, 'summary': result['summary']}}
        (self.output / 'index.json').write_text(json.dumps(index), encoding='utf8')
        return 'noark5_tests/xpath_regression/JOB-001__test/index.json'


class StaticSourceTraceTests(Fixture):
    def test_kdrs_fragment_detection_does_not_claim_semantic_parity(self):
        self.sources()
        report = source_crosswalk(load_rows(self.project), self.project)
        c01 = report['tests']['kdrs.c01']
        self.assertEqual(c01['status'], 'partial_fragments_found')
        self.assertEqual(c01['literal_fragments'], 2)
        self.assertEqual(c01['namespace_candidates'], 1)
        self.assertEqual(c01['without_literal_match'], 1)
        self.assertEqual(len(report['provenance']['Standard']['sha256']), 64)
        self.assertEqual(report['summary']['semantic_equivalence_verified'], 0)

    def test_exact_lexical_fragment_is_not_equivalence_proof(self):
        self.sources()
        report = source_crosswalk(load_rows(self.project), self.project)
        self.assertEqual(report['tests']['kdrs.c02']['status'], 'all_literal_fragments_found')
        self.assertFalse(report.get('semantic_equivalence_to_saxon_verified', False))

    def test_u1_u2_use_dedicated_original_files_and_dwm_is_extension(self):
        self.sources()
        report = source_crosswalk(load_rows(self.project), self.project)['tests']
        self.assertEqual(report['kdrs.u01']['source_group'], 'U1')
        self.assertEqual(report['kdrs.u02']['source_group'], 'U2')
        self.assertEqual(report['kdrs.extension']['status'], 'dwm_extension')

    def test_source_file_conflict_is_detected(self):
        self.sources()
        report = source_crosswalk(load_rows(self.project), self.project)['tests']
        self.assertEqual(report['kdrs.c03']['status'], 'source_xml_conflict')

    def test_missing_reference_does_not_get_assumed_to_match(self):
        report = source_crosswalk(load_rows(self.project), self.project)
        self.assertEqual(report['tests']['kdrs.c01']['status'], 'source_unavailable')
        self.assertEqual(report['summary']['literal_fragments'], 0)

    def test_kdrs_label_string_is_not_counted_as_executable_expression(self):
        self.assertEqual(_fragment_status('count(//arkiv)', '"count(//arkiv)"'), 'not_found')
        self.assertEqual(_fragment_status('count(//arkiv)', 'concat("X", count(//arkiv))'),
                         'literal_fragment_present')

    def test_literals_with_same_length_are_not_conflated(self):
        self.assertEqual(_fragment_status('count(//mappe[@type="sak"])',
                                          'count(//mappe[@type="reg"])'), 'not_found')
        self.assertEqual(_fragment_status('count(//mappe[@type="sak"])',
                                          'count(//mappe[@xsi:type="sak"])'),
                         'namespace_rewrite_candidate')

    def test_full_audit_only_includes_selected_extra_data(self):
        self.sources()
        report = build_audit(self.project)
        self.assertIn('static_source_crosswalk', report)
        self.assertNotIn('dwm_engine_parity', report)
        self.assertNotIn('selected_saved_regression', report)
        self.assertFalse(report['noark_requirement_conformance_claimed'])


class SavedU1U2RegressionTests(Fixture):
    def test_discovery_requires_explicit_selection(self):
        rel = self.saved()
        audit = build_audit(self.project, work=self.work)
        self.assertEqual(len(audit['saved_regression_runs']), 1)
        self.assertNotIn('selected_saved_regression', audit)
        self.assertEqual(audit['saved_regression_runs'][0]['relative_index'], rel)

    def test_consistent_saved_comparison_rechecked(self):
        rel = self.saved()
        report = inspect_saved_regression(self.work, rel)
        self.assertEqual(report['status'], 'match')
        self.assertEqual(report['counts']['matches'], 2)
        self.assertFalse(report['saved_counts_disagree'])

    def test_mismatch_is_retained_not_rounded_to_ok(self):
        rel = self.saved(whole={'a': {'status': 'mismatch', 'legacy': 8, 'canonical': 7}},
                         summary={'checks': 2, 'matches': 1, 'mismatches': 1, 'not_comparable': 0})
        report = inspect_saved_regression(self.work, rel)
        self.assertEqual(report['status'], 'mismatch')
        self.assertEqual(report['counts']['mismatches'], 1)
        self.assertTrue(report['findings'])

    def test_unavailable_is_never_passed(self):
        rel = self.saved(whole={'a': {'status': 'not_comparable', 'error': 'not available'}},
                         summary={'checks': 2, 'matches': 1, 'mismatches': 0, 'not_comparable': 1})
        self.assertEqual(inspect_saved_regression(self.work, rel)['status'], 'incomplete')

    def test_invalid_stored_summary_is_flagged(self):
        rel = self.saved(summary={'checks': 100, 'matches': 100, 'mismatches': 0, 'not_comparable': 0})
        report = inspect_saved_regression(self.work, rel)
        self.assertTrue(report['saved_counts_disagree'])
        self.assertEqual(report['status'], 'invalid_summary')

    def test_unknown_status_is_not_accepted(self):
        rel = self.saved(whole={'a': {'status': 'approved'}},
                         summary={'checks': 2, 'matches': 1, 'mismatches': 0, 'not_comparable': 0})
        self.assertEqual(inspect_saved_regression(self.work, rel)['status'], 'invalid_summary')

    def test_non_regression_index_is_rejected(self):
        rel = self.saved()
        p = self.work / rel
        doc = json.loads(p.read_text(encoding='utf8'))
        doc['execution_profile'] = 'normal'
        p.write_text(json.dumps(doc), encoding='utf8')
        self.assertEqual(discover_saved_regressions(self.work), [])
        with self.assertRaises(ValueError):
            inspect_saved_regression(self.work, rel)

    def test_work_traversal_is_rejected(self):
        self.saved()
        self.assertIsNone(_safe_work_index(self.work, '../index.json'))
        self.assertIsNone(_safe_work_index(self.work, 'noark5_tests/xpath/JOB/index.json'))
        self.assertIsNone(_safe_work_index(self.work, self.project / 'outside.json'))

    def test_symlink_escape_does_not_get_discovered(self):
        outside = self.project / 'outside'
        outside.mkdir()
        (outside / 'index.json').write_text('{"execution_profile":"regression"}', encoding='utf8')
        dest = self.work / 'noark5_tests/xpath_regression/escape'
        try:
            dest.symlink_to(outside, target_is_directory=True)
        except (NotImplementedError, OSError):
            self.skipTest('Symlinks unavailable on this platform')
        self.assertEqual(discover_saved_regressions(self.work), [])

    def test_empty_comparison_is_not_a_pass(self):
        rel = self.saved(whole={}, parts={}, summary={'checks': 0, 'matches': 0,
                                                        'mismatches': 0, 'not_comparable': 0})
        self.assertEqual(inspect_saved_regression(self.work, rel)['status'], 'no_comparisons')


class EngineParityResultsTests(Fixture):
    def result_dirs(self, *, left_status='ok', right_status='ok',
                    left_values=None, right_values=None, right_missing=False):
        a = self.project / 'a'
        b = self.project / 'b'
        for folder, status, values in ((a, left_status, left_values), (b, right_status, right_values)):
            (folder / 'results').mkdir(parents=True)
            index = {'tests': [{'test_id': 'kdrs.c01', 'status': status,
                                'file': 'results/kdrs_c01.json'}]}
            (folder / 'index.json').write_text(json.dumps(index), encoding='utf8')
            if folder == b and right_missing:
                continue
            (folder / 'results/kdrs_c01.json').write_text(json.dumps({
                'test_id': 'kdrs.c01', 'status': status,
                'values': values if values is not None else {'archive_count': 2}
            }), encoding='utf8')
        return a, b

    def test_equal_data_is_verified_between_two_dwm_engines(self):
        a, b = self.result_dirs()
        result = compare_dwm_result_dirs(a, b)
        self.assertEqual(result['summary']['matches'], 1)
        self.assertEqual(result['summary']['status'], 'match')
        self.assertFalse(result['semantic_equivalence_to_kdrs_saxon_verified'])

    def test_real_metric_difference_is_flagged(self):
        a, b = self.result_dirs(right_values={'archive_count': 3})
        result = compare_dwm_result_dirs(a, b)
        self.assertEqual(result['summary']['mismatches'], 1)
        self.assertEqual(result['summary']['status'], 'review')

    def test_missing_source_never_counts_as_parity(self):
        a, b = self.result_dirs(left_status='source_missing', right_status='source_missing')
        result = compare_dwm_result_dirs(a, b)
        self.assertEqual(result['summary']['unverified'], 1)
        self.assertEqual(result['summary']['matches'], 0)

    def test_failure_on_both_sides_is_still_unverified(self):
        a, b = self.result_dirs(left_status='error', right_status='error')
        self.assertEqual(compare_dwm_result_dirs(a, b)['summary']['unverified'], 1)

    def test_unequal_status_is_not_ignored(self):
        a, b = self.result_dirs(right_status='source_missing')
        self.assertEqual(compare_dwm_result_dirs(a, b)['summary']['mismatches'], 1)

    def test_missing_result_does_not_claim_success(self):
        a, b = self.result_dirs(right_missing=True)
        self.assertEqual(compare_dwm_result_dirs(a, b)['summary']['unverified'], 1)

    def test_source_xml_is_required_for_executing_engine(self):
        empty = self.project / 'extract'
        empty.mkdir()
        with self.assertRaises(ValueError):
            execute_dwm_engine_parity(self.project, empty)

    def test_original_cli_prints_json_without_writing_source(self):
        self.sources()
        from contextlib import redirect_stdout
        from io import StringIO
        stdout = StringIO()
        with redirect_stdout(stdout):
            result = main(['--project', str(self.project)])
        self.assertEqual(result, 0)
        parsed = json.loads(stdout.getvalue())
        from version import VERSION
        self.assertEqual(parsed['dwm_version'], VERSION)


class GUISourceContract(unittest.TestCase):
    def test_existing_dialog_now_has_optional_kdrs_comparison_filter(self):
        path = ROOT / 'gui_qt/noark5_xpath_audit_v021_a1.py'
        src = path.read_text(encoding='utf8')
        ast.parse(src)
        self.assertIn('KDRS-formelkobling:', src)
        self.assertIn('self.mapping.currentIndexChanged.connect(self._filter)', src)
        self.assertIn('KDRS -> DWM: KILDESPORING', src)
        self.assertIn('self._source_audit = source_crosswalk(self._rows)', src)
        self.assertIn('Vis alle XPath-kontroller...', src)

    def test_versions_are_synchronized(self):
        from version import VERSION
        from tests.version_assertions import assert_release_at_least
        assert_release_at_least(self, f'VERSION = "{VERSION}"', "0.2.1", 2)
        self.assertEqual((ROOT / 'version.py').read_text(encoding='utf8').count(VERSION), 1)
        import re
        project = (ROOT / 'pyproject.toml').read_text(encoding='utf8')
        match = re.search(r'(?m)^version\s*=\s*"([^"]+)"', project)
        self.assertIsNotNone(match)
        self.assertEqual(match.group(1), VERSION.replace('-a', 'a'))


if __name__ == '__main__':
    unittest.main()
