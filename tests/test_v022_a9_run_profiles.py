"""a9: regression coverage for editable, frozen Noark 5 run profiles."""
from __future__ import annotations

import tomllib
import unittest
from dataclasses import dataclass
from pathlib import Path

from app.run_profiles_v022_a8 import builtin_profiles, available_profiles, toggle_arkade
from app.run_profiles_v022_a9 import (
    TECHNICAL_IDS, compose_profile_operations, install_default_on_new_job,
    legacy_fallback_sequence, stage_default_profile, stage_profile_edit,
    staged_profile_settings_valid, technical_operations,
)
from app.workflow_dependencies_v022_a7 import dependency_label, validate_dependencies
from version import VERSION

ROOT = Path(__file__).resolve().parents[1]


class RunProfilesA9Tests(unittest.TestCase):
    def test_edit_builtin_creates_custom_copy_and_preserves_builtin(self):
        built = builtin_profiles()[0]
        original = built.operation_ids
        new_order = ('siegfried_pronom_identification',
                     'run_noark5_xpath_tests_2026', 'validate_xml_schema')
        edit = stage_profile_edit({}, built.profile_id, 'Egen depotprofil', new_order)
        self.assertTrue(edit.profile_id.startswith('custom_'))
        self.assertEqual(built.operation_ids, original)
        self.assertEqual(technical_operations(builtin_profiles()[0]),
                         technical_operations(built))
        self.assertEqual(edit.operation_ids[:3], new_order)
        self.assertFalse(validate_dependencies(edit.operation_ids))
        self.assertEqual(edit.operation_ids[-1], 'build_noark5_qa_draft')
        self.assertEqual(len(available_profiles(edit.changes)), 4)

    def test_dependent_processing_is_inserted_after_tests(self):
        for chosen in ((False, False), (True, False), (False, True), (True, True)):
            ordered = ['run_noark5_xpath_tests_2026',
                       'siegfried_pronom_identification']
            if chosen[0]:
                ordered.append('arkade5_noark5_test')
            if chosen[1]:
                ordered.append('arkade5_pronom_analysis')
            actual = compose_profile_operations(ordered)
            self.assertEqual('import_arkade5_reports' in actual, any(chosen))
            self.assertEqual(actual.index('audit_noark5_evidence') + 1,
                             actual.index('compose_noark5_views'))
            self.assertFalse(validate_dependencies(actual))
            self.assertLess(max(actual.index(x) for x in ordered),
                            actual.index('build_noark5_canonical_evidence'))

    def test_mandatory_xpath_unknown_duplicate_and_empty_rejected(self):
        invalid = ((), ('metadata_inventory',),
                   ('run_noark5_xpath_tests_2026', 'run_noark5_xpath_tests_2026'),
                   ('run_noark5_xpath_tests_2026', 'fake_operation'))
        for seq in invalid:
            with self.subTest(seq=seq), self.assertRaises(ValueError):
                compose_profile_operations(seq)

    def test_custom_profile_can_be_updated_without_changing_identity(self):
        one = stage_profile_edit({}, 'dwm_standard', 'IKAMR egen',
                                 ('run_noark5_xpath_tests_2026',))
        edited = stage_profile_edit(one.changes, one.profile_id, 'IKAMR justert',
                                    ('arkade5_noark5_test', 'run_noark5_xpath_tests_2026'))
        self.assertEqual(edited.profile_id, one.profile_id)
        self.assertEqual(len(edited.changes['noark5_custom_run_profiles']), 1)
        self.assertEqual(available_profiles(edited.changes)[-1].name, 'IKAMR justert')
        self.assertIn('arkade5_noark5_test', edited.operation_ids)
        self.assertNotIn('arkade5_pronom_analysis', edited.operation_ids)

    def test_default_is_user_setting_not_mutation_of_builtins(self):
        initial = {}
        customized = stage_profile_edit(initial, 'dwm_standard', 'Min standard',
                                        ('run_noark5_xpath_tests_2026',))
        staged = {**initial, **customized.changes,
                  **stage_default_profile(customized.changes, customized.profile_id)}
        self.assertEqual(staged_profile_settings_valid(staged)[-1].profile_id,
                         customized.profile_id)
        with self.assertRaises(ValueError):
            stage_default_profile(staged, 'missing_profile')
        with self.assertRaises(ValueError):
            staged_profile_settings_valid({**staged,
                                           'noark5_default_run_profile': 'missing_profile'})
        self.assertEqual(builtin_profiles()[0].profile_id, 'dwm_standard')

    def test_simple_chooser_preserves_custom_arkade_order_when_unchanged(self):
        edited = stage_profile_edit({}, 'dwm_complete', 'Tidlig Arkade',
                                    ('arkade5_pronom_analysis',
                                     'run_noark5_xpath_tests_2026',
                                     'siegfried_pronom_identification',
                                     'arkade5_noark5_test'))
        profile = available_profiles(edited.changes)[-1]
        reopened = toggle_arkade(profile, noark=True, pronom=True)
        self.assertEqual(reopened.operation_ids, profile.operation_ids)
        self.assertEqual(profile.operation_ids[0], 'arkade5_pronom_analysis')
        no_pronom = toggle_arkade(profile, noark=True, pronom=False)
        self.assertNotIn('arkade5_pronom_analysis', no_pronom.operation_ids)
        self.assertIn('arkade5_noark5_test', no_pronom.operation_ids)

    def test_old_advanced_mode_fallback_is_conservative(self):
        names = builtin_profiles()
        self.assertEqual(legacy_fallback_sequence(names[0]), 'noark5_standard')
        self.assertEqual(legacy_fallback_sequence(names[1]), 'noark5_standard')
        self.assertEqual(legacy_fallback_sequence(names[2]), 'noark5_standard_arkade')
        only_pronom = stage_profile_edit({}, 'dwm_standard', 'Pronom',
                                         ('run_noark5_xpath_tests_2026',
                                          'arkade5_pronom_analysis'))
        self.assertEqual(legacy_fallback_sequence(available_profiles(only_pronom.changes)[-1]),
                         'noark5_standard')

    def test_regression_operation_has_stable_a190_number(self):
        self.assertIn('run_noark5_xpath_regression_2026', TECHNICAL_IDS)
        self.assertEqual(dependency_label('run_noark5_xpath_regression_2026'), 'A190')

    def test_new_advanced_job_gets_user_default_but_old_job_is_unchanged(self):
        @dataclass
        class Job:
            job_id: str
            profile_id: str = 'noark5'
            progress: float = 0
            next_operation_index: int = 0

        class FakeApi:
            settings = {'noark5_default_run_profile': 'dwm_advanced'}
            jobs = [Job('JOB-001')]
            installed = []
            def workspace(self):
                return self
            def set_workflow(self, job_id, operations):
                self.installed.append((job_id, tuple(operations)))
        api = FakeApi()
        api.jobs.append(Job('JOB-002'))
        self.assertEqual(install_default_on_new_job(api, {'JOB-001'}), 'JOB-002')
        self.assertEqual(len(api.installed), 1)
        self.assertEqual(api.installed[0][0], 'JOB-002')
        self.assertIn('analyse_noark5_u1', api.installed[0][1])
        self.assertEqual(install_default_on_new_job(api, {'JOB-001','JOB-002'}), None)
        api.jobs.append(Job('JOB-003', next_operation_index=1))
        self.assertIsNone(install_default_on_new_job(api, {'JOB-001','JOB-002'}))
        self.assertEqual(len(api.installed), 1)

    def test_qt_setup_stages_without_saving_until_shared_save(self):
        setup = (ROOT / 'gui_qt/setup_run_profiles_v022_a9.py').read_text('utf-8')
        main = (ROOT / 'gui_qt/main_v020_a6.py').read_text('utf-8')
        api = (ROOT / 'app/workbench_api_v020_a2.py').read_text('utf-8')
        self.assertIn('Eldre profiler', setup)
        self.assertIn('Rediger deljobber og rekkefølge', setup)
        self.assertIn('noark5_default_run_profile', setup)
        self.assertIn('noark5_custom_run_profiles', setup)
        self.assertNotIn('save_config(', setup)
        self.assertIn('install_default_on_new_job', main)
        self.assertIn('from gui_qt.setup_run_profiles_v022_a9 import DwmSetupDialog', main)
        self.assertIn('staged_profile_settings_valid', api)
        self.assertIn("'noark5_custom_run_profiles'", api)

    def test_version_matches_distribution_and_runtime(self):
        with (ROOT / 'pyproject.toml').open('rb') as stream:
            dist = tomllib.load(stream)['project']['version']
        self.assertEqual(VERSION, '0.2.2-a11')
        self.assertEqual(dist, VERSION.replace('-a', 'a'))


if __name__ == '__main__':
    unittest.main()
