"""Focused, offline regression tests for the depot receiving-directory tool."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.receiving_folders import (
    ReceiveProfile, create_receiving_folders, load_profiles, plan_receiving_folders,
    safe_suggestion, suggested_folder_name, SETUP_FILE_TYPE,
)


class ReceivingFolderTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.profile = ReceiveProfile('depot', 'Test', '{label}', ('01', '02/metadata', '02/log'))

    def test_load_profiles_with_custom_folders(self):
        path = self.base / 'profile.json'
        path.write_text(json.dumps({
            'file_type': SETUP_FILE_TYPE, 'format_version': 1,
            'profiles': [{'id': 'depot1', 'name': 'Depot 1', 'name_template': '{label}',
                          'folders': ['original', 'work/metadata']}]
        }))
        profile, = load_profiles(path)
        self.assertEqual(profile.folders, ('original', 'work/metadata'))

    def test_load_profiles_rejects_unsupported_placeholder(self):
        path = self.base / 'profile.json'
        path.write_text(json.dumps({
            'file_type': SETUP_FILE_TYPE, 'format_version': 1,
            'profiles': [{'id': 'bad', 'name': 'Bad', 'name_template': '{label.__class__}',
                          'folders': []}]
        }))
        with self.assertRaises(ValueError):
            load_profiles(path)

    def test_load_profiles_rejects_parent_escape(self):
        path = self.base / 'profile.json'
        path.write_text(json.dumps({
            'file_type': SETUP_FILE_TYPE, 'format_version': 1,
            'profiles': [{'id': 'bad', 'name': 'Bad', 'name_template': 'x',
                          'folders': ['../escape']}]
        }))
        with self.assertRaises(ValueError):
            load_profiles(path)

    def test_plan_is_read_only_until_commit(self):
        plan = plan_receiving_folders(self.base, 'AIP 1', self.profile)
        self.assertEqual(len(plan.paths), 5)
        self.assertFalse(plan.root.exists())
        self.assertEqual([p.relative_to(plan.root).as_posix() for p in plan.paths],
                         ['.', '01', '02', '02/log', '02/metadata'])

    def test_create_exact_planned_tree(self):
        plan = plan_receiving_folders(self.base, 'AIP 1', self.profile)
        result = create_receiving_folders(plan)
        self.assertEqual(len(result), 5)
        for path in plan.paths:
            self.assertTrue(path.is_dir())

    def test_refuse_existing_destination(self):
        (self.base / 'AIP 1').mkdir()
        with self.assertRaises(FileExistsError):
            plan_receiving_folders(self.base, 'AIP 1', self.profile)
        self.assertTrue((self.base / 'AIP 1').is_dir())

    def test_no_overwrite_on_race_after_preview(self):
        plan = plan_receiving_folders(self.base, 'AIP 1', self.profile)
        plan.root.mkdir()
        with self.assertRaises(FileExistsError):
            create_receiving_folders(plan)
        self.assertTrue(plan.root.exists())

    def test_parent_traversal_blocked_from_metadata(self):
        profile = ReceiveProfile('depot', 'Test', '{label}', ('data/{system}',))
        with self.assertRaises(ValueError):
            plan_receiving_folders(self.base, 'AIP 1', profile, {'system': '../../elsewhere'})
        self.assertFalse((self.base / 'AIP 1').exists())

    def test_unsafe_manual_names_rejected(self):
        for name in ('../other', 'CON', 'con.txt', 'a/b', 'a\\b', 'a:', 'file.', 'file '):
            with self.subTest(name=name), self.assertRaises(ValueError):
                plan_receiving_folders(self.base, name, self.profile)

    def test_absolute_subfolder_rejected(self):
        for name in ('/root', 'C:\\Windows', 'a//b', 'a/../b'):
            profile = ReceiveProfile('test', 'Test', '{label}', (name,))
            with self.subTest(name=name), self.assertRaises(ValueError):
                plan_receiving_folders(self.base, 'AIP 1', profile)

    def test_template_requires_available_metadata(self):
        with self.assertRaisesRegex(ValueError, 'system'):
            suggested_folder_name(ReceiveProfile('p', 'P', '{system}', ()), {'label': 'A'})

    def test_safe_xml_suggestion_only(self):
        self.assertEqual(safe_suggestion('IKAMR 20/21 - A'), 'IKAMR 20 - 21 - A')
        self.assertEqual(suggested_folder_name(self.profile, {'label': 'IKAMR 20/21'}),
                         'IKAMR 20 - 21')

    def test_literal_folders_work_without_xml(self):
        result = plan_receiving_folders(self.base, 'Manuelt',
                     ReceiveProfile('manual', 'Manual', '{label}', ('Sjekk', 'DOK/Meta')))
        create_receiving_folders(result)
        self.assertTrue((self.base / 'Manuelt' / 'DOK' / 'Meta').is_dir())

    def test_rolls_back_created_empty_directories_on_failure(self):
        plan = plan_receiving_folders(self.base, 'AIP 1', self.profile)
        actual_mkdir = Path.mkdir
        state = {'attempts': 0}
        def fail_midway(path, *args, **kwargs):
            state['attempts'] += 1
            if state['attempts'] == 3:
                raise OSError('disk test failure')
            return actual_mkdir(path, *args, **kwargs)
        with patch.object(Path, 'mkdir', fail_midway):
            with self.assertRaises(OSError):
                create_receiving_folders(plan)
        self.assertFalse(plan.root.exists())

    def test_depot_settings_loads_repo_default(self):
        source = Path(__file__).resolve().parents[1] / 'config' / 'receiving_folder_profiles.json'
        profiles = load_profiles(source)
        self.assertEqual(profiles[0].profile_id, 'ikamr_karantene')
        self.assertEqual(profiles[0].folders, ())
        self.assertEqual(profiles[0].audit_file, 'ingest.events.jsonl')
        self.assertEqual(profiles[1].folders, ())


if __name__ == '__main__':
    unittest.main()


class ReceivingGuiWiringTests(unittest.TestCase):
    def test_current_entry_point_uses_receiving_runtime(self):
        root = Path(__file__).resolve().parents[1]
        launcher = (root / 'gui' / 'persistent_app_a27_2.py').read_text(encoding='utf-8')
        runtime = (root / 'gui' / 'persistent_app_a4_7_runtime.py').read_text(encoding='utf-8')
        self.assertIn('from .persistent_app_a4_7_runtime import WorkflowApp as CurrentWorkflowApp', launcher)
        self.assertIn("text='Mottak / Ingest'", runtime)
        self.assertIn('receiving_folder_dialog', runtime)
        self.assertIn('A46WorkflowApp', runtime)

    def test_gui_requires_confirmation_before_creation(self):
        root = Path(__file__).resolve().parents[1]
        dialog = (root / 'gui' / 'receiving_folder_dialog.py').read_text(encoding='utf-8')
        self.assertIn('messagebox.askyesno(', dialog)
        self.assertIn('create_receiving_folders(plan, actor=identity)', dialog)
        self.assertLess(dialog.index('messagebox.askyesno('), dialog.index('create_receiving_folders(plan, actor=identity)'))
