"""a1: generic storage profiles, safe suggestions and version boundary."""
from __future__ import annotations

import ast
import json
from pathlib import Path
import re
import tempfile
import tomllib
import unittest
from unittest.mock import patch

from app.storage_profiles_v0110_a1 import (
    DEFAULT_STORAGE_PROFILE, BUILTIN_STORAGE_PROFILE_IDS,
    propose_profile_work_location, propose_work_with_suffix,
    require_storage_profile, storage_profile_choices, suggest_known_source_work,
)
from app.storage_layouts import materialize_storage_roles
from settings import DEFAULT_CONFIG, load_config
from version import VERSION

ROOT = Path(__file__).resolve().parents[1]


class A1StorageProfileTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)

    def test_clean_new_default_is_simple(self):
        self.assertEqual(DEFAULT_CONFIG['storage_layout_profile'], 'standard_enkel')
        self.assertEqual(DEFAULT_STORAGE_PROFILE, 'standard_enkel')

    def test_three_generic_profiles_have_stable_ids_and_previews(self):
        choices = storage_profile_choices()
        self.assertEqual(tuple(p.profile_id for p in choices), BUILTIN_STORAGE_PROFILE_IDS)
        self.assertEqual(len(choices), 3)
        self.assertTrue(all(p.example_tree and p.description for p in choices))
        self.assertIn('Standard', choices[0].label)
        self.assertIn('Pakkeorientert', choices[1].label)
        self.assertIn('Arkivskaperorientert', choices[2].label)
        self.assertNotIn('IKAMR', choices[1].label)
        self.assertNotIn('IKAR', choices[2].label)

    def test_legacy_profile_ids_are_still_valid(self):
        self.assertEqual(require_storage_profile('ikamr_standard'), 'ikamr_standard')
        self.assertEqual(require_storage_profile('none'), 'none')
        self.assertEqual(len(storage_profile_choices(include_legacy=True)), 4)
        with self.assertRaisesRegex(ValueError, 'Ukjent lagringsprofil'):
            require_storage_profile('invented-profile')

    def test_standard_source_work_aip_are_independent(self):
        pkg = self.root / 'my-package'
        extraction = pkg / 'source' / 'noark5-extraction'
        roles = suggest_known_source_work(extraction, profile_id='standard_enkel')
        self.assertEqual(roles['source_root'], pkg / 'source')
        self.assertEqual(roles['source_extraction'], extraction)
        self.assertEqual(roles['work_root'], pkg)
        self.assertEqual(roles['work_operations'], pkg / 'work')
        self.assertEqual(roles['archive_root'], pkg / 'aip')
        self.assertNotIn('work_content', roles)
        self.assertFalse(pkg.exists())

    def test_package_profile_matches_historic_physical_ikamr_structure(self):
        pkg = self.root / '1547_003_ephorte'
        extraction = pkg / 'content' / 'sip' / 'content'
        roles = materialize_storage_roles(extraction, layout_id='ikamr_standard')
        self.assertEqual(roles['source_root'], pkg)
        self.assertEqual(roles['work_content'], pkg / 'content')
        self.assertEqual(roles['work_operations'], pkg / 'repository_operations')
        self.assertEqual(roles['archive_root'], pkg / 'aip')
        self.assertFalse(pkg.exists())

    def test_hierarchical_profile_is_an_example_not_ikar_hardcoding(self):
        sys = self.root / 'depot' / 'arkivskaper' / 'system'
        extraction = sys / 'avlevering' / 'eksempel'
        roles = suggest_known_source_work(extraction, profile_id='arkivskaper_hierarkisk')
        self.assertEqual(roles['source_root'], sys / 'avlevering')
        self.assertEqual(roles['work_operations'], sys / 'arbeidsområder')
        self.assertEqual(roles['archive_root'], sys / 'arkivpakker')
        self.assertFalse(sys.exists())

    def test_unknown_source_never_guesses_a_package(self):
        extraction = self.root / 'mottak' / 'n5'
        for profile in BUILTIN_STORAGE_PROFILE_IDS:
            self.assertEqual(suggest_known_source_work(extraction, profile_id=profile),
                             {'source_extraction': extraction})

    def test_standard_work_proposals_do_not_duplicate_work_or_dwm(self):
        pkg = self.root / 'package'
        for selected, role in (
            (pkg, 'work_root'),
            (pkg / 'work', 'work_operations'),
            (pkg / 'work' / 'dwm', 'app_subfolder'),
            (pkg / 'work' / 'dwm' / 'JOB-001', 'job_subfolder'),
        ):
            proposal = propose_profile_work_location(selected, profile_id='standard_enkel')
            self.assertEqual(proposal.work_root, pkg)
            self.assertEqual(proposal.work_operations, pkg / 'work')
            self.assertEqual(proposal.selected_role, role)
        self.assertFalse(pkg.exists())

    def test_hierarchical_work_proposal_uses_own_operation_level(self):
        root = self.root / 'depot' / 'skaper' / 'system'
        plan = propose_profile_work_location(root, profile_id='arkivskaper_hierarkisk')
        self.assertEqual(plan.work_operations, root / 'arbeidsområder')
        direct = propose_profile_work_location(root / 'arbeidsområder', profile_id='arkivskaper_hierarkisk')
        self.assertEqual(direct.work_operations, plan.work_operations)

    def test_nested_operations_from_configuration_are_supported(self):
        root = self.root / 'workarea'
        suffix = ('administrative-metadata', 'repository_operations')
        plan = propose_work_with_suffix(root, suffix)
        self.assertEqual(plan.work_operations, root / 'administrative-metadata' / 'repository_operations')
        again = propose_work_with_suffix(plan.work_operations / 'dwm', suffix)
        self.assertEqual(again.work_root, root)
        self.assertEqual(again.work_operations, plan.work_operations)

    def test_reject_unrecognized_children_inside_work_operations(self):
        with self.assertRaisesRegex(ValueError, 'inne i Work-operasjoner'):
            propose_profile_work_location(self.root / 'work' / 'other', profile_id='standard_enkel')
        with self.assertRaisesRegex(ValueError, 'Ukjent'):
            propose_profile_work_location(self.root, profile_id='invalid')

    def test_previous_settings_keep_explicit_legacy_selection(self):
        import settings
        path = self.root / 'config.json'
        path.write_text(json.dumps({'storage_layout_profile': 'ikamr_standard'}), encoding='utf-8')
        with patch.object(settings, 'CONFIG_PATH', path):
            loaded = load_config()
        self.assertEqual(loaded['storage_layout_profile'], 'ikamr_standard')

    def test_version_and_distribution_are_synchronized(self):
        match = re.fullmatch(r'(\d+)\.(\d+)\.(\d+)(?:-a(\d+)(?:\.(\d+))*)?', VERSION)
        self.assertIsNotNone(match, VERSION)
        release = tuple(int(match.group(i)) for i in (1, 2, 3))
        self.assertGreaterEqual(release, (0, 1, 10))
        if release == (0, 1, 10) and match.group(4) is not None:
            self.assertGreaterEqual(int(match.group(4)), 1)
        with (ROOT / 'pyproject.toml').open('rb') as handle:
            self.assertEqual(tomllib.load(handle)['project']['version'], VERSION.replace('-a', 'a'))

    def test_gui_and_api_reference_new_profiles_without_rewriting_old_models(self):
        main = (ROOT / 'gui_qt/main_window.py').read_text(encoding='utf-8')
        gui = (ROOT / 'gui_qt/setup_v0110_a1.py').read_text(encoding='utf-8')
        api = (ROOT / 'app/workbench_api_v0110_a1.py').read_text(encoding='utf-8')
        for source in (main, gui, api):
            ast.parse(source)
        self.assertIn('suggest_known_source_work(source, profile_id=profile_id)', main)
        self.assertIn('propose_profile_work_location(', main)
        self.assertIn("self._complexity == 'Standard' and not planned_work", main)
        self.assertIn('from gui_qt.setup_v0110_a2 import DwmSetupDialog', main)
        self.assertIn('storage_layout_profile', gui)
        self.assertIn("'storage_layout_profile' not in changes", api)
        self.assertIn('saved = save_config(updated)', api)

    @unittest.skipUnless((ROOT / 'app/application_api.py').is_file(), 'Requires complete DWM checkout')
    def test_workbench_setup_persists_selected_profile_in_one_write(self):
        from app.workbench_api_v0110_a1 import DwmWorkbenchAPI
        from noark5_workflow.core.job import Job
        api = DwmWorkbenchAPI(settings={'storage_layout_profile': 'ikamr_standard',
                                        'app_work_subfolder': 'dwm'})
        job = Job('JOB-001', work_root=self.root, work_operations=self.root / 'repository_operations')
        api._batch.add(job)
        with patch('app.workbench_api_v0110_a1.save_config', side_effect=lambda values: dict(values)) as save:
            updated = api.save_setup({'storage_layout_profile': 'standard_enkel'})
        save.assert_called_once()
        self.assertEqual(updated['storage_layout_profile'], 'standard_enkel')
        self.assertEqual(api.settings['storage_layout_profile'], 'standard_enkel')
        self.assertEqual(job.work_operations, self.root / 'repository_operations')
        self.assertFalse((self.root / 'repository_operations').exists())

    @unittest.skipUnless((ROOT / 'app/application_api.py').is_file(), 'Requires complete DWM checkout')
    def test_invalid_profile_does_not_write_setup(self):
        from app.workbench_api_v0110_a1 import DwmWorkbenchAPI
        from app.application_api import DwmApiError
        api = DwmWorkbenchAPI(settings={'storage_layout_profile': 'ikamr_standard'})
        with patch('app.workbench_api_v0110_a1.save_config') as save:
            with self.assertRaises(DwmApiError):
                api.save_setup({'storage_layout_profile': 'not-real'})
        save.assert_not_called()
        self.assertEqual(api.settings['storage_layout_profile'], 'ikamr_standard')


if __name__ == '__main__':
    unittest.main()
