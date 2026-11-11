"""a5.5 regression: never replace/detach the original Qt detail widgets.

These headless stand-ins explicitly fail if replaceWidget() is called. The
previous a5.4 mock always returned a live replacement and missed the real bug.
Windows PySide6 GUI testing is still required before committing.
"""
from __future__ import annotations

import ast
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'gui_qt' / 'result_detail_view_v0110_a5.py'


class Signal:
    def connect(self, _function):
        pass


class Widget:
    def __init__(self):
        self.deleted = False
        self.hidden = False

    def show(self):
        self.hidden = False

    def hide(self):
        self.hidden = True

    def clear(self):
        self._check()

    def _check(self):
        if self.deleted:
            raise RuntimeError('libshiboken: Internal C++ object already deleted')


class Raw(Widget):
    def __init__(self):
        super().__init__()
        self.text = ''

    def setPlainText(self, text):
        self._check()
        self.text = text

    def toPlainText(self):
        self._check()
        return self.text


class Browser(Widget):
    def setOpenLinks(self, _value): pass
    def setOpenExternalLinks(self, _value): pass
    def setReadOnly(self, _value): pass
    def setPlaceholderText(self, _value): pass


class Combo(Widget):
    def __init__(self):
        super().__init__()
        self.currentIndexChanged = Signal()
        self.currentChanged = Signal()
        self.index = 0

    def addItems(self, _values): pass
    def addTab(self, _title): pass
    def setExpanding(self, _value): pass
    def setToolTip(self, _value): pass
    def setCurrentIndex(self, index): self.index = index
    def currentIndex(self): return self.index
    def blockSignals(self, _value): pass


class Label(Widget):
    def __init__(self, _text): super().__init__()

class Button(Widget):
    def __init__(self, _text):
        super().__init__()
        self.clicked = Signal()
    def setToolTip(self, _value): pass


class Layout:
    def __init__(self):
        self.entries = []

    def addWidget(self, item): self.entries.append(item)
    def addStretch(self, _value): pass
    def indexOf(self, item):
        try: return self.entries.index(item)
        except ValueError: return -1
    def insertLayout(self, position, item): self.entries.insert(position, item)


class Splitter:
    def __init__(self, raw):
        self.widgets = [object(), raw]
        self.splitterMoved = Signal()
        self.lengths = [560, 140]
        self.insertions = 0
        self.orientation = 'vertical'

    def setOrientation(self, direction):
        self.orientation = direction

    def replaceWidget(self, *_args):
        raise RuntimeError('unsafe replaceWidget() must not be used')

    def insertWidget(self, index, widget):
        self.widgets.insert(index, widget)
        self.lengths.insert(index, 0)
        self.insertions += 1

    def setChildrenCollapsible(self, _value): pass
    def sizes(self): return self.lengths[:]
    def setSizes(self, values):
        if len(values) != len(self.widgets):
            raise AssertionError('Qt splitter size vector must cover all widgets')
        self.lengths = list(values)


class Tree:
    def __init__(self, splitter, count=1):
        self.splitter = splitter
        self.rows = [type('Row', (), {
            'isHidden': lambda self: False,
            'text': lambda self, _index: 'Real test',
        })() for _ in range(count)]
    def parentWidget(self): return self.splitter
    def topLevelItemCount(self): return len(self.rows)
    def topLevelItem(self, index): return self.rows[index]


class Settings:
    def __init__(self, mode):
        self.values = {'qt/result_detail_mode': mode}
    def value(self, name, default=None): return self.values.get(name, default)
    def setValue(self, name, value): self.values[name] = value
    def remove(self, name): self.values.pop(name, None)


class Tabs:
    def __init__(self):
        self.currentChanged = Signal()
        self.active = 'Arkade 5'
    def currentIndex(self): return 0
    def tabText(self, _index): return self.active


class Page:
    def __init__(self, splitter):
        self._layout = Layout()
        self._layout.addWidget(splitter)
    def layout(self): return self._layout


def extract(name):
    tree = ast.parse(SOURCE.read_text(encoding='utf-8'))
    cls = next(node for node in tree.body
               if isinstance(node, ast.ClassDef) and node.name == 'ResultDetailModesMixin')
    method = next(node for node in cls.body
                  if isinstance(node, ast.FunctionDef) and node.name == name)
    ns = {
        'QSplitter': Splitter, 'QPlainTextEdit': Raw, 'QHBoxLayout': Layout,
        'QLabel': Label, 'QComboBox': Combo, 'QTabBar': Combo,
        'QPushButton': Button, '_NoExternalResourceBrowser': Browser,
        'Qt': type('Qt', (), {'Orientation': type('O', (), {'Horizontal': 'horizontal'})}),
        '_SIDE_DETAIL_TABS': frozenset({'Arkade 5', 'PRONOM', 'Periodevurdering'}),
        '_SIDE_FRACTIONS': {'Arkade 5': 0.61, 'PRONOM': 0.65, 'Periodevurdering': 0.58},
        'default_table_fraction': lambda _count, tab: 0.22 if tab == 'Oversikt' else 0.55,
    }
    exec(compile(ast.fix_missing_locations(ast.Module(body=[method], type_ignores=[])),
                 str(SOURCE), 'exec'), ns)
    return ns[name]


