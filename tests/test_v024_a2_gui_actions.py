"""v0.2.4-a2: GUI action binding and inheritance, with no native Qt needed."""
from __future__ import annotations

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import patch
import ast
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'gui_qt/main_v024_a2.py'
ENTRY = ROOT / 'gui_qt/__main__.py'


class FakeBase:
    def __init__(self, api):
        self.api = api
        self._active_id = 'JOB-001'
        self._basic_job_id = 'JOB-001'
        self._basic_active = False
        self._worker = None
        self._job_controls_running = False
        self._basic_starting = False
        self.logs = []
        self.workers = []
        self.restored = []

    def _continue_job(self):
        self.logs.append('legacy_checkpoint')

    def _start_worker(self, jobs):
        self.workers.append(jobs)

    def _append_log(self, message):
        self.logs.append(message)

    def _refresh(self, *args, **kwargs):
        self.restored.append('refresh')

    def _sync_basic_status(self):
        pass

    def _a8_restore_run_context(self, *, force=False):
        self.restored.append('run')

    def _a8_refresh_job_log(self, *, force=False):
        self.restored.append('log')

    def _set_running_ui(self, state):
        pass


class FakeApi:
    def __init__(self, status='Feil', cursor=4):
        self.running = False
        self.status = status
        self.cursor = cursor
        self.calls = []
        self._v024_a2_reset_index_warning = ''

    def job_details(self, job_id):
        self.calls.append(('details', job_id))
        return SimpleNamespace(job=SimpleNamespace(job_id=job_id,
                      status=self.status, current_operation=self.cursor,
                      operation_count=17, progress=self.cursor/17),
                operations=tuple(SimpleNamespace(checkpoint=i==4) for i in range(1,18)),
                message='Workflow stoppet med feil')

    def reset_job_execution(self, job_id):
        self.calls.append(('reset', job_id))
        self.status = 'Klar'
        self.cursor = 0


class FakeMessageBox:
    StandardButton = SimpleNamespace(Yes=1, No=2)
    answers = []
    notices = []

    @classmethod
    def question(cls, *_args):
        return cls.answers.pop(0) if cls.answers else cls.StandardButton.Yes

    @classmethod
    def information(cls, *_args):
        cls.notices.append('information')


class FakeControl:
    def __init__(self):
        self.enabled = None
        self.tooltip = ''
    def setEnabled(self, enabled):
        self.enabled = enabled
    def setToolTip(self, text):
        self.tooltip = text
    def toolTip(self):
        return self.tooltip


def load_gui_window():
    stub = ModuleType('gui_qt.main_v024_a1')
    stub.DwmMainWindow = FakeBase
    with patch.dict(sys.modules, {'gui_qt.main_v024_a1': stub}):
        spec = spec_from_file_location('dwm_gui_a2_testonly', SOURCE)
        module = module_from_spec(spec)
        spec.loader.exec_module(module)
    return module.DwmMainWindow


class GuiActionTests(unittest.TestCase):
    def setUp(self):
        self.gui = load_gui_window()(FakeApi())
        qtwidgets = ModuleType('PySide6.QtWidgets')
        qtwidgets.QMessageBox = FakeMessageBox
        self.qtpatch = patch.dict(sys.modules, {'PySide6': ModuleType('PySide6'),
                                                'PySide6.QtWidgets': qtwidgets})
        self.qtpatch.start()
        self.addCleanup(self.qtpatch.stop)
        FakeMessageBox.answers = []
        FakeMessageBox.notices = []

    def install_controls(self):
        for field in ('continue_action', 'overview_continue', 'basic_continue_button',
                      'reset_action', 'overview_reset', 'basic_reset_button',
                      'run_action', 'overview_run', 'basic_run_button'):
            setattr(self.gui, field, FakeControl())
        self.gui._v024_a2_actions_ready = True

    def test_failed_job_continue_targets_exact_failed_operation(self):
        self.gui._continue_job()
        self.assertEqual(self.gui.workers, [[('JOB-001', False, True)]])
        self.assertTrue(any('5/17' in line for line in self.gui.logs))

    def test_continue_cancel_keeps_state_and_does_not_start(self):
        FakeMessageBox.answers = [FakeMessageBox.StandardButton.No]
        self.gui._continue_job()
        self.assertEqual(self.gui.workers, [])

    def test_reset_updates_only_selected_job_and_refreshes_views(self):
        self.gui._v024_a2_reset_job()
        self.assertIn(('reset', 'JOB-001'), self.gui.api.calls)
        self.assertIn('refresh', self.gui.restored)
        self.assertIn('log', self.gui.restored)
        self.assertIn('run', self.gui.restored)

    def test_reset_cancel_makes_no_api_change(self):
        FakeMessageBox.answers = [FakeMessageBox.StandardButton.No]
        self.gui._v024_a2_reset_job()
        self.assertNotIn(('reset', 'JOB-001'), self.gui.api.calls)

    def test_advanced_and_basic_control_states_match(self):
        self.install_controls()
        self.gui._v024_a2_update_actions()
        for field in ('continue_action', 'overview_continue', 'basic_continue_button',
                      'reset_action', 'overview_reset', 'basic_reset_button'):
            self.assertTrue(getattr(self.gui, field).enabled, field)
        self.assertFalse(self.gui.run_action.enabled)
        self.assertFalse(self.gui.overview_run.enabled)

    def test_busy_disables_continue_and_reset_everywhere(self):
        self.install_controls()
        self.gui.api.running = True
        self.gui._v024_a2_update_actions()
        for field in ('continue_action','overview_continue','basic_continue_button',
                      'reset_action','overview_reset','basic_reset_button'):
            self.assertFalse(getattr(self.gui, field).enabled, field)

    def test_draft_basic_does_not_affect_previous_selected_job(self):
        self.gui._basic_active = True
        self.gui._v022_draft = True
        self.assertEqual(self.gui._v024_a2_selected(), (None, None))
        self.gui._v024_a2_reset_job()
        self.assertNotIn(('reset','JOB-001'), self.gui.api.calls)

    def test_checkpoint_remains_existing_worker_path(self):
        self.gui.api.status = 'Venter ved kontrollpunkt'
        self.gui._continue_job()
        self.assertEqual(self.gui.logs, ['legacy_checkpoint'])
        self.assertEqual(self.gui.workers, [])

    def test_entrypoint_keeps_old_imports_and_selects_a2(self):
        src = ENTRY.read_text(encoding='utf-8')
        self.assertIn('from gui_qt.main_v023_a4 import DwmMainWindow', src)
        self.assertIn('from gui_qt.main_v024_a2 import DwmMainWindow as _A2Window', src)
        self.assertIn('from app.workbench_api_v024_a2 import DwmWorkbenchAPI as _A2WorkbenchAPI', src)
        self.assertLess(src.index('from gui_qt.main_v024_a1 import'),
                        src.index('from gui_qt.main_v024_a2 import'))

    def test_gui_code_keeps_qt_imports_inside_actions(self):
        tree = ast.parse(SOURCE.read_text(encoding='utf-8'))
        for node in tree.body:
            if isinstance(node, ast.ImportFrom):
                self.assertFalse((node.module or '').startswith('PySide6'))
        self.assertIn('class DwmMainWindow(_A1Window):', SOURCE.read_text('utf-8'))


if __name__ == '__main__':
    unittest.main()
