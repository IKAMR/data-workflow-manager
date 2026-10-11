import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location('overview', Path(__file__).resolve().parents[1] / 'tools' / 'noark5_batch_overview_a6.py')
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

class TestExplicitSelections(unittest.TestCase):
    def setUp(self):
        self.item = {'job': 'JOB-002', 'extraction': 'C:/test/extraction_2',
                     'metrics': {'folder_count': None},
                     'quantity_comparison': [{'metric': 'folder_count', 'arkade_count': 66834,
                                              'arkade_candidates': [{'count': 66834}]}]}
        self.selection = {'choices': [{'job': 'JOB-002', 'extraction': 'extraction_2',
                                       'metric': 'folder_count', 'source': 'Arkade 5', 'count': 66834}]}
    def test_explicit_selection_does_not_overwrite_native(self):
        self.assertEqual(mod.apply_explicit_quantity_choices([self.item], self.selection), 1)
        self.assertIsNone(self.item['metrics']['folder_count'])
        self.assertEqual(self.item['quantity_comparison'][0]['report_selected_count'], 66834)
        self.assertEqual(self.item['quantity_comparison'][0]['report_selected_scope'], 'Hele uttrekket')
    def test_disallow_unknown_count(self):
        self.selection['choices'][0]['count'] = 99999
        with self.assertRaises(ValueError): mod.apply_explicit_quantity_choices([self.item], self.selection)
    def test_disallow_ambiguous_job(self):
        with self.assertRaises(ValueError): mod.apply_explicit_quantity_choices([self.item, dict(self.item)], self.selection)
    def test_disallow_duplicate(self):
        self.selection['choices'] *= 2
        with self.assertRaises(ValueError): mod.apply_explicit_quantity_choices([self.item], self.selection)
    def test_disallow_unverified_source(self):
        self.selection['choices'][0]['source'] = 'KDRS Query'
        with self.assertRaises(ValueError): mod.apply_explicit_quantity_choices([self.item], self.selection)

if __name__ == '__main__': unittest.main()
