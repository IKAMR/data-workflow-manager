"""a2.5: Qt-free regression tests for PRONOM default and column sizing.

No source evidence is read or modified by these presentation changes.
The production PySide6 window still needs an actual Windows GUI smoke test.
"""
from __future__ import annotations

import ast
from pathlib import Path
from types import SimpleNamespace
import unittest

from app.format_assessment_v0111_a2 import (
    FORMAT_SOURCE_NASJONALARKIVET, FORMAT_SOURCE_ARKADE_RAF,
)

SOURCE = Path(__file__).resolve().parents[1] / 'gui_qt' / 'result_center_v0111_a2.py'
TREE = ast.parse(SOURCE.read_text(encoding='utf-8'))
CLASS = next(n for n in TREE.body if isinstance(n, ast.ClassDef)
             and n.name == 'ResultCenterWindow')


def extract_method(name, namespace=None):
    node = next(n for n in CLASS.body if isinstance(n, ast.FunctionDef)
                and n.name == name)
    ns = dict(namespace or {})
    compiled = ast.fix_missing_locations(ast.Module(body=[node], type_ignores=[]))
    exec(compile(compiled, str(SOURCE), 'exec'), ns)
    return ns[name]


class Settings:
    def __init__(self, initial=None):
        self.values = dict(initial or {})
    def value(self, key, default=None):
        return self.values.get(key, default)
    def setValue(self, key, value):
        self.values[key] = value


class Combo:
    def __init__(self, options, selected=0):
        self.options = list(options)
        self.index = selected
        self.changes = []
        self.on_change = None
    def currentIndex(self):
        return self.index
    def currentData(self):
        return self.options[self.index]
    def findData(self, value):
        try:
            return self.options.index(value)
        except ValueError:
            return -1
    def setCurrentIndex(self, value):
        self.changes.append(value)
        self.index = value
        if self.on_change is not None:
            self.on_change(value)


class Heading:
    def __init__(self):
        self.labels = {}
    def setText(self, col, value):
        self.labels[col] = value


class Tree:
    def __init__(self):
        self.heading = Heading()
    def headerItem(self):
        return self.heading


class PolicyStartupTests(unittest.TestCase):
    policy_path = '/app/config/formats/nasjonalarkivet_2026-11-10.json'
    custom_path = '/settings/custom-list.json'

    def window(self, options=None, selected=0, preferences=None, missing=''):
        settings = Settings(preferences)
        combo = Combo(options or ['', self.policy_path, self.custom_path], selected)
        tree = Tree()
        called = []
        view = SimpleNamespace(
            _a2_source=FORMAT_SOURCE_NASJONALARKIVET,
            _a4_settings=settings,
            _a4_profiles=[SimpleNamespace(path=Path(self.policy_path))],
            _a5_missing_policy_warning=missing,
            format_policy_combo=combo,
            _trees={'PRONOM': tree},
            _a4_filter_pronom=lambda: called.append('filtered'),
        )
        fn = extract_method('_a2_apply_source', {'FORMAT_SOURCE_ARKADE_RAF': FORMAT_SOURCE_ARKADE_RAF})
        return view, fn, called

    def test_default_selects_actual_json_combo_entry_not_no_assessment(self):
        view, select, called = self.window()
        select(view)
        self.assertEqual(view.format_policy_combo.currentIndex(), 1)
        self.assertEqual(view.format_policy_combo.currentData(), self.policy_path)
        self.assertEqual(called, ['filtered'])
        self.assertEqual(view._trees['PRONOM'].heading.labels[6], 'Valgt regelprofil')

    def test_existing_custom_json_profile_remains_selected(self):
        view, select, _ = self.window(selected=2)
        select(view)
        self.assertEqual(view.format_policy_combo.currentIndex(), 2)
        self.assertEqual(view.format_policy_combo.changes, [])

    def test_explicit_no_assessment_is_preserved(self):
        for flag in (True, 'true', '1'):
            with self.subTest(flag=flag):
                view, select, _ = self.window(
                    preferences={'qt/format_policy_none_explicit': flag})
                select(view)
                self.assertEqual(view.format_policy_combo.currentIndex(), 0)

    def test_missing_custom_profile_does_not_silently_disappear(self):
        view, select, _ = self.window(missing='Previously selected JSON is missing')
        select(view)
        self.assertEqual(view.format_policy_combo.currentIndex(), 0)

    def test_no_available_builtin_does_not_select_wrong_profile(self):
        view, select, _ = self.window(options=['', self.custom_path])
        select(view)
        self.assertEqual(view.format_policy_combo.currentIndex(), 0)

    def test_profile_change_records_deliberate_none_separately(self):
        class ParentBase:
            def _a4_change_policy(self, _index=None, *, persist=True):
                return ('parent-called', persist)
        node = next(n for n in CLASS.body if isinstance(n, ast.FunctionDef)
                    and n.name == '_a4_change_policy')
        parent = ast.ClassDef(name='View', bases=[ast.Name(id='ParentBase', ctx=ast.Load())],
                              keywords=[], body=[node], decorator_list=[])
        ns = {'ParentBase': ParentBase}
        exec(compile(ast.fix_missing_locations(ast.Module(body=[parent], type_ignores=[])),
                     str(SOURCE), 'exec'), ns)
        view = ns['View']()
        view._a4_settings = Settings()
        view.format_policy_combo = Combo(['', self.policy_path], 0)
        self.assertEqual(view._a4_change_policy(), ('parent-called', True))
        self.assertTrue(view._a4_settings.values['qt/format_policy_none_explicit'])
        view.format_policy_combo.index = 1
        view._a4_change_policy()
        self.assertFalse(view._a4_settings.values['qt/format_policy_none_explicit'])
        view.format_policy_combo.index = 0
        view._a4_change_policy(persist=False)
        self.assertFalse(view._a4_settings.values['qt/format_policy_none_explicit'])


