import unittest
from pathlib import Path

class CompactEvidenceLayoutTests(unittest.TestCase):
    def test_compact_metric_rows_and_direct_selection(self):
        text = (Path(__file__).resolve().parents[1] / 'gui/depot_result_center_v017_a1.py').read_text(encoding='utf8')
        self.assertIn("headings = ('Måltall', 'DWM', 'KDRS', 'Valgt', 'Vurdering', '')", text)
        self.assertIn("text='Velg'", text)
        self.assertIn('def _choose_a5_metric(', text)
        self.assertIn('self._choose_a5_part_evidence()', text)
        self.assertIn("if item['detail'] and chosen != 'Ikke valgt':", text)
        self.assertNotIn('card = ctk.CTkFrame(table)', text)

if __name__ == '__main__': unittest.main()
