from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "gui" / "depot_result_center_a21_16.py"


class A2116FormatViewTests(unittest.TestCase):
    def test_runtime_activates_a2116(self):
        source = (ROOT / "main.py").read_text(encoding="utf-8")
        self.assertIn("from gui.persistent_app_a21_16 import run_gui", source)

    def test_search_field_exists(self):
        source = SRC.read_text(encoding="utf-8")
        self.assertIn("Søk i filformater, PUID, MIME ...", source)
        self.assertIn('search_var.trace_add("write", render)', source)

    def test_header_and_rows_share_geometry(self):
        source = SRC.read_text(encoding="utf-8")
        self.assertIn("for holder in (headers, table):", source)
        self.assertIn('("format_id", "PUID")', source)
        self.assertIn('padx=(6, 6)', source)

    def test_format_tooltip_contains_full_metadata(self):
        source = SRC.read_text(encoding="utf-8")
        self.assertIn("Fullt navn:", source)
        self.assertIn("PUID:", source)
        self.assertIn("Versjon:", source)
        self.assertIn("MIME:", source)
        self.assertIn("Arkivformatstatus:", source)
        self.assertIn('label.bind("<Enter>"', source)

    def test_default_sort_is_count_desc(self):
        source = SRC.read_text(encoding="utf-8")
        self.assertIn('state = {"key": "count", "reverse": True}', source)


if __name__ == "__main__":
    unittest.main()
