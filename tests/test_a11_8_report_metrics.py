import importlib.util
from pathlib import Path
import unittest
ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('a118', ROOT/'tools/noark5_batch_overview_a6.py')
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

class ReportMetricsTests(unittest.TestCase):
    def test_selected_total_separate_from_native(self):
        item={'job':'JOB-002','extraction':'C:/x/uttak','metrics':{'folder_count':None},
              'native_metrics':{'folder_count':None},'go_assessment':{'status':'STOPP'},
              'quantity_comparison':[{'metric':'folder_count','arkade_count':66834,'dwm_count':None}]}
        mod.apply_explicit_quantity_choices([item],{'choices':[{'job':'JOB-002','extraction':'uttak',
             'metric':'folder_count','source':'Arkade 5','count':66834}]})
        result=mod.build_report_metrics(item)['folder_count']
        self.assertEqual(result['value'],66834)
        self.assertEqual(result['dwm_original'],None)
        self.assertEqual(result['source'],'Arkade 5 (eksplisitt rapportvalg)')
        self.assertEqual(result['scope'],'Hele uttrekket')
        self.assertTrue(result['explicit_selection'])
        self.assertEqual(item['go_assessment']['status'],'STOPP')
    def test_unselected_uses_native_without_invention(self):
        item={'metrics':{'folder_count':7},'native_metrics':{'folder_count':7},
              'quantity_comparison':[{'metric':'folder_count','selected_source':'DWM'}]}
        result=mod.build_report_metrics(item)['folder_count']
        self.assertEqual(result['value'],7)
        self.assertEqual(result['source'],'DWM')
        self.assertFalse(result['explicit_selection'])
if __name__=='__main__': unittest.main()
