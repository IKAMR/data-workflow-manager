from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "gui" / "depot_result_center_a21_15.py"


class A2115FormatPresentationTests(unittest.TestCase):
    def test_runtime_activates_a2115(self):
        source = (ROOT / "main.py").read_text(encoding="utf-8")
        self.assertIn("from gui.persistent_app_a21_15 import run_gui", source)

    def test_extensions_are_lowercase_and_acrobat_names_are_consistent(self):
        source = SRC.read_text(encoding="utf-8")
        self.assertIn('"Microsoft Word (docx)"', source)
        self.assertIn('"Microsoft Word (doc)"', source)
        self.assertIn('"Acrobat PDF/A-1b"', source)
        self.assertIn('return f"Acrobat PDF {clean_version}"', source)

    def test_overview_puid_has_own_right_aligned_column(self):
        source = SRC.read_text(encoding="utf-8")
        self.assertIn('text=f"({puid})" if puid else ""', source)
        self.assertIn('anchor="e"', source)

    def test_format_view_is_four_meaningful_sortable_columns(self):
        source = SRC.read_text(encoding="utf-8")
        self.assertIn('(\"file_type\", \"Filformat\")', source)
        self.assertIn('(\"format_id\", \"PUID\")', source)
        self.assertIn('(\"archive_format\", \"Arkivformatstatus\")', source)
        self.assertIn('(\"count\", \"Antall\")', source)
        self.assertNotIn('(\"format_version\", \"Formatversjon\")', source)
        self.assertIn('state = {"key": "count", "reverse": True}', source)
        self.assertIn('state["reverse"] = not state["reverse"]', source)

    def test_tooltip_font_is_larger(self):
        source = SRC.read_text(encoding="utf-8")
        self.assertIn('effective_size(theme.NORMAL_SIZE) + 1', source)
        self.assertIn('self._a2114_place_tooltip()', source)


if __name__ == "__main__":
    unittest.main()
