from pathlib import Path
import unittest
import re
from version_assertions import assert_v016_at_least
ROOT = Path(__file__).resolve().parents[1]
class A212OverviewDetailTests(unittest.TestCase):
    def test_runtime(self):
        self.assertIn('persistent_app_a21_2 import run_gui', (ROOT/'main.py').read_text(encoding='utf-8'))
        version=(ROOT/'version.py').read_text(encoding='utf-8')
        assert_v016_at_least(self, version, 21, 2, consolidated_alpha=True)
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
