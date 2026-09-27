from __future__ import annotations
import ast
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]

class V016A142ResultStructureTests(unittest.TestCase):
    def test_sources_compile(self):
        for rel in ("gui/depot_result_center_a14_2.py", "gui/persistent_app_a14_2.py", "main.py"):
            path = ROOT / rel
            ast.parse(path.read_text(encoding="utf-8"), filename=str(path))

    def test_six_top_level_areas(self):
        text = (ROOT / "gui/depot_result_center_a14_2.py").read_text(encoding="utf-8")
        for label in ("Oversikt", "Noark 5", "Filformater", "Depotvurdering", "Rapporter"):
            self.assertIn(f'tabs.add("{label}")', text)
        self.assertIn('tabs.delete(old_name)', text)
        self.assertIn('"Totalt", "Teknisk", "Vurderingspunkter", "Ekstern evidens"', text)
        self.assertNotIn('tabs.delete("Arkivdeler")', text)

    def test_noark5_groups_old_technical_areas(self):
        text = (ROOT / "gui/depot_result_center_a14_2.py").read_text(encoding="utf-8")
        self.assertIn('("Teknisk", "Vurderingspunkter", "Arkade 5")', text)
        self.assertIn("PRONOM/Siegfried-statistikk vises under Filformater", text)

    def test_version_is_a14_2_or_newer(self):
        text = (ROOT / "version.py").read_text(encoding="utf-8")
        match = re.search(r'VERSION\s*=\s*"0\.1\.6-a(\d+)', text)
        self.assertIsNotNone(match)
        self.assertGreaterEqual(int(match.group(1)), 14)


if __name__ == "__main__":
    unittest.main()
