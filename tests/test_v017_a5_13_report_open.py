from __future__ import annotations

import ast
from pathlib import Path
import unittest


class A513ReportOpenTests(unittest.TestCase):
    def test_report_dialog_is_shared_and_checks_files(self):
        source = Path(__file__).resolve().parents[1] / 'gui' / 'depot_result_center_v017_a1.py'
        text = source.read_text(encoding='utf-8')
        ast.parse(text)
        self.assertIn('text="Depotrapporter"', text)
        self.assertIn('def _open_a5_report_dialog(', text)
        self.assertIn('depot-derived-evidence-report.html', text)
        self.assertIn('depot_validation_report.html', text)
        self.assertIn('state="normal" if path.is_file() else "disabled"', text)

    def test_refresh_generates_derived_html(self):
        source = Path(__file__).resolve().parents[1] / 'gui' / 'depot_result_center_v017_a1.py'
        text = source.read_text(encoding='utf-8')
        self.assertIn('write_derived_depot_html(self._a5_derived_report_path)', text)
        self.assertIn('self._a5_derived_html_path', text)

if __name__ == '__main__':
    unittest.main()
