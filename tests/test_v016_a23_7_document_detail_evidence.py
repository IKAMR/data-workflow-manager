from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
CENTER = ROOT / "gui" / "depot_result_center_a23_7.py"


class A237DocumentDetailEvidenceTests(unittest.TestCase):
    def test_runtime_activates_a237_or_newer(self):
        source = (ROOT / "main.py").read_text(encoding="utf-8")
        imports = [
            int(v)
            for v in re.findall(
                r"from gui\.persistent_app_a23_(\d+) import run_gui",
                source,
            )
        ]
        self.assertTrue(imports)
        self.assertGreaterEqual(max(imports), 7)

    def test_version_is_a237_or_newer(self):
        source = (ROOT / "version.py").read_text(encoding="utf-8")
        match = re.search(r'VERSION\s*=\s*"0\.1\.6-a(\d+)(?:\.(\d+))?"', source)
        self.assertIsNotNone(match)
        alpha = int(match.group(1))
        increment = int(match.group(2) or 0)
        self.assertTrue(alpha > 23 or (alpha == 23 and increment >= 7))

    def test_four_document_controls_have_structured_distribution_evidence(self):
        source = CENTER.read_text(encoding="utf-8")
        for label in (
            "Tilknytning til registrering",
            "Dokumenttype",
            "Variantformat",
            "Versjonsnummer",
        ):
            self.assertIn(f'label == "{label}"', source)
        self.assertIn("_a237_render_distribution_control", source)
        self.assertIn("_a233_distribution", source)

    def test_materialized_sources_only(self):
        source = CENTER.read_text(encoding="utf-8")
        self.assertIn('_values_for_row(kind, row)', source)
        self.assertNotIn("subprocess", source)
        self.assertNotIn("lxml", source)
        self.assertNotIn("etree", source)


if __name__ == "__main__":
    unittest.main()
