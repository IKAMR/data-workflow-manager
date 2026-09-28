from pathlib import Path
import re
import unittest

from gui.depot_result_center_a19_4 import _period_profile_layout

ROOT = Path(__file__).resolve().parents[1]


def _assert_version_at_least(testcase, version_text, alpha, sub=0):
    match = re.search(r'VERSION = "0\.1\.6-a(\d+)(?:\.(\d+))?"', version_text)
    testcase.assertIsNotNone(match)
    actual = (int(match.group(1)), int(match.group(2) or 0))
    testcase.assertGreaterEqual(actual, (alpha, sub))


class A194PeriodProfileTests(unittest.TestCase):
    def test_remote_2099_is_detached_but_near_boundary_years_remain_visible(self):
        profile = _period_profile_layout(
            {2007: 4, 2008: 20, 2019: 30, 2020: 5, 2099: 11},
            2008,
            2019,
            2008,
            2019,
        )
        self.assertEqual(profile["main_start"], 2007)
        self.assertEqual(profile["main_end"], 2020)
        self.assertEqual(profile["right_outliers"], [2099])

    def test_technical_closing_year_can_remain_beside_assessed_end(self):
        profile = _period_profile_layout({2018: 20, 2019: 40, 2020: 35, 2021: 12}, 2008, 2019, 2008, 2019)
        self.assertEqual(profile["main_end"], 2021)
        self.assertEqual(profile["right_outliers"], [])

    def test_runtime_activates_a19_4_and_keeps_a19_3_layer(self):
        main = (ROOT / "main.py").read_text(encoding="utf-8")
        version = (ROOT / "version.py").read_text(encoding="utf-8")
        source = (ROOT / "gui/persistent_app_a19_4.py").read_text(encoding="utf-8")
        self.assertIn("from gui.persistent_app_a19_3 import run_gui", main)
        self.assertIn("from gui.persistent_app_a19_4 import run_gui", main)
        _assert_version_at_least(self, version, 19, 4)
        self.assertIn("A19_3WorkflowApp", source)
        self.assertIn("DepotResultCenterDialogA19_4", source)

    def test_period_markers_refresh_after_saved_assessment(self):
        source = (ROOT / "gui/depot_result_center_a19_4.py").read_text(encoding="utf-8")
        self.assertIn("def _save_reviewed_period", source)
        self.assertIn("self._a194_refresh_period_profiles", source)
        self.assertIn("fill=theme.BLUE", source)
        self.assertIn("right_outliers", source)

    def test_open_overlay_is_centered_and_larger(self):
        source = (ROOT / "gui/persistent_app_a19_4.py").read_text(encoding="utf-8")
        self.assertIn('relx=0.5, rely=0.5', source)
        self.assertIn('width=390', source)
        self.assertIn("Leser eksisterende depotrapport", source)


if __name__ == "__main__":
    unittest.main()
