"""DWM v0.2.2-a3: source-bound manual findings and draft reporting.

Run with: py -m unittest tests.test_v022_a3_qa_workflow -v
The existing DWM test.bat must additionally run on Windows.
"""
from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from noark5_workflow.reporting.qa_review_v021_a13 import (
    ReviewError, finding_key, record_review, with_selected_reviews,
)
from noark5_workflow.reporting.qa_workflow_v022_a3 import (
    attach_a3_findings, finding_summary, manual_findings,
    record_manual_finding,
)
from noark5_workflow.reporting.qa_export_v022_a3 import (
    _register_csv, _render_register, export_review_bundle_v022_a3, register_rows,
)


class _User:
    user_id = "qa-tester"

    def as_dict(self):
        return {"user_id": self.user_id, "name": "Testoperatør", "username": "test"}


class ManualFindingsA3(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.work = self.root / "work"
        self.work.mkdir()
        (self.work / "noark5_evidence").mkdir()
        (self.work / "job.json").write_text(
            json.dumps({"job_uid": "stable-uid-002", "job": {"job_id": "JOB-002"}}), encoding="utf-8")
        self.rel = "noark5_reports/depot_validation/JOB-002__run/depot_validation_report.json"
        self.report = self.work / self.rel
        self.report.parent.mkdir(parents=True)
        self.report.write_text('{"report_type":"noark5_depot_validation","technical_validation":{"tests":[{"test_id":"kdrs.c01","status":"ok"}]}}', encoding="utf-8")
        self.snapshot = self._snapshot()
        self.user = _User()

    def tearDown(self):
        self.temp.cleanup()

    def _snapshot(self):
        return {
            "model_id": "ikamr.dwm.noark5.qa-decision.a12.v1",
            "work_identity": {"job_uid": "stable-uid-002", "job_id": "JOB-002",
                              "extraction_label": "1525_005"},
            "dwm_report_source": self.rel,
            "evidence_manifest": [{"kind": "dwm_depot", "path": self.rel,
                                   "sha256": sha256(self.report.read_bytes()).hexdigest()}],
            "arkade": {"source": None, "summary": {}, "findings": []},
            "findings": [{"source": "DWM depotvalidering", "test_id": "period_source_divergence",
                          "severity": "REVIEW", "message": "Ulike sluttår", "context": "",
                          "file": "", "lines": [], "source_ref": self.rel,
                          "requires_review": True}],
        }

    def test_gui_shortcuts_preserve_existing_qa_and_report_workflow(self):
        root = Path(__file__).resolve().parents[1]
        main = (root / "gui_qt/main_v020_a6.py").read_text(encoding="utf-8")
        dialog = (root / "gui_qt/qa_workflow_v022_a3.py").read_text(encoding="utf-8")
        self.assertIn("Avvik, kvalitetssikring og godkjenning", main)
        self.assertIn("_a2_overview_page", main)
        self.assertIn("install_qa_review_panel", main)
        self.assertIn("_a12_open_result_center", main)
        self.assertIn("QaFindingReviewDialogV022A3", dialog)
        self.assertIn("export_review_bundle_v022_a3", dialog)
        self.assertNotIn("install_dropdown_positioning", dialog)

    def test_append_only_manual_finding_preserves_source(self):
        before = self.report.read_bytes()
        event = record_manual_finding(
            self.work, self.snapshot, severity="warning", message="Manglende saksopplysning",
            context="Arkivdel X", file="arkivstruktur.xml", user=self.user)
        self.assertEqual(event["severity"], "WARNING")
        records = manual_findings(self.work, self.snapshot)
        self.assertEqual(len(records), 1)
        self.assertTrue(records[0]["test_id"].startswith("MAN-"))
        self.assertIn("Manuell", records[0]["source"])
        self.assertEqual(self.report.read_bytes(), before)
        self.assertEqual(len(list((self.work / "noark5_evidence/qa_manual_findings_v022_a3").glob("*.json"))), 1)

    def test_old_revision_is_not_current_and_history_is_preserved(self):
        record_manual_finding(self.work, self.snapshot, severity="ERROR", message="Kontroller kilde", user=self.user)
        self.report.write_text('{"changed":true}', encoding="utf-8")
        revised = self._snapshot()
        self.assertEqual(manual_findings(self.work, revised), [])
        self.assertEqual(len(list((self.work / "noark5_evidence/qa_manual_findings_v022_a3").glob("*.json"))), 1)
        with self.assertRaises(ReviewError):
            manual_findings(self.work, self.snapshot)

    def test_tamper_detection_and_unknown_values(self):
        with self.assertRaises(ReviewError):
            record_manual_finding(self.work, self.snapshot, severity="PASS", message="Wrong", user=self.user)
        with self.assertRaises(ReviewError):
            record_manual_finding(self.work, self.snapshot, severity="NOTE", message="  ", user=self.user)
        event = record_manual_finding(self.work, self.snapshot, severity="REVIEW", message="Original", user=self.user)
        path = self.work / "noark5_evidence/qa_manual_findings_v022_a3" / (event["event_id"] + ".json")
        changed = json.loads(path.read_text(encoding="utf-8"))
        changed["message"] = "Endret"
        path.write_text(json.dumps(changed), encoding="utf-8")
        with self.assertRaises(ReviewError):
            manual_findings(self.work, self.snapshot)

    def test_all_findings_and_reviews_are_accounted_for(self):
        record_manual_finding(self.work, self.snapshot, severity="ERROR", message="=formel", user=self.user)
        extended = attach_a3_findings(self.work, self.snapshot)
        self.assertEqual(len(extended["findings"]), 2)
        self.assertEqual(extended["a3_finding_summary"]["manual_findings"], 1)
        original = extended["findings"][0]
        record_review(self.work, extended, original,
                      status="requires_clarification", comment="Kontakt arkivskaper",
                      include_in_ks=True, include_in_depot=False, user=self.user)
        state = finding_summary(self.work, extended)
        self.assertEqual((state["total"], state["reviewed"], state["unreviewed"]), (2, 1, 1))
        selected = with_selected_reviews(self.work, extended)
        rows = register_rows(selected, self.work)
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["comment"], "Kontakt arkivskaper")
        self.assertTrue(rows[0]["include_in_ks"])
        self.assertFalse(rows[0]["include_in_depot"])
        self.assertEqual(rows[1]["professional_status"], "Ikke vurdert")
        self.assertIn(b"'=formel", _register_csv(rows))
        html = _render_register(rows, selected, state)
        self.assertIn("UTKAST", html)
        self.assertIn("Kontakt arkivskaper", html)

    def test_review_not_selected_does_not_export_private_note(self):
        extended = attach_a3_findings(self.work, self.snapshot)
        record_review(self.work, extended, extended["findings"][0],
                      status="context_documented", comment="INTERN HEMMELIG MERKNAD",
                      include_in_ks=False, include_in_depot=False, user=self.user)
        selected = with_selected_reviews(self.work, extended)
        rows = register_rows(selected, self.work)
        self.assertNotIn("INTERN HEMMELIG MERKNAD", _render_register(rows, selected,
                                                                     finding_summary(self.work, selected)))
        self.assertNotIn(b"INTERN HEMMELIG", _register_csv(rows))
        self.assertEqual(rows[0]["professional_status"], "Vurdert internt (ikke valgt til eksport)")

    def test_historic_raf_candidates_are_not_called_normative_failures(self):
        rel = "external_evidence/arkade5/IMPORT/normalized/pronom_statistics.json"
        path = self.work / rel
        path.parent.mkdir(parents=True)
        payload = {"evidence_type": "arkade5_pronom_format_statistics",
                   "source": {"original_name": "filformatinfo-statistikk.csv"},
                   "csv": {"rows": [{"Format-ID": "fmt/50", "Filtype": "RTF",
                                     "RAF-220301": "Ikke gyldig", "Antall": "1"},
                                    {"Format-ID": "fmt/354", "Filtype": "PDF/A",
                                     "RAF-220301": "Gyldig", "Antall": "796"}]}}
        path.write_text(json.dumps(payload), encoding="utf-8")
        self.snapshot["arkade"]["source"] = "external_evidence/arkade5/IMPORT/normalized/arkade5_results.json"
        self.snapshot["evidence_manifest"].append(
            {"kind": "external", "path": rel, "sha256": sha256(path.read_bytes()).hexdigest()})
        merged = attach_a3_findings(self.work, self.snapshot)
        self.assertEqual(len(merged["findings"]), 2)
        flagged = merged["findings"][-1]
        self.assertEqual(flagged["severity"], "REVIEW")
        self.assertIn("historisk", flagged["source"])
        self.assertIn("dagens valgt regelprofil separat", flagged["message"])

    def test_html_escapes_untrusted_manual_text(self):
        record_manual_finding(self.work, self.snapshot, severity="REVIEW",
                              message="<script>alert(1)</script>", user=self.user)
        extended = with_selected_reviews(self.work, attach_a3_findings(self.work, self.snapshot))
        rendered = _render_register(register_rows(extended, self.work), extended,
                                    finding_summary(self.work, extended))
        self.assertNotIn("<script>", rendered)
        self.assertIn("&lt;script&gt;", rendered)

    def test_failed_dwm_xpath_not_conflated_with_success(self):
        payload = {"technical_validation": {"tests": [
            {"test_id": "kdrs.c01", "status": "ok"},
            {"test_id": "kdrs.c20", "status": "error", "test_point": "N5.22"},
            {"test_id": "kdrs.c21", "status": "not_run"}]}}
        self.report.write_text(json.dumps(payload), encoding="utf-8")
        updated = self._snapshot()
        merged = attach_a3_findings(self.work, updated)
        non_ok = [x for x in merged["findings"] if x["source"].startswith("DWM – XPath")]
        self.assertEqual(len(non_ok), 2)
        self.assertEqual([x["severity"] for x in non_ok], ["ERROR", "REVIEW"])
        self.assertEqual(merged["a3_finding_summary"]["dwm_non_ok_tests"], 2)

    def test_atomic_export_and_failure_cleanup_without_rerunning_analyses(self):
        snapshot = with_selected_reviews(self.work, attach_a3_findings(self.work, self.snapshot))
        destination = self.root / "completed"

        def fake_publisher(s, target, *, work):
            Path(target).mkdir()
            (Path(target) / "01-kvalitetssikring-arkivskaper.html").write_text("UTKAST", encoding="utf-8")
            (Path(target) / "02-depot-godkjenning-ferdigstilling.html").write_text("UTKAST", encoding="utf-8")
            (Path(target) / "rapportgrunnlag.json").write_text("{}", encoding="utf-8")
            (Path(target) / "evidensmanifest.json").write_text("{}", encoding="utf-8")

        module = "noark5_workflow.reporting.qa_export_v022_a3"
        with patch(module + ".build_review_snapshot_v022_a3", return_value=snapshot), \
             patch(module + ".publish_a12", side_effect=fake_publisher):
            out = export_review_bundle_v022_a3(work=self.work, output_dir=destination)
        self.assertTrue(Path(out["index"]).is_file())
        self.assertTrue((destination / "avviksregister.json").is_file())
        self.assertTrue((destination / "rapporter/01-kvalitetssikring-arkivskaper.html").is_file())
        self.assertTrue((destination / "rapporter/02-depot-godkjenning-ferdigstilling.html").is_file())
        self.assertFalse(out["manifest"]["automatic_approval"])
        self.assertFalse(out["technical_a20_included"])
        with patch(module + ".build_review_snapshot_v022_a3", return_value=snapshot), \
             self.assertRaises(FileExistsError):
            export_review_bundle_v022_a3(work=self.work, output_dir=destination)
        fail_target = self.root / "broken"
        with patch(module + ".build_review_snapshot_v022_a3", return_value=snapshot), \
             patch(module + ".publish_a12", side_effect=ValueError("source changed")):
            with self.assertRaises(ValueError):
                export_review_bundle_v022_a3(work=self.work, output_dir=fail_target)
        self.assertFalse(fail_target.exists())
        self.assertEqual(list(self.root.glob(".dwm-a3-*")), [])


if __name__ == "__main__":
    unittest.main()
