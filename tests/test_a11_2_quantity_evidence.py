import importlib.util
from pathlib import Path
import unittest

MODULE=Path(__file__).resolve().parents[1]/'tools'/'noark5_batch_overview_a6.py'
spec=importlib.util.spec_from_file_location('overview_a112',MODULE)
mod=importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

class QuantityEvidenceTests(unittest.TestCase):
    def test_no_unverified_arkade_counts(self):
        data={'metrics':{key:None for key,_ in mod.METRICS},
              'native_metrics':{key:None for key,_ in mod.METRICS},
              'external_evidence':{'approved':0},
              'arkade5_import':{'controls':[{'id':'N5.10','has_results':True}]}}
        rows=mod.quantity_evidence_comparison(data)
        folder=next(x for x in rows if x['metric']=='folder_count')
        self.assertIsNone(folder['arkade_count'])
        self.assertIn('ikke verifisert',folder['arkade_status'])
        self.assertEqual(folder['effective_source'],'DWM')

    def test_kdrs_changes_distinguished(self):
        native={key:None for key,_ in mod.METRICS}
        effective=native.copy(); effective['folder_count']=2188
        data={'metrics':effective,'native_metrics':native,'external_evidence':{'approved':1},
              'arkade5_import':{'controls':[]}}
        row=next(x for x in mod.quantity_evidence_comparison(data) if x['metric']=='folder_count')
        self.assertEqual(row['effective_source'],'KDRS Query (godkjent)')
        self.assertIsNone(row['dwm_count'])

if __name__=='__main__':unittest.main()
