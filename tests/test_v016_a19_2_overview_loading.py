from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]


def _assert_version_at_least(testcase, version_text, alpha, sub=0):
    match = re.search(r'VERSION = "0\.1\.6-a(\d+)(?:\.(\d+))?"', version_text)
    testcase.assertIsNotNone(match)
    actual = (int(match.group(1)), int(match.group(2) or 0))
    testcase.assertGreaterEqual(actual, (alpha, sub))


class A192OverviewAndLoadingTests(unittest.TestCase):
    def test_runtime_activates_a19_2(self):
        main = (ROOT / "main.py").read_text(encoding="utf-8")
        version = (ROOT / "version.py").read_text(encoding="utf-8")
        self.assertIn("from gui.persistent_app_a19_2 import run_gui", main)
        _assert_version_at_least(self, version, 19, 2)

    def test_overview_uses_aligned_correspondence_cells(self):
        source = (ROOT / "gui/depot_result_center_a19_2.py").read_text(encoding="utf-8")
        self.assertIn("Four equal cells remove the ambiguity", source)
        self.assertIn("CTkProgressBar", source)
        for label in ("Inngående", "Utgående", "Notat", "Andre"):
            self.assertIn(label, source)

    def test_main_window_shows_opening_feedback(self):
        source = (ROOT / "gui/persistent_app_a19_2.py").read_text(encoding="utf-8")
        self.assertIn("Åpner Resultatvisninger", source)
        self.assertIn('cursor="watch"', source)
        self.assertIn("_a192_begin_open_indicator", source)
        self.assertIn("_a192_end_open_indicator", source)


if __name__ == "__main__":
    unittest.main()
