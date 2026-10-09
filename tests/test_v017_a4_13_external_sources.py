"""Guard source-neutral tab naming and source-specific drill-down."""
import unittest
from pathlib import Path


class TestExternalSources(unittest.TestCase):
    def test_generic_tab_and_existing_detail(self):
        source = (Path(__file__).resolve().parents[1] / 'gui' / 'depot_result_center_v017_a1.py').read_text(encoding='utf-8')
        self.assertIn('tabs.add("Eksterne kilder")', source)
        self.assertIn('tabs.tab("Eksterne kilder")', source)
        self.assertNotIn('tabs.add("KDRS Query")', source)
        self.assertIn('KdrsQueryResultsDialog(self, work_operations=work)', source)
        self.assertIn('infer_work_operations_from_depot_report(self.report_path)', source)


if __name__ == '__main__':
    unittest.main()
