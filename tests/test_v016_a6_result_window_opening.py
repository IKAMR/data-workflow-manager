from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]


class V016A6ResultWindowOpeningTests(unittest.TestCase):

    def test_version_is_a6_or_newer_v016(self):
        text = (ROOT / "version.py").read_text(encoding="utf-8")
        match = re.search(r'VERSION\s*=\s*"0\.1\.6-a(\d+)(?:\.\d+)*"', text)
        self.assertIsNotNone(match)
        self.assertGreaterEqual(int(match.group(1)), 6)

    def test_normal_display_is_maximized(self):
        source = (ROOT / "gui" / "window_geometry.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("def result_review_window_geometry", source)
        self.assertIn('return "maximized", None', source)
        self.assertIn("ratio < wide_ratio", source)

    def test_ultrawide_display_uses_fitted_window(self):
        source = (ROOT / "gui" / "window_geometry.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("int(screen.width * 0.62)", source)
        self.assertIn("int(screen.height * 0.88)", source)
        self.assertIn('return "fitted"', source)
        self.assertIn("wide_ratio: float = 2.0", source)

    def test_windows_uses_current_monitor_not_virtual_desktop(self):
        source = (ROOT / "gui" / "window_geometry.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("MonitorFromWindow", source)
        self.assertIn("GetMonitorInfoW", source)
        self.assertIn("rcWork", source)

    def test_result_view_applies_rule_after_a5_has_completed(self):
        source = (ROOT / "gui" / "depot_result_views_a26.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("DepotResultViewsDialogA25", source)
        self.assertIn("super().__init__(master, **kwargs)", source)
        self.assertIn("apply_result_review_opening_mode", source)
        self.assertIn("wide_ratio=2.0", source)

    def test_result_view_releases_parent_z_order_before_presenting(self):
        source = (ROOT / "gui" / "depot_result_views_a26.py").read_text(
            encoding="utf-8"
        )

        # Compare runtime calls only inside __init__, not import lines.
        init_body = source.split("def __init__(self, master, **kwargs):", 1)[1]
        self.assertIn("release_parent_work_window(master)", init_body)
        self.assertIn("apply_result_review_opening_mode(self", init_body)
        self.assertIn("present_child_over_parent(self, master)", init_body)
        self.assertLess(
            init_body.index("release_parent_work_window(master)"),
            init_body.index("apply_result_review_opening_mode(self"),
        )

        helper = (ROOT / "gui" / "window_placement.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("def release_parent_work_window", helper)
        self.assertIn('parent.attributes("-topmost", False)', helper)
        self.assertIn("parent.lower()", helper)
        self.assertIn("def present_child_over_parent", helper)
        self.assertIn("SetWindowPos", helper)
        self.assertIn("HWND_NOTOPMOST", helper)
        self.assertIn("HWND_TOPMOST", helper)
        self.assertIn("_dwm_present_generation", helper)
        self.assertIn("def is_current()", helper)
        self.assertIn("parent._dwm_present_generation", helper)

    def test_runtime_activates_a66(self):
        main = (ROOT / "main.py").read_text(encoding="utf-8")
        self.assertIn("from gui.persistent_app_a66 import run_gui", main)


if __name__ == "__main__":
    unittest.main()
