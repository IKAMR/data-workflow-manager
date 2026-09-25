from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class V016A10DepotReportDiscoveryTests(unittest.TestCase):

    def test_discovery_knows_current_dwm_layout(self):
        source = (ROOT / "gui" / "persistent_app_a70.py").read_text(
            encoding="utf-8"
        )
        self.assertIn(
            '"repository_operations/dwm/*/noark5_reports/depot_validation/*/depot_validation_report.json"',
            source,
        )
        self.assertIn(
            '"dwm/*/noark5_reports/depot_validation/*/depot_validation_report.json"',
            source,
        )

    def test_unavailable_storage_is_detected_before_report_discovery(self):
        source = (ROOT / "gui" / "persistent_app_a70.py").read_text(
            encoding="utf-8"
        )
        block = source.split("def _depot_report_for_job", 1)[1].split(
            "def _open_validation_overview", 1
        )[0]
        self.assertIn("expected = self._expected_work_operations(job)", block)
        self.assertIn("not self._path_exists(expected)", block)
        self.assertIn("return None, expected, expected", block)

    def test_available_roots_are_bounded_to_known_job_paths(self):
        source = (ROOT / "gui" / "persistent_app_a70.py").read_text(
            encoding="utf-8"
        )
        block = source.split("roots: list[Path] = []", 1)[1].split(
            "patterns = (", 1
        )[0]

        for expected in (
            'add(expected)',
            'add(getattr(job, "work_root", None))',
            'add(getattr(job, "archive_root", None))',
            'add(getattr(job, "output_root", None))',
            'add(getattr(job, "source_root", None))',
            'add(getattr(job, "source_extraction", None))',
        ):
            self.assertIn(expected, block)

        # No drive-wide recursive scan should be introduced.
        self.assertNotIn("rglob(", block)

    def test_existing_report_opens_direct_assessment(self):
        source = (ROOT / "gui" / "persistent_app_a70.py").read_text(
            encoding="utf-8"
        )
        block = source.split("def _open_depot_assessment", 1)[1].split(
            "def run_gui", 1
        )[0]
        self.assertIn("DirectDepotAssessmentDialogA30", block)
        self.assertIn("report_path=report_path", block)


if __name__ == "__main__":
    unittest.main()
