from __future__ import annotations

import ast
from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]


class V016A141ResultCenterStaticTests(unittest.TestCase):
    def test_result_center_source_compiles(self):
        path = ROOT / "gui" / "depot_result_center_a14_1.py"
        ast.parse(path.read_text(encoding="utf-8"), filename=str(path))

    def test_persistent_app_source_compiles(self):
        path = ROOT / "gui" / "persistent_app_a14_1.py"
        ast.parse(path.read_text(encoding="utf-8"), filename=str(path))

    def test_result_center_contains_consolidated_sections(self):
        text = (ROOT / "gui" / "depot_result_center_a14_1.py").read_text(encoding="utf-8")
        for label in ("Filformater", "Depotvurdering", "Rapport"):
            self.assertIn(f'tabs.add("{label}")', text)
        self.assertIn("PRONOM-STATISTIKK FRA ARKADE 5 / SIEGFRIED", text)
        self.assertIn("record_depot_assessment", text)

    def test_app_routes_existing_report_directly_to_result_center(self):
        text = (ROOT / "gui" / "persistent_app_a14_1.py").read_text(encoding="utf-8")
        self.assertIn("DepotResultCenterDialogA14_1", text)
        self.assertIn("if report_path is None", text)
        self.assertIn("super()._open_depot_assessment()", text)

    def test_version_is_a14_1_or_newer(self):
        text = (ROOT / "version.py").read_text(encoding="utf-8")
        match = re.search(r'VERSION\s*=\s*"0\.1\.6-a(\d+)', text)
        self.assertIsNotNone(match)
        self.assertGreaterEqual(int(match.group(1)), 14)



if __name__ == "__main__":
    unittest.main()
