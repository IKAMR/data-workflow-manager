from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
CENTER = ROOT / "gui" / "depot_result_center_a23_6.py"


class A236StructuredCountEvidenceTests(unittest.TestCase):
    def test_runtime_activates_a236_or_newer(self):
        source = (ROOT / "main.py").read_text(encoding="utf-8")
        imports = [int(v) for v in re.findall(r"from gui\.persistent_app_a23_(\d+) import run_gui", source)]
        self.assertTrue(imports)
        self.assertGreaterEqual(max(imports), 6)

    def test_version_is_a236_or_newer(self):
        source = (ROOT / "version.py").read_text(encoding="utf-8")
        match = re.search(r'VERSION\s*=\s*"0\.1\.6-a(\d+)(?:\.(\d+))?"', source)
        self.assertIsNotNone(match)
        alpha = int(match.group(1))
        increment = int(match.group(2) or 0)
        self.assertTrue(alpha > 23 or (alpha == 23 and increment >= 6))

    def test_six_quantity_controls_have_structured_evidence(self):
        source = CENTER.read_text(encoding="utf-8")
        for label in (
            "Mapper",
            "Saker (saksmappe)",
            "Registreringer",
            "Journalposter",
            "Dokumentbeskrivelser",
            "Dokumentobjekter",
        ):
            self.assertIn(f'"{label}"', source)
        self.assertIn("_a236_render_count_control", source)
        self.assertIn("Kontekst i valgt arkivdel", source)

    def test_no_new_analysis(self):
        source = CENTER.read_text(encoding="utf-8")
        self.assertNotIn("subprocess", source)
        self.assertNotIn("lxml", source)
        self.assertNotIn("etree", source)


if __name__ == "__main__":
    unittest.main()
