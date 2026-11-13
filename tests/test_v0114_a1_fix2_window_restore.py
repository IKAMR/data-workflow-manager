"""Regression contracts for existing completed jobs and independent result viewers."""
from __future__ import annotations

import ast
from pathlib import Path
from types import SimpleNamespace
import unittest

ROOT = Path(__file__).resolve().parents[1]
GUI = ROOT / 'gui_qt' / 'basic_main_v0113_a2.py'
POSITION = ROOT / 'gui_qt' / 'window_positions_v0114_a1.py'


def method(name):
    tree = ast.parse(GUI.read_text(encoding='utf-8'))
    cls = next(node for node in tree.body if isinstance(node, ast.ClassDef)
               and node.name == 'DwmMainWindow')
    node = next(node for node in cls.body if isinstance(node, ast.FunctionDef)
                and node.name == name)
    wrapper = ast.fix_missing_locations(ast.Module(body=[node], type_ignores=[]))
    namespace = {}
    exec(compile(wrapper, str(GUI), 'exec'), namespace)
    return namespace[name]


class CompletedJobStartupTests(unittest.TestCase):
    def test_completed_job_opens_run(self):
        for status in ('Ferdig', 'Fullført', 'completed'):
            with self.subTest(status=status):
                shown = []
                w = SimpleNamespace(_basic_active=True, _active_id='JOB-001',
                                    api=SimpleNamespace(job_details=lambda _id:
                                        SimpleNamespace(job=SimpleNamespace(status=status))),
                                    _a2_set_step=shown.append)
                method('_a14_open_completed_job_in_run')(w)
                self.assertEqual(shown, ['run'])

    def test_new_and_unfinished_job_remain_on_overview(self):
        for status in ('Klar', 'Kjører', 'Venter ved kontrollpunkt'):
            shown = []
            w = SimpleNamespace(_basic_active=True, _active_id='JOB-001',
                                api=SimpleNamespace(job_details=lambda _id:
                                    SimpleNamespace(job=SimpleNamespace(status=status))),
                                _a2_set_step=shown.append)
            method('_a14_open_completed_job_in_run')(w)
            self.assertFalse(shown)
        shown = []
        w = SimpleNamespace(_basic_active=True, _active_id=None, _a2_set_step=shown.append)
        method('_a14_open_completed_job_in_run')(w)
        self.assertFalse(shown)

    def test_result_viewers_store_geometry_and_maximized_state(self):
        content = POSITION.read_text(encoding='utf-8')
        self.assertIn("qt/a14_result_geometry", content)
        self.assertIn("qt/a14_result_maximized", content)
        self.assertIn('viewer.showMaximized()', content)
        self.assertIn('viewer.restoreGeometry(saved)', content)
        self.assertIn('QEvent.Type.Close', content)

    def test_main_initial_sizing_does_not_override_saved_geometry(self):
        code = ast.get_source_segment(GUI.read_text(encoding='utf-8'),
            next(node for node in ast.walk(ast.parse(GUI.read_text(encoding='utf-8')))
                 if isinstance(node, ast.FunctionDef) and node.name == '_a2_fit_initial_window'))
        self.assertIn("if self.config.value('qt/window_geometry'):", code)
        self.assertIn('return', code)


if __name__ == '__main__':
    unittest.main()
