from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]


class A2114FormatSortAndHoverTests(unittest.TestCase):
    def test_version(self):
        text = (ROOT / 'version.py').read_text(encoding='utf-8')
        m = re.search(r'0\.1\.6-a(\d+)(?:\.(\d+))?', text)
        self.assertIsNotNone(m)
        self.assertTrue(int(m.group(1)) > 21 or (int(m.group(1)) == 21 and (m.group(2) is None or int(m.group(2)) >= 14)))

    def test_runtime_activates_a2114(self):
        source = (ROOT / 'main.py').read_text(encoding='utf-8')
        self.assertIn('from gui.persistent_app_a21_14 import run_gui', source)

    def test_pdfa_display_names(self):
        source = (ROOT / 'gui' / 'depot_result_center_a21_14.py').read_text(encoding='utf-8')
        self.assertIn('PDF/A-', source)
        self.assertIn('fmt/354', source)
        self.assertIn('fmt/95', source)

    def test_pronom_defaults_to_count_descending_and_headers_sort(self):
        source = (ROOT / 'gui' / 'depot_result_center_a21_14.py').read_text(encoding='utf-8')
        self.assertIn('{"key": "count", "reverse": True}', source)
        self.assertIn('command=lambda k=key: set_sort(k)', source)
        self.assertIn('▼', source)
        self.assertIn('▲', source)

    def test_hover_uses_current_pointer_and_motion(self):
        source = (ROOT / 'gui' / 'depot_result_center_a21_14.py').read_text(encoding='utf-8')
        self.assertIn('winfo_pointerx()', source)
        self.assertIn('winfo_pointery()', source)
        self.assertIn('"<Motion>"', source)


if __name__ == '__main__':
    unittest.main()
