import importlib.util
from pathlib import Path
import unittest

MODULE=Path(__file__).resolve().parents[1]/'tools'/'noark5_batch_overview_a6.py'
spec=importlib.util.spec_from_file_location('overview_a113', MODULE)
mod=importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

class ArkadeTotalsTests(unittest.TestCase):
    def test_strict_totals_only(self):
        test={'test_id':'N5.10','results':[{'message':'Totalt: 66834'},
               {'message':'Antall: 6848'}]}
        self.assertEqual(mod.extract_arkade_quantity(test,'N5.10'),66834)
        test['results']=[{'message':'Antall: 6848'}]
        self.assertIsNone(mod.extract_arkade_quantity(test,'N5.10'))

    def test_journalposts_special_label(self):
        test={'test_id':'N5.59','results':[{'message':'Antall journalposter funnet i arkivstrukturen: 639848'},
                                           {'message':'Antall journalposter dokumentert i offentlig journal: 639848'}]}
        self.assertEqual(mod.extract_arkade_quantity(test,'N5.59'),639848)

    def test_conflicting_imports_not_summed(self):
        native={key:None for key,_ in mod.METRICS}
        ark={'controls':[{'id':'N5.10','has_results':True}],
             'quantity_candidates':[{'metric':'folder_count','count':100,'source':'run1'},
                                    {'metric':'folder_count','count':110,'source':'run2'}]}
        base={'metrics':native,'native_metrics':native,'external_evidence':{'approved':0},'arkade5_import':ark}
        row=next(r for r in mod.quantity_evidence_comparison(base) if r['metric']=='folder_count')
        self.assertIsNone(row['arkade_count'])
        self.assertEqual(len(row['arkade_candidates']),2)
        self.assertIsNone(row['effective_count'])
        self.assertIn('Ulike',row['arkade_status'])
        ark['quantity_candidates'][1]['count']=100
        row=next(r for r in mod.quantity_evidence_comparison(base) if r['metric']=='folder_count')
        self.assertEqual(row['arkade_count'],100)
        self.assertIsNone(row['effective_count'])

    def test_provenance(self):
        value={'source_version':'2.12.3','source':{'sha256':'abc'},'tests':[
            {'test_id':'N5.05','results':[{'message':'Totalt: 43'}]},
            {'test_id':'N5.26','results':[{'message':'Totalt: 3436422'}]}]}
        c=mod.imported_quantity_candidates(value,'example.json')
        self.assertEqual({r['count'] for r in c},{43,3436422})
        self.assertEqual(c[0]['source'],'example.json')
        self.assertEqual(c[0]['source_sha256'],'abc')

if __name__=='__main__':unittest.main()
