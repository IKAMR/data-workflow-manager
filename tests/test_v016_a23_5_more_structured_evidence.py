from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
CENTER = ROOT / "gui" / "depot_result_center_a23_5.py"


class A235MoreStructuredEvidenceTests(unittest.TestCase):
    def test_runtime_activates_a235(self):
        source = (ROOT / "main.py").read_text(encoding="utf-8")
        self.assertIn("from gui.persistent_app_a23_5 import run_gui", source)

    def test_version(self):
        source = (ROOT / "version.py").read_text(encoding="utf-8")
        self.assertRegex(source, r'VERSION\s*=\s*"0\.1\.6-a23(?:\.\d+)?"')

    def test_journalstatus_has_structured_evidence(self):
        source = CENTER.read_text(encoding="utf-8")
        self.assertIn('label == "Journalstatus"', source)
        self.assertIn("_a235_render_journal_status", source)
        self.assertIn("Journalstatus – materialisert fordeling", source)

    def test_registreringstyper_has_structured_evidence(self):
        source = CENTER.read_text(encoding="utf-8")
        self.assertIn('label == "Registreringstyper"', source)
        self.assertIn("_a235_render_registration_types", source)
        self.assertIn("Registreringstyper – materialisert fordeling", source)

    def test_no_new_analysis(self):
        source = CENTER.read_text(encoding="utf-8")
        self.assertNotIn("subprocess", source)
        self.assertNotIn("lxml", source)
        self.assertNotIn("etree", source)


if __name__ == "__main__":
    unittest.main()
