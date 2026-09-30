from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
CENTER = ROOT / "gui" / "depot_result_center_a23_2.py"


class A232StructuredArchiveEvidenceTests(unittest.TestCase):
    def test_runtime_activates_a232(self):
        source = (ROOT / "main.py").read_text(encoding="utf-8")
        self.assertIn("from gui.persistent_app_a23_2 import run_gui", source)

    def test_version_is_a232_or_newer_a23_increment(self):
        source = (ROOT / "version.py").read_text(encoding="utf-8")
        match = re.search(r'VERSION\s*=\s*"0\.1\.6-a(\d+)(?:\.(\d+))?"', source)
        self.assertIsNotNone(match)
        alpha = int(match.group(1))
        increment = int(match.group(2) or 0)
        self.assertTrue(alpha > 23 or (alpha == 23 and increment >= 0))

    def test_archive_part_has_structured_visual_cards(self):
        source = CENTER.read_text(encoding="utf-8")
        self.assertIn("_a232_render_archive_part", source)
        self.assertIn('_a232_card(parent, 0, "Identitet"', source)
        self.assertIn('_a232_card(parent, 1, "Omfang"', source)
        self.assertIn('_a232_card(parent, 2, "Kontrollgrunnlag"', source)
        self.assertIn("CTkScrollableFrame", source)

    def test_a232_keeps_other_a231_specific_evidence(self):
        source = CENTER.read_text(encoding="utf-8")
        self.assertIn("self._a223_context_text(index, item)", source)
        self.assertIn('label == "Arkivdel"', source)

    def test_a232_does_not_start_new_analysis(self):
        source = CENTER.read_text(encoding="utf-8")
        self.assertNotIn("lxml", source)
        self.assertNotIn("etree", source)
        self.assertNotIn("subprocess", source)


if __name__ == "__main__":
    unittest.main()
