"""v0.1.9-a2: independent depot decisions and Work-local professional review."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import sys
import tempfile
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import patch

from app.depot_review_v019_a2 import (
    PART_FILE, STATUS_LABELS, _verified_report, build_depot_review_rows,
    load_part_decisions, record_depot_review, record_part_decision,
)


@dataclass(frozen=True)
class _User:
    user_id: str = "valid-uid"
    username: str = "tester"
    name: str = "Test User"
    email: str = "tester@example.invalid"

    def as_dict(self):
        return dict(user_id=self.user_id, username=self.username, name=self.name, email=self.email)


class DepotReviewA2Tests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.work = self.root / "dwm"
        folder = self.work / "noark5_reports" / "depot_validation" / "JOB-001__RUN-1"
        folder.mkdir(parents=True)
        self.report = folder / "depot_validation_report.json"
        self.data = {
            "report_type": "noark5_depot_validation", "run_id": "RUN-1",
            "summary": {"archive_part_count": 2, "folder_count": 5},
            "technical_validation": {"status": "complete_with_findings"},
            "assessment": {"status": "accepted", "automatic_decision": True},
            "archive_parts": [
                {"archive_part": {"system_id": "AD-1", "title": "Saksarkiv"}, "folder_count": 4},
                {"archive_part": {"system_id": "AD-2", "title": "Historisk"}},
            ],
            "deviations": [{"requires_review": True, "summary": "XML referanser"}],
            "period_reconciliation": {
                "declared_period": {"start_year": 2017, "end_year": 2020},
                "archive_parts": [
                    {"archive_part": {"system_id": "AD-1"},
                     "observed_period": {"first_year": 2017, "last_year": 2019}},
                ],
            },
        }
        self.write_report()
        self.depot_stub = ModuleType("noark5_workflow.analysis.depot_assessment")
        self.depot_stub.ASSESSMENT_STATUSES = tuple(STATUS_LABELS)
        self.depot_stub.load_depot_assessment = lambda path: None
        self.depot_stub.record_depot_assessment = lambda path, **kwargs: {"whole": True, "options": kwargs}
        self.identity_stub = ModuleType("noark5_workflow.core.identity")
        self.identity_stub.UserIdentity = _User
        self.period_stub = ModuleType("app.result_evidence_v018_a13")
        self.period_stub.period_rows = lambda shots: []

    def write_report(self):
        self.report.write_text(json.dumps(self.data), encoding="utf-8")

    def _packages(self):
        return patch.dict(sys.modules, {
            "noark5_workflow.analysis.depot_assessment": self.depot_stub,
            "noark5_workflow.core.identity": self.identity_stub,
            "app.result_evidence_v018_a13": self.period_stub,
        })

    def make_shot(self, *, uid="uuid-A", job_id="JOB-001"):
        return SimpleNamespace(
            job=SimpleNamespace(job_uid=uid, job_id=job_id, name="Production", work=self.work),
            results=SimpleNamespace(depot_report_path=self.report), depot=self.data,
        )

    def test_part_decision_is_explicit_and_keeps_history(self):
        report_hash = hashlib.sha256(self.report.read_bytes()).hexdigest()
        with self._packages():
            first = record_part_decision(self.report, "AD-1", status="requires_clarification",
                                         reason="Need original evidence", user=_User())
            second = record_part_decision(self.report, "AD-1", status="accepted_with_deviation",
                                          reason="Deviation documented", user=_User())
        doc = load_part_decisions(self.report)
        self.assertEqual(first["history_count"], 1)
        self.assertEqual(second["history_count"], 2)
        self.assertEqual(len(doc["parts"]), 1)
        self.assertEqual(len(doc["parts"]["AD-1"]["history"]), 2)
        self.assertEqual(doc["parts"]["AD-1"]["current"]["status"], "accepted_with_deviation")
        self.assertEqual(doc["parts"]["AD-1"]["current"]["user"]["user_id"], "valid-uid")
        self.assertEqual(doc["report"]["sha256"], report_hash)
        self.assertEqual(hashlib.sha256(self.report.read_bytes()).hexdigest(), report_hash)
        self.assertTrue(self.report.with_name(PART_FILE).samefile(second["file"]))

    def test_another_part_keeps_first_part_unchanged(self):
        with self._packages():
            record_part_decision(self.report, "AD-1", status="accepted", reason="Reviewed A", user=_User())
            record_part_decision(self.report, "AD-2", status="requires_clarification",
                                 reason="Reviewed B", user=_User())
        stored = load_part_decisions(self.report)
        self.assertEqual(len(stored["parts"]), 2)
        self.assertEqual(stored["parts"]["AD-1"]["current"]["status"], "accepted")
        self.assertEqual(stored["parts"]["AD-2"]["current"]["status"], "requires_clarification")

    def test_changed_report_blocks_reuse_or_overwrite_of_old_review(self):
        with self._packages():
            record_part_decision(self.report, "AD-1", status="accepted", reason="OK", user=_User())
            sidecar_before = self.report.with_name(PART_FILE).read_bytes()
            self.data["summary"]["folder_count"] = 99
            self.write_report()
            with self.assertRaisesRegex(ValueError, "annen rapportversjon"):
                load_part_decisions(self.report)
            with self.assertRaisesRegex(ValueError, "annen rapportversjon"):
                record_part_decision(self.report, "AD-1", status="accepted", reason="Retry", user=_User())
        self.assertEqual(sidecar_before, self.report.with_name(PART_FILE).read_bytes())

    def test_unknown_part_and_duplicate_ids_blocked(self):
        with self._packages():
            with self.assertRaises(ValueError):
                record_part_decision(self.report, "KDRS-U2-1", status="accepted", reason="No", user=_User())
            self.data["archive_parts"].append({"archive_part": {"system_id": "AD-1"}})
            self.write_report()
            with self.assertRaises(ValueError):
                record_part_decision(self.report, "AD-1", status="accepted", reason="No", user=_User())
        self.assertFalse(self.report.with_name(PART_FILE).exists())

    def test_reason_identity_status_and_timestamp_validated(self):
        with self._packages():
            for options in (
                dict(status="accepted", reason="  ", user=_User()),
                dict(status="auto_accepted", reason="No", user=_User()),
                dict(status="accepted", reason="No", user=None),
                dict(status="accepted", reason="No", user=_User(), assessed_at="2026-11-04T12:00:00"),
            ):
                with self.assertRaises(ValueError):
                    record_part_decision(self.report, "AD-1", **options)
        self.assertFalse(self.report.with_name(PART_FILE).exists())

    def test_original_generated_assessment_is_not_human_approval(self):
        with self._packages():
            rows = build_depot_review_rows((self.make_shot(),))
        self.assertEqual(len(rows), 3)
        self.assertEqual(rows[0].professional_status, "Ikke vurdert")
        self.assertEqual(rows[0].technical_status, "complete_with_findings")
        self.assertEqual(rows[0].deviation_count, 1)
        self.assertEqual(rows[1].scope, "arkivdel")
        self.assertEqual(rows[1].native_id, "AD-1")
        self.assertEqual(rows[2].native_id, "AD-2")
        self.assertEqual(rows[1].deviation_count, None)
        self.assertTrue(rows[1].editable)
        self.assertIn("opprinnelig_automatisk_vurdering", rows[0].details)

    def test_review_reloads_human_status_and_per_part_status(self):
        with self._packages():
            record_part_decision(self.report, "AD-1", status="accepted_with_deviation",
                                 reason="Real decision", user=_User())
            self.depot_stub.load_depot_assessment = lambda path: {
                "current": {"status": "requires_clarification", "assessed_at": "2026-11-04T09:00:00Z"},
                "history": [{"status": "requires_clarification"}],
            }
            rows = build_depot_review_rows((self.make_shot(),))
        self.assertEqual(rows[0].professional_status, "Krever avklaring")
        self.assertEqual(rows[0].history_count, 1)
        self.assertEqual(rows[1].professional_status, "Akseptert med avvik")
        self.assertEqual(rows[1].history_count, 1)
        self.assertEqual(rows[2].professional_status, "Ikke vurdert")

    def test_stale_part_history_does_not_block_whole_decision(self):
        with self._packages():
            record_part_decision(self.report, "AD-1", status="accepted", reason="OK", user=_User())
            self.data["summary"]["folder_count"] = 6
            self.write_report()
            rows = build_depot_review_rows((self.make_shot(),))
        self.assertTrue(rows[0].editable)
        self.assertFalse(rows[1].editable)
        self.assertIn("Historikk krever kontroll", rows[1].professional_status)

    def test_work_missing_and_duplicate_uid_not_double_counted(self):
        shot = self.make_shot()
        offline = SimpleNamespace(job=shot.job,
            results=SimpleNamespace(depot_report_path=self.root / "lost.json"), depot=None)
        with self._packages():
            rows = build_depot_review_rows((offline,))
            duplicate = build_depot_review_rows((shot, self.make_shot(job_id="JOB-002")))
        self.assertEqual(len(rows), 1)
        self.assertFalse(rows[0].editable)
        self.assertIsNone(rows[0].deviation_count)
        self.assertEqual(len(duplicate), 3)

    def test_reports_outside_work_are_never_accepted_for_review(self):
        outside = self.root / "depot_validation_report.json"
        outside.write_bytes(self.report.read_bytes())
        self.assertIsNone(_verified_report(self.work, outside))
        self.assertEqual(_verified_report(self.work, self.report), self.report.resolve(strict=True))

    def test_selected_report_changed_before_click_blocks_decision(self):
        with self._packages():
            row = build_depot_review_rows((self.make_shot(),))[0]
            self.data["summary"]["folder_count"] = 10
            self.write_report()
            with self.assertRaisesRegex(ValueError, "endret"):
                record_depot_review(row, status="accepted", reason="OK", user=_User())

    def test_whole_review_is_delegated_to_legacy_audited_engine(self):
        with self._packages():
            row = build_depot_review_rows((self.make_shot(),))[0]
            result = record_depot_review(row, status="requires_clarification", reason="Explain",
                                         user=_User())
        self.assertTrue(result["whole"])
        self.assertEqual(result["options"]["status"], "requires_clarification")
        self.assertTrue(result["options"]["render_html"])

    def test_report_work_identity_cannot_be_rebound(self):
        with self._packages():
            record_part_decision(self.report, "AD-1", status="accepted", reason="First",
                                 user=_User(), job_uid="uuid-a")
            before = self.report.with_name(PART_FILE).read_bytes()
            with self.assertRaisesRegex(ValueError, "annen Work-jobbidentitet"):
                record_part_decision(self.report, "AD-2", status="accepted", reason="Second",
                                     user=_User(), job_uid="uuid-b")
            self.assertEqual(before, self.report.with_name(PART_FILE).read_bytes())

    def test_invalid_part_history_never_silently_discarded(self):
        sidecar = self.report.with_name(PART_FILE)
        sidecar.write_text(json.dumps({
            "format_version": 1,
            "report": {"filename": self.report.name,
                       "sha256": hashlib.sha256(self.report.read_bytes()).hexdigest()},
            "parts": {"AD-1": {"current": "bad", "history": []}},
        }), encoding="utf-8")
        before = sidecar.read_bytes()
        with self._packages():
            with self.assertRaisesRegex(ValueError, "ugyldig innhold"):
                record_part_decision(self.report, "AD-1", status="accepted", reason="No",
                                     user=_User())
        self.assertEqual(before, sidecar.read_bytes())

    def test_source_provenance_kept_separate_from_decision(self):
        source = SimpleNamespace(job_uid="uuid-A", source="KDRS Query", import_id="K-11",
                                 status="Imported, not approved", count=None,
                                 unit="reports", sha256="deadbeef")
        with self._packages():
            row = build_depot_review_rows((self.make_shot(),), sources=(source,))[0]
        data = row.details["evidenskilder"]
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["kilde"], "KDRS Query")
        self.assertIsNone(data[0]["antall"])
        self.assertEqual(data[0]["sha256"], "deadbeef")


if __name__ == "__main__":
    unittest.main()
