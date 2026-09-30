from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "gui" / "depot_result_center_a23_2.py"


class A2315CircularControlNavigationTests(unittest.TestCase):
    def test_runtime_activates_a2315_or_newer(self):
        source = (ROOT / "main.py").read_text(encoding="utf-8")
        imports = [int(v) for v in re.findall(r"from gui\.persistent_app_a23_(\d+) import run_gui", source)]
        self.assertTrue(imports)
        self.assertGreaterEqual(max(imports), 15)

    def test_version_is_a2315_or_newer(self):
        source = (ROOT / "version.py").read_text(encoding="utf-8")
        match = re.search(r'VERSION\s*=\s*"0\.1\.6-a23(?:\.(\d+))?"', source)
        self.assertIsNotNone(match)
        self.assertTrue(match.group(1) is None or int(match.group(1)) >= 15)

    def test_control_navigation_wraps(self):
        source = BASE.read_text(encoding="utf-8")
        self.assertIn("pos = pos % len(items)", source)
        self.assertNotIn("pos = max(0, min(pos, len(items) - 1))", source)
        self.assertIn('text="Neste kontroll →"', source)
        self.assertIn('text="← Forrige kontroll"', source)


if __name__ == "__main__":
    unittest.main()
