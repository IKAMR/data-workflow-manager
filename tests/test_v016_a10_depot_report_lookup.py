from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class V016A10DepotReportLookupTests(unittest.TestCase):

    def test_effective_work_path_is_recalculated(self):
        source = (ROOT / "gui" / "persistent_app_a70.py").read_text(encoding="utf-8")
        block = source.split("def _expected_work_operations", 1)[1].split(
            "def _depot_report_for_job", 1
        )[0]
        self.assertIn("self._apply_effective_work_operations(job)", block)
        self.assertIn('getattr(job, "_effective_work_operations", None)', block)

    def test_unavailable_work_is_not_reported_as_missing_report(self):
        source = (ROOT / "gui" / "persistent_app_a70.py").read_text(encoding="utf-8")
        block = source.split("def _depot_report_for_job", 1)[1].split(
            "def _open_validation_overview", 1
        )[0]
        self.assertIn("not self._path_exists(expected)", block)
        self.assertIn("return None, expected, expected", block)

    def test_available_storage_still_uses_existing_report_lookup(self):
        source = (ROOT / "gui" / "persistent_app_a70.py").read_text(encoding="utf-8")
        self.assertIn("report = latest_depot_report(expected)", source)

    def test_depot_assessment_receives_storage_state(self):
        source = (ROOT / "gui" / "persistent_app_a70.py").read_text(encoding="utf-8")
        block = source.split("def _open_depot_assessment", 1)[1].split(
            "def run_gui", 1
        )[0]
        self.assertIn("storage_unavailable_path=unavailable_path", block)


if __name__ == "__main__":
    unittest.main()
