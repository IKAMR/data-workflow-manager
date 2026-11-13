"""GUI selection contract, with Qt optional on headless build/test hosts."""
import unittest

from app.canonical_selection_v0115_a3 import selected_sources

class CanonicalGuiSelectionTests(unittest.TestCase):
    def test_select_one_normal_master_and_raw(self):
        got = selected_sources([
            ('master', 'noark5_tests/a/master-results.json', True, 'normal_master'),
            ('raw', 'wf/results/raw-results.jsonl', True, 'candidate'),
            ('master', 'noark5_tests/old/master-results.json', False, 'unsupported_or_historical'),
        ])
        self.assertEqual(got['master_paths'], ('noark5_tests/a/master-results.json',))
        self.assertEqual(got['raw_results_path'], 'wf/results/raw-results.jsonl')
        self.assertIsNone(got['external_bank_path'])

    def test_reject_empty(self):
        with self.assertRaises(ValueError):
            selected_sources([])

    def test_reject_unsupported_selected(self):
        with self.assertRaises(ValueError):
            selected_sources([('master', 'old/master-results.json', True, 'unsupported_or_historical')])

    def test_reject_multiple_raw_logs(self):
        with self.assertRaises(ValueError):
            selected_sources([('raw', 'a/raw-results.jsonl', True, 'candidate'),
                              ('raw', 'b/raw-results.jsonl', True, 'candidate')])

if __name__ == '__main__':
    unittest.main()
