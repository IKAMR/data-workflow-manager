from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]


class A211OverviewRefreshTests(unittest.TestCase):
    def test_runtime_wires_a211(self):
        main = (ROOT / "main.py").read_text(encoding="utf-8")
        version = (ROOT / "version.py").read_text(encoding="utf-8")
        self.assertIn("from gui.persistent_app_a21_1 import run_gui", main)
        match = re.search(r'VERSION = "0\.1\.6-a(\d+)(?:\.(\d+))?"', version)
        self.assertIsNotNone(match)
        self.assertTrue(int(match.group(1)) > 21 or (int(match.group(1)) == 21 and (match.group(2) is None or int(match.group(2)) >= 1)))

    def test_overview_has_distinct_orientation_sections(self):
        text = (ROOT / "gui" / "depot_result_center_a21_1.py").read_text(encoding="utf-8")
        for token in (
            "Kontrollresultat – DWM",
            "Arkivdelstatus",
            "Korrespondanseprofil – journalposter",
            "Tidsprofil – hele uttrekket",
            "Filformater",
            "Vurderingspunkter",
            "Videre arbeid",
        ):
            self.assertIn(token, text)

    def test_overview_keeps_analysis_out_of_gui(self):
        text = (ROOT / "gui" / "depot_result_center_a21_1.py").read_text(encoding="utf-8")
        self.assertIn("No Noark source analysis is started here", text)
        self.assertIn("all_archive_parts_summary", text)
        self.assertIn("external_validation", text)

    def test_overview_uses_same_semantic_domain_colours_as_archive_parts(self):
        text = (ROOT / "gui" / "depot_result_center_a21_1.py").read_text(encoding="utf-8")
        self.assertIn('theme.CATEGORY_COLORS["Innhold"]', text)
        self.assertIn('theme.CATEGORY_COLORS["Metadata"]', text)
        self.assertIn("theme.BLUE", text)


if __name__ == "__main__":
    unittest.main()
