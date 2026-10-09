from __future__ import annotations

import ast
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class A4GuiKdrsQueryTests(unittest.TestCase):
    def test_result_view_has_gui_entry_point(self):
        source = (ROOT / 'gui/depot_result_views_a31.py').read_text(encoding='utf-8')
        ast.parse(source)
        self.assertIn('KDRS Query – importerte resultater', source)
        self.assertIn('KdrsQueryResultsDialog(self, work_operations=work)', source)
        self.assertIn('infer_work_operations_from_depot_report(self.report_path)', source)

    def test_gui_reads_bank_and_can_export_report_data(self):
        source = (ROOT / 'gui/kdrs_query_results_a4.py').read_text(encoding='utf-8')
        ast.parse(source)
        for token in ('build_external_result_bank', 'write_kdrs_query_views',
                      'source_sha256', 'archive_part_title', 'Standard', 'U1', 'U2',
                      'CTkTextbox', 'self._export'):
            self.assertIn(token, source)
        self.assertNotIn('subprocess', source)
        self.assertNotIn('os.system', source)

    def test_gui_preserves_a31_dashboard_methods(self):
        source = (ROOT / 'gui/depot_result_views_a31.py').read_text(encoding='utf-8')
        root = ast.parse(source)
        cls = next(n for n in root.body if isinstance(n, ast.ClassDef) and n.name == 'DepotResultViewsDialogA31')
        method_names = {n.name for n in cls.body if isinstance(n, ast.FunctionDef)}
        self.assertTrue({'_install_a11_dashboard', '_refresh_a11_dashboard', '_dashboard_counts',
                         '_render_a11_archive_part', '_refresh_a11_archive_cards',
                         '_show_archive_part', '_draw_a11_chart', '_open_kdrs_query_results'} <= method_names)

if __name__ == '__main__':
    unittest.main()
