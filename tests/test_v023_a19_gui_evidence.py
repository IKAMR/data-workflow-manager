"""A19 PySide6-free GUI contracts: Source inspection stays on Guided KS page."""
from __future__ import annotations

import ast
import importlib.util
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import patch


class _Label:
    def __init__(self):
        self.value = ''
        self.enabled = False
    def setText(self, text):
        self.value = text
    def setPlainText(self, text):
        self.value = text
    def setEnabled(self, value):
        self.enabled = value
    def toPlainText(self):
        return self.value
    def setFocus(self):
        pass


class _Item:
    def __init__(self, texts):
        self.texts = texts
        self.ordinal = None
    def setData(self, _column, _role, value):
        self.ordinal = value
    def text(self, column):
        return self.texts[column]
    def setText(self, column, text):
        self.texts[column] = text


class _Tree:
    def __init__(self):
        self.items = []
        self.chosen = None
    def clear(self):
        self.items.clear()
        self.chosen = None
    def addTopLevelItem(self, item):
        self.items.append(item)
    def setCurrentItem(self, item):
        self.chosen = item
    def currentItem(self):
        return self.chosen
    def topLevelItem(self, index):
        return self.items[index]


class _Base:
    def _guided_select(self, key):
        self.selected_by_base = key
    def _guided_rule_text(self, *_):
        self.rule_updated = True


