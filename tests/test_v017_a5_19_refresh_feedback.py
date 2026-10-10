"""a5.19 regression: user must not be told an unsuccessful refresh succeeded."""
import ast
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

class TestA519(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.gui = (ROOT / 'gui/kdrs_query_results_a4.py').read_text(encoding='utf-8')
        cls.results = (ROOT / 'gui/depot_result_center_v017_a1.py').read_text(encoding='utf-8')

    def test_valid_python(self):
        ast.parse(self.gui)
        ast.parse(self.results)

    def test_native_dwm_preview_and_unknown(self):
        self.assertIn('def _dwm_count_for_evidence(', self.gui)
        self.assertIn('read_dwm_values(report)', self.gui)
        self.assertIn('Ukjent / ikke tilgjengelig', self.gui)
        self.assertIn('report_path=self.report_path', self.results)

    def test_refresh_distinguishes_success_from_failure(self):
        self.assertIn('updated = self._on_evidence_saved()', self.gui)
        self.assertIn('if updated is False:', self.gui)
        self.assertIn('return False', self.results)
        self.assertIn('return True', self.results)
        self.assertIn('Evidensvalget er lagret, men rapportgrunnlaget ble ikke oppdatert', self.gui)

if __name__ == '__main__':
    unittest.main()
