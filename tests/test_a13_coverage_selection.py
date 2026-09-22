from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class A13CoverageSelectionTests(unittest.TestCase):
    def test_test_coverage_selects_between_multiple_imports(self):
        text = (
            ROOT / "gui" / "depot_result_views_a13.py"
        ).read_text(encoding="utf-8")

        self.assertIn("class Arkade5CoverageSelectionDialog", text)
        self.assertIn("Velg Arkade 5-rapport", text)
        self.assertIn("Åpne testdekning", text)
        self.assertIn("list_arkade5_imports", text)
        self.assertIn("_open_arkade5_coverage_for_import", text)

    def test_single_import_still_opens_directly(self):
        text = (
            ROOT / "gui" / "depot_result_views_a13.py"
        ).read_text(encoding="utf-8")

        self.assertIn("if len(imports) == 1:", text)


if __name__ == "__main__":
    unittest.main()
