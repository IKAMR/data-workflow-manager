from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]

class V016A12NativeDialogPolicyTests(unittest.TestCase):
    def test_version(self):
        text=(ROOT/'version.py').read_text(encoding='utf-8')
        m=re.search(r'VERSION\s*=\s*"0\.1\.6-a(\d+)',text)
        self.assertIsNotNone(m); self.assertGreaterEqual(int(m.group(1)),12)
    def test_global_policy(self):
        s=(ROOT/'gui'/'window_placement.py').read_text(encoding='utf-8')
        self.assertIn('def install_native_dialog_policy',s)
        self.assertIn('ctk.CTkToplevel.transient = native_transient',s)
        self.assertIn('ctk.CTkToplevel.resizable = native_resizable',s)
    def test_windows_only(self):
        s=(ROOT/'gui'/'window_placement.py').read_text(encoding='utf-8')
        self.assertIn('if not sys.platform.startswith("win")',s)
    def test_runtime(self):
        s=(ROOT/'main.py').read_text(encoding='utf-8')
        self.assertIn('from gui.persistent_app_a72 import run_gui',s)

if __name__ == '__main__': unittest.main()
