from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]

class A1618SummaryLayoutTests(unittest.TestCase):
    def test_runtime_uses_a1618(self):
        self.assertIn('persistent_app_a16_18 import run_gui', (ROOT / 'main.py').read_text(encoding='utf-8'))

    def test_summary_has_three_paired_kpis(self):
        text = (ROOT / 'gui' / 'depot_result_center_a16_18.py').read_text(encoding='utf-8')
        self.assertIn('Mapper / saker', text)
        self.assertIn('Registreringer / JP', text)
        self.assertIn('Dok.beskrivelser / objekter', text)
        self.assertIn('document_description_count', text)

if __name__ == '__main__':
    unittest.main()
