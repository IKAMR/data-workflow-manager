"""A13 GUI: preserves A12 page/save APIs and uses the COMPLETE reporter.

Qt modules are stubbed without reloading or altering imported production code.
The real PySide6 window remains a Windows integration test.
"""
from __future__ import annotations

import ast
import importlib.util
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
FILE = ROOT / 'gui_qt/ks_paged_v023_a12.py'


class _Base:
    def _new_observation(self, context):
        return ('base_observation', context)
    def _save_recommendation(self):
        return 'base_recommendation'
    def _guided_stop_workers(self):
        pass


class GuiA13Contract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        s=FILE.read_text(encoding='utf-8')
        cls.source=s
        cls.tree=ast.parse(s)
        cls.warnings=[]
        fake_qt=ModuleType('PySide6')
        core=ModuleType('PySide6.QtCore')
        core.Qt=SimpleNamespace(ItemDataRole=SimpleNamespace(UserRole=32))
        core.QThread=type('QThread',(object,),{})
        core.Signal=lambda *_: object()
        widgets=ModuleType('PySide6.QtWidgets')
        for name in ('QComboBox','QHBoxLayout','QLabel','QLineEdit','QPushButton','QSpinBox',
                     'QTreeWidgetItem','QVBoxLayout'):
            setattr(widgets,name,type(name,(object,),{}))
        widget_warning=lambda *args:cls.warnings.append(args) or None
        widgets.QMessageBox=SimpleNamespace(warning=widget_warning)
        base=ModuleType('gui_qt.ks_guided_v023_a4')
        base.KsWorkshopDialog=_Base
        modules={'PySide6':fake_qt,'PySide6.QtCore':core,
                 'PySide6.QtWidgets':widgets,'gui_qt.ks_guided_v023_a4':base}
        with patch.dict(sys.modules,modules):
            spec=importlib.util.spec_from_file_location('_a13_gui_contract_', FILE)
            module=importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
        cls.gui=module

    def _window(self, busy=False):
        window=object.__new__(self.gui.KsWorkshopDialog)
        window._a13_export_busy=busy
        window._a12_save_review=lambda *args,**kwargs:('a12_save_review',args,kwargs)
        return window

    def test_existing_a12_paginated_review_unchanged(self):
        s=self.source
        self.assertIn('def _a12_save_review(',s)
        self.assertIn('save_review_for_page(',s)
        self.assertIn('load_review_events(',s)
        self.assertIn('build_paged_index(',s)
        self.assertIn('def _guided_save_review(',s)
        self.assertIn('self._a12_save_review(_checked, move_next=move_next)',s)

    def test_legacy_partial_export_is_not_used(self):
        self.assertIn('export_complete_reports(',self.source)
        self.assertIn('preview_complete_summary(',self.source)
        self.assertNotIn('return super()._export()',self.source)
        self.assertNotIn('return super()._preview()',self.source)
        self.assertIn('v023_a13_cancel_export',self.source)
        self.assertIn('_a13_export_worker.complete.connect(',self.source)
        self.assertIn('_a13_export_worker.failed.connect(',self.source)
        self.assertIn('isInterruptionRequested',self.source)

    def test_review_save_is_original_a12_api_and_blocked_while_exporting(self):
        self.warnings.clear()
        window=self._window(busy=True)
        self.assertIsNone(window._guided_save_review(move_next=True))
        self.assertTrue(self.warnings)
        window._a13_export_busy=False
        self.assertEqual(window._guided_save_review(move_next=True)[0],'a12_save_review')
        self.assertTrue(window._guided_save_review(move_next=True)[2]['move_next'])

    def test_no_observations_or_recommendation_edits_during_export(self):
        self.warnings.clear()
        window=self._window(busy=True)
        self.assertIsNone(window._new_observation('Arkivdel A'))
        self.assertIsNone(window._save_recommendation())
        self.assertEqual(len(self.warnings),2)
        window._a13_export_busy=False
        self.assertEqual(window._new_observation('Arkivdel A'),('base_observation','Arkivdel A'))
        self.assertEqual(window._save_recommendation(),'base_recommendation')

    def test_full_export_is_cancelled_when_dialog_closes(self):
        self.assertIn('def _a13_cancel_export(',self.source)
        self.assertIn('worker.requestInterruption()',self.source)
        self.assertIn('export_worker.wait()',self.source)
        self.assertIn('self._a13_cancel_export()',self.source)
        self.assertIn('self._a12_stop_index()',self.source)

    def test_main_entrypoint_still_routes_to_existing_a12_dialog(self):
        # No changes to multi-job Source/Work selection or entrypoint needed.
        main=ROOT/'gui_qt/main_v023_a4.py'
        if main.is_file():
            text=main.read_text('utf-8')
            self.assertIn('from gui_qt.ks_paged_v023_a12 import KsWorkshopDialog',text)
            self.assertIn('saved_job_decision(',text)



if __name__ == '__main__': unittest.main()
