from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]

class A256ImportedStatusIconTests(unittest.TestCase):
    def test_imported_rows_use_fixed_checked_icon_not_disabled_checkbox(self):
        source = (ROOT / 'gui' / 'arkade5_batch_discovery_dialog.py').read_text(encoding='utf-8')
        self.assertIn('text="✓"', source)
        self.assertIn('if imported:', source)
        self.assertNotIn('state="disabled" if imported else "normal"', source)
        self.assertIn('checkbox = None', source)
        self.assertIn('checkbox.destroy()', source)

    def test_new_rows_remain_selectable(self):
        source = (ROOT / 'gui' / 'arkade5_batch_discovery_dialog.py').read_text(encoding='utf-8')
        self.assertIn('checkbox = ctk.CTkCheckBox(', source)
        self.assertIn('value=not imported', source)

    def test_runtime_is_a256(self):
        main = (ROOT / 'main.py').read_text(encoding='utf-8')
        version = (ROOT / 'version.py').read_text(encoding='utf-8')
        self.assertIn('from gui.persistent_app_a25_6 import run_gui', main)
        self.assertRegex(version, r'VERSION\s*=\s*"0\.1\.6-a25(?:\.(?:6|[7-9]|[1-9]\d+))?"')

if __name__ == '__main__':
    unittest.main()
