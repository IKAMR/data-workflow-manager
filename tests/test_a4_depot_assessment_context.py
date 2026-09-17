import json
import tempfile
import unittest
from pathlib import Path

from gui.depot_assessment_dialog import latest_depot_report, report_summary_text

ROOT = Path(__file__).resolve().parents[1]


class A4DepotAssessmentContextTests(unittest.TestCase):
    def test_latest_report_is_found_under_active_job_work_operations(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            older = root / "noark5_reports" / "depot_validation" / "20260913-100000"
            newer = root / "noark5_reports" / "depot_validation" / "20260913-110000"
            older.mkdir(parents=True)
            newer.mkdir(parents=True)
            (older / "depot_validation_report.json").write_text("{}", encoding="utf-8")
            latest = newer / "depot_validation_report.json"
            latest.write_text("{}", encoding="utf-8")
            self.assertEqual(latest_depot_report(root), latest)

    def test_summary_uses_existing_report_model_without_reanalysis(self):
        model = {
            "summary": {"archive_part_count": 3, "document_object_count": 42},
            "technical_validation": {
                "status": "error",
                "summary": {"ok": 10, "error": 1, "legacy_disabled": 2, "other": 0},
                "reconciliation": {"match": 8, "mismatch": 1, "not_comparable": 0, "other": 0},
            },
            "deviations": [
                {"severity": "serious", "summary": "1 reconciliation-avvik er registrert."}
            ],
        }
        text = report_summary_text(model)
        self.assertIn("Arkivdeler: 3", text)
        self.assertIn("Dokumentobjekter: 42", text)
        self.assertIn("Status: error", text)
        self.assertIn("mismatch 1", text)
        self.assertIn("1 reconciliation-avvik er registrert.", text)

    def test_dialog_has_full_report_action_and_active_job_context(self):
        dialog = (ROOT / "gui" / "depot_assessment_dialog.py").read_text(encoding="utf-8")
        runtime = (ROOT / "gui" / "persistent_app_a19.py").read_text(encoding="utf-8")
        self.assertIn('text="Åpne full rapport"', dialog)
        self.assertIn("report_summary_text", dialog)
        self.assertIn("latest_depot_report", dialog)
        self.assertIn("self.current_job.work_operations", runtime)
        self.assertIn("work_operations=work_operations", runtime)

    def test_save_confirmation_does_not_dump_long_paths(self):
        dialog = (ROOT / "gui" / "depot_assessment_dialog.py").read_text(encoding="utf-8")
        self.assertNotIn("Vurderingsfil: {result['assessment_file']}", dialog)
        self.assertNotIn("Vurdert rapport: {result['assessed_report_json']}", dialog)
        self.assertIn("skrevet ved siden av originalrapporten", dialog)


if __name__ == "__main__":
    unittest.main()
