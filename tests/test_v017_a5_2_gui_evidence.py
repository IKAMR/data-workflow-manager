import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

class A52Integration(unittest.TestCase):
    def test_gui_wires_explicit_selection(self):
        source = (ROOT / 'gui/kdrs_query_results_a4.py').read_text(encoding='utf-8')
        self.assertIn('Velg dokumentert evidens', source)
        self.assertIn('select_evidence(self.work_operations, pool', source)
        self.assertIn('note.get().strip()', source)
        self.assertIn('part_index=scopes[scope_menu.get()]', source)
        self.assertNotIn('subprocess', source)

    def test_results_use_verified_evidence(self):
        source = (ROOT / 'gui/depot_result_center_v017_a1.py').read_text(encoding='utf-8')
        self.assertIn('report_evidence(build_mapped_pool(work), decisions', source)
        self.assertIn("resolved['status'] == 'external_evidence_selected'", source)
        self.assertIn("'case_count': 'case_folder_count'", source)

if __name__ == '__main__':
    unittest.main()
