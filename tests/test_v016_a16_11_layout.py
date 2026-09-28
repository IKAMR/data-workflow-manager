from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]

class A1611LayoutTests(unittest.TestCase):
    def test_archive_tab_order(self):
        text = (ROOT / 'gui' / 'depot_result_center_a16_11.py').read_text(encoding='utf-8')
        self.assertIn('["Sammendrag", "Per år", "Kontroller", "Vurderingspunkter"]', text)

    def test_annual_table_is_compact(self):
        text = (ROOT / 'gui' / 'depot_result_center_a16_11.py').read_text(encoding='utf-8')
        self.assertIn('widths = (58, 118, 128, 118, 118)', text)
        self.assertIn('pady=1', text)

    def test_controls_omit_duplicate_annual_section(self):
        text = (ROOT / 'gui' / 'depot_result_center_a16_11.py').read_text(encoding='utf-8')
        self.assertIn('casefold() == "omfang per år"', text)

    def test_runtime_uses_a1611_dialog(self):
        text = (ROOT / 'gui' / 'persistent_app_a16_11.py').read_text(encoding='utf-8')
        self.assertIn('DepotResultCenterDialogA16_11', text)

if __name__ == '__main__':
    unittest.main()