class A19GuiContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = Path(__file__).resolve().parents[1]
        cls.source = (cls.root / 'gui_qt' / 'ks_paged_v023_a12.py').read_text(encoding='utf-8')
        fake_qt = ModuleType('PySide6')
        core = ModuleType('PySide6.QtCore')
        core.Qt = SimpleNamespace(ItemDataRole=SimpleNamespace(UserRole=32))
        core.QThread = type('QThread',(object,),{})
        core.Signal = lambda *_: object()
        widgets = ModuleType('PySide6.QtWidgets')
        for name in ('QComboBox','QHBoxLayout','QLabel','QLineEdit','QMessageBox',
                     'QPushButton','QSpinBox','QVBoxLayout'):
            setattr(widgets,name,type(name,(object,),{}))
        widgets.QTreeWidgetItem = _Item
        guided = ModuleType('gui_qt.ks_guided_v023_a4')
        guided.KsWorkshopDialog = _Base
        mocks = {'PySide6': fake_qt, 'PySide6.QtCore': core,
                 'PySide6.QtWidgets': widgets, 'gui_qt.ks_guided_v023_a4': guided}
        with patch.dict(sys.modules,mocks):
            spec=importlib.util.spec_from_file_location('_a19_gui_test_',str(cls.root / 'gui_qt' / 'ks_paged_v023_a12.py'))
            cls.gui=importlib.util.module_from_spec(spec)
            spec.loader.exec_module(cls.gui)

    def _view(self):
        gui = object.__new__(self.gui.KsWorkshopDialog)
        gui.guided_occurrences = _Tree()
        gui.guided_open_xml = _Label()
        gui.guided_insert_source = _Label()
        gui.guided_source = _Label()
        gui.guided_xml_view = _Label()
        gui._guided_anchor = None
        gui._a12_info = {'arkade_source_sha256': 'b' * 64}
        return gui

    def test_actual_main_gui_uses_paged_review_dialog(self):
        entry=(self.root / 'gui_qt' / 'main_v023_a4.py').read_text(encoding='utf-8')
        self.assertIn('from gui_qt.ks_paged_v023_a12 import KsWorkshopDialog',entry)
        self.assertIn('inspect_xml_anchor',self.source)
        self.assertIn('_A19XmlReader',self.source)
        self.assertNotIn('shell=True',self.source)

    def test_non_arkade_issue_with_observed_lines_has_actual_xml_anchor(self):
        gui = self._view()
        gui._a12_anchors({'source': 'DWM periodekonsistens', 'test_id': 'DWM-PER-1',
                         'file': 'arkivstruktur.xml', 'lines': [77, 78],
                         'source_ref': 'noark5_evidence/delivery.jsonl',
                         'archive_part_id': 'AD-9', 'source_xml_sha256': 'a' * 64})
        self.assertTrue(gui.guided_open_xml.enabled)
        self.assertEqual(len(gui.guided_occurrences.items), 2)
        self.assertEqual(gui._guided_occurrences['rows'][0]['line'], 77)
        self.assertEqual(gui._guided_occurrences['rows'][0]['archive_part_id'], 'AD-9')
        self.assertEqual(gui._guided_occurrences['rows'][0]['source_xml_sha256'], 'a' * 64)
        self.assertEqual(gui._guided_occurrences['source_sha256_role'], 'source_xml')
        self.assertIn('Dokumentert XML-SHA-256', gui.guided_source.value)

    def test_arkade_report_hash_is_not_mislabelled_xml_hash(self):
        gui = self._view()
        gui._a12_anchors({'source': 'Arkade 5', 'test_id': 'N5.22',
                         'file': 'arkivstruktur.xml', 'lines': [77],
                         'source_ref': 'external_evidence/arkade5/x/normalized/arkade5_results.json'})
        self.assertEqual(gui._guided_occurrences['source_sha256_role'], 'arkade_report')
        self.assertEqual(gui._guided_occurrences['rows'][0]['source_xml_sha256'], '')
        self.assertIn('(ikke XML-hash)', gui.guided_source.value)

    def test_no_line_no_automatic_xml_anchor(self):
        gui = self._view()
        gui._a12_anchors({'source': 'DWM depot', 'test_id':'D1',
                          'file': 'arkivstruktur.xml', 'lines': [], 'source_ref':'qa/e.json'})
        self.assertFalse(gui.guided_open_xml.enabled)
        self.assertIsNone(gui._guided_occurrences)
        self.assertEqual(gui.guided_occurrences.items, [])

    def test_successful_xml_context_render_includes_source_status_and_hierarchy(self):
        gui=self._view()
        gui._guided_anchor={'line': 77}
        gui.guided_occurrences.addTopLevelItem(_Item(['1', '', 'arkivstruktur.xml', '77', 'Ikke undersøkt']))
        gui.guided_occurrences.setCurrentItem(gui.guided_occurrences.topLevelItem(0))
        gui._guided_xml_ready({
            'available': True, 'source_path': 'D:/archive/arkivstruktur.xml',
            'line': 77, 'source_identity': 'not_attested',
            'reported_xpath': '/arkiv[9]', 'provenance_note':'Ikke attestert',
            'metadata': {'xpath':'/arkiv[1]/arkivdel[2]/mappe[3]', 'hierarchy': [
                {'element': 'arkiv', 'position':1, 'system_id':'A', 'title':''},
                {'element': 'arkivdel', 'position':2, 'system_id':'AD-2', 'title':'Andre'},
                {'element': 'mappe', 'position':3, 'system_id':'M-3', 'title':''},
            ], 'note':'Faktisk observert hierarki'},
            'excerpt':'> 77: <saksstatus>Avsluttet</saksstatus>'})
        self.assertIn('Kildeidentitet: Ikke attestert',gui.guided_xml_view.value)
        self.assertIn('arkivdel[2] · systemID: AD-2', gui.guided_xml_view.value)
        self.assertIn('Faktisk XPath fra XML: /arkiv[1]/arkivdel[2]/mappe[3]',gui.guided_xml_view.value)
        self.assertIn('Rapportert XPath fra funn: /arkiv[9]',gui.guided_xml_view.value)
        self.assertEqual(gui.guided_occurrences.chosen.text(4), 'M-3')

    def test_generic_dwm_source_note_never_mislabels_it_as_arkade(self):
        gui=self._view()
        gui._guided_current={'source': 'DWM XPath', 'test_id': 'kdrs.c01',
                             'source_ref': 'noark5_tests/xpath/run/result.json'}
        gui._guided_anchor={'file':'arkivstruktur.xml','line':17,
                            'reported_xpath':'/arkiv[1]/arkivdel[1]'}
        gui._guided_occurrences={'rows':[gui._guided_anchor], 'source_sha256':''}
        gui._guided_xml={'available':True, 'source_identity':'not_attested',
                         'metadata':{'xpath':'/arkiv[1]/arkivdel[2]'}}
        gui.guided_comment=_Label()
        gui._guided_add_source_note()
        self.assertIn('Funnkilde: DWM XPath', gui.guided_comment.value)
        self.assertIn('ikke attestert', gui.guided_comment.value)
        self.assertIn('Faktisk XPath i nåværende XML: /arkiv[1]/arkivdel[2]',gui.guided_comment.value)
        self.assertNotIn('Arkade-kontroll', gui.guided_comment.value)

    def test_lifecycle_keeps_review_actions_and_export_path_intact(self):
        self.assertIn('save_review_for_page(',self.source)
        self.assertIn('export_complete_reports(',self.source)
        self.assertIn('_guided_can_leave()',self.source)
        self.assertIn('self._guided_xml_finished',self.source)
        self.assertIs(self.gui.KsWorkshopDialog.__bases__[0],_Base)


if __name__ == '__main__':
    unittest.main()
