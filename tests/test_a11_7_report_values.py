import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('overview_a117', ROOT/'tools/noark5_batch_overview_a6.py')
mod=importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)

class TestA117(unittest.TestCase):
    def test_explicit_value_preserves_native_and_go(self):
        item={'job':'JOB-002','extraction':'C:/a/test','metrics':{'folder_count':None},
              'go_assessment':{'status':'STOPP'},
              'quantity_comparison':[{'metric':'folder_count','dwm_count':None,'arkade_count':66834,'arkade_candidates':[{'count':66834}]}]}
        mod.apply_explicit_quantity_choices([item],{'choices':[{'job':'JOB-002','extraction':'test','metric':'folder_count','source':'Arkade 5','count':66834}]})
        self.assertEqual(mod.report_quantity_value(item,'folder_count'),(66834,'Arkade 5 (eksplisitt rapportvalg)'))
        self.assertIsNone(item['metrics']['folder_count'])
        self.assertEqual(item['go_assessment']['status'],'STOPP')
    def test_default_and_unscoped_not_applied(self):
        item={'metrics':{'folder_count':17},'quantity_comparison':[{'metric':'folder_count','selected_source':'DWM'}]}
        self.assertEqual(mod.report_quantity_value(item,'folder_count'),(17,'DWM'))
        item['quantity_comparison'][0].update(report_selection_only=True, report_selected_scope='Bare arkivdel',report_selected_count=99)
        self.assertEqual(mod.report_quantity_value(item,'folder_count'),(17,'DWM'))
    def test_quick_selection_controls_exist(self):
        gui=(ROOT/'gui/noark5_multi_overview_a65.py').read_text(encoding='utf-8')
        for txt in ('Velg der DWM mangler','Velg alle','Fjern alle','def choose_by'):
            self.assertIn(txt,gui)

if __name__=='__main__':unittest.main()