class PronomColumnTests(unittest.TestCase):
    class Header:
        def __init__(self):
            self.modes = {}
            self.stretch_last = False
        def setSectionResizeMode(self, column, mode):
            self.modes[column] = mode
        def setStretchLastSection(self, enabled):
            self.stretch_last = enabled

    class Item:
        def __init__(self):
            self.values = ['uttrekk', 'fmt/354', 'Acrobat PDF/A-1b', '1b', '15',
                           'Gyldig', 'Akseptert i valgt profil']
            self.tips = {}
        def columnCount(self): return len(self.values)
        def text(self, column): return self.values[column]
        def setToolTip(self, column, text): self.tips[column] = text

    class FormatTree:
        def __init__(self):
            self.columns = {}
            self._header = PronomColumnTests.Header()
            self._heading = Heading()
            self.items = [PronomColumnTests.Item()]
        def header(self): return self._header
        def headerItem(self): return self._heading
        def columnCount(self): return 7
        def setColumnWidth(self, column, width): self.columns[column] = width
        def topLevelItemCount(self): return len(self.items)
        def topLevelItem(self, index): return self.items[index]

    @staticmethod
    def widgets():
        fake_qt = SimpleNamespace(ResizeMode=SimpleNamespace(
            Interactive='interactive', Stretch='stretch'))
        tree = PronomColumnTests.FormatTree()
        view = SimpleNamespace(_trees={'PRONOM': tree})
        return view, tree, {'QHeaderView': fake_qt}

    def test_last_assessment_column_receives_remaining_width(self):
        view, tree, ns = self.widgets()
        extract_method('_a25_fit_pronom_columns', ns)(view)
        self.assertLessEqual(sum(tree.columns.values()), 585)
        self.assertEqual(tree._header.modes[6], 'stretch')
        self.assertTrue(tree._header.stretch_last)
        # At the screenshot's ~790 px table viewport, >190 px remains for
        # the user-important independent profile verdict.
        self.assertGreaterEqual(790 - sum(tree.columns.values()), 190)
        self.assertEqual(tree._heading.labels[5], 'RAF-220301')
        self.assertEqual(tree.items[0].tips[6], 'Akseptert i valgt profil')
        self.assertEqual(tree.items[0].tips[2], 'Acrobat PDF/A-1b')

    def test_older_widths_are_preserved_for_other_tabs(self):
        class ParentBase:
            def _a56_configure_columns(self): self.parent_called = True
        node1 = next(n for n in CLASS.body if isinstance(n, ast.FunctionDef)
                     and n.name == '_a56_configure_columns')
        node2 = next(n for n in CLASS.body if isinstance(n, ast.FunctionDef)
                     and n.name == '_a25_fit_pronom_columns')
        klass = ast.ClassDef(name='View', bases=[ast.Name(id='ParentBase', ctx=ast.Load())],
                             keywords=[], body=[node1, node2], decorator_list=[])
        view, tree, ns = self.widgets()
        ns['ParentBase'] = ParentBase
        exec(compile(ast.fix_missing_locations(ast.Module(body=[klass], type_ignores=[])),
                     str(SOURCE), 'exec'), ns)
        real = ns['View']()
        real._trees = dict(view._trees)
        real._trees['Arkade 5'] = 'unchanged object'
        real._a56_configure_columns()
        self.assertTrue(real.parent_called)
        self.assertEqual(real._trees['Arkade 5'], 'unchanged object')
        self.assertEqual(tree._header.modes[6], 'stretch')

    def test_layout_changes_do_not_modify_evidence_or_assessment_functions(self):
        functions = {n.name for n in CLASS.body if isinstance(n, ast.FunctionDef)}
        self.assertNotIn('_a4_assess_pronom', functions)
        self.assertNotIn('_a4_export_pronom_standard', functions)
        self.assertNotIn('load_format_policy', functions)
        self.assertIn('readable_pronom_details', SOURCE.read_text('utf-8'))


if __name__ == '__main__':
    unittest.main()
