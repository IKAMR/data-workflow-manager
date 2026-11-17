"""Regression: a3 operates on completed DWM Work without opt-in canonical data.

Only synthetic evidence is used here.  No Noark tests, Source reads or
external CLI programs are started by these tests.
"""
from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
import tempfile
import unittest

from noark5_workflow.reporting.qa_decision_v021_a12 import ReportInputError
from noark5_workflow.reporting.qa_work_snapshot_v022_a3 import build_saved_work_snapshot
from noark5_workflow.reporting.qa_workflow_v022_a3 import (
    build_review_snapshot_v022_a3, manual_findings, record_manual_finding,
    ensure_qa_evidence_parent,
)
from noark5_workflow.reporting.qa_review_v021_a13 import record_review
from noark5_workflow.reporting.qa_export_v022_a3 import export_review_bundle_v022_a3


class _User:
    user_id = "test-operator"

    def as_dict(self):
        return {"user_id": self.user_id, "name": "Test Operator"}


class SavedWorkA3(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.work = self.root / "work"
        self.work.mkdir()
        self.uid = "11111111-2222-4333-8444-555555555555"
        self.run = "JOB-002__20261117T012259Z-demo"
        self.report_rel = (
            "noark5_reports/depot_validation/" + self.run + "/depot_validation_report.json"
        )
        self.master_rel = "noark5_tests/xpath/" + self.run + "/master-results.json"
        self.job = {
            "file_type": "dwm-work-job", "format_version": 1, "job_uid": self.uid,
            "job": {"job_id": "JOB-002", "job_uid": self.uid, "name": "content",
                    "profile_id": "noark5", "source_root": "I:\\archive\\1525_005_E-test\\content"},
        }
        self._write("job.json", self.job)
        self.master = {
            "format_version": 1, "source": {"execution_profile": "normal"},
            "tests": [{"test_id": "kdrs.c01", "status": "ok"}],
        }
        self._write(self.master_rel, self.master)
        self.depot = {
            "report_type": "noark5_depot_validation",
            "summary": {"archive_part_count": 1, "folder_count": 7},
            "technical_validation": {
                "status": "ok", "summary": {"ok": 1, "error": 0},
                "reconciliation": {},
                "tests": [{"test_id": "kdrs.c01", "status": "ok"}],
            },
            "archive_parts": [{
                "archive_part": {"system_id": "part-001", "title": "Part one",
                                 "status": "Avsluttet periode"},
                "folder_count": 7, "registration_count": 4, "document_object_count": 5,
            }],
            "deviations": [{"category": "period_source_divergence", "severity": "review",
                            "summary": "Different period end years", "requires_review": True}],
            "evidence": {"source_xpath_run": "I:\\archive\\work\\" + self.run},
            "external_validation": {"arkade5": {"imports": []}},
        }
        self._write(self.report_rel, self.depot)

    def _write(self, relative, value):
        path = self.work / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
        return path

    def _json(self, path):
        return json.loads((self.work / path).read_text(encoding="utf-8"))

    def _add_arkade(self):
        base = "external_evidence/arkade5/IMPORT-002"
        normal_rel = base + "/normalized/arkade5_results.json"
        original_rel = base + "/source/arkade.json"
        pron_rel = base + "/normalized/pronom_statistics.json"
        csv_rel = base + "/source/filformatinfo-statistikk.csv"
        original = self.work / original_rel
        original.parent.mkdir(parents=True, exist_ok=True)
        original.write_bytes(b"original-arkade-result")
        source_hash = sha256(original.read_bytes()).hexdigest()
        p_csv = self.work / csv_rel
        p_csv.parent.mkdir(parents=True, exist_ok=True)
        p_csv.write_bytes(b"Format-ID,RAF-220301,Antall\nfmt/50,Ikke gyldig,1\n")
        csv_hash = sha256(p_csv.read_bytes()).hexdigest()
        self._write(normal_rel, {
            "format_version": 2, "source_system": "Arkade 5",
            "source": {"sha256": source_hash},
            "summary": {"system_name": "ACOS WebSak", "number_of_tests_run": "2 av 2",
                        "number_of_errors": "1", "number_of_warnings": "0"},
            "tests": [
                {"test_id": "N5.01", "source_status": "ok", "results": []},
                {"test_id": "N5.22", "source_status": "error", "number_of_errors": 1,
                 "results": [{"result_type": "Error", "message": "Observed invalid status",
                              "location": {"file_name": "arkivstruktur.xml", "line_numbers": [25]},
                              "result_set_path": ["Archive part"]}]},
            ],
        })
        self._write(pron_rel, {"evidence_type": "arkade5_pronom_format_statistics",
                               "csv": {"rows": [{"Format-ID": "fmt/50", "Filtype": "RTF",
                                                 "RAF-220301": "Ikke gyldig", "Antall": "1"}]}})
        self._write(base + "/manifest.json", {
            "format_version": 2, "import_id": "IMPORT-002",
            "imported_by": {"job_id": "JOB-002"},
            "normalized_file": normal_rel.replace("/", "\\"),
            "source": {"preserved_file": original_rel.replace("/", "\\"),
                       "sha256": source_hash},
            "pronom_evidence": {"statistics": {
                "imported": True, "normalized_file": pron_rel.replace("/", "\\"),
                "preserved_file": csv_rel.replace("/", "\\"), "sha256": csv_hash}},
        })
        self.depot["external_validation"]["arkade5"]["imports"] = [
            {"normalized_file": normal_rel.replace("/", "\\"), "source_sha256": source_hash}
        ]
        self._write(self.report_rel, self.depot)
        return original_rel

    def test_completed_work_loads_without_canonical_or_extra_writes(self):
        self.assertFalse((self.work / "noark5_evidence").exists())
        snapshot = build_review_snapshot_v022_a3(work=self.work, depot_report=self.report_rel)
        self.assertEqual(snapshot["work_identity"]["job_id"], "JOB-002")
        self.assertEqual(snapshot["work_identity"]["job_uid"], self.uid)
        self.assertEqual(snapshot["dwm_summary"]["folder_count"], 7)
        self.assertEqual(len(snapshot["archive_parts"]), 1)
        self.assertEqual(len(snapshot["findings"]), 1)
        self.assertFalse((self.work / "noark5_evidence").exists())

    def test_arkade_and_historical_pronom_remain_separate(self):
        self._add_arkade()
        snapshot = build_review_snapshot_v022_a3(work=self.work)
        self.assertEqual(snapshot["arkade"]["test_count"], 2)
        self.assertEqual(snapshot["arkade"]["summary"]["number_of_errors"], "1")
        self.assertEqual(len(snapshot["arkade"]["findings"]), 1)
        self.assertEqual(snapshot["arkade"]["findings"][0]["lines"], [25])
        historical = [f for f in snapshot["findings"] if f["test_id"].startswith("RAF-220301:")]
        self.assertEqual(len(historical), 1)
        self.assertEqual(historical[0]["severity"], "REVIEW")
        self.assertFalse((self.work / "noark5_evidence").exists())

    def test_wrong_work_or_report_is_rejected(self):
        self.job["job"]["job_uid"] = "another-work"
        self._write("job.json", self.job)
        with self.assertRaises(ReportInputError):
            build_saved_work_snapshot(self.work)
        self.job["job"]["job_uid"] = self.uid
        self._write("job.json", self.job)
        self.depot["evidence"]["source_xpath_run"] = "I:\\elsewhere\\JOB-001__old"
        self._write(self.report_rel, self.depot)
        with self.assertRaises(ReportInputError):
            build_saved_work_snapshot(self.work)

    def test_modified_arkade_source_is_rejected_not_silently_accepted(self):
        original_rel = self._add_arkade()
        original = self.work / original_rel
        original.write_bytes(b"changed-after-import")
        with self.assertRaisesRegex(ReportInputError, "SHA-256"):
            build_saved_work_snapshot(self.work)

    def test_master_status_disagreement_is_rejected(self):
        self.master["tests"][0]["status"] = "error"
        self._write(self.master_rel, self.master)
        with self.assertRaisesRegex(ReportInputError, "status"):
            build_saved_work_snapshot(self.work)

    def test_manual_finding_saved_in_new_event_directory_without_canonical(self):
        snapshot = build_review_snapshot_v022_a3(work=self.work)
        before = (self.work / "job.json").read_bytes()
        record_manual_finding(self.work, snapshot, severity="REVIEW",
                              message="Manual observation", user=_User())
        self.assertEqual(len(manual_findings(self.work, snapshot)), 1)
        self.assertFalse((self.work / "noark5_evidence/canonical-results.json").exists())
        self.assertEqual((self.work / "job.json").read_bytes(), before)

    def test_existing_review_works_after_first_parent_creation(self):
        snapshot = build_review_snapshot_v022_a3(work=self.work)
        ensure_qa_evidence_parent(self.work)
        result = record_review(self.work, snapshot, snapshot["findings"][0],
                               status="requires_clarification", comment="Needs explanation",
                               user=_User(), include_in_ks=True, include_in_depot=True)
        self.assertEqual(result["status"], "requires_clarification")
        self.assertFalse((self.work / "noark5_evidence/canonical-results.json").exists())

    def test_reports_export_without_any_new_noark_run(self):
        # A3 report export relies only on existing Work evidence and does not
        # depend on previous manual canonical projection.
        target = self.root / "export"
        result = export_review_bundle_v022_a3(work=self.work, output_dir=target,
                                               depot_report=self.report_rel, report_jobs=())
        self.assertTrue(result["index"].is_file())
        self.assertTrue((target / "rapporter/01-kvalitetssikring-arkivskaper.html").is_file())
        self.assertTrue((target / "rapporter/02-depot-godkjenning-ferdigstilling.html").is_file())
        self.assertTrue((target / "avviksregister.html").is_file())
        self.assertFalse(result["manifest"]["automatic_approval"])
        self.assertFalse((self.work / "noark5_evidence").exists())


if __name__ == "__main__":
    unittest.main()
