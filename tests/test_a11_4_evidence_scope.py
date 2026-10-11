import importlib.util
from pathlib import Path
import unittest
spec=importlib.util.spec_from_file_location('overview',Path(__file__).resolve().parents[1]/'tools'/'noark5_batch_overview_a6.py')
mod=importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
class TestA114(unittest.TestCase):
 def item(self, **overrides):
  v={'metrics':dict(folder_count=None), 'native_metrics':dict(folder_count=None),
   'external_evidence':{'approved':1,'whole_selected':{},'part_selected':[{'archive_part':43,'metric':'folder_count','value':2188}]},
   'arkade5_import':{'controls':[],'quantity_candidates':[{'metric':'folder_count','count':66834,'source':'archive'}]}}
  v.update(overrides)
  return v
 def test_part_only_keeps_unknown_whole_and_arkade_unselected(self):
  r=next(r for r in mod.quantity_evidence_comparison(self.item()) if r['metric']=='folder_count')
  self.assertIsNone(r['effective_count'])
  self.assertFalse(r['kdrs_whole_selected'])
  self.assertEqual(r['kdrs_archive_parts_selected'][0]['archive_part'],43)
  self.assertEqual(r['selection_scope'],'Bare arkivdel')
  self.assertFalse(r['arkade_selected'])
  self.assertFalse(r['comparable'])
 def test_two_imports_conflict(self):
  item=self.item(arkade5_import={'controls':[],'quantity_candidates':[{'metric':'folder_count','count':10},{'metric':'folder_count','count':11}]})
  r=next(r for r in mod.quantity_evidence_comparison(item) if r['metric']=='folder_count')
  self.assertIsNone(r['arkade_count'])
  self.assertEqual(r['availability'],'Motstridende Arkade-importer')
 def test_whole_selected_even_if_equals_native(self):
  item=self.item(native_metrics={'folder_count':10},metrics={'folder_count':10},external_evidence={'approved':1,'whole_selected':{'folder_count':10},'part_selected':[]})
  r=next(r for r in mod.quantity_evidence_comparison(item) if r['metric']=='folder_count')
  self.assertTrue(r['kdrs_whole_selected'])
  self.assertEqual(r['selected_source'],'KDRS Query (valgt for hele uttrekket)')
  self.assertEqual(r['comparison_status'],'Avvik')
if __name__=='__main__':unittest.main()