class Window:
    _a53_install_details = extract('_a53_install_details')
    _a53_select_detail_mode = extract('_a53_select_detail_mode')
    _a53_apply_splitter = extract('_a53_apply_splitter')
    _a53_store_splitter = extract('_a53_store_splitter')
    _a53_fraction_key = extract('_a53_fraction_key')
    _a53_auto_size = extract('_a53_auto_size')

    def __init__(self, mode=0):
        self._a4_settings = Settings(mode)
        self.tabs = Tabs()
        self._trees = {}
        self._details = {}
        self._pages = {}
        for tab in ('Oversikt', 'Arkivdeler', 'Tekniske kontroller', 'Arkade 5', 'PRONOM', 'Periodevurdering'):
            raw = Raw()
            raw.setPlainText('Saved ' + tab)
            splitter = Splitter(raw)
            self._trees[tab] = Tree(splitter)
            self._details[tab] = raw
            self._pages[tab] = Page(splitter)
        self.originals = dict(self._details)
        self.scheduled = 0

    def _a53_schedule_splitter(self, _index=None):
        self.scheduled += 1



class LifetimeRegressionTests(unittest.TestCase):
    def test_raw_editor_identity_is_preserved_for_all_tabs(self):
        window = Window()
        window._a53_install_details()
        for tab, old_raw in window.originals.items():
            self.assertIs(window._details[tab], old_raw)
            self.assertFalse(old_raw.deleted)
            self.assertTrue(old_raw.hidden)
            self.assertEqual(old_raw.toPlainText(), 'Saved ' + tab)
            old_raw.clear()  # The real a5.3/a5.4 error occurred here.
            self.assertEqual(window._a53_splitters[tab].insertions, 1)
            self.assertEqual(window._a53_splitters[tab].widgets[2], old_raw)
            self.assertEqual(window._a53_splitters[tab].widgets[1], window._a53_browsers[tab])
            self.assertEqual(window._a53_splitters[tab].orientation,
                             'horizontal' if tab in {'Arkade 5', 'PRONOM', 'Periodevurdering'} else 'vertical')

    def test_switching_modes_hides_only_sibling_widget(self):
        window = Window(mode=1)
        window._a53_install_details()
        self.assertTrue(all(browser.hidden for browser in window._a53_browsers.values()))
        self.assertTrue(all(not raw.hidden for raw in window._details.values()))
        window._a53_select_detail_mode('PRONOM', 0)
        self.assertTrue(all(raw.hidden for raw in window._details.values()))
        self.assertTrue(all(not browser.hidden for browser in window._a53_browsers.values()))
        self.assertEqual(window._a4_settings.value('qt/result_detail_mode'), 0)
        window._a53_select_detail_mode('PRONOM', 1)
        self.assertTrue(all(not raw.hidden for raw in window._details.values()))
        window._details['Arkade 5'].setPlainText('Still alive')
        self.assertEqual(window._details['Arkade 5'].toPlainText(), 'Still alive')

    def test_splitter_sizing_includes_hidden_third_widget(self):
        window = Window(mode=0)
        window._a53_install_details()
        window._a53_apply_splitter()
        self.assertEqual(len(window._a53_splitters['Arkade 5'].sizes()), 3)
        self.assertEqual(window._a53_splitters['Arkade 5'].sizes()[2], 0)
        window._a53_select_detail_mode('Arkade 5', 1)
        window._a53_apply_splitter()
        self.assertEqual(window._a53_splitters['Arkade 5'].sizes()[1], 0)
        self.assertGreater(window._a53_splitters['Arkade 5'].sizes()[2], 0)

    def test_horizontal_split_settings_are_separate_from_vertical(self):
        window = Window()
        window._a53_install_details()
        self.assertEqual(window._a53_fraction_key('PRONOM'),
                         'qt/result_splitter_fraction_horizontal/PRONOM')
        self.assertEqual(window._a53_fraction_key('Oversikt'),
                         'qt/result_splitter_fraction/Oversikt')
        window._a4_settings.setValue('qt/result_splitter_fraction/Oversikt', 0.7)
        window._a53_auto_size('Oversikt')
        self.assertIsNone(window._a4_settings.value('qt/result_splitter_fraction/Oversikt'))

    def test_never_uses_qsplitter_replace_widget_or_reparents_raw(self):
        code = SOURCE.read_text(encoding='utf-8')
        syntax = ast.parse(code)
        cls = next(x for x in syntax.body if isinstance(x, ast.ClassDef)
                   and x.name == 'ResultDetailModesMixin')
        methods = [x for x in cls.body if isinstance(x, ast.FunctionDef)]
        attributes = [n.func.attr for method in methods for n in ast.walk(method)
                      if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)]
        self.assertNotIn('replaceWidget', attributes)
        self.assertIn('insertWidget', attributes)
        self.assertNotIn('setParent', attributes)
        self.assertNotIn('deleteLater', attributes)


if __name__ == '__main__':
    unittest.main()
