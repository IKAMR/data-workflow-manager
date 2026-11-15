"""a13 regression: Work review events, recipient selection, and a20 coexistence."""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import importlib.util
import json
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
spec = importlib.util.spec_from_file_location("_a12_fixture_v021_a13", ROOT / "tests/test_v021_a12_qa_decision.py")
baseline = importlib.util.module_from_spec(spec)
spec.loader.exec_module(baseline)
from noark5_workflow.reporting.qa_decision_v021_a12 import (
    build_snapshot, render_reports, ReportInputError,
)
from noark5_workflow.reporting.qa_decision_v021_a13 import (
    BUNDLE_MODEL, build_review_snapshot, export_review_bundle, main,
)
from noark5_workflow.reporting.qa_review_v021_a13 import (
    REVIEW_DIR, ReviewError, finding_key, latest_reviews, record_review,
    with_selected_reviews,
)


class FakeUser:
    user_id = "depot-faglig-1"

    def as_dict(self):
        return {"user_id": self.user_id, "display_name": "Faglig tester"}


@dataclass
class FakeJob:
    job_id: str
    job_uid: str
    effective_work_operations: Path


class A13ReviewAndReport(unittest.TestCase):
    def setUp(self):
        self.fixture = baseline.A12Reports("test_two_distinct_reports_and_unapproved_status")
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.root = self.fixture.root
        self.work = self.fixture.work
        self.output = self.fixture.output
        self.snapshot = self.fixture.build()
        self.finding = self.snapshot["findings"][1]
        self.user = FakeUser()

    def save(self, **kw):
        opts = {"status": "context_documented", "comment": "Historisk verdi – krever faglig kontekst",
                "user": self.user, "recorded_at": "2026-11-15T22:00:00+00:00"}
        opts.update(kw)
        return record_review(self.work, self.snapshot, self.finding, **opts)

    def test_one_immutable_work_event_and_no_source_changes(self):
        old = {p: sha256(p.read_bytes()).hexdigest() for p in (
            self.fixture.canonical, self.fixture.ext, self.fixture.ark, self.fixture.depot,
            self.fixture.index, self.fixture.master)}
        first = self.save()
        self.assertEqual(first["status"], "context_documented")
        folder = self.work / REVIEW_DIR
        self.assertEqual(len(list(folder.glob("*.json"))), 1)
        record = latest_reviews(self.work, self.snapshot)
        self.assertEqual(record["current"][finding_key(self.finding)]["comment"], first["comment"])
        second = self.save(comment="Revidert merknad", include_in_ks=False)
        self.assertNotEqual(first["event_id"], second["event_id"])
        self.assertEqual(len(list(folder.glob("*.json"))), 2)
        self.assertEqual(latest_reviews(self.work, self.snapshot)["current"][finding_key(self.finding)]["comment"],
                         "Revidert merknad")
        self.assertEqual(old, {p: sha256(p.read_bytes()).hexdigest() for p in old})

    def test_comments_are_scoped_to_selected_report_and_html_escaped(self):
        self.save(comment="<script>falsk</script> – dokumentert kontekst", include_in_depot=False)
        enriched = with_selected_reviews(self.work, self.snapshot)
        self.assertTrue(enriched["report_status"].startswith("DRAFT"))
        self.assertFalse(enriched["depot_formal_decision_registered_by_a12"])
        self.assertEqual(enriched["a13_review_summary"]["selected_for_ks"], 1)
        self.assertEqual(enriched["a13_review_summary"]["selected_for_depot"], 0)
        html = render_reports(enriched)
        ks = html["01-kvalitetssikring-arkivskaper.html"]
        depot = html["02-depot-godkjenning-ferdigstilling.html"]
        self.assertIn("&lt;script&gt;falsk&lt;/script&gt;", ks)
        self.assertNotIn("<script>", ks)
        self.assertNotIn("falsk", depot)
        self.assertIn("Ingen faglige kommentarer er valgt", depot)
        from noark5_workflow.reporting.qa_decision_v021_a12 import _csv
        exported = _csv(enriched).decode("utf-8-sig")
        self.assertIn("Valgt til KS", exported)

    def test_comments_not_selected_remain_in_work_only(self):
        self.save(comment="Intern merknad", include_in_ks=False, include_in_depot=False)
        enriched = with_selected_reviews(self.work, self.snapshot)
        self.assertEqual(enriched["a13_review_rows"], [])
        self.assertEqual(enriched["a13_review_summary"]["reviewed_findings"], 1)
        self.assertNotIn("Intern merknad", json.dumps(enriched, ensure_ascii=False))
        self.assertTrue((self.work / REVIEW_DIR).is_dir())

    def test_stale_report_blocks_writes_and_excludes_old_notes(self):
        self.save()
        value = json.loads(self.fixture.depot.read_text())
        value["changed_after_review"] = True
        self.fixture.depot.write_text(json.dumps(value))
        with self.assertRaisesRegex(ReviewError, "Depotrapporten er endret"):
            self.save(comment="Kan ikke skrives")
        new_snapshot = build_snapshot(work=self.work)
        record = latest_reviews(self.work, new_snapshot)
        self.assertEqual(record["current"], {})
        self.assertEqual(record["older_or_changed"], 1)
        enriched = with_selected_reviews(self.work, new_snapshot)
        self.assertEqual(enriched["a13_review_rows"], [])

    def test_malicious_events_and_invalid_identity_fail_closed(self):
        with self.assertRaisesRegex(ReviewError, "Registrert brukerprofil"):
            self.save(user="anonym")
        with self.assertRaisesRegex(ReviewError, "kommentar"):
            self.save(comment=" ")
        with self.assertRaisesRegex(ReviewError, "Ukjent"):
            self.save(status="approved")
        self.save()
        path = next((self.work / REVIEW_DIR).glob("*.json"))
        original = json.loads(path.read_text())
        original["status"] = "approved"
        path.write_text(json.dumps(original))
        with self.assertRaises(ReviewError):
            latest_reviews(self.work, self.snapshot)

    def test_bundle_preserves_existing_a12_and_no_a20_without_job(self):
        target = self.output / "reviewed"
        result = export_review_bundle(work=self.work, output_dir=target, kdrs_qa=self.fixture.kdrs)
        self.assertTrue(result["index"].is_file())
        self.assertTrue((target / "rapporter/index.html").is_file())
        self.assertFalse((target / "teknisk-detaljrapport").exists())
        manifest = json.loads((target / "rapportpakke-manifest.json").read_text())
        self.assertEqual(manifest["model_id"], BUNDLE_MODEL)
        self.assertFalse(manifest["a20_included"])
        self.assertFalse(manifest["automatic_approval"])
        for rel, digest in manifest["files"].items():
            self.assertEqual(sha256((target / rel).read_bytes()).hexdigest(), digest)
        with self.assertRaises(FileExistsError):
            export_review_bundle(work=self.work, output_dir=target)

    def test_a20_full_report_is_reused_and_integrated_not_reimplemented(self):
        target = self.output / "with-a20"
        job = FakeJob("JOB-001", self.fixture.uid, self.work)
        observed = []

        def writer(directory, jobs, options, **kwargs):
            observed.append((tuple(jobs), options, kwargs))
            (directory / "index.html").write_text("a20 Full overview")
            for part in "abcd":
                (directory / ("vedlegg-" + part + ".html")).write_text("Existing a20 annex " + part)
            return directory / "index.html"

        fake_summary = types.ModuleType("noark5_workflow.reporting.job_summary_a16")
        fake_summary.ReportOptions = lambda *args: {"args": args}
        fake_service = types.ModuleType("noark5_workflow.reporting.report_service_a20")
        fake_service.write_report_package = writer
        with patch.dict(sys.modules, {
            fake_summary.__name__: fake_summary,
            fake_service.__name__: fake_service,
        }):
            result = export_review_bundle(work=self.work, output_dir=target,
                                          report_jobs=(job,), _a20_writer=writer)
        self.assertTrue(result["technical_a20_included"])
        self.assertEqual(len(observed), 1)
        self.assertEqual(observed[0][1]["args"], ("Full", (), True, True))
        self.assertEqual(observed[0][2]["formats"], ("html", "json", "csv"))
        self.assertTrue((target / "teknisk-detaljrapport/vedlegg-d.html").is_file())
        self.assertIn("teknisk-detaljrapport/index.html", (target / "index.html").read_text())

    def test_a20_failure_does_not_publish_partial_bundle(self):
        target = self.output / "failed-a20"
        job = FakeJob("JOB-001", self.fixture.uid, self.work)
        fake_summary = types.ModuleType("noark5_workflow.reporting.job_summary_a16")
        fake_summary.ReportOptions = lambda *args: {"args": args}
        fake_service = types.ModuleType("noark5_workflow.reporting.report_service_a20")
        fake_service.write_report_package = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("a20 crashed"))
        with patch.dict(sys.modules, {fake_summary.__name__:fake_summary, fake_service.__name__:fake_service}):
            with self.assertRaisesRegex(RuntimeError, "a20 crashed"):
                export_review_bundle(work=self.work, output_dir=target, report_jobs=(job,))
        self.assertFalse(target.exists())
        self.assertFalse(any(p.name.startswith(".a13-rapport-") for p in self.output.iterdir()))

    def test_wrong_job_source_and_destination_are_rejected(self):
        target = self.output / "bad"
        bad = FakeJob("JOB-001", self.fixture.uid, self.root)
        fake_summary = types.ModuleType("noark5_workflow.reporting.job_summary_a16")
        fake_summary.ReportOptions = lambda *args: args
        fake_service = types.ModuleType("noark5_workflow.reporting.report_service_a20")
        fake_service.write_report_package = lambda *args, **kw: None
        with patch.dict(sys.modules, {fake_summary.__name__:fake_summary, fake_service.__name__:fake_service}):
            with self.assertRaisesRegex(ReportInputError, "annen Work"):
                export_review_bundle(work=self.work, output_dir=target, report_jobs=(bad,))
        with self.assertRaisesRegex(ReportInputError, "atskilt fra Work"):
            export_review_bundle(work=self.work, output_dir=self.work / "somewhere")
        (self.root / "source").mkdir()
        with self.assertRaisesRegex(ReportInputError, "Source eller AIP"):
            export_review_bundle(work=self.work, output_dir=self.root / "source" / "noark5-a13")
        self.assertFalse(target.exists())

    def test_preflight_and_structural_gui_integration(self):
        from contextlib import redirect_stdout
        from io import StringIO
        with redirect_stdout(StringIO()) as capture:
            self.assertEqual(main(["--work", str(self.work), "--preflight"]), 0)
        self.assertIn('"formell_depotgodkjenning": false', capture.getvalue())
        main_gui = (ROOT / "gui_qt/main_v020_a6.py").read_text(encoding="utf-8")
        panel_gui = (ROOT / "gui_qt/qa_review_v021_a13.py").read_text(encoding="utf-8")
        for marker in ("install_compact_result_navigation", "install_xpath_catalog_link", "install_qa_review_panel"):
            self.assertIn(marker, main_gui)
        for marker in ("_a2_panel", "QaFindingReviewDialog", "selected_report_jobs", "include_in_depot"):
            self.assertIn(marker, panel_gui)


if __name__ == "__main__":
    unittest.main()
