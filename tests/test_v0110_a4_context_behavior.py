"""Headless regression of the Qt context toolbar and read-only format overlay."""
from __future__ import annotations

import ast
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'gui_qt/result_center_v0110_a4.py'


def _load_context_method():
    code = ast.parse(SOURCE.read_text(encoding='utf-8'))
    cls = next(node for node in code.body
               if isinstance(node, ast.ClassDef) and node.name == 'ResultCenterWindow')
    method = next(node for node in cls.body
                  if isinstance(node, ast.FunctionDef)
                  and node.name == '_a4_apply_context_actions')
    ns = {}
    for node in code.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id in {'_CONTEXT_ACTIONS', '_COMMON_ACTIONS'}:
                    ns[target.id] = ast.literal_eval(node.value)
    exec(compile(ast.fix_missing_locations(ast.Module(body=[method], type_ignores=[])),
                 str(SOURCE), 'exec'), ns)
    return ns['_a4_apply_context_actions']


class FakeTabControl:
    def __init__(self):
        self.active = 'Oversikt'
    def currentIndex(self):
        return 0
    def tabText(self, index):
        return self.active


class FakeButton:
    def __init__(self):
        self.visible = False
    def setVisible(self, visible):
        self.visible = bool(visible)
    def setText(self, value):
        self.title = value


class ContextToolbarA4Tests(unittest.TestCase):
    def test_tab_specific_actions_plus_two_common_actions(self):
        expected = {
            'Oversikt': ('Klassisk uttrekksoversikt…',),
            'Periodevurdering': ('Vurder periode…',),
            'Depotrapporter': ('Åpne kildefil', 'Lag rapport / samlerapport…'),
            'KDRS Query': ('Åpne kildefil', 'Velg KDRS-evidens…'),
            'PRONOM': ('Åpne kildefil',),
            'Årsfordeling': (),
            'Depotvurdering': (),
        }
        all_labels = {'Oppdater visning', 'Åpne Work-mappe'}
        for names in expected.values():
            all_labels.update(names)
        class Window:
            _a4_apply_context_actions = _load_context_method()
            def __init__(self):
                self.tabs = FakeTabControl()
                self._a4_action_buttons = {text: FakeButton() for text in all_labels}
        obj = Window()
        for title, actions in expected.items():
            obj.tabs.active = title
            obj._a4_apply_context_actions()
            actual = {name for name, control in obj._a4_action_buttons.items()
                      if control.visible}
            self.assertEqual(actual, set(actions) | {'Oppdater visning', 'Åpne Work-mappe'}, title)
            if title == 'Depotrapporter':
                self.assertEqual(obj._a4_action_buttons['Åpne kildefil'].title, 'Åpne rapport')
            else:
                self.assertEqual(obj._a4_action_buttons['Åpne kildefil'].title, 'Åpne kildefil')


class PronomOverlayHeadlessTests(unittest.TestCase):
    def test_overlay_uses_original_data_without_modifying_evidence(self):
        from app.format_policy_v0110_a4 import load_format_policy, FORMAT_PROFILE_DIR, evaluate_puid
        from app.format_context_v0110_a5 import read_pronom_import_context
        source = ast.parse(SOURCE.read_text(encoding='utf-8'))
        cls = next(n for n in source.body if isinstance(n, ast.ClassDef)
                   and n.name == 'ResultCenterWindow')
        method = next(n for n in cls.body if isinstance(n, ast.FunctionDef)
                      and n.name == '_a4_assess_pronom')
        ns = {'evaluate_puid': evaluate_puid,
              'read_pronom_import_context': read_pronom_import_context,
              '_ORIGINAL_DETAIL_ROLE': 83, '_FORMAT_STATUS_ROLE': 84,
              'DETAIL_ROLE': 32, 'PATH_ROLE': 33}
        exec(compile(ast.fix_missing_locations(ast.Module(body=[method], type_ignores=[])),
                     str(SOURCE), 'exec'), ns)
        class Item:
            def __init__(self, fields, details):
                self.fields = list(fields) + ['']; self.roles = {32: details}; self.tooltips = {}
            def text(self, col): return self.fields[col]
            def setText(self, col, text): self.fields[col] = text
            def data(self, col, role): return self.roles.get(role)
            def setData(self, col, role, value): self.roles[role] = value
            def setToolTip(self, col, text): self.tooltips[col] = text
        class Tree:
            def __init__(self, items): self.items=items
            def topLevelItemCount(self): return len(self.items)
            def topLevelItem(self, index): return self.items[index]
            def currentItem(self): return None
        class Window:
            _a4_assess_pronom = ns['_a4_assess_pronom']
            def _a4_filter_pronom(self): self.filtered = True
            def _show_detail(self, tab): pass
        original={'import_id': 'immutable-import', 'source_row': {'PUID': 'fmt/101'}}
        a=Item(['Jobb-A', 'fmt/101', 'XML', '1.0', '7', 'historical-RAF'], original)
        b=Item(['Jobb-A', 'fmt/999999', 'Ukategorisert', '', '3', ''], {})
        w=Window()
        w._trees={'PRONOM': Tree([a,b])}
        w._a4_format_policy=load_format_policy(FORMAT_PROFILE_DIR/'nasjonalarkivet_2026-11-10.json')
        w._a4_assess_pronom()
        self.assertTrue(w.filtered)
        self.assertEqual(a.text(6),'Akseptert i valgt profil')
        self.assertEqual(b.text(6),'Til avklaring')
        self.assertIn('regelprofil',a.roles[32]['formatvurdering'])
        self.assertEqual(original,{'import_id': 'immutable-import', 'source_row': {'PUID': 'fmt/101'}})
        self.assertEqual(a.text(5),'historical-RAF')
        self.assertEqual(a.roles[32]['historisk_arkade_raf']['klassifisering'], 'historical-RAF')
        self.assertIn('Importert', a.tooltips[5])
        w._a4_format_policy=None
        w._a4_assess_pronom()
        self.assertEqual(a.text(6),'Ikke vurdert')
        self.assertEqual(a.roles[32]['source_row'],original['source_row'])
        self.assertEqual(a.roles[83],original)


if __name__ == '__main__':
    unittest.main()
