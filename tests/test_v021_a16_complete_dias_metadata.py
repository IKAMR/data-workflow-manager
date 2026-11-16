"""a16 complete DIAS metadata: source byte-integrity, cardinality and Work edits."""
from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from noark5_workflow.reporting.dias_metadata_v021_a16 import (
    FIELD_ROWS, LOC_NS, INNER_NS, MetadataA16Error, import_inner_mets,
    load_metadata, save_field,
)

AUTHOR = {"user_id": "test-operator-01", "display_name": "Test-operatør"}


def make_xml(ns=LOC_NS):
    # 2 distinct ARCHIVISTs, contact notes, 2 file objects, repeated unknown
    # extension and an explicit alternative record ID that is not in the 47.
    return (f'''<?xml version="1.0" encoding="utf-8"?>
<mets xmlns="{ns}" xmlns:xlink="http://www.w3.org/1999/xlink"
 OBJID="UUID:11111111-2222-4333-8444-555555555555" LABEL="Test LABEL" TYPE="SIP" PROFILE="urn:test">
 <metsHdr CREATEDATE="2026-01-15T10:00:00+01:00" RECORDSTATUS="NEW">
  <agent ROLE="ARCHIVIST" TYPE="ORGANIZATION"><name>Test kommune</name></agent>
  <agent ROLE="ARCHIVIST" TYPE="ORGANIZATION"><name>Historisk kommune</name></agent>
  <agent ROLE="ARCHIVIST" TYPE="INDIVIDUAL"><name>Arkivleder</name>
   <note>Kontaktveien 2</note><note>70000000</note><note>contact@example.invalid</note>
   <note>notescontent:Address,Telephone,Email</note></agent>
  <agent ROLE="OTHER" OTHERROLE="SUBMITTER" TYPE="ORGANIZATION"><name>Innsender AS</name></agent>
  <agent ROLE="IPOWNER" TYPE="ORGANIZATION"><name>Eier kommune</name></agent>
  <agent ROLE="CREATOR" TYPE="OTHER" OTHERTYPE="SOFTWARE"><name>Arkade 5</name>
   <note>2.13.1</note><note>notescontent:Version</note></agent>
  <agent ROLE="ARCHIVIST" TYPE="OTHER" OTHERTYPE="SOFTWARE"><name>WebSak</name>
   <note>9.0.36</note><note>Noark5</note><note>5.0</note>
   <note>notescontent:Version,Type,TypeVersion</note></agent>
  <agent ROLE="OTHER" OTHERROLE="PRODUCER" TYPE="OTHER" OTHERTYPE="SOFTWARE">
   <name>Uttrekk</name><note>2.0</note><note>notescontent:Version</note></agent>
  <altRecordID TYPE="DELIVERYSPECIFICATION">Sakarkiv 2008-2020</altRecordID>
  <altRecordID TYPE="SUBMISSIONAGREEMENT">DEPOT-1</altRecordID>
  <altRecordID TYPE="STARTDATE">2008-01-01</altRecordID>
  <altRecordID TYPE="ENDDATE">2020-12-31</altRecordID>
  <altRecordID TYPE="UNKNOWN_VENDOR_REF">viktig ekstrafelt</altRecordID>
 </metsHdr>
 <fileSec><fileGrp USE="FILES">
   <file ID="file_1" MIMETYPE="application/xml" SIZE="300" CHECKSUM="abc" CHECKSUMTYPE="SHA-256">
     <FLocat LOCTYPE="URL" xlink:href="file:first.xml"/></file>
   <file ID="file_2" SIZE="400" CHECKSUM="def" CHECKSUMTYPE="SHA-256">
     <FLocat LOCTYPE="URL" xlink:href="file:second.xml"/></file>
  </fileGrp></fileSec>
 <structMap><div/></structMap>
</mets>''').encode("utf-8")


