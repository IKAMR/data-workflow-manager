"""a2.4: PRONOM layout/readable-detail regressions without a Qt installation.

The production PySide6 window still needs a manual Windows smoke test.
"""
from __future__ import annotations

import ast
from pathlib import Path
from types import SimpleNamespace
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'gui_qt' / 'result_center_v0111_a2.py'
TREE = ast.parse(SOURCE.read_text(encoding='utf-8'))


def extract_function(name, namespace=None):
    function = next(node for node in TREE.body if isinstance(node, ast.FunctionDef)
                    and node.name == name)
    symbols = dict(namespace or {})
    exec(compile(ast.fix_missing_locations(ast.Module(body=[function], type_ignores=[])),
                 str(SOURCE), 'exec'), symbols)
    return symbols[name]


def extract_method(name, namespace=None):
    klass = next(node for node in TREE.body if isinstance(node, ast.ClassDef)
                 and node.name == 'ResultCenterWindow')
    method = next(node for node in klass.body if isinstance(node, ast.FunctionDef)
                  and node.name == name)
    symbols = dict(namespace or {})
    exec(compile(ast.fix_missing_locations(ast.Module(body=[method], type_ignores=[])),
                 str(SOURCE), 'exec'), symbols)
    return symbols[name]


present = extract_function('readable_pronom_details')


class PronomDetailsTests(unittest.TestCase):
    def setUp(self):
        self.source = {
            'format_id': 'fmt/354',
            'version': '1b',
            'formatvurdering': {'visning': 'Akseptert i valgt profil'},
            'historisk_arkade_raf': {'klassifisering': 'Gyldig'},
            'source_row': {'Format-ID': 'fmt/354', 'Antall': '15'},
        }
        self.columns = ('uttrekk', 'fmt/354', 'Acrobat PDF/A', '1b',
                        '15', 'Gyldig', 'Akseptert i valgt profil')

    def test_selected_format_and_assessment_come_first(self):
        actual = present(self.source, self.columns)
        self.assertEqual(list(actual), ['Valgt format', 'formatvurdering',
                                         'historisk_arkade_raf', 'Øvrig evidens'])
        self.assertEqual(actual['Valgt format']['Antall'], '15')
        self.assertEqual(actual['Valgt format']['Valgt vurdering'],
                         'Akseptert i valgt profil')
        self.assertEqual(actual['formatvurdering']['visning'],
                         'Akseptert i valgt profil')
        self.assertEqual(actual['Øvrig evidens']['source_row']['Format-ID'], 'fmt/354')

    def test_historical_selection_prioritizes_raf(self):
        actual = present(self.source, self.columns, arkade_selected=True)
        self.assertEqual(list(actual)[:3], ['Valgt format', 'historisk_arkade_raf',
                                            'formatvurdering'])

    def test_original_data_is_not_mutated_and_raw_remains_available(self):
        before = repr(self.source)
        actual = present(self.source, self.columns)
        self.assertEqual(repr(self.source), before)
        self.assertNotIn('Valgt format', self.source)
        self.assertIsNot(actual, self.source)
        self.assertIs(actual['Øvrig evidens']['source_row'], self.source['source_row'])

    def test_handles_incomplete_evidence(self):
        self.assertEqual(present('original', ('not enough',)), 'original')
        actual = present(None, self.columns)
        self.assertIn('Kildeevidens', actual['Øvrig evidens'])


class PaneLayoutTests(unittest.TestCase):
    class Label:
        def __init__(self): self.size_policy = None
        def setSizePolicy(self, width, height): self.size_policy = width, height

    class Splitter:
        def __init__(self): self.size_policy = None
        def setSizePolicy(self, width, height): self.size_policy = width, height

    class Item:
        def __init__(self, widget=None): self._widget = widget
        def widget(self): return self._widget

    class Layout:
        def __init__(self, splitter):
            self.items = [PaneLayoutTests.Item(None) for _ in range(8)]
            self.items.append(PaneLayoutTests.Item(splitter))
            self.spacing = None
            self.margins = None
            self.stretch = {}
        def setSpacing(self, n): self.spacing = n
        def setContentsMargins(self, *args): self.margins = args
        def count(self): return len(self.items)
        def itemAt(self, i): return self.items[i]
        def setStretch(self, i, value): self.stretch[i] = value

    def test_pronom_splitter_gets_all_extra_vertical_space(self):
        class P: 
            class Policy:
                Preferred='preferred'
                Maximum='maximum'
                Expanding='expanding'
        splitter = self.Splitter()
        layout = self.Layout(splitter)
        obj = SimpleNamespace(
            _pages={'PRONOM':SimpleNamespace(layout=lambda:layout)},
            _a53_splitters={'PRONOM':splitter},
            format_summary=self.Label(),
            format_arkade_source=self.Label(),
            format_profile_source=self.Label(),
            format_note=self.Label(),
            _a53_schedule_splitter=lambda:None,
        )
        fn = extract_method('_a24_compact_pronom', {'QSizePolicy':P})
        fn(obj)
        self.assertEqual(layout.stretch, {i:(1 if i==8 else 0) for i in range(9)})
        self.assertEqual(layout.spacing, 5)
        self.assertEqual(splitter.size_policy, ('expanding','expanding'))
        self.assertTrue(obj._a24_pronom_layout_ready)
        for label in (obj.format_summary, obj.format_arkade_source,
                      obj.format_profile_source, obj.format_note):
            self.assertEqual(label.size_policy, ('preferred','maximum'))

    def test_detail_scroll_is_reset_in_both_viewers(self):
        class Bar:
            def __init__(self):self.value=50
            def setValue(self,v):self.value=v
        class Viewer:
            def __init__(self):self.start=False;self.bar=Bar()
            def moveCursor(self,start):self.start=start
            def verticalScrollBar(self):return self.bar
        b, raw = Viewer(), Viewer()
        obj=SimpleNamespace(_a53_details_ready=True,
            _a53_browsers={'PRONOM':b},_details={'PRONOM':raw})
        fn=extract_method('_a24_reset_pronom_scroll', {'QTextCursor':
            SimpleNamespace(MoveOperation=SimpleNamespace(Start='start'))})
        fn(obj)
        self.assertEqual((b.start,raw.start),('start','start'))
        self.assertEqual((b.bar.value,raw.bar.value),(0,0))

    def test_does_not_replace_or_reparent_existing_qt_viewers(self):
        source=SOURCE.read_text(encoding='utf-8')
        self.assertNotIn('.replaceWidget(',source)
        self.assertNotIn('.setParent(',source)
        self.assertIn('super()._show_detail(tab)',source)
        self.assertIn('QTimer.singleShot(0, self._a24_reset_pronom_scroll)',source)
        self.assertIn('self._a53_schedule_splitter()',source)


if __name__ == '__main__':
    unittest.main()
