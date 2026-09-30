from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
CENTER = ROOT / "gui" / "depot_result_center_a23_12.py"


class A2312AllArchivePartsSystemIdTests(unittest.TestCase):
    def test_runtime_activates_a2312_or_newer(self):
        source = (ROOT / "main.py").read_text(encoding="utf-8")
        imports = [int(v) for v in re.findall(r"from gui\.persistent_app_a23_(\d+) import run_gui", source)]
        self.assertTrue(imports)
        self.assertGreaterEqual(max(imports), 12)

    def test_version_is_a2312_or_newer(self):
        source = (ROOT / "version.py").read_text(encoding="utf-8")
        match = re.search(r'VERSION\s*=\s*"0\.1\.6-a23(?:\.(\d+))?"', source)
        self.assertIsNotNone(match)
        self.assertTrue(match.group(1) is None or int(match.group(1)) >= 12)

    def test_all_scope_uses_concrete_archive_parts(self):
        source = CENTER.read_text(encoding="utf-8")
        self.assertIn("_a2312_concrete_archive_parts", source)
        self.assertIn('if row.get("is_all_archive_parts"):', source)
        self.assertIn("return self._a2312_concrete_archive_parts()", source)

    def test_all_scope_always_uses_system_id_table(self):
        source = CENTER.read_text(encoding="utf-8")
        self.assertIn("_a2311_render_system_table(parent, scope_rows)", source)
        self.assertIn('("Utvalg", "Alle arkivdeler")', source)
        self.assertIn('"Manglende systemID"', source)
        self.assertIn('"Dupliserte systemID"', source)


if __name__ == "__main__":
    unittest.main()