class A16MetadataTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.work = self.root / "work"
        (self.work / "metadata").mkdir(parents=True)
        self.uid = "784bbd90-7e1b-4cda-a938-8908f760aa5f"
        (self.work / "job.json").write_text(json.dumps({"file_type": "dwm-work-job",
            "job_uid": self.uid, "job": {"job_id": "JOB-001", "job_uid": self.uid}}), encoding="utf-8")
        source = self.work / "metadata" / "preserved-info.xml"
        source.write_bytes(make_xml())
        self.original_bytes = source.read_bytes()
        self.source_hash = sha256(self.original_bytes).hexdigest()
        self.meta_path = self.work / "metadata" / "depot_metadata.json"
        self.meta = {"file_type": "dwm-depot-metadata", "format_version": 3, "job_id": "JOB-001",
                     "source_imports": [{"kind": "dias-mets", "sha256": self.source_hash,
                        "path": "X:\\staging\\info.xml", "preserved_file": "metadata\\preserved-info.xml"}],
                     "current": {"archivist_org": "Test kommune", "system": "WebSak",
                                 "system_version": "9.0.36", "period_end": "2020-12-31",
                                 "label": "Test LABEL"},
                     "review": {"history": [], "acknowledged_state_signature": "keep"}}
        self._write_meta()

    def _write_meta(self):
        self.meta_path.write_text(json.dumps(self.meta, ensure_ascii=False), encoding="utf-8")

    def _load(self):
        return load_metadata(self.work)

    def _edit(self, rowid, new, old=None, source=True, comment="Dokumentert av arkivskaper"):
        state = self._load()
        row = next(r for r in state["rows"] if r["id"] == rowid)
        return save_field(self.work, source_sha256=self.source_hash if source else None,
            row_id=rowid, previous_value=row["current"] if old is None else old,
            new_value=new, comment=comment, author=AUTHOR,
            expected_metadata_sha256=state["metadata_sha256"])

    def test_47_arkade_fields_in_original_order(self):
        self.assertEqual(len(FIELD_ROWS), 47)
        self.assertEqual(FIELD_ROWS[0][0], "archive_description")
        self.assertEqual(FIELD_ROWS[45][0], "extraction_date")
        self.assertEqual(FIELD_ROWS[46][0], "label")
        self.assertEqual(len(set(x[0] for x in FIELD_ROWS)), 47)

    def test_mixed_content_and_preserved_whitespace_are_not_lost(self):
        # This is XML *source inventory*, not normalised Arkade metadata.
        source = self.work / "metadata/preserved-info.xml"
        xml = make_xml().replace(b'viktig ekstrafelt', b'  viktig ekstrafelt  ')
        xml = xml.replace(b'<structMap><div/></structMap>',
                          b'<structMap><div/>viktig tail</structMap>')
        source.write_bytes(xml)
        self.meta["source_imports"][0]["sha256"] = sha256(xml).hexdigest()
        self._write_meta()
        state = self._load()
        raw = [r for r in state["rows"] if r["kind"] == "xml"]
        self.assertTrue(any(r["historical"] == "  viktig ekstrafelt  " for r in raw))
        self.assertTrue(any(r["historical"] == "viktig tail" and
                            r["key"].endswith("tail()") for r in raw))

    def test_complete_inventory_of_repeat_agents_file_attributes_and_vendor_extensions(self):
        state = self._load()
        self.assertEqual(state["canonical_count"], 47)
        self.assertGreater(state["xml_field_count"], 30)
        rows = [r for r in state["rows"] if r["kind"] == "xml"]
        values = [r["historical"] for r in rows]
        for value in ("Test kommune", "Historisk kommune", "viktig ekstrafelt", "file:first.xml",
                      "file:second.xml", "300", "400", "abc", "def", "Arkivleder"):
            self.assertIn(value, values)
        multiple = [r for r in rows if r["historical"] in ("Test kommune", "Historisk kommune")]
        self.assertNotEqual(multiple[0]["key"], multiple[1]["key"])

    def test_inner_namespace_is_distinct_and_imports_as_immutable_evidence(self):
        source = self.root / "dias-mets.xml"
        source.write_bytes(make_xml(INNER_NS))
        before = source.read_bytes()
        entry = import_inner_mets(self.work, source)
        self.assertEqual(entry["kind"], "indre dias-mets.xml")
        self.assertEqual(before, source.read_bytes())
        state = load_metadata(self.work, entry["sha256"])
        self.assertEqual(state["source_type"], "indre dias-mets.xml")
        self.assertGreater(state["xml_field_count"], 30)
        self.assertEqual(next(r["historical"] for r in state["rows"] if r["id"] == "field:system"), "WebSak")
        self.assertEqual(entry, import_inner_mets(self.work, source))
        self.assertEqual(len(load_metadata(self.work)["sources"]), 2)
        self.assertEqual(before, (self.work / entry["path"]).read_bytes())

    def test_catalogue_fields_separate_from_dias_47(self):
        state = self._load()
        extra = [r for r in state["rows"] if r["kind"] == "depot"]
        self.assertEqual(len(extra), 4)
        self.assertEqual(state["canonical_count"], 47)
        self.assertEqual(set(r["historical"] for r in extra), {None})
        self._edit("depot:system_region", "Interkommunalt samarbeid")
        value = json.loads(self.meta_path.read_text(encoding="utf-8"))
        self.assertEqual(value["current"]["system_region"], "Interkommunalt samarbeid")

    def test_new_outer_import_visible_to_existing_metadata_editor(self):
        self.meta["source_imports"] = []
        self._write_meta()
        src = self.root / "new-info.xml"
        src.write_bytes(make_xml())
        entry = import_inner_mets(self.work, src)
        self.assertEqual(entry["kind"], "ytre info.xml")
        revised = json.loads(self.meta_path.read_text(encoding="utf-8"))
        self.assertEqual(len(revised["source_imports"]), 1)
        original = revised["source_imports"][0]
        self.assertEqual(original["sha256"], entry["sha256"])
        self.assertEqual(original["fields"]["system"], "WebSak")
        self.assertEqual(original["preserved_file"], entry["path"])
        self.assertEqual(len(load_metadata(self.work)["sources"]), 1)

    def test_status_neutral_for_equal_and_bold_for_difference(self):
        state = self._load()
        self.assertEqual(next(r["status"] for r in state["rows"] if r["id"] == "field:system"), "lik")
        self.meta["current"]["system"] = "Annet system"
        self._write_meta()
        row = next(r for r in self._load()["rows"] if r["id"] == "field:system")
        self.assertTrue(row["changed"])
        self.assertEqual(row["status"], "ulik")

    def test_canonical_edit_shared_with_existing_editor_and_preserves_source_and_review(self):
        event = self._edit("field:system_version", "9.0.37")
        self.assertEqual(event["old_value"], "9.0.36")
        self.assertEqual(event["new_value"], "9.0.37")
        actual = json.loads(self.meta_path.read_text(encoding="utf-8"))
        self.assertEqual(actual["current"]["system_version"], "9.0.37")
        self.assertEqual(actual["review"]["history"][-1]["reason"], "Dokumentert av arkivskaper")
        self.assertEqual(actual["review"]["acknowledged_state_signature"], "keep")
        self.assertEqual(actual["source_imports"], self.meta["source_imports"])
        self.assertEqual((self.work / "metadata/preserved-info.xml").read_bytes(), self.original_bytes)
        self.assertTrue(next(r["changed"] for r in self._load()["rows"] if r["id"] == "field:system_version"))

    def test_linked_canonical_xml_is_read_only_and_stays_consistent(self):
        state = self._load()
        raw_label = next(r for r in state["rows"] if r["kind"] == "xml" and
                         r["key"].endswith("/@LABEL"))
        self.assertEqual(raw_label["linked_to"], "label")
        self.assertFalse(raw_label["editable"])
        self.assertEqual(raw_label["current"], "Test LABEL")
        self._edit("field:label", "New LABEL")
        state = self._load()
        canonical = next(r for r in state["rows"] if r["id"] == "field:label")
        raw_label = next(r for r in state["rows"] if r["id"] == raw_label["id"])
        self.assertEqual(raw_label["current"], canonical["current"])
        self.assertEqual(raw_label["historical"], "Test LABEL")
        self.assertEqual(state["changed"], 1)  # no double-count

    def test_explicit_clearing_of_value_is_highlighted(self):
        self._edit("field:label", "")
        row = next(r for r in self._load()["rows"] if r["id"] == "field:label")
        self.assertTrue(row["changed"])
        self.assertEqual(row["status"], "ulik")

    def test_gui_and_distribution_are_wired_without_replacing_a15(self):
        root = Path(__file__).resolve().parents[1]
        gui = (root / "gui_qt/checklist_v021_a15.py").read_text(encoding="utf-8")
        editor = (root / "gui_qt/dias_metadata_v021_a16.py").read_text(encoding="utf-8")
        self.assertIn("Komplett DIAS/METS: sammenlign og rediger metadata", gui)
        self.assertIn("CompleteDiasMetadataDialog", gui)
        self.assertIn("self.panel._identity()", editor)
        self.assertIn("QFont", editor)
        self.assertIn("if row[\"changed\"]", editor)
        # Final release satisfies the historical a16 feature milestone.
        from tests.version_assertions import assert_release_at_least
        from version import VERSION
        import tomllib
        physical_version = (root / "version.py").read_text(encoding="utf-8")
        assert_release_at_least(self, physical_version, "0.2.1", 16)
        with (root / "pyproject.toml").open("rb") as handle:
            distribution_version = tomllib.load(handle)["project"]["version"]
        self.assertEqual(distribution_version, VERSION.replace("-a", "a"))

    def test_xml_occurrence_edit_is_source_bound_and_append_only(self):
        state = self._load()
        row = next(r for r in state["rows"] if r["kind"] == "xml" and r["historical"] == "Historisk kommune")
        self._edit(row["id"], "Historisk kommunes nye navn")
        new = next(r for r in self._load()["rows"] if r["id"] == row["id"])
        self.assertEqual(new["historical"], "Historisk kommune")
        self.assertEqual(new["current"], "Historisk kommunes nye navn")
        self.assertEqual(new["status"], "endret")
        self.assertEqual((self.work / "metadata/preserved-info.xml").read_bytes(), self.original_bytes)
        self._edit(row["id"], "Historisk kommune", comment="Tilbakestilt etter kontroll")
        events = list((self.work / "metadata/dias_mets_field_events_v021_a16").glob("*.json"))
        self.assertEqual(len(events), 2)
        self.assertEqual(next(r for r in self._load()["rows"] if r["id"] == row["id"])["status"], "lik")

    def test_no_auto_approval_and_original_source_content_unchanged(self):
        self._edit("field:period_end", "2022-12-31")
        state = self._load()
        self.assertNotIn("depot_decision", state)
        self.assertEqual((self.work / "metadata/preserved-info.xml").read_bytes(), self.original_bytes)

    def test_stale_edit_rejected(self):
        state = self._load()
        self._edit("field:label", "Nytt LABEL")
        with self.assertRaisesRegex(MetadataA16Error, "endret"):
            save_field(self.work, source_sha256=self.source_hash, row_id="field:label",
                previous_value="Test LABEL", new_value="Overskriver", comment="Begrunnelse",
                author=AUTHOR, expected_metadata_sha256=state["metadata_sha256"])

    def test_bad_metadata_digest_rejected_even_with_same_value(self):
        state = self._load()
        with self.assertRaisesRegex(MetadataA16Error, "oppdater"):
            save_field(self.work, source_sha256=self.source_hash, row_id="field:label",
                previous_value="Test LABEL", new_value="Endret", comment="Begrunnelse",
                author=AUTHOR, expected_metadata_sha256="0" * 64)

    def test_invalid_actor_reason_and_unchanged_values(self):
        for params in ({"author": {}}, {"comment": ""}, {"new_value": "Test LABEL"}):
            args = {"source_sha256": self.source_hash, "row_id": "field:label",
                    "previous_value": "Test LABEL", "new_value": "Nytt LABEL",
                    "comment": "Begrunnelse", "author": AUTHOR,
                    "expected_metadata_sha256": self._load()["metadata_sha256"]}
            args.update(params)
            with self.assertRaises(MetadataA16Error):
                save_field(self.work, **args)

    def test_empty_structural_element_not_editable(self):
        state = self._load()
        elem = next(r for r in state["rows"] if r["kind"] == "xml" and not r["editable"])
        with self.assertRaisesRegex(MetadataA16Error, "ikke-redigerbart"):
            self._edit(elem["id"], "WRONG")

    def test_original_digest_mismatch_fails_closed(self):
        (self.work / "metadata/preserved-info.xml").write_bytes(b"changed")
        with self.assertRaisesRegex(MetadataA16Error, "SHA-256"):
            self._load()

    def test_symlinked_evidence_rejected_even_without_windows_privilege(self):
        real = Path.is_symlink
        def patch_path(p):
            return p.name == "preserved-info.xml" or real(p)
        with mock.patch.object(Path, "is_symlink", patch_path):
            with self.assertRaisesRegex(MetadataA16Error, "Symbolsk lenke"):
                self._load()

    def test_path_traversal_rejected(self):
        self.meta["source_imports"][0]["preserved_file"] = "../../outside/info.xml"
        self._write_meta()
        with self.assertRaisesRegex(MetadataA16Error, "Work-relativ"):
            self._load()

    def test_doctype_and_entity_rejected(self):
        source = self.root / "bad-info.xml"
        source.write_bytes(b'<!DOCTYPE mets [<!ENTITY x SYSTEM "file:///etc/passwd">]>' + make_xml())
        with self.assertRaisesRegex(MetadataA16Error, "DTD"):
            import_inner_mets(self.work, source)

    def test_non_mets_xml_rejected(self):
        p = self.root / "not-mets.xml"
        p.write_text("<other>irrelevant</other>")
        with self.assertRaisesRegex(MetadataA16Error, "METS"):
            import_inner_mets(self.work, p)

    def test_changed_raw_event_digest_rejected(self):
        state = self._load()
        row = next(r for r in state["rows"] if r["kind"] == "xml" and r["historical"] == "Historisk kommune")
        self._edit(row["id"], "Corrected")
        path = next((self.work / "metadata/dias_mets_field_events_v021_a16").glob("*.json"))
        entry = json.loads(path.read_text(encoding="utf-8"))
        entry["new_value"] = "FORGED"
        path.write_text(json.dumps(entry), encoding="utf-8")
        with self.assertRaisesRegex(MetadataA16Error, "endret"):
            self._load()

    def test_other_job_evidence_rejected(self):
        (self.work / "job.json").write_text(json.dumps({"file_type": "dwm-work-job",
            "job_uid": self.uid, "job": {"job_id": "OTHER", "job_uid": self.uid}}), encoding="utf-8")
        with self.assertRaisesRegex(MetadataA16Error, "tilhører ikke"):
            self._load()

    def test_source_without_preserved_bytes_not_claimed_complete(self):
        self.meta["source_imports"] = [{"kind": "dias-mets", "sha256": self.source_hash,
                                         "path": "X:\\staging\\info.xml", "fields": {"system": "WebSak"}}]
        self._write_meta()
        state = self._load()
        self.assertFalse(state["source_original_preserved"])
        self.assertEqual(state["xml_field_count"], 0)
        self.assertEqual(state["canonical_count"], 47)

    def test_reimported_inner_byte_copy_is_verified(self):
        p = self.root / "inner.xml"
        p.write_bytes(make_xml(INNER_NS))
        entry = import_inner_mets(self.work, p)
        (self.work / entry["path"]).write_text("overwritten", encoding="utf-8")
        with self.assertRaisesRegex(MetadataA16Error, "SHA-256"):
            load_metadata(self.work, entry["sha256"])

    def test_core_source_inventory_has_no_unknown_xml_discard(self):
        state = self._load()
        actual = (self.work / "metadata/preserved-info.xml").read_bytes()
        self.assertEqual(sha256(actual).hexdigest(), state["selected_source"]["sha256"])
        self.assertIn("UNKNOWN_VENDOR_REF", actual.decode("utf-8"))
        self.assertTrue(any("viktig ekstrafelt" == r["current"] for r in state["rows"]))


if __name__ == "__main__":
    unittest.main()
