from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]


class V016A4NativeWindowsAndArchiveDetailsTests(unittest.TestCase):

    def test_version_is_a4_or_newer_v016(self):
        version = (ROOT / "version.py").read_text(encoding="utf-8")
        match = re.search(r'VERSION\s*=\s*"0\.1\.6-a(\d+)(?:\.\d+)*"', version)
        self.assertIsNotNone(match)
        self.assertGreaterEqual(int(match.group(1)), 4)

    def test_global_map_hook_only_places_windows(self):
        source = (ROOT / "gui" / "window_placement.py").read_text(encoding="utf-8")
        on_map = source.split("def on_map(event):", 1)[1]
        self.assertIn("place_near_parent", on_map)
        self.assertNotIn("enable_native_work_window(w)", on_map)
        self.assertNotIn('"wm", "transient"', on_map)

    def test_native_work_window_helper_is_explicit_and_platform_neutral(self):
        source = (ROOT / "gui" / "window_placement.py").read_text(encoding="utf-8")
        self.assertIn("def enable_native_work_window", source)
        self.assertIn("window.resizable(True, True)", source)
        self.assertIn('"wm", "transient"', source)
        self.assertIn("overrideredirect", source)
        self.assertIn("sys.platform.startswith", source)

    def test_major_noark_windows_opt_in_explicitly(self):
        files = (
            "depot_result_views_a24.py",
            "depot_assessment_dialog_a24.py",
            "direct_depot_assessment_dialog_a24.py",
            "noark5_control_overview_dialog_a24.py",
        )
        for name in files:
            source = (ROOT / "gui" / name).read_text(encoding="utf-8")
            self.assertIn("enable_native_work_window", source, name)
            self.assertIn("enable_native_work_window(self)", source, name)

    def test_archive_part_view_reads_existing_materialized_presentation(self):
        source = (ROOT / "gui" / "depot_result_views_a24.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("source_presentation_file", source)
        self.assertIn("archive_part_overview", source)
        self.assertIn("Ingen XML/XPath-analyse kjøres", source)
        self.assertIn("Innhold og omfang", source)
        self.assertIn("Bevaring, skjerming og kassasjon", source)
        self.assertIn("Sporbarhet", source)

    def test_missing_values_are_explained_not_only_rendered_as_dash(self):
        source = (ROOT / "gui" / "depot_result_views_a24.py").read_text(
            encoding="utf-8"
        )
        self.assertIn('"value_missing": "Ikke materialisert"', source)
        self.assertIn('"archive_part_missing": "Mangler for arkivdelen"', source)
        self.assertIn('"source_missing": "Kildetest mangler"', source)

    def test_runtime_activates_a64(self):
        main = (ROOT / "main.py").read_text(encoding="utf-8")
        self.assertIn("from gui.persistent_app_a64 import run_gui", main)


if __name__ == "__main__":
    unittest.main()
