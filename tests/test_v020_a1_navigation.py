"""v0.2.0-a1 GUI navigation regressions; runs without installing PySide6."""
from __future__ import annotations

import ast
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest import TestCase
from unittest.mock import patch
import sys

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'gui_qt' / 'start_shell_v020_a1.py'


def _pure_rules():
    parsed = ast.parse(SOURCE.read_text(encoding='utf-8'))
    wanted = {'PROFILE_KEY', 'STARTUP_KEY', 'FEATURES_KEY', 'PROFILES', 'STARTUP_MODES', 'PROFILE_NAMES'}
    functions = {'normalize_profile', 'normalize_startup', 'startup_target', 'navigation_labels'}
    selected = [n for n in parsed.body if (
        isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id in wanted for t in n.targets)
    ) or (isinstance(n, ast.FunctionDef) and n.name in functions)]
    environment = {}
    exec(compile(ast.fix_missing_locations(ast.Module(body=selected, type_ignores=[])), str(SOURCE), 'exec'), environment)
    return environment


class _Signal:
    def __init__(self):
        self.handlers = []

    def connect(self, fn):
        self.handlers.append(fn)

    def disconnect(self):
        self.handlers.clear()

    def emit(self, *args):
        for handler in list(self.handlers):
            handler(*args)


class _Widget:
    def __init__(self, *args):
        self.parent = args[-1] if args else None
        self.text_value = str(args[0]) if args and isinstance(args[0], str) else ''
        self.clicked = _Signal()
        self.triggered = _Signal()
        self.items = []
        self.shown = False

    def __getattr__(self, name):
        if name.startswith('set'):
            return lambda *_: None
        raise AttributeError(name)

    def setText(self, text):
        self.text_value = text

    def setParent(self, parent):
        self.parent = parent

    def show(self):
        self.shown = True

    def addWidget(self, widget):
        self.items.append(widget)

    def addStretch(self, *_):
        pass


class _Layout(_Widget):
    def indexOf(self, widget):
        try:
            return self.items.index(widget)
        except ValueError:
            return -1

    def removeWidget(self, widget):
        self.items.remove(widget)

    def itemAt(self, _index):
        return SimpleNamespace(layout=lambda: self.items[0])


class _Content:
    def __init__(self, layout):
        self._layout = layout

    def layout(self):
        return self._layout


class _Button(_Widget):
    def parentWidget(self):
        return self.parent


class _Window:
    def __init__(self, settings=None, mode='basic'):
        self._basic_active = mode == 'basic'
        self.api = SimpleNamespace(settings=settings or {})
        self.config = SimpleNamespace(value=lambda key, default: mode)
        self.pages = SimpleNamespace(currentChanged=_Signal())
        self._toolbar = _Widget('inherited-advanced-toolbar')
        original_horizontal = _Layout()
        original_content_layout = _Layout()
        original_content_layout.items = [original_horizontal]
        original_content = _Content(original_content_layout)
        self.basic_advanced_button = _Button('Avansert modus', original_content)
        self.basic_advanced_button.clicked.connect(self._leave_basic)
        original_horizontal.items.append(self.basic_advanced_button)
        self.original_horizontal = original_horizontal
        self.fixed_toolbar = None
        self.toolbar_break_before = None

    def addAction(self, action):
        self.action = action

    def insertToolBar(self, before, toolbar):
        assert before is self._toolbar
        self.fixed_toolbar = toolbar

    def insertToolBarBreak(self, before):
        self.toolbar_break_before = before

    def _enter_basic(self):
        self._basic_active = True
        self.pages.currentChanged.emit(0)

    def _leave_basic(self):
        self._basic_active = False
        self.pages.currentChanged.emit(1)


