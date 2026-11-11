"""Qt-free behavioral check for historical PRONOM presentation."""
from __future__ import annotations

import ast
from pathlib import Path
import unittest

from app.format_assessment_v0111_a2 import historical_arkade_status, FORMAT_SOURCE_ARKADE_RAF

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'gui_qt' / 'result_center_v0111_a2.py'


class Item:
    def __init__(self, values):
        self.values = list(values)
        self.role_values = {}
        self.hidden = False
        self.tips = {}
    def text(self, col): return self.values[col]
    def setText(self, col, val): self.values[col] = val
    def columnCount(self): return len(self.values)
    def setData(self, col, role, data): self.role_values[(col, role)] = data
    def setToolTip(self, col, text): self.tips[col] = text
    def setHidden(self, flag): self.hidden = bool(flag)


class Tree:
    def __init__(self, items): self.items = items
    def topLevelItemCount(self): return len(self.items)
    def topLevelItem(self, index): return self.items[index]


class Label:
    def __init__(self): self.value = None
    def setText(self, value): self.value = value


class Select:
    def __init__(self, value=''): self.value = value
    def currentData(self): return self.value


class Text:
    def __init__(self, value=''): self.value = value
    def text(self): return self.value


class HistoricalResultViewTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        root = ast.parse(SOURCE.read_text('utf-8'))
        klass = next(node for node in root.body if isinstance(node, ast.ClassDef)
                     and node.name == 'ResultCenterWindow')
        method = next(node for node in klass.body if isinstance(node, ast.FunctionDef)
                      and node.name == '_a4_filter_pronom')
        class_node = ast.ClassDef(name='Window', bases=[ast.Name(id='Base',ctx=ast.Load())],
                                  keywords=[], body=[method], decorator_list=[])
        src = ast.fix_missing_locations(ast.Module(body=[class_node], type_ignores=[]))
        namespace = {'Base': object, 'historical_arkade_status': historical_arkade_status,
                     'FORMAT_SOURCE_ARKADE_RAF': FORMAT_SOURCE_ARKADE_RAF,
                     '_FORMAT_STATUS_ROLE': 99}
        exec(compile(src, str(SOURCE), 'exec'), namespace)
        cls.Window = namespace['Window']

    def test_historical_status_filters_are_actual_not_simulated_ui(self):
        view = self.Window()
        view._a2_source = FORMAT_SOURCE_ARKADE_RAF
        view._a4_ready = True
        view.format_status_combo = Select('conditional')
        view.format_search = Text('')
        items = [Item(['JOB','fmt/101','XML','1','2','Gyldig*','']),
                 Item(['JOB','fmt/16','PDF','1','3','Ikke gyldig',''])]
        view._trees = {'PRONOM': Tree(items)}
        view._a4_format_rows = [(items[0],{'raf':'Gyldig*','count':2}),
                                (items[1],{'raf':'Ikke gyldig','count':3})]
        view.format_summary = Label()
        view.format_arkade_source = Label()
        view.format_profile_source = Label()
        view._a4_filter_pronom()
        self.assertFalse(items[0].hidden)
        self.assertTrue(items[1].hidden)
        self.assertEqual(items[0].text(6), 'Gyldig med forbehold')
        self.assertEqual(items[1].text(6), 'Ikke gyldig arkivformat')
        self.assertIn('Med forbehold: 2', view.format_summary.value)
        self.assertIn('historisk', view.format_arkade_source.value)
        self.assertIn('JSON-regelprofil', view.format_profile_source.value)
        # Source observation never rewritten to a derived value.
        self.assertEqual(items[0].text(5), 'Gyldig*')

    def test_no_evidence_is_a_message_not_zero_format_claim(self):
        view = self.Window()
        view._a2_source = FORMAT_SOURCE_ARKADE_RAF
        view._a4_ready = True
        view.format_status_combo = Select('')
        view.format_search = Text('')
        view._trees = {'PRONOM': Tree([Item(['Ingen lagret evidens','','','','','',''])])}
        view._a4_format_rows = []
        view.format_summary = Label()
        view.format_arkade_source = Label()
        view.format_profile_source = Label()
        view._a4_filter_pronom()
        self.assertIn('Ingen lagret Arkade/Siegfried', view.format_summary.value)


if __name__ == '__main__':
    unittest.main()
