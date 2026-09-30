from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
CENTER = ROOT / "gui" / "depot_result_center_a23_1.py"


class A231ControlSpecificEvidenceTests(unittest.TestCase):
    def test_runtime_has_a231_layer(self):
        source = (ROOT / "main.py").read_text(encoding="utf-8")
        self.assertIn("from gui.persistent_app_a23_1 import run_gui", source)

    def test_version_is_a231_or_newer_a23_increment(self):
        source = (ROOT / "version.py").read_text(encoding="utf-8")
        match = re.search(r'VERSION\s*=\s*"0\.1\.6-a(\d+)(?:\.(\d+))?"', source)
        self.assertIsNotNone(match)
        alpha = int(match.group(1))
        increment = int(match.group(2) or 0)
        self.assertTrue(alpha > 23 or (alpha == 23 and increment >= 0))

    def test_four_representative_controls_have_dedicated_evidence(self):
        source = CENTER.read_text(encoding="utf-8")
        for label in ("Arkivdel", "Mappetyper", "Journalposttyper", "Format (metadata)"):
            self.assertIn(f'"{label}"', source)
        self.assertIn("_a231_archive_part_evidence", source)
        self.assertIn("_a231_folder_type_evidence", source)
        self.assertIn("_a231_journalpost_type_evidence", source)
        self.assertIn("_a231_format_metadata_evidence", source)

    def test_a231_uses_materialized_values_only(self):
        source = CENTER.read_text(encoding="utf-8")
        self.assertIn('_values_for_row("folders", row)', source)
        self.assertIn('_values_for_row("journalposts", row)', source)
        self.assertIn('_values_for_row("objects", row)', source)
        self.assertNotIn("lxml", source)
        self.assertNotIn("etree", source)


if __name__ == "__main__":
    unittest.main()
