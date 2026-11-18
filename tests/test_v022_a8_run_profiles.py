from __future__ import annotations

import unittest

from app.run_profiles_v022_a8 import (builtin_profiles, selected_default,
    toggle_arkade, profile_controls, save_custom_profile, custom_profiles,
    operation_microtest_support)
from app.workflow_dependencies_v022_a7 import validate_dependencies


class RunProfileA8Tests(unittest.TestCase):
    def test_three_builtins_and_standard_without_arkade(self):
        profiles = builtin_profiles()
        self.assertEqual([p.profile_id for p in profiles],
                         ['dwm_standard', 'dwm_advanced', 'dwm_complete'])
        self.assertEqual(selected_default({}).profile_id, 'dwm_standard')
        self.assertEqual(profile_controls(profiles[0]), (False, False))
        self.assertEqual(profile_controls(profiles[1]), (False, False))
        self.assertEqual(profile_controls(profiles[2]), (True, True))

    def test_all_profiles_have_audited_evidence_and_qa(self):
        for profile in builtin_profiles():
            self.assertEqual(validate_dependencies(profile.operation_ids), (), profile.name)
            self.assertIn('siegfried_pronom_identification', profile.operation_ids)
            self.assertIn('build_noark5_canonical_evidence', profile.operation_ids)
            self.assertIn('audit_noark5_evidence', profile.operation_ids)
            self.assertEqual(profile.operation_ids[-1], 'build_noark5_qa_draft')

    def test_independent_arkade_options(self):
        standard = builtin_profiles()[0]
        for noark, pronom in [(False, False), (True, False), (False, True), (True, True)]:
            configured = toggle_arkade(standard, noark=noark, pronom=pronom)
            self.assertEqual(profile_controls(configured), (noark, pronom))
            self.assertEqual(validate_dependencies(configured.operation_ids), ())
            self.assertEqual('import_arkade5_reports' in configured.operation_ids,
                             noark or pronom)
            self.assertLess(configured.operation_ids.index('run_noark5_xpath_tests_2026'),
                            configured.operation_ids.index('build_noark5_canonical_evidence'))

    def test_custom_persistence_is_data_not_global_state(self):
        builtins = builtin_profiles()
        changes = save_custom_profile({}, 'Depot profil', builtins[2].operation_ids)
        saved = custom_profiles(changes)
        self.assertEqual(len(saved), 1)
        self.assertEqual(saved[0].operation_ids, builtins[2].operation_ids)
        self.assertEqual(selected_default({'noark5_default_run_profile': saved[0].profile_id,
            **changes}).profile_id, saved[0].profile_id)
        self.assertEqual(selected_default({'noark5_default_run_profile': 'does_not_exist'}).profile_id,
                         'dwm_standard')

    def test_invalid_custom_workflow_is_rejected(self):
        valid = list(builtin_profiles()[0].operation_ids)
        valid.remove('audit_noark5_evidence')
        with self.assertRaises(ValueError):
            custom_profiles({'noark5_custom_run_profiles': [{'profile_id': 'custom_broken',
                'name': 'Broken', 'operation_ids': valid}]})

    def test_microtest_switches_are_not_faked(self):
        support = operation_microtest_support()
        self.assertIn('arkade5_noark5_test', support)
        self.assertTrue(all('planlagt' in text for text in support.values()))


if __name__ == '__main__':
    unittest.main()

class SimpleModeProfileIntegrationTests(unittest.TestCase):
    def test_basic_plan_uses_advanced_default_without_arkade(self):
        import sys
        import tempfile
        from pathlib import Path
        from types import SimpleNamespace
        from unittest.mock import patch
        from app.basic_start_v0111_a1 import prepare_basic_plan
        with tempfile.TemporaryDirectory() as tmp:
            source, work = Path(tmp) / 'source', Path(tmp) / 'work'
            source.mkdir(); work.mkdir()
            stubs = {
                'app.job_preflight_v018_a6': SimpleNamespace(
                    check_extraction_folder=lambda *args, **kwargs: ()),
                'app.storage_profiles_v0110_a2': SimpleNamespace(
                    resolve_storage_profile=lambda settings: 'standard_enkel'),
                'app.workflow_sequences': SimpleNamespace(workflow_sequence_by_id=lambda value:
                    SimpleNamespace(profile_id='noark5',
                                    operation_ids=builtin_profiles()[0].operation_ids))}
            with patch.dict(sys.modules, stubs):
                plan = prepare_basic_plan(source, work,
                    {'noark5_default_run_profile': 'dwm_advanced'},
                    controls=('dwm','siegfried'))
            self.assertEqual(plan.operation_ids, builtin_profiles()[1].operation_ids)
            self.assertNotIn('arkade5_noark5_test', plan.operation_ids)
            self.assertNotIn('arkade5_pronom_analysis', plan.operation_ids)

    def test_basic_plan_separately_selects_arkade_noark(self):
        import sys
        import tempfile
        from pathlib import Path
        from types import SimpleNamespace
        from unittest.mock import patch
        from app.basic_start_v0111_a1 import prepare_basic_plan
        with tempfile.TemporaryDirectory() as tmp:
            source, work = Path(tmp) / 'source', Path(tmp) / 'work'
            source.mkdir(); work.mkdir()
            stubs = {
                'app.job_preflight_v018_a6': SimpleNamespace(
                    check_extraction_folder=lambda *args, **kwargs: ()),
                'app.storage_profiles_v0110_a2': SimpleNamespace(
                    resolve_storage_profile=lambda settings: 'standard_enkel'),
                'app.workflow_sequences': SimpleNamespace(workflow_sequence_by_id=lambda value:
                    SimpleNamespace(profile_id='noark5',
                                    operation_ids=builtin_profiles()[0].operation_ids))}
            with patch.dict(sys.modules, stubs):
                plan = prepare_basic_plan(source, work, {},
                    controls=('dwm','siegfried','arkade_noark5'))
            self.assertIn('arkade5_noark5_test', plan.operation_ids)
            self.assertNotIn('arkade5_pronom_analysis', plan.operation_ids)
            self.assertEqual(validate_dependencies(plan.operation_ids), ())
