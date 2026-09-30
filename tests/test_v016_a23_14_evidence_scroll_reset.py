from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
CENTER = ROOT / "gui" / "depot_result_center_a23_14.py"


class A2314EvidenceScrollResetTests(unittest.TestCase):
    def test_runtime_activates_a2314_or_newer(self):
        source = (ROOT / "main.py").read_text(encoding="utf-8")
        imports = [int(v) for v in re.findall(r"from gui\.persistent_app_a23_(\d+) import run_gui", source)]
        self.assertTrue(imports)
        self.assertGreaterEqual(max(imports), 14)

    def test_version_is_a2314_or_newer(self):
        source = (ROOT / "version.py").read_text(encoding="utf-8")
        match = re.search(r'VERSION\s*=\s*"0\.1\.6-a(\d+)(?:\.(\d+))?"', source)
        self.assertIsNotNone(match)
        alpha = int(match.group(1))
        increment = int(match.group(2) or 0)
        self.assertTrue(alpha > 23 or (alpha == 23 and increment >= 14))

    def test_scroll_reset_happens_after_render(self):
        source = CENTER.read_text(encoding="utf-8")
        self.assertIn("result = super()._a232_render_evidence", source)
        self.assertIn("after_idle(_reset)", source)
        self.assertIn("after(25, _reset)", source)
        self.assertIn("yview_moveto(0.0)", source)


if __name__ == "__main__":
    unittest.main()
