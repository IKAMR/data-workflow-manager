from pathlib import Path
import re
import unittest
from version_assertions import assert_v016_at_least

ROOT = Path(__file__).resolve().parents[1]


class V016A10TargetArchiveLayoutTests(unittest.TestCase):

    def test_version_is_a10_or_newer(self):
        text = (ROOT / "version.py").read_text(encoding="utf-8")
        assert_v016_at_least(self, text, 10, 0)

    def test_archive_target_tabs_exist(self):
        source = (ROOT / "gui" / "depot_result_views_a30.py").read_text(
            encoding="utf-8"
        )
        for label in ("Sammendrag", "Kontroller", "Vurderingspunkter"):
            self.assertIn(f'"{label}"', source)

    def test_summary_has_target_headline_metrics(self):
        source = (ROOT / "gui" / "depot_result_views_a30.py").read_text(
            encoding="utf-8"
        )
        self.assertIn('("registration_count", "Registreringer")', source)
        self.assertIn('("journalpost_count", "Journalposter")', source)
        self.assertIn('("document_object_count", "Dokumentobjekter")', source)

    def test_missing_data_remains_explicit(self):
        source = (ROOT / "gui" / "depot_result_views_a30.py").read_text(
            encoding="utf-8"
        )
        self.assertIn('text="Manglende datagrunnlag"', source)
        self.assertIn("_missing_archive_fields(row)", source)

    def test_review_layer_is_explicitly_separate(self):
        source = (ROOT / "gui" / "depot_result_views_a30.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("depotets behandlingslag", source)
        self.assertIn("adskilt fra teknisk teststatus", source)

    def test_no_new_analysis_is_started(self):
        source = (ROOT / "gui" / "depot_result_views_a30.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("Ingen ny XML/XPath-analyse kjøres", source)

    def test_runtime_activates_a70(self):
        main = (ROOT / "main.py").read_text(encoding="utf-8")
        self.assertIn("from gui.persistent_app_a70 import run_gui", main)


if __name__ == "__main__":
    unittest.main()
