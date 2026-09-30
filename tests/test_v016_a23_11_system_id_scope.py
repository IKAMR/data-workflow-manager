from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
CENTER = ROOT / "gui" / "depot_result_center_a23_11.py"


class A2311SystemIdScopeTests(unittest.TestCase):
    def test_runtime_activates_a2311_or_newer(self):
        source = (ROOT / "main.py").read_text(encoding="utf-8")
        imports = [int(v) for v in re.findall(r"from gui\.persistent_app_a23_(\d+) import run_gui", source)]
        self.assertTrue(imports)
        self.assertGreaterEqual(max(imports), 11)

    def test_version_is_a2311_or_newer(self):
        source = (ROOT / "version.py").read_text(encoding="utf-8")
        match = re.search(r'VERSION\s*=\s*"0\.1\.6-a(\d+)(?:\.(\d+))?"', source)
        self.assertIsNotNone(match)
        alpha = int(match.group(1))
        increment = int(match.group(2) or 0)
        self.assertTrue(alpha > 23 or (alpha == 23 and increment >= 11))

    def test_all_and_multi_selection_are_scope_aware(self):
        source = CENTER.read_text(encoding="utf-8")
        self.assertIn("is_all_archive_parts", source)
        self.assertIn("is_virtual_selection", source)
        self.assertIn("_a171_selected", source)
        self.assertIn("Arkivdeler og systemID", source)

    def test_missing_and_duplicate_ids_are_summarized(self):
        source = CENTER.read_text(encoding="utf-8")
        self.assertIn("Manglende systemID", source)
        self.assertIn("Dupliserte systemID", source)
        self.assertIn("len(ids) - len(set(ids))", source)

    def test_materialized_only(self):
        source = CENTER.read_text(encoding="utf-8")
        self.assertNotIn("subprocess", source)
        self.assertNotIn("lxml", source)
        self.assertNotIn("etree", source)


if __name__ == "__main__":
    unittest.main()
