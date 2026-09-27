from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]


def _a14_or_newer_version():
    text = (ROOT / "version.py").read_text(encoding="utf-8")
    match = re.search(r'VERSION\s*=\s*"0\.1\.6-a(\d+)', text)
    return match if match and int(match.group(1)) >= 14 else None



class V016A1431ResultWindowStabilityTests(unittest.TestCase):
    def test_result_center_starts_on_overview_not_forced_archive_parts(self):
        text = (ROOT / "gui" / "depot_result_center_a14_3.py").read_text(encoding="utf-8")
        self.assertIn("def _activate_archive_parts_tab", text)
        self.assertIn('tabs.set("Oversikt")', text)
        self.assertNotIn("_activate_a14_3_initial_tab", text)

    def test_inherited_a6_presentation_is_suppressed_during_construction(self):
        text = (ROOT / "gui" / "depot_result_center_a14_3.py").read_text(encoding="utf-8")
        self.assertIn("_a26_window_layer.present_child_over_parent = lambda", text)
        self.assertIn("_a26_window_layer.present_native_work_window = lambda", text)
        self.assertIn("_a26_window_layer.release_parent_work_window = lambda", text)
        self.assertIn("finally:", text)

    def test_completed_window_is_presented_once_after_super(self):
        text = (ROOT / "gui" / "depot_result_center_a14_3.py").read_text(encoding="utf-8")
        pos_super = text.index("super().__init__(master, **kwargs)")
        pos_release = text.rindex("release_parent_work_window(master)")
        pos_present = text.rindex("present_child_over_parent(self, master)")
        self.assertLess(pos_super, pos_release)
        self.assertLess(pos_release, pos_present)

    def test_version_is_a14_3_1_or_newer_increment(self):
        self.assertIsNotNone(_a14_or_newer_version())


if __name__ == "__main__":
    unittest.main()
