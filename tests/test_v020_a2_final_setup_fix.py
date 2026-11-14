"""v0.2.0-a2: Setup startup shortcut and screen-bounded tab sizing.

Qt-free tests validate the real source contract without requiring PySide6 in CI.
"""
from __future__ import annotations

import ast
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SHELL = ROOT / 'gui_qt' / 'start_shell_v020_a1.py'
HOME = ROOT / 'gui_qt' / 'production_home_v020_a2.py'


def isolate(name):
    tree = ast.parse(SHELL.read_text(encoding='utf-8'))
    node = next(x for x in tree.body if isinstance(x, ast.FunctionDef) and x.name == name)
    scope = {}
    exec(compile(ast.fix_missing_locations(ast.Module(body=[node], type_ignores=[])), str(SHELL), 'exec'), scope)
    return scope[name]


class FinalSetupFixA2Tests(unittest.TestCase):
    def test_startup_shortcut_selects_tab_and_restores_normal_setup(self):
        class Window:
            def __init__(self):
                self.seen = []

            def _open_setup(self):
                self.seen.append(getattr(self, '_v020_setup_target', None))
                return 'opened'

        window = Window()
        self.assertEqual(isolate('open_startup_setup')(window), 'opened')
        self.assertEqual(window.seen, ['startup'])
        self.assertFalse(hasattr(window, '_v020_setup_target'))
        window._open_setup()
        self.assertEqual(window.seen[-1], None)

    def test_shortcut_restores_previous_marker_on_exception(self):
        class Window:
            _v020_setup_target = 'another'

            def _open_setup(self):
                self.seen = self._v020_setup_target
                raise ValueError('failed')

        window = Window()
        with self.assertRaises(ValueError):
            isolate('open_startup_setup')(window)
        self.assertEqual(window.seen, 'startup')
        self.assertEqual(window._v020_setup_target, 'another')

    def test_height_grows_to_content_without_exceeding_screen(self):
        target = isolate('preferred_setup_height')
        self.assertEqual(target(640, 650, 200, 1080), 878)
        self.assertEqual(target(640, 1200, 200, 1080), 1040)
        self.assertEqual(target(640, 1200, 200, 768), 728)

    def test_height_never_shrinks_user_expanded_dialog_unless_screen_requires(self):
        target = isolate('preferred_setup_height')
        self.assertEqual(target(920, 300, 150, 1080), 920)
        self.assertEqual(target(920, 300, 150, 720), 680)

    def test_both_home_shortcuts_use_the_startup_helper(self):
        shell = SHELL.read_text(encoding='utf-8')
        home = HOME.read_text(encoding='utf-8')
        self.assertIn('open_startup_setup(self.window)', shell)
        self.assertIn('open_startup_setup(self.window)', home)
        self.assertIn('self.tabs.setCurrentWidget(self.startup_page)', shell)
        self.assertIn("if getattr(parent, '_v020_setup_target', None) == 'startup'", shell)
        self.assertIn('def open_setup():\n        window._open_setup()', shell)

    def test_startup_options_are_placed_before_large_profile_grid(self):
        source = SHELL.read_text(encoding='utf-8')
        self.assertLess(source.index('layout.addWidget(mode_group)'),
                        source.index('layout.addWidget(page_group)'))
        self.assertLess(source.index('layout.addWidget(page_group)'),
                        source.index('layout.addWidget(profile_group)'))
        self.assertIn("('control', 'Alltid Kontroll')", source)

    def test_resize_observes_tab_changes_and_screen_space(self):
        source = SHELL.read_text(encoding='utf-8')
        for fragment in (
            'self.tabs.currentChanged.connect(self._v020_fit_active_setup_tab)',
            'QTimer.singleShot(0, self._v020_fit_active_setup_tab)',
            'page.findChild(QScrollArea)',
            'screen.availableGeometry()',
            'self.resize(self.width(), target_height)',
            'self.isMaximized() or self.isFullScreen()',
            'self.move(left, top)',
        ):
            with self.subTest(fragment=fragment):
                self.assertIn(fragment, source)
        self.assertNotIn('setFixedHeight(', source)


if __name__ == '__main__':
    unittest.main()
