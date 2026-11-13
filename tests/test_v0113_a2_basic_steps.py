"""Qt-free contract checks for a2 Fix 3: paths, overview and geometry."""
from __future__ import annotations

import ast
from pathlib import Path
from types import SimpleNamespace
import unittest

ROOT = Path(__file__).resolve().parents[1]
GUI = ROOT / 'gui_qt' / 'basic_main_v0113_a2.py'


class BasicStepTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        tree = ast.parse(GUI.read_text(encoding='utf-8'))
        window = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'DwmMainWindow')
        names = {'_a2_compact_path', '_a2_set_step', '_a2_refresh_overview',
                 '_a2_start_from_overview', '_a2_fit_initial_window'}
        methods = [n for n in window.body if isinstance(n, ast.FunctionDef) and n.name in names]
        fragment = ast.fix_missing_locations(ast.Module(body=[ast.ClassDef(
            name='StepWindow', bases=[], keywords=[], body=methods, decorator_list=[],
        )], type_ignores=[]))
        scope = {'Path': Path, 'describe_info_xml_status': lambda *a, **k: 'Ikke funnet', 'DIAS_LINK_LABEL_DELIVERYSPECIFICATION': True}
        exec(compile(fragment, str(GUI), 'exec'), scope)
        cls.StepWindow = scope['StepWindow']

    def test_original_basic_widgets_preserved(self):
        code = GUI.read_text(encoding='utf-8')
        self.assertIn('self._a2_step_groups = {', code)
        self.assertIn('group.setVisible(step == name)', code)
        self.assertIn("self._a2_overview_page.setVisible(step == 'overview')", code)
        self.assertIn('self._open_path(path)', code)
        self.assertIn('self._save_as()', code)
        self.assertIn("self._a2_set_step('run')", code)
        self.assertIn('self._a2_overview_start.clicked.connect(self._start_basic_control)', code)
        self.assertIn("('info.xml', 'InfoStatus')", code)
        self.assertNotIn('setattr(ResultCenterWindow', code)

    def test_step_navigation_hides_other_groups(self):
        class Widget:
            def __init__(self): self.visible = None; self.checked = None
            def setVisible(self, value): self.visible = value
            def setChecked(self, value): self.checked = value
        w = self.StepWindow()
        w._a2_step_groups = {key: Widget() for key in ('source', 'work', 'run')}
        w._a2_step_buttons = {key: Widget() for key in ('overview', 'source', 'work', 'run')}
        w._a2_overview_page = Widget()
        w._a2_refresh_overview = lambda: None
        w._a2_set_step('run')
        self.assertTrue(w._a2_step_groups['run'].visible)
        self.assertFalse(w._a2_step_groups['source'].visible)
        w._a2_set_step('overview')
        self.assertTrue(w._a2_overview_page.visible)
        self.assertFalse(w._a2_step_groups['run'].visible)

    def test_full_paths_not_abbreviated(self):
        path = r'I:\arkiv-noark5\1525\1525_004\content\sip\content'
        self.assertEqual(self.StepWindow._a2_compact_path(path), path)
        self.assertEqual(self.StepWindow._a2_compact_path(''), 'Ikke valgt')

    def test_overview_missing_and_selected_fields(self):
        class Label:
            def __init__(self, value=''): self.value = value; self.tooltip = ''
            def text(self): return self.value
            def setText(self, value): self.value = value
            def setToolTip(self, value): self.tooltip = value
        class Button:
            def __init__(self): self.enabled = None
            def setEnabled(self, value): self.enabled = value
        class API:
            running = False
            def workspace(self): return SimpleNamespace(job_list_path=None)
        w = self.StepWindow()
        w.api = API()
        w._active_id = None
        w._worker = None
        w.basic_source_path = Label()
        w.basic_work_path = Label()
        w.basic_dias_label = Label()
        w._a2_original = None
        w._a2_pending_dirty = False
        w._selected_basic_controls = lambda: ('dwm',)
        w._a2_overview_labels = {key: Label() for key in (
            'Fil', 'Uttrekk', 'LABEL', 'InfoStatus', 'Work', 'Valg', 'Status')}
        w._a2_overview_statuses = {key: Label() for key in ('joblist', 'source', 'work', 'run')}
        w._a2_overview_start = Button()
        w._a2_refresh_overview()
        self.assertEqual(w._a2_overview_labels['Fil'].text(), 'Ikke lagret')
        self.assertEqual(w._a2_overview_labels['Uttrekk'].text(), 'Ikke valgt')
        self.assertEqual(w._a2_overview_labels['InfoStatus'].text(), 'Ikke funnet')
        self.assertFalse(w._a2_overview_start.enabled)
        source = r'C:\arc\2026\test\content'
        work = r'D:\work\2026\test'
        w.basic_source_path.setText(source)
        w.basic_work_path.setText(work)
        w.basic_dias_label.setText('Arkivlabel')
        w._a2_refresh_overview()
        self.assertEqual(w._a2_overview_labels['Uttrekk'].text(), source)
        self.assertEqual(w._a2_overview_labels['Work'].text(), work)
        self.assertEqual(w._a2_overview_labels['LABEL'].text(), 'Arkivlabel')
        self.assertEqual(w._a2_overview_statuses['run'].text(), 'Klar til kjøring')
        self.assertTrue(w._a2_overview_start.enabled)

    def test_saved_window_geometry_is_respected(self):
        # Saved Qt geometry is handled by the inherited window and the a14
        # controller. Basic mode must not resize or recenter it at launch.
        code = GUI.read_text(encoding='utf-8')
        self.assertIn("self.config.value('qt/window_geometry')", code)
        self.assertIn('if self.config.value(\'qt/window_geometry\'):\n            # The Qt restore path', code)
        self.assertIn('QTimer.singleShot(0, self._a2_fit_initial_window)', code)
        self.assertNotIn('def closeEvent(', code)
        self.assertNotIn('def resizeEvent(', code)


if __name__ == '__main__':
    unittest.main()
