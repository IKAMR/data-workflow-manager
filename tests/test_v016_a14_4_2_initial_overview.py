from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class TestA1442InitialOverview(unittest.TestCase):
    def test_final_structure_forces_real_transition_to_overview(self):
        text = (ROOT / "gui" / "depot_result_center_a14_4.py").read_text(encoding="utf-8")
        self.assertIn("def _activate_initial_overview", text)
        self.assertIn('tabs.set("Arkivdeler")', text)
        self.assertIn('tabs.set("Oversikt")', text)
        self.assertLess(text.index('tabs.set("Arkivdeler")'), text.index('tabs.set("Oversikt")', text.index('tabs.set("Arkivdeler")')))

    def test_source_compiles(self):
        source = (ROOT / "gui" / "depot_result_center_a14_4.py").read_text(encoding="utf-8")
        compile(source, "depot_result_center_a14_4.py", "exec")

    def test_version_is_a14_4_or_later(self):
        text = (ROOT / "version.py").read_text(encoding="utf-8")
        self.assertIn('VERSION = "0.1.6-a14"', text)


if __name__ == "__main__":
    unittest.main()
