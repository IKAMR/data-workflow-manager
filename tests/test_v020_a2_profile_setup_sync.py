"""v0.2.0-a2: fixed work profiles show effective checks; custom edits survive.

Execute the actual Setup methods with lightweight checkbox/combobox doubles.
The regression runs in test.bat even without PySide6 installed.
"""
from __future__ import annotations

import ast
from pathlib import Path
from types import SimpleNamespace
import unittest

SHELL = Path(__file__).resolve().parents[1] / 'gui_qt' / 'start_shell_v020_a1.py'


def setup_methods():
    tree = ast.parse(SHELL.read_text(encoding='utf-8'))
    needed_names = {
        'PROFILE_KEY', 'FEATURES_KEY', 'STARTUP_KEY', 'PAGE_KEY',
        'AREA_VISIBILITY_KEY', 'PROFILES', 'SECTIONS',
    }
    needed_functions = {
        'normalize_profile', 'normalize_sections', 'visible_sections',
    }
    nodes = []
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id in needed_names
            for target in node.targets
        ):
            nodes.append(node)
        elif isinstance(node, ast.FunctionDef) and node.name in needed_functions:
            nodes.append(node)
        elif isinstance(node, ast.ClassDef) and node.name == 'StartupSetupPage':
            # Execute the actual production methods without instantiating Qt.
            methods = [
                item for item in node.body
                if isinstance(item, ast.FunctionDef) and item.name in ('_sync', 'updates')
            ]
            assert {item.name for item in methods} == {'_sync', 'updates'}
            node.bases = [ast.Name(id='object', ctx=ast.Load())]
            node.body = methods
            nodes.append(node)
    env = {}
    exec(compile(ast.fix_missing_locations(ast.Module(body=nodes, type_ignores=[])),
                 str(SHELL), 'exec'), env)
    return env


class Combo:
    def __init__(self, current):
        self.value = current

    def currentData(self):
        return self.value


class Check:
    def __init__(self, checked=False):
        self.checked = checked
        self.enabled = True

    def setChecked(self, value):
        self.checked = bool(value)

    def isChecked(self):
        return self.checked

    def setEnabled(self, value):
        self.enabled = bool(value)

    def click(self, value):
        if not self.enabled:
            raise AssertionError('Fixed profile checkboxes must be disabled')
        self.setChecked(value)


class SetupProfilesA2Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.env = setup_methods()
        cls.keys = tuple(item[0] for item in cls.env['SECTIONS'])

    def new_page(self, profile, custom=('control',)):
        page = SimpleNamespace(
            profile=Combo(profile),
            checks={key: Check() for key in self.keys},
            _custom_sections=list(custom),
            _shown_profile=None,
            modes={'basic': Check(True), 'last': Check(), 'advanced': Check()},
            pages={'profile': Check(True), 'last': Check(),
                   'home': Check(), 'control': Check()},
            area_visibility=Combo(0),
        )
        self.sync(page)
        return page

    def sync(self, page):
        self.env['StartupSetupPage']._sync(page)

    def updates(self, page):
        return self.env['StartupSetupPage'].updates(page)

    def selected(self, page):
        return [key for key, check in page.checks.items() if check.isChecked()]

    def test_control_profile_displays_only_control_not_saved_custom(self):
        page = self.new_page('control', ('ingest', 'report'))
        self.assertEqual(self.selected(page), ['control'])
        self.assertTrue(all(not check.enabled for check in page.checks.values()))
        with self.assertRaises(AssertionError):
            page.checks['ingest'].click(True)
        self.assertEqual(self.updates(page)['ui_visible_sections'], ['ingest', 'report'])

    def test_depot_profile_displays_all_eight_not_saved_custom(self):
        page = self.new_page('depot', ('control',))
        self.assertEqual(self.selected(page), list(self.keys))
        self.assertTrue(all(not check.enabled for check in page.checks.values()))
        saved = self.updates(page)
        self.assertEqual(saved['ui_work_profile'], 'depot')
        self.assertEqual(saved['ui_visible_sections'], ['control'])

    def test_custom_profile_displays_saved_checkboxes_and_is_editable(self):
        page = self.new_page('custom', ('workspace', 'report'))
        self.assertEqual(self.selected(page), ['workspace', 'report'])
        self.assertTrue(all(check.enabled for check in page.checks.values()))
        page.checks['control'].click(True)
        self.assertEqual(self.updates(page)['ui_visible_sections'],
                         ['workspace', 'control', 'report'])

    def test_unsaved_custom_edits_survive_fixed_profiles_before_save(self):
        page = self.new_page('custom', ('control', 'report'))
        page.checks['control'].click(False)
        page.checks['ingest'].click(True)
        page.profile.value = 'depot'
        self.sync(page)
        self.assertEqual(self.selected(page), list(self.keys))
        self.assertEqual(self.updates(page)['ui_visible_sections'], ['ingest', 'report'])
        page.profile.value = 'control'
        self.sync(page)
        self.assertEqual(self.selected(page), ['control'])
        page.profile.value = 'custom'
        self.sync(page)
        self.assertEqual(self.selected(page), ['ingest', 'report'])
        self.assertTrue(all(check.enabled for check in page.checks.values()))
        self.assertEqual(self.updates(page)['ui_visible_sections'], ['ingest', 'report'])

    def test_switch_between_fixed_profiles_never_overwrites_custom(self):
        page = self.new_page('depot', ('access', 'crm'))
        page.profile.value = 'control'
        self.sync(page)
        page.profile.value = 'depot'
        self.sync(page)
        page.profile.value = 'custom'
        self.sync(page)
        self.assertEqual(self.selected(page), ['crm', 'access'])
        self.assertEqual(self.updates(page)['ui_visible_sections'], ['crm', 'access'])

    def test_empty_custom_profile_is_preserved(self):
        page = self.new_page('custom', ())
        self.assertEqual(self.selected(page), [])
        page.profile.value = 'depot'
        self.sync(page)
        self.assertEqual(self.updates(page)['ui_visible_sections'], [])
        page.profile.value = 'custom'
        self.sync(page)
        self.assertEqual(self.selected(page), [])

    def test_setup_wiring_and_explanation(self):
        src = SHELL.read_text(encoding='utf-8')
        self.assertIn('self.profile.currentIndexChanged.connect(self._sync)', src)
        self.assertIn('self._shown_profile = profile', src)
        self.assertIn('self._custom_sections = normalize_sections(', src)
        self.assertIn('control.setEnabled(profile == \'custom\')', src)
        self.assertIn('Velg Egendefinert', src)
        self.assertIn('self._sync()', src)


if __name__ == '__main__':
    unittest.main()
