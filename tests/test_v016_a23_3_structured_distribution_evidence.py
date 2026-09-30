from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
CENTER = ROOT / "gui" / "depot_result_center_a23_3.py"


class A233StructuredDistributionEvidenceTests(unittest.TestCase):
    def test_runtime_activates_a233(self):
        source = (ROOT / "main.py").read_text(encoding="utf-8")
        imports = [
            int(value)
            for value in re.findall(
                r"from gui\.persistent_app_a23_(\d+) import run_gui",
                source,
            )
        ]
        self.assertTrue(imports)
        self.assertGreaterEqual(max(imports), 3)

    def test_version_is_a233(self):
        source = (ROOT / "version.py").read_text(encoding="utf-8")
        match = re.search(r'VERSION\s*=\s*"0\.1\.6-a(\d+)(?:\.(\d+))?"', source)
        self.assertIsNotNone(match)
        alpha = int(match.group(1))
        increment = int(match.group(2) or 0)
        self.assertTrue(alpha > 23 or (alpha == 23 and increment >= 3))

    def test_three_distribution_controls_have_structured_visual_evidence(self):
        source = CENTER.read_text(encoding="utf-8")
        self.assertIn("_a233_render_folder_types", source)
        self.assertIn("_a233_render_journalpost_types", source)
        self.assertIn("_a233_render_format_metadata", source)
        self.assertIn('label == "Mappetyper"', source)
        self.assertIn('label == "Journalposttyper"', source)
        self.assertIn('label == "Format (metadata)"', source)

    def test_distribution_uses_visual_bars_and_percentages(self):
        source = CENTER.read_text(encoding="utf-8")
        self.assertIn("CTkProgressBar", source)
        self.assertIn("share =", source)
        self.assertIn("%", source)
        self.assertIn("_a233_distribution", source)

    def test_a233_uses_materialized_values_only(self):
        source = CENTER.read_text(encoding="utf-8")
        self.assertIn('_values_for_row("folders", row)', source)
        self.assertIn('_values_for_row("journalposts", row)', source)
        self.assertIn('_values_for_row("objects", row)', source)
        self.assertNotIn("lxml", source)
        self.assertNotIn("etree", source)
        self.assertNotIn("subprocess", source)


if __name__ == "__main__":
    unittest.main()
