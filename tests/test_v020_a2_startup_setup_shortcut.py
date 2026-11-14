"""v0.2.0-a2: the 'Oppstart og profil' shortcut opens the correct Setup tab.

Qt is not required to run these tests. The real shortcut function is exercised;
the GUI's tab selection and button wiring are additionally checked as code.
"""
from __future__ import annotations

import ast
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SHELL = ROOT / 'gui_qt' / 'start_shell_v020_a1.py'
HOME = ROOT / 'gui_qt' / 'production_home_v020_a2.py'


def shortcut():
    source = ast.parse(SHELL.read_text(encoding='utf-8'))
    function = next(node for node in source.body
                    if isinstance(node, ast.FunctionDef) and node.name == 'open_startup_setup')
    namespace = {}
    exec(compile(ast.fix_missing_locations(ast.Module(body=[function], type_ignores=[])),
                 str(SHELL), 'exec'), namespace)
    return namespace['open_startup_setup']


class StartupSetupShortcutA2Tests(unittest.TestCase):
    def test_shortcut_marks_correct_tab_only_while_opening(self):
        class Window:
            def __init__(self):
                self.calls = []

            def _open_setup(self):
                self.calls.append(getattr(self, '_v020_setup_target', None))
                return 'opened'

        window = Window()
        self.assertEqual(shortcut()(window), 'opened')
        self.assertEqual(window.calls, ['startup'])
        self.assertFalse(hasattr(window, '_v020_setup_target'))
        self.assertEqual(window._open_setup(), 'opened')
        self.assertEqual(window.calls[-1], None)  # ordinary Setup unaffected

    def test_shortcut_restores_marker_after_error_or_existing_target(self):
        class Window:
            _v020_setup_target = 'some-other-tab'

            def _open_setup(self):
                self.seen = self._v020_setup_target
                raise RuntimeError('Setup unavailable')

        window = Window()
        with self.assertRaisesRegex(RuntimeError, 'Setup unavailable'):
            shortcut()(window)
        self.assertEqual(window.seen, 'startup')
        self.assertEqual(window._v020_setup_target, 'some-other-tab')

    def test_setup_tab_is_selected_after_insertion(self):
        source = SHELL.read_text(encoding='utf-8')
        insertion = "self.tabs.insertTab(0, self.startup_page, 'Oppstart og profil')"
        selection = 'self.tabs.setCurrentWidget(self.startup_page)'
        self.assertIn(insertion, source)
        self.assertIn("getattr(parent, '_v020_setup_target', None) == 'startup'", source)
        self.assertEqual(source.count(selection), 1)
        self.assertLess(source.index(insertion), source.index(selection))

    def test_both_home_shortcuts_use_helper_not_generic_setup(self):
        shell_source = SHELL.read_text(encoding='utf-8')
        home_source = HOME.read_text(encoding='utf-8')
        self.assertIn("setup.clicked.connect(self._open_setup)", shell_source)
        self.assertIn("setup.clicked.connect(self._open_setup)", home_source)
        self.assertIn('open_startup_setup(self.window)', shell_source)
        self.assertIn('open_startup_setup(self.window)', home_source)
        self.assertIn('def open_setup():\n        window._open_setup()', shell_source)
        self.assertNotIn('def _open_setup(self):\n        self.window._open_setup()',
                         shell_source + home_source)


if __name__ == '__main__':
    unittest.main()
