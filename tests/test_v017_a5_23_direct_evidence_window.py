"""a5.23 source-level regression: direct evidence selection has no result-browser window."""
import ast
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

class TestDirectEvidenceWindow(unittest.TestCase):
    def test_direct_selector_shares_existing_form(self):
        source = (ROOT / 'gui/kdrs_query_results_a4.py').read_text(encoding='utf-8')
        tree = ast.parse(source)
        cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'DirectEvidenceSelector')
        self.assertIn('_show_evidence_dialog = KdrsQueryResultsDialog._show_evidence_dialog', source)
        self.assertNotIn('super().__init__(', ast.get_source_segment(source, cls))
        self.assertIn("parent = getattr(self, '_evidence_parent', self)", source)
        self.assertIn('dialog = ctk.CTkToplevel(parent)', source)

    def test_button_uses_direct_selector_and_browser_still_exists(self):
        source = (ROOT / 'gui/depot_result_center_v017_a1.py').read_text(encoding='utf-8')
        self.assertIn('dialog = DirectEvidenceSelector(self, work_operations=work,', source)
        self.assertIn('dialog._show_evidence_dialog(initial_metric=metric, initial_part=part_index)', source)
        self.assertIn('KdrsQueryResultsDialog(self, work_operations=work, report_path=self.report_path)', source)

if __name__ == '__main__':
    unittest.main()
