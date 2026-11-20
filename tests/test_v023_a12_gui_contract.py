"""A12 GUI integration contract without a native Qt display server.

Imports the new dialog against disposable fake modules: it must NOT monkeypatch
or reload already-imported production GUI modules in the real test suite.
"""
from __future__ import annotations

import ast
import importlib.util
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import patch


class FakeControl:
    def __init__(self, pairs=None):
        self.pairs = list(pairs or [])
        self.current = 0
        self.enabled = True
        self.text_value = ''
        self.signals_blocked = False
        self.calls = []
    def currentData(self):
        return self.pairs[self.current][1] if self.pairs else ''
    def blockSignals(self, active):
        self.signals_blocked = active
    def findData(self, data):
        return next((i for i, (_,value) in enumerate(self.pairs) if data==value), -1)
    def setCurrentIndex(self,index):
        self.current = index
    def count(self):
        return len(self.pairs)
    def clear(self):
        self.pairs.clear(); self.current = 0
    def addItem(self,title,value):
        self.pairs.append((title,value))
    def text(self):
        return self.text_value
    def setText(self,value):
        self.text_value = value
    def setPlainText(self,value):
        self.text_value = value
    def setEnabled(self,active):
        self.enabled = bool(active)
    def toPlainText(self):
        return self.text_value
    def isChecked(self):
        return self.enabled
    def setFocus(self):
        pass


class DummyGuided:
    def _guided_select(self,key):
        self.dummy_base_selected = key
    def _guided_rule_text(self,*_):
        self.dummy_base_rule = True
    def _guided_refill(self,desired):
        self.dummy_base_refill = desired
    def _guided_scope_changed(self,*_):
        self.dummy_base_scope = True
    def _guided_advance(self,n):
        self.dummy_base_advance = n
    def _guided_stop_workers(self):
        self.dummy_base_stopped = True
    def _guided_add_source_note(self):
        self.dummy_base_note = True


class GuiContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = Path(__file__).resolve().parents[1] / 'gui_qt' / 'ks_paged_v023_a12.py'
        cls.path = path
        cls.tree = ast.parse(path.read_text(encoding='utf-8'))
        fake_qt = ModuleType('PySide6')
        core = ModuleType('PySide6.QtCore')
        core.Qt = SimpleNamespace(ItemDataRole=SimpleNamespace(UserRole=32))
        core.QThread = type('QThread',(object,),{})
        core.Signal = lambda *_: object()
        widgets = ModuleType('PySide6.QtWidgets')
        class FakeItem:
            def __init__(self, cells):
                self.cells=cells; self.data=None
            def setData(self,*args):
                self.data=args[-1]
        for name in ('QComboBox','QHBoxLayout','QLabel','QLineEdit','QMessageBox',
                     'QPushButton','QSpinBox','QVBoxLayout'):
            setattr(widgets,name,type(name,(object,),{}))
        widgets.QTreeWidgetItem = FakeItem
        guided=ModuleType('gui_qt.ks_guided_v023_a4')
        guided.KsWorkshopDialog=DummyGuided
        cls.fake_items={'PySide6':fake_qt,'PySide6.QtCore':core,
                        'PySide6.QtWidgets':widgets,'gui_qt.ks_guided_v023_a4':guided}
        with patch.dict(sys.modules,cls.fake_items):
            spec=importlib.util.spec_from_file_location('_a12_gui_contract_',str(path))
            m=importlib.util.module_from_spec(spec)
            spec.loader.exec_module(m)
        cls.gui=m

    def test_main_window_opens_a12_dialog_without_affecting_job_registration(self):
        entry = (Path(__file__).resolve().parents[1]/'gui_qt/main_v023_a4.py').read_text()
        self.assertIn('from gui_qt.ks_paged_v023_a12 import KsWorkshopDialog',entry)
        self.assertIn('saved_job_decision(',entry)
        self.assertIn('same_storage_path(',entry)
        self.assertIn('self._active_id',entry)

    def test_a12_keeps_a4_guided_dialog_and_existing_review_register(self):
        self.assertIs(self.gui.KsWorkshopDialog.__bases__[0],DummyGuided)
        src=self.path.read_text(encoding='utf-8')
        self.assertIn('save_review_for_page(',src)
        self.assertIn('load_review_events(',src)
        self.assertNotIn('DELETE FROM',src)
        self.assertNotIn('UPDATE findings',src)

    def _widget(self):
        gui=object.__new__(self.gui.KsWorkshopDialog)
        gui._a12_info={'finding_count':603,'arkade_source_sha256':'a'*64}
        gui._a12_last_filters=('errors','','','', '')
        gui.guided_scope=FakeControl([('errors','errors'),('all','all')])
        gui.a12_source=FakeControl([('Alle',''),('DWM','DWM')])
        gui.a12_level=FakeControl([('Alle',''),('REVIEW','REVIEW')])
        gui.a12_review=FakeControl([('Alle',''),('Vurdert','reviewed')])
        gui.a12_search=FakeControl()
        return gui

    def test_filter_edits_can_be_reverted_without_losing_unsaved_review(self):
        gui=self._widget()
        gui.a12_source.setCurrentIndex(1)
        gui.a12_search.setText('forslag')
        gui._guided_can_leave=lambda:False
        gui._a12_refill=lambda *_args,**_kwargs:self.fail('No refill on unsaved edits')
        gui._a12_filter_changed()
        self.assertEqual(gui.a12_source.currentData(),'')
        self.assertEqual(gui.a12_search.text(),'')
        self.assertEqual(gui._a12_page_no if hasattr(gui,'_a12_page_no') else 0,0)

    def test_page_navigation_respects_dirty_guard(self):
        gui=self._widget()
        gui._a12_page_data={'pages':3}
        gui._a12_page_no=1
        gui._guided_reader=None
        gui._guided_can_leave=lambda:False
        gui._a12_refill=lambda *a,**k:self.fail('Should not switch')
        gui._a12_go_page(1)
        self.assertEqual(gui._a12_page_no,1)
        gui._guided_can_leave=lambda:True
        visited=[]
        gui._a12_refill=lambda *a,**k:visited.append(gui._a12_page_no)
        gui._a12_go_page(1)
        self.assertEqual(visited,[2])
        self.assertEqual(gui._a12_page_no,2)
        gui._a12_go_page(1)
        self.assertEqual(visited,[2])

    def test_documented_large_arkade_anchors_use_source_not_index_sha(self):
        gui=self._widget()
        class FakeTree:
            def __init__(self):self.items=[]
            def clear(self):self.items.clear()
            def addTopLevelItem(self,item):self.items.append(item)
            def setCurrentItem(self,item):self.selected=item
            def topLevelItem(self,index):return self.items[index]
        gui.guided_occurrences=FakeTree()
        gui.guided_open_xml=FakeControl()
        gui.guided_insert_source=FakeControl()
        gui.guided_source=FakeControl()
        gui._guided_occurrence_selected=lambda *args:None
        gui._a12_anchors({'source':'Arkade 5','lines':[17,18],
                          'file':'arkivstruktur.xml','test_id':'A5-001',
                          'source_ref':'external_evidence/arkade5/x/normalized/arkade5_results.json'})
        self.assertEqual(len(gui._guided_occurrences['rows']),2)
        self.assertEqual(gui._guided_occurrences['source_sha256'],'a'*64)
        self.assertIn('2 dokumenterte XML-linjer',gui.guided_source.text())

    def test_dwm_rule_text_uses_observed_version_and_keeps_review_distinct(self):
        gui=self._widget()
        gui.guided_rule=FakeControl()
        gui._guided_current={'source':'DWM periodekonsistens',
            'test_id':'DWM-PERIODE-M107-M108','metadata_id':'M107/M108',
            'noark_version':'3.1','xpath':'/arkiv/arkivdel[1]',
            'lines':[123], 'object_id':'S-1', 'archive_part_id':'AD-1',
            'standard_value':None,'delivery_value':None}
        gui._guided_rule_text()
        self.assertIn('v3.1',gui.guided_rule.text())
        self.assertIn('REVIEW, ikke normativ',gui.guided_rule.text())


if __name__=='__main__':
    unittest.main()
