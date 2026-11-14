"""Headless v0.2.0-a3 regression: home/ingest/AV must preserve Advanced docks."""
from __future__ import annotations

import ast
from pathlib import Path
from types import SimpleNamespace
import unittest

HOME = Path(__file__).resolve().parents[1] / 'gui_qt' / 'production_home_v020_a2.py'


class FakeVisible:
    def __init__(self, visible=True):
        self.visible = visible
    def isVisible(self):
        return self.visible
    def hide(self):
        self.visible = False
    def setVisible(self, state):
        self.visible = bool(state)


class FakeSignal:
    def __init__(self):
        self.handler = None
    def disconnect(self):
        self.handler = None
    def connect(self, handler):
        self.handler = handler
    def click(self):
        self.handler()


class FakeStack:
    def __init__(self, window):
        self.widgets = []
        self.current = None
    def setObjectName(self, value):
        pass
    def addWidget(self, widget):
        if self.current is None:
            self.current = widget
        self.widgets.append(widget)
    def setCurrentWidget(self, widget):
        assert widget in self.widgets
        self.current = widget
    def currentWidget(self):
        return self.current


class FakeQObject:
    def __init__(self, *args):
        pass
    def eventFilter(self, obj, event):
        return False


class FakePage:
    def __init__(self, window):
        self.refresh_calls = 0
    def refresh(self):
        self.refresh_calls += 1


class FakeConfig:
    def __init__(self):
        self.items = {'qt/v020_last_page': 'control'}
    def value(self, key, default=''):
        return self.items.get(key, default)
    def setValue(self, key, value):
        self.items[key] = value


class FakeWindow:
    def __init__(self):
        self.api = SimpleNamespace(settings={'ui_work_profile': 'depot'})
        self._central = object()
        self._basic_active = False
        self.dock_jobs = FakeVisible(True)
        self.dock_workflow = FakeVisible(False)
        self._toolbar = FakeVisible(True)
        self._menu = FakeVisible(True)
        self._status = FakeVisible(True)
        self.config = FakeConfig()
        self.v020_mode_button = SimpleNamespace(clicked=FakeSignal())
        self.v020_section_label = SimpleNamespace(setText=lambda s: None)
        self.v020_sync_navigation = lambda: None
        self._work = []
        self._filters = []
    def takeCentralWidget(self):
        value = self._central
        self._central = None
        return value
    def setCentralWidget(self, widget):
        self._central = widget
    def menuBar(self):
        return self._menu
    def statusBar(self):
        return self._status
    def installEventFilter(self, handler):
        self._filters.append(handler)
    def _enter_basic(self):
        self._basic_active = True
    def _leave_basic(self):
        self._basic_active = False
    def _a2_set_step(self, step):
        self._work.append(step)


def isolated_install():
    source = ast.parse(HOME.read_text(encoding='utf-8'))
    original = next(node for node in source.body if isinstance(node, ast.FunctionDef)
                    and node.name == 'install_integrated_home')
    # Replace ONLY imports for Qt/other modules; use the real function body.
    original.body = [node for node in original.body if not isinstance(node, ast.ImportFrom)]
    ns = {
        'DOCK_NAMES': ('jobs', 'workflow'),
        'QStackedWidget': FakeStack,
        'ProductionStartPage': FakePage,
        'IngestPage': FakePage,
        'AntivirusPage': FakePage,
        'ReportingPage': FakePage,
        'PreservationPage': FakePage,
        'ProductionProgressPage': FakePage,
        'active_job_context': lambda w: (None, ''),
        'saved_section_for_window': lambda w: '',
        'PROFILE_NAMES': {'depot': 'Depot'},
        'PROFILE_KEY': 'ui_work_profile',
        'normalize_profile': lambda x: x,
        'startup_page_target': lambda settings, last: 'control',
        'QObject': FakeQObject,
        'QEvent': SimpleNamespace(Type=SimpleNamespace(Close='close')),
        'QTimer': SimpleNamespace(singleShot=lambda n, cb: None),
    }
    exec(compile(ast.fix_missing_locations(ast.Module(body=[original], type_ignores=[])),
                 str(HOME), 'exec'), ns)
    return ns['install_integrated_home']


