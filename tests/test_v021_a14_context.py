"""a14 regression: factual METS context and explanatory presentation, no new rules."""
from __future__ import annotations

from hashlib import sha256
import importlib.util
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
spec = importlib.util.spec_from_file_location("_a12_fixture_for_a14", ROOT / "tests/test_v021_a12_qa_decision.py")
baseline = importlib.util.module_from_spec(spec)
spec.loader.exec_module(baseline)

from noark5_workflow.reporting.qa_context_v021_a14 import (
    _declared_version, _registry_context, enrich_snapshot, explain_finding,
    format_explanation, render_context_html,
)
from noark5_workflow.reporting.qa_decision_v021_a12 import ReportInputError, render_reports
from noark5_workflow.reporting.qa_decision_v021_a13 import build_review_snapshot, export_review_bundle
from noark5_workflow.reporting.qa_review_v021_a13 import record_review
from noark5_workflow.reporting.qa_source_details_v021_a14 import format_source_details


class FakeUser:
    user_id = "faglig-person-7"
    def as_dict(self):
        return {"user_id": self.user_id, "username": "fagtest", "name": "Testbruker"}


class A14ContextTests(unittest.TestCase):
    def setUp(self):
        self.fixture = baseline.A12Reports("test_two_distinct_reports_and_unapproved_status")
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.work = self.fixture.work
        self.root = self.fixture.root
        self.base = self.fixture.build()
        self.registry_root = self.root / "repository"
        self.registry = self.registry_root / "config/noark5/standards/noark5_standard_values.json"
        self.registry.parent.mkdir(parents=True)
        self.registry.write_text(json.dumps({"registry_format_version": 1, "versions": {
            "3.1": {"value_sets": {"M053_journalstatus": {"metadata_id": "M053", "values": ["Journalført", "Ferdigstilt fra saksbehandler", "Arkivert", "Utgår"]}}},
            "4.0": {"value_sets": {"M053_journalstatus": {"metadata_id": "M053", "values": ["Journalført", "Ferdigstilt fra saksbehandler", "Arkivert", "Utgår"]}}},
            "5.0": {"value_sets": {"M053_journalstatus": {"metadata_id": "M053", "values": ["Journalført", "Ekspedert", "Arkivert", "Utgår"]}}},
        }}), encoding="utf-8")
        self.a22 = {"source":"Arkade 5", "test_id":"N5.22", "severity":"ERROR",
                    "message":"Journalstatus: Journalført - Antall: 20", "context":"Arkivdel 4",
                    "file":"arkivstruktur.xml", "lines": [7, 8]}

    def add_mets(self, *, system_version="5.0", extraction_version="5.0",
                 title="<b>1525_004 eksempel</b>", creator="Ekstern pakkeprodusent", org="Arkivansvarlig virksomhet"):
        path = self.work / "metadata/source_evidence/import123/source/info.xml"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("<METS>Opphavsdata</METS>", encoding="utf-8")
        checksum = sha256(path.read_bytes()).hexdigest()
        doc = {"file_type": "dwm-depot-metadata", "job_id": "JOB-001",
               "current": {
                  "archive_description": title, "archivist_org": org,
                  "owner_org": "Arkiveier AS", "creator_org": creator,
                  "system": "WebSak", "system_version": "9.0.36",
                  "system_type": "Noark5", "system_type_version": system_version,
                  "extraction_system_type": "Noark5", "extraction_system_type_version": extraction_version,
                  "period_start": "2005-01-01", "period_end": "2022-02-01",
                  "submission_agreement": "25/689-4", "package_number": "1"},
               "source_imports": [{"kind": "dias-mets", "preserved_file":
                                   "metadata\\source_evidence\\import123\\source\\info.xml",
                                   "sha256": checksum}]}
        mpath = self.fixture.put("metadata/depot_metadata.json", doc)
        return mpath, path

    def contextual(self):
        return enrich_snapshot(self.work, self.fixture.build(), registry_root=self.registry_root)

    def test_absence_of_work_metadata_is_unknown_not_approved(self):
        context = self.contextual()
        self.assertEqual(context["a14_context"]["mets"]["status"], "not_available")
        self.assertIsNone(context["a14_context"]["mets"]["version"]["version"])
        self.assertTrue(context["review_required"])
        self.assertFalse(context["depot_formal_decision_registered_by_a12"])
        self.assertEqual(len(context["evidence_manifest"]), len(self.base["evidence_manifest"]))

    def test_work_metadata_and_preserved_original_have_distinct_source_hashes(self):
        mp, original = self.add_mets()
        before = (sha256(mp.read_bytes()).hexdigest(), sha256(original.read_bytes()).hexdigest())
        result = self.contextual()
        mets = result["a14_context"]["mets"]
        self.assertEqual(mets["fields"]["system"], "WebSak")
        self.assertEqual(mets["fields"]["archivist_org"], "Arkivansvarlig virksomhet")
        self.assertEqual(mets["version"]["version"], "5.0")
        self.assertEqual(mets["version"]["status"], "work_mets_only")
        self.assertEqual(mets["sources"][0]["verification"], "preserved_copy_hash_matches")
        self.assertIn("a14_original_mets_copy", [r["kind"] for r in result["evidence_manifest"]])
        self.assertIn("a14_work_mets_metadata", [r["kind"] for r in result["evidence_manifest"]])
        self.assertEqual(before, (sha256(mp.read_bytes()).hexdigest(), sha256(original.read_bytes()).hexdigest()))
        self.assertIsNone(result["reported_identity"]["noark_version_from_canonical"])

    def test_metadata_roles_are_not_conflated_with_verified_archive_creator(self):
        self.add_mets()
        result = self.contextual()
        html = render_context_html(result, depot=False)
        self.assertIn("Arkivansvarlig virksomhet (METS ARCHIVIST)", html)
        self.assertIn("Oppgitt arkiveier (METS OWNER)", html)
        self.assertIn("METS CREATOR (ikke automatisk arkivskaper)", html)
        self.assertIn("Ekstern pakkeprodusent", html)
        self.assertNotIn("<b>1525_004 eksempel</b>", html)
        self.assertIn("&lt;b&gt;1525_004 eksempel&lt;/b&gt;", html)

    def test_conflict_in_work_versions_blocks_selection(self):
        self.add_mets(system_version="4.0", extraction_version="5.0")
        result = self.contextual()
        v = result["a14_context"]["mets"]["version"]
        self.assertIsNone(v["version"])
        self.assertEqual(v["status"], "conflict")
        self.assertIn("Ikke entydig dokumentert", render_context_html(result, depot=True))

    def test_conflict_between_canonical_and_work_versions_is_reported(self):
        self.add_mets()
        self.base["reported_identity"]["noark_version_from_canonical"] = "4.0"
        result = enrich_snapshot(self.work, self.base, registry_root=self.registry_root)
        self.assertEqual(result["a14_context"]["mets"]["version"]["status"], "conflict")
        self.assertIsNone(result["a14_context"]["mets"]["version"]["version"])

    def test_noark_4_must_not_be_misread_as_noark5_v40(self):
        self.add_mets(system_version="4", extraction_version="4")
        result = self.contextual()
        v = result["a14_context"]["mets"]["version"]
        self.assertEqual(v["status"], "unrecognized")
        self.assertIsNone(v["version"])
        self.assertNotIn("Noark 5 v4.0 oppgitt", format_explanation(self.a22, result["a14_context"]))

    def test_mets_identity_mismatch_refused(self):
        mp, _ = self.add_mets()
        d = json.loads(mp.read_text())
        d["job_id"] = "JOB-999"
        mp.write_text(json.dumps(d))
        with self.assertRaisesRegex(ReportInputError, "annen jobb"):
            self.contextual()

    def test_changed_preserved_source_hash_refused(self):
        _, original = self.add_mets()
        original.write_text("<METS>Endret kopi!</METS>")
        with self.assertRaisesRegex(ReportInputError, "SHA-256"):
            self.contextual()

    def test_escape_from_work_by_symlink_refused(self):
        _, original = self.add_mets()
        original.unlink()
        try:
            original.symlink_to(self.registry)
        except (NotImplementedError, OSError):
            self.skipTest("Symlink er ikke støttet i testmiljøet")
        with self.assertRaisesRegex(ReportInputError, "Symbolsk lenke"):
            self.contextual()

    def test_historical_value_register_is_reference_not_validation(self):
        self.add_mets()
        result = self.contextual()
        values = result["a14_context"]["standard_values"]
        self.assertEqual(values["status"], "read_only_reference")
        self.assertEqual(set(values["versions"]), {"3.1", "4.0", "5.0"})
        self.assertIn("Ferdigstilt fra saksbehandler", values["versions"]["3.1"])
        self.assertNotIn("Ferdigstilt fra saksbehandler", values["versions"]["5.0"])
        self.assertEqual(result["dwm_technical"], self.base["dwm_technical"])
        self.assertEqual(result["arkade"], self.base["arkade"])

    def test_n522_explains_real_error_and_distinguishes_valid_value(self):
        self.add_mets()
        result = self.contextual()
        info = explain_finding(self.a22, result["a14_context"])
        self.assertEqual(info["metadata_id"], "M053")
        self.assertIn("20 journalposter", info["observed"])
        self.assertIn("Arkivert", info["requirement"])
        self.assertIn("Utgår", info["requirement"])
        self.assertIn("registrert M053-standardverdi", info["distinction"])
        self.assertIn("Arkades ERROR beholdes", info["distinction"])
        self.assertEqual(self.a22["severity"], "ERROR")
        self.assertIn("VERSJONSKILDE", format_explanation(self.a22, result["a14_context"]))

    def test_no_other_test_is_assigned_unverified_rule(self):
        self.add_mets()
        result = self.contextual()
        other = dict(self.a22, test_id="N5.15", message="Saksmappestatus: Under behandling - Antall: 4")
        info = explain_finding(other, result["a14_context"])
        self.assertIsNone(info["metadata_id"])
        self.assertIn("ikke knyttet", info["requirement"])
        self.assertNotIn("Arkivert", info["requirement"])

    def test_n522_non5_requires_version_specific_source_review(self):
        self.add_mets(system_version="3.1", extraction_version="3.1")
        result = self.contextual()
        info = explain_finding(self.a22, result["a14_context"])
        self.assertIn("må bekreftes separat", info["requirement"])
        self.assertIn("registrert M053-standardverdi", info["distinction"])

    def test_context_html_and_review_comments_remain_separate(self):
        self.add_mets()
        selected = self.fixture.build()
        target = next(x for x in selected["findings"] if x.get("test_id") == "N5.22")
        record_review(self.work, selected, target, user=FakeUser(), status="requires_clarification",
                      comment="Kun for depot; ikke send til arkivskaper", include_in_ks=False,
                      include_in_depot=True)
        result = build_review_snapshot(work=self.work)
        self.assertIn("a14_context", result)
        output = render_reports(result)
        public = output["01-kvalitetssikring-arkivskaper.html"]
        internal = output["02-depot-godkjenning-ferdigstilling.html"]
        self.assertNotIn("Kun for depot; ikke send til arkivskaper", public)
        self.assertIn("Kun for depot; ikke send til arkivskaper", internal)
        self.assertIn("DIAS/METS", public)
        self.assertIn("DIAS/METS", internal)
        self.assertTrue(result["review_required"])
        self.assertFalse(result["depot_formal_decision_registered_by_a12"])

    def test_export_produces_new_hash_verified_bundle_and_originals_unchanged(self):
        mp, original = self.add_mets()
        sources = (self.fixture.canonical, self.fixture.depot, self.fixture.ext, mp, original)
        before = {str(x):sha256(x.read_bytes()).hexdigest() for x in sources}
        target = self.fixture.output / "a14-mets-export"
        summary = export_review_bundle(work=self.work, output_dir=target)
        self.assertTrue(summary["index"].is_file())
        self.assertTrue((target / "rapporter/rapportgrunnlag.json").exists())
        exported = json.loads((target / "rapporter/rapportgrunnlag.json").read_text(encoding="utf-8"))
        self.assertEqual(exported["a14_context"]["mets"]["fields"]["system"], "WebSak")
        html = (target / "rapporter/02-depot-godkjenning-ferdigstilling.html").read_text(encoding="utf-8")
        self.assertIn("Noark-versjon fra opplysninger", html)
        self.assertEqual(before, {str(x):sha256(x.read_bytes()).hexdigest() for x in sources})
        manifest = json.loads((target / "rapportpakke-manifest.json").read_text(encoding="utf-8"))
        for rel, digest in manifest["files"].items():
            self.assertEqual(sha256((target / rel).read_bytes()).hexdigest(), digest)

    def test_cli_preflight_reports_declared_version_with_provenance(self):
        from noark5_workflow.reporting.qa_decision_v021_a13 import main
        from contextlib import redirect_stdout
        from io import StringIO
        self.add_mets()
        with redirect_stdout(StringIO()) as stream:
            self.assertEqual(main(["--work", str(self.work), "--preflight"]), 0)
        data = json.loads(stream.getvalue())
        self.assertEqual(data["a14_noark_version"], "5.0")
        self.assertEqual(data["a14_noark_version_basis"], "work_mets_only")
        self.assertFalse(data["formell_depotgodkjenning"])

    def test_gui_default_is_readable_and_source_details_have_separate_dialog(self):
        gui = (ROOT / "gui_qt/qa_review_v021_a13.py").read_text(encoding="utf-8")
        self.assertIn('"Hva er funnet, og hvorfor er det et avvik?"', gui)
        self.assertIn('"Vis XML-linjenumre og kildehenvisninger…"', gui)
        self.assertIn("self.source_toggle.clicked.connect(self._open_source_details)", gui)
        self.assertIn('dialog.setWindowTitle("Tekniske kildedetaljer', gui)
        self.assertIn('dialog.resize(950, 600)', gui)
        self.assertIn('details = QPlainTextEdit(dialog)', gui)
        self.assertIn('details.setPlainText(format_source_details(finding))', gui)
        self.assertIn("format_explanation(finding, self._snapshot", gui)
        # No 118-pixel inline technical field may squeeze professional controls.
        self.assertNotIn("self.details.setMaximumHeight(118)", gui)
        self.assertNotIn("self.source_toggle.setCheckable(True)", gui)
        self.assertNotIn("self._toggle_source_details", gui)

    def test_source_details_are_complete_readable_and_source_faithful(self):
        original = dict(self.a22)
        original.update({
            "lines": [56115, 56226, 56333, 56451, 56563, 56648, 56784,
                      56893, 57001, 57167, 57268, 57404, 57512, 57694,
                      57809, 57913, 58021, 58138, 58235, 58309],
            "source_ref": "external_evidence/arkade5/normalized/arkade5_results.json",
        })
        before = json.dumps(original, sort_keys=True)
        formatted = format_source_details(original)
        self.assertIn("Test-ID: N5.22", formatted)
        self.assertIn("Rapportert nivå: ERROR", formatted)
        self.assertIn("Journalstatus: Journalført - Antall: 20", formatted)
        self.assertIn("Antall linjereferanser: 20", formatted)
        self.assertIn("Linjenumre:", formatted)
        self.assertIn("56115", formatted)
        self.assertIn("58309", formatted)
        self.assertIn("external_evidence/arkade5/normalized/arkade5_results.json", formatted)
        self.assertIn("ikke XML-innhold", formatted)
        self.assertEqual(json.dumps(original, sort_keys=True), before)

    def test_undocumented_source_lines_are_unknown_not_zero(self):
        value = format_source_details({"test_id": "N5.15", "severity": "ERROR",
                                       "source": "Arkade 5", "message": "Testfunn"})
        self.assertIn("Antall linjereferanser: Ikke dokumentert", value)
        self.assertIn("Fil: Ikke dokumentert", value)
        self.assertIn("  Ikke dokumentert", value)


if __name__ == "__main__":
    unittest.main()
