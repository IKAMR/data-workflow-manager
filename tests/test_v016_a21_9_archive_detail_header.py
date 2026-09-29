from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]


class A219ArchiveDetailHeaderTests(unittest.TestCase):
    def test_version_is_a219_or_newer(self):
        text = (ROOT / "version.py").read_text(encoding="utf-8")
        match = re.search(r"0\.1\.6-a(\d+)(?:\.(\d+))?", text)
        self.assertIsNotNone(match)
        self.assertTrue(int(match.group(1)) > 21 or (int(match.group(1)) == 21 and (match.group(2) is None or int(match.group(2)) >= 9)))

    def test_runtime_activates_a219(self):
        source = (ROOT / "main.py").read_text(encoding="utf-8")
        self.assertIn("from gui.persistent_app_a21_9 import run_gui", source)
        self.assertLess(source.rfind("persistent_app_a21_9"), source.find('if __name__ == "__main__":'))

    def test_internal_all_archive_id_is_not_rendered(self):
        source = (ROOT / "gui" / "depot_result_center_a21_9.py").read_text(encoding="utf-8")
        self.assertIn("Alle arkivdeler", source)
        self.assertNotIn("_ALL_ARCHIVE_PARTS_", source)

    def test_selected_archive_header_exposes_identity_and_data_status(self):
        source = (ROOT / "gui" / "depot_result_center_a21_9.py").read_text(encoding="utf-8")
        self.assertIn("Arkivdel:", source)
        self.assertIn("systemID:", source)
        self.assertIn("Datagrunnlag: komplett", source)
        self.assertIn("Datagrunnlag: mangler", source)


if __name__ == "__main__":
    unittest.main()
