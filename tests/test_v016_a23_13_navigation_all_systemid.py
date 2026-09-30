from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
CENTER = ROOT / "gui" / "depot_result_center_a23_13.py"


class A2313NavigationAndAllSystemIdTests(unittest.TestCase):
    def test_runtime_activates_a2313_or_newer(self):
        source = (ROOT / "main.py").read_text(encoding="utf-8")
        imports = [int(v) for v in re.findall(r"from gui\.persistent_app_a23_(\d+) import run_gui", source)]
        self.assertTrue(imports)
        self.assertGreaterEqual(max(imports), 13)

    def test_version_is_a2313_or_newer(self):
        source = (ROOT / "version.py").read_text(encoding="utf-8")
        match = re.search(r'VERSION\s*=\s*"0\.1\.6-a(\d+)(?:\.(\d+))?"', source)
        self.assertIsNotNone(match)
        alpha = int(match.group(1))
        increment = int(match.group(2) or 0)
        self.assertTrue(alpha > 23 or (alpha == 23 and increment >= 13))

    def test_all_scope_exposes_system_id_control(self):
        source = CENTER.read_text(encoding="utf-8")
        self.assertIn('row.get("is_all_archive_parts")', source)
        self.assertIn('"label": "systemID"', source)
        self.assertIn('"source": "arkivstruktur.xml"', source)
        self.assertIn("_a2311_systemid_summary", source)

    def test_evidence_scroll_resets_to_top(self):
        source = CENTER.read_text(encoding="utf-8")
        self.assertIn("def _a232_clear", source)
        self.assertIn("yview_moveto(0.0)", source)
        self.assertIn("after_idle", source)


if __name__ == "__main__":
    unittest.main()
