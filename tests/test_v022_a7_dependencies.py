"""a7: fixed dependency numbers and persisted safe Noark 5 workflow order."""
from __future__ import annotations

from pathlib import Path
import json
import tomllib
import unittest

from app.workflow_dependencies_v022_a7 import (
    SPECS, BY_ID, NEW_A7, dependency_label, dependency_links,
    ensure_a7_processing, validate_dependencies, arkade_last_with_dependencies,
)
from app.workflow_order_v022_a6 import preserved_basic_order, checked_order
from version import VERSION

ROOT = Path(__file__).resolve().parents[1]
OLD = (
    'metadata_inventory', 'validate_xml_schema', 'analyse_arkivstruktur',
    'run_noark5_xpath_tests_2026', 'arkade5_noark5_test',
    'siegfried_pronom_identification', 'arkade5_pronom_analysis',
    'import_arkade5_reports', 'compose_noark5_views', 'build_noark5_depot_report',
)


class DependencyTests(unittest.TestCase):
    def test_every_registered_operation_has_a_unique_stable_number(self):
        self.assertEqual(len(SPECS), len(set(x.number for x in SPECS)))
        self.assertEqual(len(SPECS), len(set(x.operation_id for x in SPECS)))
        profile = (ROOT / 'noark5_workflow/profile.py').read_text(encoding='utf-8')
        for operation in ('MetadataInventoryOperation', 'AnalyseArkivstrukturOperation',
                          'RunNoark5XpathTestsOperation', 'SiegfriedPronomOperation',
                          'BuildNoark5QaDraftOperation', 'DiasPackageOperation'):
            self.assertIn(operation, profile)
        for no in (100, 130, 140, 150, 160, 200, 210, 220, 230, 240, 250, 260, 900):
            self.assertTrue(any(x.number == no for x in SPECS))
        self.assertEqual(dependency_label('arkade5_noark5_test'), 'A150')

    def test_new_full_workflow_includes_four_new_afterprocess_jobs(self):
        value = ensure_a7_processing(OLD)
        self.assertEqual(len(value), 14)
        self.assertEqual(set(value), set(OLD) | set(NEW_A7))
        self.assertEqual(validate_dependencies(value), ())
        self.assertLess(value.index('arkade5_pronom_analysis'),
                        value.index('build_noark5_canonical_evidence'))
        self.assertLess(value.index('build_noark5_depot_report'),
                        value.index('build_noark5_qa_draft'))

    def test_user_may_move_unrelated_technical_tests(self):
        flow = ensure_a7_processing(OLD)
        ordered = ('siegfried_pronom_identification',) + tuple(
            item for item in flow if item != 'siegfried_pronom_identification')
        self.assertFalse(validate_dependencies(ordered))

    def test_arkade_last_means_last_technical_and_valid_afterprocess(self):
        flow = ensure_a7_processing(OLD)
        result = arkade_last_with_dependencies(flow)
        self.assertEqual(result[4:7], (
            'siegfried_pronom_identification',
            'arkade5_noark5_test', 'arkade5_pronom_analysis',
        ))
        self.assertLess(result.index('arkade5_pronom_analysis'),
                        result.index('import_arkade5_reports'))
        self.assertEqual(validate_dependencies(result), ())
        self.assertEqual(arkade_last_with_dependencies(result), result)

    def test_arkade_before_import_dependency_enforced_even_in_legacy(self):
        invalid = ('import_arkade5_reports', 'arkade5_noark5_test')
        issues = validate_dependencies(invalid)
        self.assertTrue(issues)
        self.assertIn('A200', issues[0])
        self.assertIn('A150', issues[0])

    def test_xpath_must_precede_canonical_and_views(self):
        bad = ('build_noark5_canonical_evidence', 'run_noark5_xpath_tests_2026')
        self.assertTrue(validate_dependencies(bad))
        bad = ('compose_noark5_views', 'run_noark5_xpath_tests_2026')
        self.assertTrue(validate_dependencies(bad))

    def test_qa_must_be_after_evidence_and_depot_report(self):
        flow = ensure_a7_processing(OLD)
        qa = list(flow)
        qa.remove('build_noark5_qa_draft')
        qa.insert(0, 'build_noark5_qa_draft')
        self.assertTrue(any('A260' in s for s in validate_dependencies(qa)))

    def test_missing_required_canonical_provenance_rejected(self):
        bad = ('build_noark5_canonical_evidence', 'build_noark5_qa_draft')
        issues = validate_dependencies(bad)
        self.assertTrue(any('A130' in issue for issue in issues))
        self.assertTrue(any('A230' in issue for issue in issues))

    def test_old_arkade_only_is_not_forced_to_invent_xpath(self):
        old = ('arkade5_noark5_test', 'arkade5_pronom_analysis')
        self.assertEqual(ensure_a7_processing(old), old)
        self.assertEqual(validate_dependencies(old), ())

    def test_legacy_completed_job_is_not_rewritten_on_basic_save(self):
        proposed = ensure_a7_processing(OLD)
        self.assertEqual(preserved_basic_order(OLD, proposed), OLD)
        custom = tuple(reversed(OLD))
        self.assertEqual(preserved_basic_order(custom, proposed), custom)

    def test_operator_checkbox_change_still_changes_membership(self):
        old = OLD
        fewer = ensure_a7_processing(tuple(x for x in OLD if x != 'siegfried_pronom_identification'))
        self.assertEqual(preserved_basic_order(old, fewer), fewer)

    def test_known_requires_link_to_stable_numbers(self):
        flow = ensure_a7_processing(OLD)
        self.assertTrue(any('A130' in x for x in dependency_links('build_noark5_canonical_evidence', flow)))
        self.assertIn('A230', ' '.join(dependency_links('build_noark5_qa_draft', flow)))

    def test_each_builtin_production_workflow_is_valid(self):
        data = json.loads((ROOT / 'config/workflow_sequences.json').read_text(encoding='utf-8'))
        for seq in data['sequences']:
            with self.subTest(seq=seq['sequence_id']):
                self.assertFalse(validate_dependencies(seq['operation_ids']))
                self.assertEqual(len(seq['operation_ids']), len(set(seq['operation_ids'])))
                if seq['sequence_id'] not in ('noark5_analyse', 'noark5_arkade_only'):
                    self.assertIn('build_noark5_canonical_evidence', seq['operation_ids'])

    def test_no_automatic_migration_on_read(self):
        self.assertEqual(checked_order(OLD, OLD), OLD)
        self.assertNotEqual(OLD, ensure_a7_processing(OLD))

    def test_version_is_a7_in_distribution_and_runtime(self):
        self.assertRegex(VERSION, r'^0\.2\.2-a[0-9]+$')
        with (ROOT / 'pyproject.toml').open('rb') as stream:
            self.assertEqual(tomllib.load(stream)['project']['version'], VERSION.replace('-a', 'a'))


if __name__ == '__main__':
    unittest.main()
