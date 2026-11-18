"""a11 Advanced-mode autofit regressions (no Qt installation needed)."""
from __future__ import annotations

import ast
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
import sys
import types
import unittest
from unittest.mock import patch

from app.advanced_layout_v022_a11 import (
    plan_advanced_layout, restored_splitter_sizes, severe_panel_clipping,
)

ROOT = Path(__file__).resolve().parents[1]


class PlanningTests(unittest.TestCase):
    def test_wide_monitor_protects_center_and_all_name_columns(self):
        plan = plan_advanced_layout(1280, 1200, job_name_px=296,
                                    operation_name_px=263, history_name_px=250,
                                    job_count=3, history_count=17)
        self.assertGreaterEqual(plan.job_name_width, 320)
        self.assertGreaterEqual(plan.workflow_name_width, 288)
        self.assertGreaterEqual(plan.history_name_width, 275)
        self.assertGreaterEqual(plan.left_width, 500)
        self.assertLessEqual(plan.left_width, 580)
        self.assertGreaterEqual(plan.activity_width, 400)
        self.assertGreaterEqual(plan.activity_height, 680)
        self.assertGreaterEqual(plan.history_upper_height, 320)

    def test_small_window_never_expands_to_fit_a_long_name(self):
        for size in ((720, 480), (800, 700), (1040, 820)):
            with self.subTest(size=size):
                width, height = size
                plan = plan_advanced_layout(width, height,
                            job_name_px=3000, operation_name_px=2000,
                            history_name_px=4000, job_count=10, history_count=17)
                self.assertLessEqual(plan.left_width + 300, width)
                self.assertLessEqual(plan.activity_height, height)
                self.assertLessEqual(plan.history_upper_height, plan.activity_height)
                self.assertLessEqual(plan.job_name_width, 510)
                self.assertLessEqual(plan.history_name_width, 460)

    def test_system_panel_omission_uses_full_right_area(self):
        a = plan_advanced_layout(1450, 1100, job_name_px=240,
                                 system_visible=True)
        b = plan_advanced_layout(1450, 1100, job_name_px=240,
                                 system_visible=False)
        self.assertEqual(b.system_width, 0)
        self.assertGreater(b.activity_width, a.activity_width)

    def test_manual_layout_only_requires_repair_when_unusable(self):
        self.assertFalse(severe_panel_clipping(
            left_width=380, activity_height=500, activity_width=520,
            system_width=200, system_visible=True))
        self.assertTrue(severe_panel_clipping(
            left_width=210, activity_height=500, activity_width=520))
        self.assertTrue(severe_panel_clipping(
            left_width=390, activity_height=80, activity_width=520))
        self.assertTrue(severe_panel_clipping(
            left_width=390, activity_height=500, activity_width=520,
            system_width=75, system_visible=True))

    def test_splitter_persistence_restores_ratio_not_old_pixels(self):
        self.assertEqual(restored_splitter_sizes('[300, 300]', 700), (350, 350))
        self.assertEqual(restored_splitter_sizes('[100, 900]', 700), (140, 560))
        self.assertIsNone(restored_splitter_sizes('bad', 700))
        self.assertIsNone(restored_splitter_sizes('[100, 0]', 700))
        self.assertIsNone(restored_splitter_sizes('[100, 200]', 200))