class NavigationA1FixTests(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rules = _pure_rules()

    def _install(self, window):
        parsed = ast.parse(SOURCE.read_text(encoding='utf-8'))
        fn = next(n for n in parsed.body if isinstance(n, ast.FunctionDef) and n.name == 'install_start_navigation')
        env = dict(self.rules)
        env['Qt'] = SimpleNamespace(
            ToolBarArea=SimpleNamespace(TopToolBarArea=1),
            ContextMenuPolicy=SimpleNamespace(PreventContextMenu=2),
        )
        exec(compile(ast.fix_missing_locations(ast.Module(body=[fn], type_ignores=[])), str(SOURCE), 'exec'), env)

        qt = ModuleType('PySide6')
        core = ModuleType('PySide6.QtCore')
        core.QTimer = SimpleNamespace(singleShot=lambda _ms, callback: callback())
        gui = ModuleType('PySide6.QtGui')
        gui.QAction = _Widget
        widgets = ModuleType('PySide6.QtWidgets')
        for name, typ in {
            'QHBoxLayout': _Layout, 'QLabel': _Widget, 'QPushButton': _Button,
            'QSizePolicy': _Widget, 'QToolBar': _Widget, 'QWidget': _Widget,
        }.items():
            setattr(widgets, name, typ)
        widgets.QSizePolicy.Policy = SimpleNamespace(Expanding=1, Preferred=2)
        with patch.dict(sys.modules, {
            'PySide6': qt,
            'PySide6.QtCore': core,
            'PySide6.QtGui': gui,
            'PySide6.QtWidgets': widgets,
        }):
            env['install_start_navigation'](window)

    def test_controls_display_the_saved_profile_and_current_mode(self):
        label = self.rules['navigation_labels']
        self.assertEqual(label({}, True), ('Arbeidsprofil: Kontroll', 'Kontroll · Enkel modus', 'Avansert modus'))
        self.assertEqual(label({'ui_work_profile': 'depot'}, False),
                         ('Arbeidsprofil: Depot – produksjonslinje', 'Kontroll · Avansert modus', 'Enkel modus'))
        self.assertEqual(label({'ui_work_profile': 'unknown'}, True)[0], 'Arbeidsprofil: Kontroll')

    def test_startside_is_in_fixed_toolbar_not_scrolling_basic_layout(self):
        win = _Window()
        self._install(win)
        self.assertIsNotNone(win.fixed_toolbar)
        self.assertIs(win.toolbar_break_before, win._toolbar)
        self.assertTrue(win.fixed_toolbar.shown)
        self.assertNotIn(win.basic_advanced_button, win.original_horizontal.items)
        self.assertIs(win.v020_mode_button, win.basic_advanced_button)
        self.assertIsNotNone(win.v020_home_button)
        self.assertIsNotNone(win.v020_nav_toolbar)

    def test_existing_mode_button_switches_both_ways(self):
        win = _Window()
        self._install(win)
        self.assertTrue(win._basic_active)
        self.assertEqual(win.basic_advanced_button.text_value, 'Avansert modus')
        win.basic_advanced_button.clicked.emit()
        self.assertFalse(win._basic_active)
        self.assertEqual(win.basic_advanced_button.text_value, 'Enkel modus')
        win.basic_advanced_button.clicked.emit()
        self.assertTrue(win._basic_active)
        self.assertEqual(win.basic_advanced_button.text_value, 'Avansert modus')

    def test_setup_profile_change_updates_fixed_header(self):
        win = _Window()
        self._install(win)
        win.api.settings['ui_work_profile'] = 'custom'
        win.v020_sync_navigation()
        self.assertEqual(win.v020_profile_label.text_value, 'Arbeidsprofil: Egendefinert')
        self.assertEqual(win.v020_section_label.text_value, 'Kontroll · Enkel modus')

    def test_fixed_advanced_startup_has_basic_switch(self):
        win = _Window({'ui_startup_mode': 'advanced'}, 'basic')
        self._install(win)
        self.assertFalse(win._basic_active)
        self.assertEqual(win.v020_mode_button.text_value, 'Enkel modus')

    def test_setup_acceptance_refreshes_navigation(self):
        source = SOURCE.read_text(encoding='utf-8')
        self.assertIn('self.accepted.connect(self._refresh_navigation)', source)
        self.assertIn('self.window.v020_sync_navigation()', source)
        self.assertNotIn("window._toolbar.addAction(action)", source)


if __name__ == '__main__':
    import unittest
    unittest.main()