class NavigationA3Tests(unittest.TestCase):
    def setUp(self):
        self.window = FakeWindow()
        isolated_install()(self.window)

    def test_advanced_layout_survives_home_ingest_home_return(self):
        w = self.window
        w.v020_integrated_home()
        self.assertFalse(w.dock_jobs.isVisible())
        self.assertFalse(w._toolbar.isVisible())
        w.v020_show_ingest_page()
        w.v020_integrated_home()
        w.v020_show_control_page()
        self.assertTrue(w.dock_jobs.isVisible())
        self.assertFalse(w.dock_workflow.isVisible())
        self.assertTrue(w._toolbar.isVisible())
        self.assertTrue(w.menuBar().isVisible())
        self.assertTrue(w.statusBar().isVisible())

    def test_antivirus_home_then_work_uses_existing_basic_step(self):
        w = self.window
        w.v020_show_antivirus_page()
        self.assertEqual(w.config.value('qt/v020_last_page'), 'home')
        w.v020_go_to_work()
        self.assertTrue(w._basic_active)
        self.assertEqual(w._work, ['work'])
        self.assertEqual(w.config.value('qt/v020_last_page'), 'control')

    def test_advanced_layout_survives_reporting_preservation_and_home(self):
        w = self.window
        w.v020_show_reporting_page()
        self.assertFalse(w.dock_jobs.isVisible())
        self.assertEqual(w.config.value('qt/v020_last_page'), 'home')
        w.v020_show_preservation_page()
        w.v020_integrated_home()
        w.v020_show_control_page()
        self.assertTrue(w.dock_jobs.isVisible())
        self.assertFalse(w.dock_workflow.isVisible())
        self.assertTrue(w._toolbar.isVisible())
        self.assertTrue(w.menuBar().isVisible())
        self.assertTrue(w.statusBar().isVisible())

    def test_report_and_preservation_refresh_when_opened(self):
        w = self.window
        w.v020_show_reporting_page()
        report = w._central.currentWidget()
        self.assertEqual(report.refresh_calls, 1)
        w.v020_show_preservation_page()
        candidate = w._central.currentWidget()
        self.assertEqual(candidate.refresh_calls, 1)
        w.v020_show_reporting_page()
        self.assertEqual(report.refresh_calls, 2)

    def test_a5_progress_is_read_only_and_restores_advanced_docks(self):
        w = self.window
        previous = dict(w.config.items)
        w.v020_show_progress_page()
        status_page = w._central.currentWidget()
        self.assertEqual(status_page.refresh_calls, 1)
        self.assertFalse(w.dock_jobs.isVisible())
        w.v020_integrated_home()
        w.v020_show_control_page()
        self.assertTrue(w.dock_jobs.isVisible())
        self.assertFalse(w.dock_workflow.isVisible())
        self.assertNotIn('qt/v020_last_area', w.config.items)
        self.assertEqual(previous['qt/v020_last_page'], 'control')

    def test_a5_navigation_only_resumes_allowed_areas(self):
        w = self.window
        w.v020_open_area('report')
        self.assertEqual(w._central.currentWidget().refresh_calls, 1)
        w.v020_open_area('preserve')
        self.assertEqual(w._central.currentWidget().refresh_calls, 1)
        old = w._central.currentWidget()
        w.v020_open_area('crm')
        self.assertIs(w._central.currentWidget(), old)
        w.v020_resume_area()  # no job identity, so no stored resume
        self.assertIs(w._central.currentWidget(), old)

    def test_mode_button_switches_back_to_control_from_ingest(self):
        w = self.window
        w.v020_show_ingest_page()
        w.v020_mode_button.clicked.click()
        self.assertTrue(w._basic_active)
        self.assertEqual(w.config.value('qt/v020_last_page'), 'control')

    def test_close_restores_advanced_layout_without_overwriting_last_page(self):
        w = self.window
        w.v020_show_ingest_page()
        self.assertEqual(w.config.value('qt/v020_last_page'), 'home')
        w._v020_close_guard.eventFilter(w, SimpleNamespace(type=lambda: 'close'))
        self.assertTrue(w.dock_jobs.isVisible())
        self.assertEqual(w.config.value('qt/v020_last_page'), 'home')


if __name__ == '__main__':
    unittest.main()