class IntegrationContracts(unittest.TestCase):
    def test_main_version_and_distribution_are_a11(self):
        from version import VERSION
        import tomllib
        with (ROOT / 'pyproject.toml').open('rb') as stream:
            version = tomllib.load(stream)['project']['version']
        self.assertEqual(VERSION, '0.2.2-a12')
        self.assertEqual(version, '0.2.2a12')

    def test_entrypoint_extends_a10_without_new_runner(self):
        entry = (ROOT / 'gui_qt/__main__.py').read_text('utf-8')
        ui = (ROOT / 'gui_qt/main_v022_a11.py').read_text('utf-8')
        ast.parse(entry)
        ast.parse(ui)
        self.assertIn('from gui_qt.main_v022_a11 import DwmMainWindow', entry)
        self.assertIn('from gui_qt.main_v022_a10 import DwmMainWindow', entry)
        self.assertIn('from gui_qt.basic_multijob_v022_a1_2 import DwmMainWindow', entry)
        self.assertIn('from gui_qt.main_v022_a10 import DwmMainWindow as _A10Window', ui)
        self.assertNotIn('JobRunner(', ui)
        self.assertNotIn('api.set_workflow(', ui)
        self.assertNotIn('api.save_job_list(', ui)
        self.assertNotIn('installEventFilter(', ui)
        self.assertNotIn('setGeometry(', ui)

    def test_advanced_adjustment_is_deferred_once_after_show(self):
        ui = (ROOT / 'gui_qt/main_v022_a11.py').read_text('utf-8')
        self.assertIn('QTimer.singleShot(160, self._a11_initial_fit)', ui)
        self.assertIn("if getattr(self, '_basic_active', False):", ui)
        self.assertIn("self._a11_last_content", ui)
        self.assertIn("qt/a11_advanced_layout_saved", ui)
        self.assertIn('def _a10_autofit(self):', ui)
        self.assertIn('splitter.setSizes(', ui)
        self.assertIn('Qt.Orientation.Vertical', ui)
        self.assertIn('Qt.Orientation.Horizontal', ui)

    @staticmethod
    def load_mock_window():
        class OldWindow:
            def __init__(self, api):
                self.api = api
            def _refresh(self, *args, **kwargs):
                return 'base refresh'
        mock = types.ModuleType('gui_qt.main_v022_a10')
        mock.DwmMainWindow = OldWindow
        with patch.dict(sys.modules, {'gui_qt.main_v022_a10': mock,
                                      'PySide6.QtCore': None}):
            spec = importlib.util.spec_from_file_location(
                'a11_mocked_window', ROOT / 'gui_qt/main_v022_a11.py')
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
        return module.DwmMainWindow

    def test_fake_qt_startup_does_not_import_qtcore(self):
        cls = self.load_mock_window()
        api = SimpleNamespace(workspace=lambda: SimpleNamespace(
            job_list_path=None, jobs=()))
        instance = cls(api)
        self.assertIsInstance(instance, cls)
        self.assertFalse(hasattr(instance, '_a11_fit_queued'))

    def test_selecting_other_job_does_not_reflow_manual_panels(self):
        cls = self.load_mock_window()
        api = SimpleNamespace(workspace=lambda: SimpleNamespace(
            job_list_path='three.n5jobs',
            jobs=[SimpleNamespace(job_id='JOB-001', name='Alpha'),
                  SimpleNamespace(job_id='JOB-002', name='Beta')] ))
        instance = cls(api)
        instance._a11_last_content = instance._a11_content_key()
        scheduled = []
        instance._a11_queue_fit = lambda **kwargs: scheduled.append(kwargs)
        # A selection change does not mutate the file/name signature.
        self.assertEqual(instance._refresh(force=True), 'base refresh')
        self.assertEqual(scheduled, [])
        # Change the stable data returned by the same source object.
        persistent_jobs = [SimpleNamespace(job_id='JOB-001', name='Alpha')]
        api.workspace = lambda: SimpleNamespace(job_list_path='three.n5jobs',
                                                  jobs=persistent_jobs)
        instance._a11_last_content = instance._a11_content_key()
        persistent_jobs[0].name = 'Longer archive label'
        instance._refresh(force=True)
        self.assertEqual(scheduled, [{'allow_expand': False}])
        api.workspace = lambda: SimpleNamespace(job_list_path='other.n5jobs',
                                                  jobs=persistent_jobs)
        instance._refresh(force=True)
        self.assertEqual(scheduled[-1], {'allow_expand': True})


