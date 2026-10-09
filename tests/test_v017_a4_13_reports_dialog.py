"""Static regression checks for the unified KDRS report dialog."""
import ast
from pathlib import Path
import unittest

SOURCE = Path(__file__).resolve().parents[1] / 'gui' / 'kdrs_query_results_a4.py'

class ReportDialogRegressionTests(unittest.TestCase):
    def test_compiles_and_avoids_external_process(self):
        source = SOURCE.read_text(encoding='utf-8')
        ast.parse(source)
        self.assertNotIn('subprocess', source)

    def test_single_report_button_and_shared_dialog(self):
        source = SOURCE.read_text(encoding='utf-8')
        footer = source.split('    def _refresh_candidates(self):', 1)[0]
        self.assertIn("text='Åpne rapporter'", footer)
        self.assertNotIn("text='Åpne HTML'", footer)
        self.assertNotIn("text='Åpne JSON'", footer)
        self.assertIn('self._show_reports(generated=True)', source)
        self.assertIn("state='normal' if found_html else 'disabled'", source)
        self.assertIn("state='normal' if found_json else 'disabled'", source)
        self.assertIn('Ingen rapporter generert.', source)

if __name__ == '__main__':
    unittest.main()
