"""a15: full checklist scope, append-only Work events, METS, and report adapters."""
from __future__ import annotations

from hashlib import sha256
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
spec = importlib.util.spec_from_file_location("_a12_fixture_for_a15", ROOT / "tests/test_v021_a12_qa_decision.py")
baseline = importlib.util.module_from_spec(spec)
spec.loader.exec_module(baseline)

from noark5_workflow.reporting.qa_context_v021_a14 import enrich_snapshot
from noark5_workflow.reporting.qa_decision_v021_a12 import render_reports, ReportInputError
from noark5_workflow.reporting.qa_decision_v021_a13 import build_review_snapshot, export_review_bundle
from noark5_workflow.reporting.qa_checklist_v021_a15 import (
    MODEL, EVENT_MODEL, EVENT_DIR, POINTS, POINT_BY_ID, GROUPS, NOTES,
    CATALOG_SHA256, DOC_MET, DOC_BASE, STATUSES, ChecklistError, HEADER_FIELDS,
    latest_checklist, record_checklist, attach_checklist, checklist_html, mets_header,
)


class User:
    user_id = "reviewer-15"

    def as_dict(self):
        return {"user_id": self.user_id, "username": "test", "name": "Operatør"}


class A15ChecklistTests(unittest.TestCase):
    def setUp(self):
        self.fixture = baseline.A12Reports("test_two_distinct_reports_and_unapproved_status")
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.work = self.fixture.work
        self.root = self.fixture.root
        self.snapshot = self.fixture.build()
        self.user = User()
        self.point_id = "opplysninger.01"

    def save(self, **kwargs):
        settings = {"scope": "uttrekk", "status": "yes", "comment": "Kontrollert manuelt",
                    "user": self.user}
        point_id = kwargs.pop("point_id", self.point_id)
        settings.update(kwargs)
        return record_checklist(self.work, self.snapshot, point_id, **settings)

    def test_exact_catalogue_structure_is_stable(self):
        controls = [row for row in POINTS if row["kind"] == "control"]
        notes = [row for row in POINTS if row["kind"] == "note"]
        self.assertEqual(len(controls), 49)
        self.assertEqual(len(notes), 8)
        self.assertEqual(len(POINT_BY_ID), len(POINTS))
        self.assertEqual(len(GROUPS), 10)
        self.assertEqual(len(NOTES), 8)
        self.assertEqual(len(CATALOG_SHA256), 64)
        self.assertIn("sjekkliste-mets.docx", DOC_MET)
        self.assertIn("sjekkliste.docx", DOC_BASE)
        self.assertEqual(STATUSES, {"yes": "Ja", "no": "Nei", "not_applicable": "Ikke relevant"})

    def test_all_unanswered_not_passed(self):
        state = latest_checklist(self.work, self.snapshot)
        self.assertEqual(state["current"], {})
        model = attach_checklist(self.work, self.snapshot)["a15_checklist"]
        self.assertEqual(model["model_id"], MODEL)
        self.assertEqual(model["summary"]["total_controls"], 49)
        self.assertEqual(model["summary"]["job_controls_manually_reviewed"], 0)
        self.assertFalse(model["automatic_approval"])
        self.assertEqual(model["selected_rows"], [])
        self.assertIn("Ikke vurdert betyr ikke bestått", checklist_html({"a15_checklist": model}, depot=True))

    def test_append_only_and_sources_unchanged(self):
        protected = (self.fixture.canonical, self.fixture.ext, self.fixture.ark,
                     self.fixture.depot, self.fixture.index, self.fixture.master)
        before = {p: sha256(p.read_bytes()).hexdigest() for p in protected}
        first = self.save()
        self.assertEqual(first["status"], "yes")
        self.assertEqual(first["model_id"], EVENT_MODEL)
        second = self.save(status="no", comment="Mangler dokumentasjon", include_in_ks=True)
        self.assertNotEqual(first["event_id"], second["event_id"])
        paths = list((self.work / EVENT_DIR).glob("*.json"))
        self.assertEqual(len(paths), 2)
        now = latest_checklist(self.work, self.snapshot)
        self.assertEqual(now["current"][self.point_id]["status"], "no")
        self.assertEqual(before, {p: sha256(p.read_bytes()).hexdigest() for p in protected})

    def test_manual_identity_required_and_no_auto_status(self):
        with self.assertRaisesRegex(ChecklistError, "brukerprofil"):
            self.save(user=None)
        with self.assertRaisesRegex(ChecklistError, "Ugyldig svar"):
            self.save(status="approved")
        with self.assertRaisesRegex(ChecklistError, "Ugyldig svar"):
            self.save(status="")
        self.assertFalse((self.work / EVENT_DIR).exists())

    def test_no_and_not_applicable_require_reason(self):
        with self.assertRaisesRegex(ChecklistError, "begrunnelse"):
            self.save(status="no", comment="")
        with self.assertRaisesRegex(ChecklistError, "begrunnelse"):
            self.save(status="not_applicable", comment="   ")
        good = self.save(status="not_applicable", comment="SIARD er ikke del av Noark5-uttrekket")
        self.assertEqual(good["status"], "not_applicable")

    def test_independent_freetext_without_fake_jn(self):
        self.point_id = "notat.noark5_funn"
        with self.assertRaisesRegex(ChecklistError, "Ugyldig svar"):
            self.save(status="yes")
        with self.assertRaisesRegex(ChecklistError, "begrunnelse"):
            self.save(status="note", comment="")
        note = self.save(status="note", comment="Samlet kommentar til N5.15 og N5.22")
        self.assertEqual(note["status"], "note")
        self.assertIn("Noark 5", POINT_BY_ID[self.point_id]["label"])

    def test_separate_job_scope_and_archive_part(self):
        self.save()
        event = self.save(scope="arkivdel", native_id="part-2", status="no", comment="Dokumentasjon mangler")
        self.assertEqual(event["native_id"], "part-2")
        self.assertEqual(latest_checklist(self.work, self.snapshot)["current"][self.point_id]["status"], "yes")
        self.assertEqual(latest_checklist(self.work, self.snapshot, scope="arkivdel", native_id="part-2")["current"][self.point_id]["status"], "no")
        self.assertEqual(latest_checklist(self.work, self.snapshot, scope="arkivdel", native_id="part-1")["current"], {})
        with self.assertRaisesRegex(ChecklistError, "system-ID"):
            self.save(scope="arkivdel", native_id="not-in-report")
        with self.assertRaisesRegex(ChecklistError, "Uttrekksnivå"):
            self.save(native_id="part-2")

    def test_stale_depot_report_revision_never_current(self):
        self.save()
        depot = json.loads(self.fixture.depot.read_text(encoding="utf8"))
        depot["version_changed"] = True
        self.fixture.depot.write_text(json.dumps(depot), encoding="utf8")
        with self.assertRaisesRegex(ValueError, "Depotrapporten er endret"):
            self.save()
        new_base = self.fixture.build()
        result = latest_checklist(self.work, new_base)
        self.assertEqual(result["current"], {})
        self.assertEqual(result["older_or_changed"], 1)
        self.assertEqual(attach_checklist(self.work, new_base)["a15_checklist"]["selected_rows"], [])

    def test_new_comment_revision_does_not_erase_history(self):
        old = self.save(status="yes", comment="Først")
        new = self.save(status="yes", comment="Etterpå")
        self.assertNotEqual(old["event_id"], new["event_id"])
        self.assertEqual(latest_checklist(self.work, self.snapshot)["current"][self.point_id]["comment"], "Etterpå")

    def _assert_simulated_link_rejected(self, folder: Path):
        """Exercise the same path guard without SeCreateSymbolicLinkPrivilege.

        Windows normally denies symlink creation outside Developer Mode or an
        elevated process (WinError 1314). A real directory marked as a link via
        a narrowly scoped mock still tests that DWM rejects linked Work paths.
        """
        folder.mkdir()
        original_is_symlink = Path.is_symlink
        # Windows may canonicalize 8.3 (short) names when resolving Work.
        # Compare the invariant event-directory components, not the full
        # lexical Path spelling passed by the caller.
        event_parts = tuple(part.casefold() for part in Path(EVENT_DIR).parts[-2:])
        checked = []

        def appears_linked(path):
            parts = tuple(part.casefold() for part in path.parts[-2:])
            if parts == event_parts:
                checked.append(str(path))
                return True
            return original_is_symlink(path)

        with patch.object(Path, "is_symlink", appears_linked):
            with self.assertRaisesRegex((ChecklistError, ReportInputError), "lenke"):
                self.save()
        self.assertTrue(checked, "The test did not reach the a15 event-folder symlink guard")
        self.assertEqual(list(folder.iterdir()), [])

    def test_symlink_event_folder_rejected(self):
        folder = self.work / EVENT_DIR
        foreign = self.root / "foreign"
        foreign.mkdir()
        try:
            folder.symlink_to(foreign, target_is_directory=True)
        except OSError as exc:
            # A missing Windows symlink privilege is an environment limitation,
            # not a failure of the checklist's security validation.
            if os.name != "nt" or getattr(exc, "winerror", None) not in (5, 1314):
                raise
            self._assert_simulated_link_rejected(folder)
        else:
            with self.assertRaisesRegex((ChecklistError, ReportInputError), "lenke"):
                self.save()
        self.assertEqual(list(foreign.iterdir()), [])

    def test_symlink_guard_without_symlink_privilege(self):
        """Keep the permission-free security regression active on every OS."""
        self._assert_simulated_link_rejected(self.work / EVENT_DIR)

    def test_symlink_guard_with_alternate_path_spelling(self):
        """An equivalent (but lexically different) Work path must be rejected.

        This reproduces the Windows short-name/long-name mismatch without
        requiring the right to create real symlinks.
        """
        alternate = self.work / "noark5_evidence" / ".." / EVENT_DIR
        self.assertNotEqual(alternate, self.work / EVENT_DIR)
        self.assertEqual(alternate.resolve(strict=False),
                         (self.work / EVENT_DIR).resolve(strict=False))
        self._assert_simulated_link_rejected(alternate)

    def test_tampered_event_fails_closed(self):
        self.save()
        path = next((self.work / EVENT_DIR).glob("*.json"))
        obj = json.loads(path.read_text(encoding="utf8"))
        obj["status"] = "no"
        path.write_text(json.dumps(obj), encoding="utf8")
        with self.assertRaisesRegex(ChecklistError, "manipulert"):
            latest_checklist(self.work, self.snapshot)

    def test_ks_and_depot_recipient_filters_and_escaping(self):
        self.save(status="no", comment="<script>unsafe</script> spørsmål", include_in_ks=True, include_in_depot=False)
        self.save(point_id="arkivpakke.01", status="yes", comment="Intern", include_in_ks=False, include_in_depot=False)
        self.save(point_id="arkivpakke.02", status="not_applicable", comment="Depothåndtering", include_in_ks=False, include_in_depot=True)
        report = attach_checklist(self.work, self.snapshot)
        self.assertEqual(len(report["a15_checklist"]["selected_rows"]), 2)
        ks = checklist_html(report, depot=False)
        depot = checklist_html(report, depot=True)
        self.assertIn("&lt;script&gt;unsafe&lt;/script&gt;", ks)
        self.assertNotIn("<script>", ks)
        self.assertNotIn("unsafe", depot)
        self.assertNotIn("Intern", ks)
        self.assertNotIn("Intern", depot)
        self.assertIn("Depothåndtering", depot)
        self.assertNotIn("Depothåndtering", ks)

    def test_a13_report_builder_includes_a15_without_approving(self):
        self.save(status="no", comment="Avviksnotat", include_in_ks=False)
        snapshot = build_review_snapshot(work=self.work)
        self.assertIn("a14_context", snapshot)
        self.assertIn("a15_checklist", snapshot)
        self.assertFalse(snapshot["depot_formal_decision_registered_by_a12"])
        reports = render_reports(snapshot)
        self.assertNotIn("Avviksnotat", reports["01-kvalitetssikring-arkivskaper.html"])
        self.assertIn("Avviksnotat", reports["02-depot-godkjenning-ferdigstilling.html"])
        self.assertIn("49", reports["02-depot-godkjenning-ferdigstilling.html"])
        self.assertIn("faglige referanser", reports["02-depot-godkjenning-ferdigstilling.html"])

    def test_export_manifest_preserves_a20_compatibility(self):
        self.save(status="yes", comment="Gjennomgått")
        result = export_review_bundle(work=self.work, output_dir=self.fixture.output / "a15-package")
        path = result["index"].parent
        self.assertTrue((path / "rapporter/rapportgrunnlag.json").is_file())
        payload = json.loads((path / "rapporter/rapportgrunnlag.json").read_text(encoding="utf8"))
        self.assertEqual(payload["a15_checklist"]["summary"]["job_controls_manually_reviewed"], 1)
        self.assertFalse(payload["depot_formal_decision_registered_by_a12"])
        self.assertFalse((path / "teknisk-detaljrapport").exists())  # CLI without a20 job
        manifest = json.loads((path / "rapportpakke-manifest.json").read_text(encoding="utf8"))
        for rel, expected in manifest["files"].items():
            self.assertEqual(sha256((path / rel).read_bytes()).hexdigest(), expected)
        with self.assertRaises(FileExistsError):
            export_review_bundle(work=self.work, output_dir=path)

    def test_template_missing_keeps_work_valid_and_unknown(self):
        snap = enrich_snapshot(self.work, self.snapshot)
        hdr = mets_header(self.work, snap)
        self.assertIsNone(hdr["preserved_source"])
        self.assertEqual(len(hdr["rows"]), len(HEADER_FIELDS))
        self.assertTrue(all(not r["original_value"] for r in hdr["rows"]))
        self.assertFalse(any(r["conflict"] for r in hdr["rows"]))

    def _write_mets(self, original_xml: str, *, work_label="Original label"):
        rel = "metadata/source_evidence/import123/source/info.xml"
        p = self.work / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(original_xml, encoding="utf8")
        meta = {"file_type": "dwm-depot-metadata", "job_id": "JOB-001",
                "current": {"label": work_label, "archive_description": "Delivery spec",
                            "archivist_org": "Work archivist", "owner_org": "Owner A",
                            "recipient": "Depot A", "system": "WebSak", "system_version": "9.0.36"},
                "source_imports": [{"kind": "dias-mets", "preserved_file": rel,
                                    "sha256": sha256(p.read_bytes()).hexdigest()}]}
        self.fixture.put("metadata/depot_metadata.json", meta)
        return p

    def test_mets_original_and_work_preserved_without_conflation(self):
        original = '''<mets:mets xmlns:mets="http://www.loc.gov/METS/" LABEL="Original label" OBJID="UUID:123">
         <mets:metsHdr CREATEDATE="2025-12-23T10:20:00Z"><mets:agent ROLE="ARCHIVIST" TYPE="ORGANIZATION"><mets:name>Original archivist</mets:name></mets:agent>
         <mets:agent ROLE="IPOWNER" TYPE="ORGANIZATION"><mets:name>Owner A</mets:name></mets:agent>
         <mets:altRecordID TYPE="DELIVERYSPECIFICATION">Delivery spec</mets:altRecordID>
         <mets:altRecordID TYPE="STARTDATE">2005-01-01</mets:altRecordID></mets:metsHdr></mets:mets>'''
        p = self._write_mets(original)
        snap = enrich_snapshot(self.work, self.snapshot)
        header = mets_header(self.work, snap)
        rows = {x["id"]: x for x in header["rows"]}
        self.assertEqual(rows["label"]["work_value"], "Original label")
        self.assertEqual(rows["label"]["original_value"], "Original label")
        self.assertEqual(rows["objid"]["original_value"], "UUID:123")
        self.assertTrue(rows["archivist"]["conflict"])
        self.assertEqual(rows["archivist"]["work_value"], "Work archivist")
        self.assertEqual(rows["archivist"]["original_value"], "Original archivist")
        self.assertEqual(rows["delivery_spec"]["work_value"], "Delivery spec")
        self.assertEqual(rows["delivery_spec"]["original_value"], "Delivery spec")
        self.assertEqual(rows["period_start"]["original_value"], "2005-01-01")
        self.assertEqual(header["preserved_source"]["sha256"], sha256(p.read_bytes()).hexdigest())


    def test_original_mets_software_and_typeversion_are_distinct(self):
        xml = '''<mets:mets xmlns:mets="http://www.loc.gov/METS/">
          <mets:metsHdr>
          <mets:agent ROLE="ARCHIVIST" TYPE="OTHER" OTHERTYPE="SOFTWARE">
             <mets:name>WebSak</mets:name><mets:note>9.0.36</mets:note><mets:note>Noark5</mets:note><mets:note>5.0</mets:note><mets:note>notescontent:Version,Type,TypeVersion</mets:note>
          </mets:agent>
          <mets:agent ROLE="OTHER" OTHERROLE="PRODUCER" TYPE="OTHER" OTHERTYPE="SOFTWARE">
             <mets:name>Acos Avlevering</mets:name><mets:note>2.2.20</mets:note><mets:note>Noark5</mets:note><mets:note>5.0</mets:note>
          </mets:agent>
          <mets:agent ROLE="CREATOR" TYPE="OTHER" OTHERTYPE="SOFTWARE">
             <mets:name>Arkade 5</mets:name><mets:note>2.12.3</mets:note>
          </mets:agent></mets:metsHdr></mets:mets>'''
        self._write_mets(xml)
        snap = enrich_snapshot(self.work, self.snapshot)
        rows = {r["id"]: r for r in mets_header(self.work, snap)["rows"]}
        self.assertEqual(rows["system"]["original_value"], "WebSak")
        self.assertEqual(rows["system_version"]["original_value"], "9.0.36")
        self.assertEqual(rows["system_noark_version"]["original_value"], "5.0")
        self.assertEqual(rows["extraction_tool"]["original_value"], "Acos Avlevering")
        self.assertEqual(rows["extraction_version"]["original_value"], "2.2.20")
        self.assertEqual(rows["extraction_noark_version"]["original_value"], "5.0")
        self.assertEqual(rows["mets_creator_software"]["original_value"], "Arkade 5")
        self.assertNotEqual(rows["mets_creator_software"]["original_value"], rows["extraction_tool"]["original_value"])

    def test_unmodified_sources_are_required_for_mets(self):
        xml = '<mets:mets xmlns:mets="http://www.loc.gov/METS/" LABEL="A"/>'
        original = self._write_mets(xml)
        original.write_text(xml + " ", encoding="utf8")
        with self.assertRaisesRegex(ReportInputError, "SHA-256"):
            enrich_snapshot(self.work, self.snapshot)

    def test_malicious_doctype_rejected_without_external_access(self):
        xml = '''<!DOCTYPE foo [ <!ENTITY secret SYSTEM "file:///etc/passwd"> ]><mets:mets xmlns:mets="http://www.loc.gov/METS/"/>'''
        self._write_mets(xml)
        snapshot = enrich_snapshot(self.work, self.snapshot)
        with self.assertRaisesRegex(ChecklistError, "DTD"):
            mets_header(self.work, snapshot)

    def test_noark5_technical_results_not_modified_by_checklist(self):
        base = self.fixture.build()
        before_findings = json.dumps(base["findings"], ensure_ascii=False, sort_keys=True)
        self.save(status="no", comment="Ikke akseptert")
        enriched = attach_checklist(self.work, base)
        self.assertEqual(before_findings, json.dumps(enriched["findings"], ensure_ascii=False, sort_keys=True))
        self.assertEqual(enriched["dwm_technical"], base["dwm_technical"])
        self.assertTrue(enriched["review_required"])


if __name__ == "__main__":
    unittest.main()