class FakeGuiPlanningTests(unittest.TestCase):
    """Run the actual dock-sizing method against small Qt-compatible fakes."""

    def setUp(self):
        cls = IntegrationContracts.load_mock_window()
        self.window = cls.__new__(cls)
        self.modules = {
            'PySide6': types.ModuleType('PySide6'),
            'PySide6.QtCore': types.ModuleType('PySide6.QtCore'),
            'PySide6.QtWidgets': types.ModuleType('PySide6.QtWidgets'),
        }
        class Qt:
            class Orientation:
                Horizontal = 1
                Vertical = 2
            class DockWidgetArea:
                LeftDockWidgetArea = 3
                BottomDockWidgetArea = 4
            class ScrollBarPolicy:
                ScrollBarAsNeeded = 6
        class QHeaderView:
            class ResizeMode:
                Interactive = 5
        self.modules['PySide6.QtCore'].Qt = Qt
        self.modules['PySide6.QtWidgets'].QHeaderView = QHeaderView
        self.Qt = Qt
        self.qtpatch = patch.dict(sys.modules, self.modules)
        self.qtpatch.start()
        self.addCleanup(self.qtpatch.stop)
        class Config:
            entries = {}
            def value(self, key, default='', **kwargs):
                return self.entries.get(key, default)
        self.window.config = Config()
        class Header:
            def setStretchLastSection(self, value): pass
            def setSectionResizeMode(self, column, mode): pass
        class Metrics:
            def horizontalAdvance(self, text): return len(text)*8
        class Item:
            def __init__(self, text): self.value = text
            def text(self, column): return self.value
        class Tree:
            def __init__(self, texts, width=235):
                self.items=[Item(x) for x in texts]
                self.cols={1:width}
            def fontMetrics(self): return Metrics()
            def header(self): return Header()
            def topLevelItemCount(self): return len(self.items)
            def topLevelItem(self, index): return self.items[index]
            def setColumnWidth(self, column, width): self.cols[column]=width
            def columnWidth(self, column): return self.cols[column]
            def setHorizontalScrollBarPolicy(self, policy): pass
        self.window.jobs_tree=Tree([
            '1525_004 WebSak Aaknes1-3 (2008-2022)',
            '1525_005 WebSak STFJ (2009-2015)',
            '1525_006 WebSak STHA1-4 (2004-2023)'])
        self.window.workflow_tree=Tree(['[A250] Noark 5 depotvalideringsrapport',
                                      '[A260] Forbered KS-grunnlag (utkast)'])
        self.window.run_history_tree=Tree(['Noark 5 depotvalideringsrapport',
                                         'Arkade 5 PRONOM-analyse'])
        class Dock:
            def __init__(self,width,height,area):
                self.w,self.h,self.area=width,height,area
            def isVisible(self): return True
            def isFloating(self): return False
            def width(self): return self.w
            def height(self): return self.h
        self.window.dock_jobs=Dock(340, 360, Qt.DockWidgetArea.LeftDockWidgetArea)
        self.window.dock_workflow=Dock(340, 610, Qt.DockWidgetArea.LeftDockWidgetArea)
        self.window.dock_log=Dock(375, 300, Qt.DockWidgetArea.BottomDockWidgetArea)
        self.window.dock_system=Dock(185, 300, Qt.DockWidgetArea.BottomDockWidgetArea)
        class Splitter:
            def __init__(self): self.s=[145,155]
            def height(self): return sum(self.s)
            def sizes(self): return self.s[:]
            def setSizes(self, sizes): self.s=list(sizes)
        self.window.run_history_splitter=Splitter()
        self.window._a11_saved_columns_restored=False
        self.window._a11_splitter_restored=False
        self.window._a11_saved_layout=False
        self.window._basic_active=False
        self.window.isVisible=lambda: True
        self.window.width=lambda:1280
        self.window.height=lambda:1200
        self.window.dockWidgetArea=lambda dock: dock.area
        self.resized=[]
        def resize_docks(docks,sizes,orientation):
            self.resized.append((tuple(docks),tuple(sizes),orientation))
            for d,n in zip(docks,sizes):
                if orientation == Qt.Orientation.Horizontal: d.w=n
                else: d.h=n
        self.window.resizeDocks=resize_docks

    def test_cramped_advanced_docks_are_repaired_once(self):
        self.window._a11_fit_advanced(allow_expand=True)
        self.assertGreater(self.window.dock_jobs.width(),340)
        self.assertGreater(self.window.dock_log.height(),300)
        self.assertGreater(self.window.jobs_tree.columnWidth(1),235)
        self.assertGreater(self.window.workflow_tree.columnWidth(1),235)
        self.assertGreaterEqual(len(self.resized),2)

    def test_saved_manual_docks_are_not_overridden(self):
        self.window._a11_saved_layout=True
        self.window.dock_jobs.w=self.window.dock_workflow.w=380
        self.window.dock_log.w=540
        self.window.dock_log.h=500
        self.window.dock_system.w=225
        self.window.dock_system.h=500
        self.window.config.entries={
            'qt/a11_jobs_name_column':275,
            'qt/a11_workflow_name_column':310,
            'qt/a11_history_name_column':265,
            'qt/a11_run_splitter_sizes':'[400, 300]',
        }
        self.window.run_history_splitter.s=[250,350]
        self.window._a11_fit_advanced(allow_expand=True)
        self.assertEqual(self.resized,[])
        self.assertEqual(self.window.jobs_tree.columnWidth(1),275)
        self.assertEqual(self.window.workflow_tree.columnWidth(1),310)
        self.assertTrue(self.window._a11_splitter_restored)
        self.assertEqual(sum(self.window.run_history_splitter.sizes()),600)

    def test_only_explicit_autofit_changes_good_saved_layout(self):
        self.window._a11_saved_layout=True
        self.window.dock_jobs.w=self.window.dock_workflow.w=380
        self.window.dock_log.w=540
        self.window.dock_log.h=500
        self.window.dock_system.w=225
        self.window.run_history_splitter.s=[260,340]
        self.window._a11_fit_advanced(force=True,allow_expand=True)
        self.assertTrue(self.resized)

    def test_basic_mode_does_not_rearrange_advanced_docks(self):
        self.window._basic_active=True
        self.window._a11_fit_advanced(force=True,allow_expand=True)
        self.assertFalse(self.resized)



if __name__ == '__main__':
    unittest.main()
