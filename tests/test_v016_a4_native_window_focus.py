from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class V016A4NativeWindowFocusTests(unittest.TestCase):

    def test_global_map_hook_does_not_change_focus_or_window_style(self):
        source = (ROOT / "gui" / "window_placement.py").read_text(
            encoding="utf-8"
        )
        on_map = source.split("def on_map(event):", 1)[1]
        self.assertIn("place_near_parent", on_map)
        self.assertNotIn("present_native_work_window", on_map)
        self.assertNotIn("enable_native_work_window", on_map)

    def test_present_helper_uses_temporary_topmost_only_on_windows(self):
        source = (ROOT / "gui" / "window_placement.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("def present_native_work_window", source)
        self.assertIn('window.attributes("-topmost", True)', source)
        self.assertIn('window.attributes("-topmost", False)', source)
        self.assertIn("window.after(90, final_focus)", source)
        self.assertIn("window.after(180, final_focus)", source)

    def test_major_a4_windows_present_themselves_after_construction(self):
        files = (
            "depot_result_views_a24.py",
            "depot_assessment_dialog_a24.py",
            "direct_depot_assessment_dialog_a24.py",
            "noark5_control_overview_dialog_a24.py",
        )
        for name in files:
            source = (ROOT / "gui" / name).read_text(encoding="utf-8")
            self.assertIn("present_native_work_window", source, name)
            self.assertIn("present_native_work_window(self)", source, name)


if __name__ == "__main__":
    unittest.main()
