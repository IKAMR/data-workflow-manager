import json
import tempfile
import unittest
from pathlib import Path

from noark5_workflow.analysis.depot_assessment import (
    load_depot_assessment,
    record_depot_assessment,
)
from noark5_workflow.core.identity import UserIdentity


class A1DepotAssessmentTests(unittest.TestCase):
    def _report(self, root: Path) -> Path:
        path = root / "depot_validation_report.json"
        path.write_text(
            json.dumps(
                {
                    "depot_report_model_format_version": 2,
                    "report_type": "noark5_depot_validation",
                    "summary": {},
                    "technical_validation": {
                        "status": "ok",
                        "summary": {"ok": 0, "legacy_disabled": 0, "error": 0, "other": 0},
                        "reconciliation": {"match": 0, "mismatch": 0, "not_comparable": 0, "other": 0},
                        "tests": [],
                    },
                    "archive_parts": [],
                    "standard_values": {
                        "summary": {
                            "tests_with_checks": 0,
                            "status_counts": {
                                "all_observed_values_standard": 0,
                                "additional_observed_values": 0,
                                "no_observed_values": 0,
                                "other": 0,
                            },
                        },
                        "tests": [],
                    },
                    "deviations": [],
                    "assessment": {
                        "status": "requires_clarification",
                        "automatic_decision": False,
                        "reason": "Avventer faglig vurdering.",
                        "archive_creator_responsibility": "Arkivskaper er ansvarlig for innholdet.",
                        "new_extraction_guidance": "Nytt uttrekk vurderes ved alvorlige mangler.",
                    },
                    "evidence": {
                        "source_presentation_profile": "depot",
                        "source_presentation_file": "presentations/depot.json",
                        "source_view_ids": [],
                    },
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        return path

    def _user(self) -> UserIdentity:
        return UserIdentity(
            user_id="user-1",
            username="tester",
            name="Test Bruker",
            email="tester@example.invalid",
        )

    def test_assessment_is_bound_to_exact_report_and_preserves_history(self):
        with tempfile.TemporaryDirectory() as tmp:
            report = self._report(Path(tmp))
            first = record_depot_assessment(
                report,
                status="requires_clarification",
                reason="Må avklares med arkivskaper.",
                user=self._user(),
                assessed_at="2026-09-13T18:00:00+02:00",
                render_html=False,
            )
            second = record_depot_assessment(
                report,
                status="accepted_with_deviation",
                reason="Avvik dokumentert og vurdert.",
                user=self._user(),
                assessed_at="2026-09-13T18:05:00+02:00",
                render_html=False,
            )

            stored = load_depot_assessment(report)
            self.assertEqual(2, second["history_count"])
            self.assertEqual(2, len(stored["history"]))
            self.assertEqual("accepted_with_deviation", stored["current"]["status"])
            self.assertEqual("user-1", stored["current"]["user"]["user_id"])

            assessed = json.loads(
                Path(second["assessed_report_json"]).read_text(encoding="utf-8")
            )
            self.assertEqual("accepted_with_deviation", assessed["assessment"]["status"])
            self.assertFalse(assessed["assessment"]["automatic_decision"])
            self.assertEqual(2, assessed["assessment_evidence"]["history_count"])
            self.assertNotEqual(
                first["assessment"]["assessment_id"],
                second["assessment"]["assessment_id"],
            )

    def test_changed_report_rejects_existing_assessment(self):
        with tempfile.TemporaryDirectory() as tmp:
            report = self._report(Path(tmp))
            record_depot_assessment(
                report,
                status="accepted",
                reason="Kontrollert.",
                user=self._user(),
                render_html=False,
            )
            model = json.loads(report.read_text(encoding="utf-8"))
            model["summary"]["folder_count"] = 123
            report.write_text(json.dumps(model), encoding="utf-8")
            with self.assertRaises(ValueError):
                load_depot_assessment(report)

    def test_reason_and_known_status_are_required(self):
        with tempfile.TemporaryDirectory() as tmp:
            report = self._report(Path(tmp))
            with self.assertRaises(ValueError):
                record_depot_assessment(
                    report,
                    status="auto_accepted",
                    reason="Nei",
                    user=self._user(),
                    render_html=False,
                )
            with self.assertRaises(ValueError):
                record_depot_assessment(
                    report,
                    status="accepted",
                    reason="   ",
                    user=self._user(),
                    render_html=False,
                )


if __name__ == "__main__":
    unittest.main()
