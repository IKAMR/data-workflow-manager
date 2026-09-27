from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]


class TestA144ResultStructure(unittest.TestCase):
    def test_runtime_is_a14_4(self):
        text = (ROOT / "main.py").read_text(encoding="utf-8")
        self.assertIn("from gui.persistent_app_a14_4 import run_gui", text)

    def test_version_is_a14_4(self):
        text = (ROOT / "version.py").read_text(encoding="utf-8")
        match = re.search(r'VERSION\s*=\s*"0\.1\.6-a(\d+)', text)
        self.assertIsNotNone(match)
        self.assertGreaterEqual(int(match.group(1)), 14)


    def test_technical_is_last_and_noark_is_not_top_level(self):
        text = (ROOT / "gui" / "depot_result_center_a14_4.py").read_text(encoding="utf-8")
        self.assertIn('["Oversikt", "Arkivdeler", "Depotvurdering", "Filformater", "Rapporter", "Teknisk"]', text)
        self.assertIn('tabs.delete("Noark 5")', text)
        self.assertIn('"Noark 5-tester", "Vurderingspunkter", "Arkade 5"', text)

    def test_pronom_is_rendered_as_table_columns(self):
        text = (ROOT / "gui" / "depot_result_center_a14_4.py").read_text(encoding="utf-8")
        self.assertIn("CTkScrollableFrame", text)
        self.assertIn('("Format-ID / PUID", "Filtype", "Formatversjon", "RAF-220301", "Antall")', text)


if __name__ == "__main__":
    unittest.main()
