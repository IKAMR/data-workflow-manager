"""Headless regression for old detached-viewer tests and current Qt styling."""
from __future__ import annotations

import ast
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
MAIN = ROOT / "gui_qt" / "main_window.py"
TREE = ast.parse(MAIN.read_text(encoding="utf-8"))
WINDOW = next(n for n in TREE.body if isinstance(n, ast.ClassDef)
              and n.name == "DwmMainWindow")


class StoppedAfterStyle(Exception):
    pass


class FakeSignal:
    def connect(self, _callback):
        raise StoppedAfterStyle


class Viewer:
    last = None

    def __init__(self):
        Viewer.last = self
        self.redockRequested = FakeSignal()
        self.theme = None

    def setStyleSheet(self, value):
        self.theme = value


class FakeMain:
    _detached_run_window = None
    _detached_log_window = None

    def _a8_refresh_job_log(self, **_kwargs):
        pass

    def _a9_redock_run(self):
        pass

    def _a9_redock_job_log(self):
        pass


class ThemedMain(FakeMain):
    def styleSheet(self):
        return 'THEME_FROM_MAIN'


def load_method(method_name: str):
    method = next(node for node in WINDOW.body
                  if isinstance(node, ast.FunctionDef) and node.name == method_name)
    ns = {
        'STYLE': 'LEGACY_DARK_THEME',
        'DetachedJobLogWindow': Viewer,
        'DetachedRunWindow': Viewer,
    }
    exec(compile(ast.fix_missing_locations(ast.Module(body=[method], type_ignores=[])),
                 str(MAIN), 'exec'), ns)
    return ns[method_name]


class DetachedStyleCompatTests(unittest.TestCase):
    def test_log_window_uses_main_theme(self):
        method = load_method('_a8_float_job_log')
        with self.assertRaises(StoppedAfterStyle):
            method(ThemedMain())
        self.assertEqual(Viewer.last.theme, 'THEME_FROM_MAIN')

    def test_run_window_uses_main_theme(self):
        method = load_method('_a9_float_run')
        with self.assertRaises(StoppedAfterStyle):
            method(ThemedMain())
        self.assertEqual(Viewer.last.theme, 'THEME_FROM_MAIN')

    def test_old_log_test_stub_keeps_working(self):
        method = load_method('_a8_float_job_log')
        with self.assertRaises(StoppedAfterStyle):
            method(FakeMain())
        self.assertEqual(Viewer.last.theme, 'LEGACY_DARK_THEME')

    def test_old_run_test_stub_keeps_working(self):
        method = load_method('_a9_float_run')
        with self.assertRaises(StoppedAfterStyle):
            method(FakeMain())
        self.assertEqual(Viewer.last.theme, 'LEGACY_DARK_THEME')


if __name__ == '__main__':
    unittest.main()
