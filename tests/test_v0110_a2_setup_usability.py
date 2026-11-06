"""v0.1.10-a2 regression: first-use default and safe, legible Setup UI."""
from __future__ import annotations

import ast
import json
from pathlib import Path
import re
import tempfile
import tomllib
import unittest
from unittest.mock import patch

from app.storage_profiles_v0110_a2 import (
    DEFAULT_STORAGE_PROFILE, profile_best_for, resolve_storage_profile,
)
from settings import DEFAULT_CONFIG
from version import VERSION

ROOT = Path(__file__).resolve().parents[1]


class StorageProfileSelectionTests(unittest.TestCase):
    def test_new_install_uses_standard(self):
        self.assertEqual(DEFAULT_STORAGE_PROFILE, 'standard_enkel')
        self.assertEqual(DEFAULT_CONFIG['storage_layout_profile'], DEFAULT_STORAGE_PROFILE)
        self.assertFalse(DEFAULT_CONFIG['storage_layout_profile_selected'])
        self.assertEqual(resolve_storage_profile(None), DEFAULT_STORAGE_PROFILE)
        self.assertEqual(resolve_storage_profile({}), DEFAULT_STORAGE_PROFILE)
        self.assertEqual(resolve_storage_profile(DEFAULT_CONFIG), DEFAULT_STORAGE_PROFILE)

    def test_unmarked_old_default_is_not_user_selection(self):
        self.assertEqual(resolve_storage_profile({
            'storage_layout_profile': 'ikamr_standard',
        }), DEFAULT_STORAGE_PROFILE)
        self.assertEqual(resolve_storage_profile({
            'storage_layout_profile': 'ikamr_standard',
            'storage_layout_profile_selected': False,
        }), DEFAULT_STORAGE_PROFILE)
        self.assertEqual(resolve_storage_profile({
            'storage_layout_profile': 'none',
        }), DEFAULT_STORAGE_PROFILE)

    def test_explicitly_saved_package_profile_survives_reopen(self):
        settings = {
            'storage_layout_profile': 'ikamr_standard',
            'storage_layout_profile_selected': True,
        }
        self.assertEqual(resolve_storage_profile(settings), 'ikamr_standard')
        self.assertEqual(resolve_storage_profile(dict(settings)), 'ikamr_standard')

    def test_explicit_legacy_none_profile_remains_available(self):
        self.assertEqual(resolve_storage_profile({
            'storage_layout_profile': 'none',
            'storage_layout_profile_selected': True,
        }), 'none')

    def test_a1_new_only_hierarchical_profile_preserved(self):
        # A1 introduced this ID, so unlike the old IKAMR default it could not
        # appear solely because of v0.1.9's built-in configuration default.
        self.assertEqual(resolve_storage_profile({
            'storage_layout_profile': 'arkivskaper_hierarkisk',
        }), 'arkivskaper_hierarkisk')

    def test_blank_unknown_and_malformed_values_fall_back(self):
        for value in ('', ' ', 'missing', 'unknown-moved-profile', None):
            with self.subTest(value=value):
                self.assertEqual(resolve_storage_profile({
                    'storage_layout_profile': value,
                    'storage_layout_profile_selected': True,
                }), DEFAULT_STORAGE_PROFILE)

    def test_saved_profile_marker_survives_config_roundtrip(self):
        import settings
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'config.json'
            with patch.object(settings, 'CONFIG_PATH', path):
                written = settings.save_config({
                    'storage_layout_profile': 'ikamr_standard',
                    'storage_layout_profile_selected': True,
                })
                loaded = settings.load_config()
            self.assertTrue(written['storage_layout_profile_selected'])
            self.assertEqual(resolve_storage_profile(loaded), 'ikamr_standard')

    @unittest.skipUnless((ROOT / 'app/application_api.py').is_file(),
                         'Requires complete DWM checkout')
    def test_workbench_setup_marks_explicit_choice_without_moving_jobs(self):
        from app.workbench_api_v0110_a1 import DwmWorkbenchAPI
        from noark5_workflow.core.job import Job
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            api = DwmWorkbenchAPI(settings={
                'storage_layout_profile': 'ikamr_standard',
                'app_work_subfolder': 'dwm',
            })
            job = Job('JOB-001', work_root=root,
                      work_operations=root / 'repository_operations')
            api._batch.add(job)
            with patch('app.workbench_api_v0110_a1.save_config',
                       side_effect=lambda data: dict(data)) as save:
                api.save_setup({'storage_layout_profile': 'standard_enkel'})
            save.assert_called_once()
            self.assertTrue(api.settings['storage_layout_profile_selected'])
            self.assertEqual(resolve_storage_profile(api.settings), 'standard_enkel')
            self.assertEqual(job.work_operations, root / 'repository_operations')
            self.assertFalse((root / 'repository_operations').exists())

    def test_profiles_contain_generic_descriptions_and_visual_trees(self):
        data = json.loads((ROOT / 'config/storage_layouts.json').read_text('utf-8'))
        profiles = {x['id']: x for x in data['profiles']}
        self.assertEqual(data['schema_version'], 1)
        for key in ('standard_enkel', 'ikamr_standard', 'arkivskaper_hierarkisk'):
            self.assertTrue(profile_best_for(key))
            self.assertIn('├──', profiles[key]['example_tree'])
            self.assertIn('└──', profiles[key]['example_tree'])
            self.assertNotIn('IKAMR', profiles[key]['label'])
            self.assertNotIn('IKAR', profiles[key]['label'])
        self.assertEqual(profiles['ikamr_standard']['roles']['work_operations'],
                         '{package_root}/repository_operations')
        self.assertEqual(profiles['standard_enkel']['roles']['work_operations'],
                         '{package_root}/work')


