"""a5.2: select the first real result without a manual click (Qt-free tests)."""
from __future__ import annotations

import ast
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'gui_qt' / 'result_center_v0110_a4.py'


def load_selection_method():
    tree = ast.parse(SOURCE.read_text(encoding='utf-8'))
    klass = next(node for node in tree.body
                 if isinstance(node, ast.ClassDef) and node.name == 'ResultCenterWindow')
    method = next(node for node in klass.body
                  if isinstance(node, ast.FunctionDef)
                  and node.name == '_a5_select_first_result')
    namespace = {}
    exec(compile(ast.fix_missing_locations(ast.Module(body=[method], type_ignores=[])),
                 str(SOURCE), 'exec'), namespace)
    return namespace['_a5_select_first_result']


class FakeItem:
    def __init__(self, label, *, hidden=False):
        self.label = label
        self.hidden = hidden

    def text(self, col):
        return self.label if col == 0 else ''

    def isHidden(self):
        return self.hidden


class FakeTree:
    def __init__(self, items, selected=None):
        self.items = list(items)
        self.current = selected
        self.select_calls = 0

    def topLevelItemCount(self):
        return len(self.items)

    def topLevelItem(self, index):
        return self.items[index]

    def currentItem(self):
        return self.current

    def setCurrentItem(self, item):
        self.current = item
        self.select_calls += 1


class FakeTabs:
    def __init__(self, active='Oversikt'):
        self.active = active

    def currentIndex(self):
        return 0

    def tabText(self, index):
        return self.active


class FakeDetail:
    def __init__(self):
        self.cleared = False

    def clear(self):
        self.cleared = True


class Window:
    _a5_select_first_result = load_selection_method()

    def __init__(self, label, items, selected=None):
        self.tabs = FakeTabs(label)
        self.tree = FakeTree(items, selected)
        self._trees = {label: self.tree}
        self.detail = FakeDetail()
        self._details = {label: self.detail}
        self.shown = []

    def _show_detail(self, tab):
        self.shown.append(tab)


class DefaultResultSelectionTests(unittest.TestCase):
    def test_single_real_row_auto_selected_and_detail_shown(self):
        first = FakeItem('1547_007 Forum Winsak')
        w = Window('Oversikt', [first])
        w._a5_select_first_result()
        self.assertIs(w.tree.current, first)
        self.assertEqual(w.shown, ['Oversikt'])

    def test_first_of_multiple_is_chosen(self):
        rows = [FakeItem('job 1'), FakeItem('job 2')]
        w = Window('Oversikt', rows)
        w._a5_select_first_result()
        self.assertIs(w.tree.current, rows[0])
        self.assertEqual(w.tree.select_calls, 1)

    def test_existing_selection_is_not_overwritten(self):
        rows = [FakeItem('job 1'), FakeItem('job 2')]
        w = Window('Oversikt', rows, selected=rows[1])
        w._a5_select_first_result()
        self.assertIs(w.tree.current, rows[1])
        self.assertEqual(w.tree.select_calls, 0)

    def test_first_visible_real_row_not_placeholder(self):
        placeholder = FakeItem('Ingen lagret evidens for denne kilden')
        hidden = FakeItem('match', hidden=True)
        real = FakeItem('visible')
        w = Window('PRONOM', [placeholder, hidden, real])
        w._a5_select_first_result()
        self.assertIs(w.tree.current, real)

    def test_hidden_selected_row_falls_back_to_visible(self):
        hidden = FakeItem('old row', hidden=True)
        real = FakeItem('new row')
        w = Window('PRONOM', [hidden, real], selected=hidden)
        w._a5_select_first_result()
        self.assertIs(w.tree.current, real)

    def test_no_evidence_does_not_pick_fake_result(self):
        w = Window('Oversikt', [FakeItem('Ingen tilgjengelig Work')])
        w._a5_select_first_result()
        self.assertIsNone(w.tree.current)
        self.assertTrue(w.detail.cleared)

    def test_no_tree_tab_is_ignored(self):
        w = Window('Oversikt', [])
        w.tabs.active = 'Årsfordeling'
        w._a5_select_first_result()
        self.assertEqual(w.shown, [])

    def test_connection_and_initial_refresh_hooks_exist(self):
        source = SOURCE.read_text(encoding='utf-8')
        self.assertIn('self.tabs.currentChanged.connect(self._a5_select_first_result)', source)
        self.assertIn('self._a5_select_first_result()', source)
        # The selection contract remains after the a5.3 source enrichment.
        tree = ast.parse(source)
        klass = next(n for n in tree.body if isinstance(n, ast.ClassDef)
                     and n.name == 'ResultCenterWindow')
        refresh = next(n for n in klass.body if isinstance(n, ast.FunctionDef)
                       and n.name == 'refresh')
        calls = [n.func.attr for n in ast.walk(refresh) if isinstance(n, ast.Call)
                 and isinstance(n.func, ast.Attribute)]
        self.assertIn('_a53_enrich_result_tables', calls)
        self.assertIn('_a5_select_first_result', calls)


if __name__ == '__main__':
    unittest.main()
