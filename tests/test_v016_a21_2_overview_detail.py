from pathlib import Path
import unittest
import re
ROOT = Path(__file__).resolve().parents[1]
class A212OverviewDetailTests(unittest.TestCase):
    def test_runtime(self):
        self.assertIn('persistent_app_a21_2 import run_gui', (ROOT/'main.py').read_text(encoding='utf-8'))
        version=(ROOT/'version.py').read_text(encoding='utf-8')
        match=re.search(r'VERSION = "0\.1\.6-a(\d+)(?:\.(\d+))?"', version)
        self.assertIsNotNone(match)
        self.assertTrue(int(match.group(1)) > 21 or (int(match.group(1)) == 21 and (match.group(2) is None or int(match.group(2)) >= 2)))
    def test_formats_are_human_readable_with_puid_secondary(self):
        text=(ROOT/'gui'/'depot_result_center_a21_2.py').read_text(encoding='utf-8')
        self.assertIn('_A212_PUID_NAMES', text)
        self.assertIn('PDF/A-1b', text)
        self.assertIn('({puid})', text)
    def test_review_card_surfaces_materialized_cues(self):
        text=(ROOT/'gui'/'depot_result_center_a21_2.py').read_text(encoding='utf-8')
        self.assertIn('Uteliggende år:', text)
        self.assertIn('flere i Depotvurdering', text)
if __name__ == '__main__': unittest.main()