class SetupGuiContractTests(unittest.TestCase):
    def setUp(self):
        self.a2 = (ROOT / 'gui_qt/setup_v0110_a2.py').read_text(encoding='utf-8')
        self.main = (ROOT / 'gui_qt/main_window.py').read_text(encoding='utf-8')
        self.api = (ROOT / 'app/workbench_api_v0110_a1.py').read_text(encoding='utf-8')
        for code in (self.a2, self.main, self.api):
            ast.parse(code)

    def test_general_tab_optional_fields_and_unclipped_info(self):
        for key in ('temp_dir', 'run_log_dir', 'setup_dir', 'job_list_dir'):
            self.assertIn(key, self.a2)
        self.assertIn('setPlaceholderText(placeholder)', self.a2)
        self.assertIn('Tomme mappefelt er helt i orden', self.a2)
        self.assertIn('QGridLayout(body)', self.a2)
        self.assertIn('form.addRow(body)', self.a2)
        self.assertIn('setWordWrap(True)', self.a2)

    def test_profile_cards_and_source_work_aip_notice(self):
        for keyword in ('QRadioButton', 'QButtonGroup', 'STANDARD / ANBEFALT',
                        'Eksisterende Source, Work, AIP', 'Påvirker:',
                        'Påvirker ikke:', 'Eksempel på mappestruktur'):
            self.assertIn(keyword, self.a2)
        self.assertIn('resolve_storage_profile(self.settings)', self.a2)
        self.assertIn('profile.example_tree', self.a2)

    def test_profile_cards_save_only_on_explicit_save(self):
        self.assertIn('_BaseSetupDialog._save(self)', self.a2)
        self.assertIn("result['storage_layout_profile']", (ROOT / 'gui_qt/setup_v0110_a1.py').read_text('utf-8'))
        self.assertIn("updated['storage_layout_profile_selected'] = True", self.api)
        self.assertIn('saved = save_config(updated)', self.api)
        self.assertIn('self.settings.update(updated)', self.api)
        # The UI cannot silently mutate a job or create folders during selection.
        self.assertNotIn('update_storage(', self.a2)
        self.assertNotIn('.mkdir(', self.a2)

    def test_new_job_and_work_selection_use_same_effective_default(self):
        self.assertIn('from gui_qt.setup_v0110_a2 import DwmSetupDialog', self.main)
        self.assertIn('profile_id = pick_profile(api_settings)', self.main)
        self.assertIn('profile_id = resolve_storage_profile(self.api.settings)', self.main)
        self.assertIn('elif resolve_storage_profile(self.api.settings)', self.main)
        self.assertIn('propose_profile_work_location(', self.main)
        self.assertIn('suggest_known_source_work(source, profile_id=profile_id)', self.main)

    def test_version_matches_distribution_and_has_a2(self):
        self.assertEqual(VERSION, '0.1.10-a2')
        with (ROOT / 'pyproject.toml').open('rb') as f:
            self.assertEqual(tomllib.load(f)['project']['version'], '0.1.10a2')


if __name__ == '__main__':
    unittest.main()
