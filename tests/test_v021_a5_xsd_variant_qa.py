from __future__ import annotations

import hashlib
import json
from contextlib import redirect_stdout, redirect_stderr
from io import StringIO
from pathlib import Path
import tempfile
import unittest

from app.noark_xsd_variant_qa_v021_a5 import (
    build_schema_variant_inventory,
    aggregate_existing_work_ledgers,
    compare_variant,
    diagnostic_comparison,
    fingerprint,
    metadata_type_facets,
    main,
    reference_metadata_overview,
    compare_dwm_value_sets,
    value_candidate,
)

NS = "http://www.arkivverket.no/standarder/noark5/arkivstruktur"


def schema_text(*, version="4.0", strict=True):
    restrictions = (
        '<xs:restriction base="xs:string"><xs:enumeration value="X"/></xs:restriction>'
        if strict else '<xs:restriction base="xs:string"><xs:minLength value="1"/></xs:restriction>'
    )
    return (f'<?xml version="1.0" encoding="utf-8"?>\n'
            f'<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema" '
            f'targetNamespace="{NS}" xmlns="{NS}" elementFormDefault="qualified" version="{version}">\n'
            f'  <xs:element name="root"><xs:complexType><xs:sequence>'
            f'<xs:element name="code" minOccurs="1" maxOccurs="unbounded">'
            f'<xs:simpleType>{restrictions}</xs:simpleType></xs:element>'
            f'</xs:sequence></xs:complexType></xs:element>\n'
            f'</xs:schema>\n').encode("utf-8")


class TestXsdVariantsA5(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.reference = self.root / "ref" / "docs" / "kilder" / "noark" / "noark5" / "v4.0" / "schemas" / "arkivstruktur.xsd"
        self.reference.parent.mkdir(parents=True)
        self.original_bytes = schema_text()
        self.reference.write_bytes(self.original_bytes.replace(b"\n", b"\r\n"))
        self.outside = self.root / "observed" / "arkivstruktur.xsd"
        self.outside.parent.mkdir(parents=True)

    def test_exact_reference_bytes(self):
        self.outside.write_bytes(self.reference.read_bytes())
        report = compare_variant(self.outside, self.reference, source_commit="abc")
        self.assertEqual(report["status"], "exact_reference_bytes")
        self.assertEqual(report["reference_commit"], "abc")
        self.assertTrue(report["exact_reference_byte_identity"])
        self.assertFalse(report["normative_compliance_approved"])

    def test_only_lf_crlf_diff_is_not_unknown_variant(self):
        self.outside.write_bytes(self.original_bytes)
        report = compare_variant(self.outside, self.reference)
        self.assertEqual(report["status"], "line_endings_only")
        self.assertNotEqual(report["observed"]["sha256"], report["reference"]["sha256"])
        self.assertEqual(report["observed"]["sha256_lf_normalized"],
                         report["reference"]["sha256_lf_normalized"])
        self.assertFalse(report["exact_reference_byte_identity"])

    def test_changed_schema_requires_qa_even_if_version_matches(self):
        self.outside.write_bytes(schema_text(strict=False))
        report = compare_variant(self.outside, self.reference,
                                 parent_path=self.reference, declared_purpose="diagnostic only")
        self.assertEqual(report["status"], "content_variant_requires_qa")
        self.assertEqual(report["qa_status"], "operator_review_required")
        self.assertNotEqual(report["parent"]["sha256"], report["observed"]["sha256"])

    def test_version_conflict_is_not_accepted(self):
        self.outside.write_bytes(schema_text(version="5.0"))
        report = compare_variant(self.outside, self.reference)
        self.assertEqual(report["status"], "declared_version_conflict")

    def test_bad_schema_not_assigned_version(self):
        self.outside.write_bytes(b"<foo/>")
        with self.assertRaises(ValueError):
            fingerprint(self.outside)

    def test_variant_inventory_maps_only_to_own_version(self):
        self.outside.write_bytes(self.original_bytes)
        inventory = build_schema_variant_inventory(self.root / "ref", [self.outside])
        self.assertEqual(inventory["records"][0]["status"], "line_endings_only")
        self.assertEqual(len(inventory["records"]), 1)

    def test_schema_unavailable_is_observed_not_accepted(self):
        self.outside.write_bytes(schema_text(version="5.0"))
        inventory = build_schema_variant_inventory(self.root / "ref", [self.outside])
        self.assertEqual(inventory["records"][0]["status"], "authoritative_reference_missing")

    def test_diagnostic_comparison_cleared_two_errors_not_source(self):
        self.outside.write_bytes(schema_text(strict=False))
        xml = self.root / "source" / "arkivstruktur.xml"
        xml.parent.mkdir()
        xml.write_text(f'<root xmlns="{NS}"><code>Y</code><code>Z</code></root>', encoding="utf-8")
        expected_sha = hashlib.sha256(xml.read_bytes()).hexdigest()
        report = diagnostic_comparison(xml, self.reference, self.outside)
        self.assertEqual(report["xml_sha256"], expected_sha)
        self.assertEqual(report["original_error_count"], 2)
        self.assertEqual(report["diagnostic_error_count"], 0)
        self.assertEqual(report["error_occurrences_removed"], 2)
        self.assertEqual(report["error_occurrences_introduced"], 0)
        self.assertTrue(report["original_xsd_failure_preserved"])
        self.assertEqual(report["normative_approval"], "not_assessed")
        self.assertEqual(xml.read_bytes(), f'<root xmlns="{NS}"><code>Y</code><code>Z</code></root>'.encode())

    def test_diagnostic_covers_changed_imported_metadatakatalog(self):
        md_ns = "http://www.arkivverket.no/standarder/noark5/metadatakatalog"
        main = (f'<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema" '
                f'xmlns:m="{md_ns}" targetNamespace="{NS}" '
                f'xmlns="{NS}" version="4.0" elementFormDefault="qualified">'
                f'<xs:import namespace="{md_ns}" schemaLocation="metadatakatalog.xsd"/>'
                f'<xs:element name="root"><xs:complexType><xs:sequence>'
                f'<xs:element name="code" type="m:codeType"/>'
                f'</xs:sequence></xs:complexType></xs:element></xs:schema>')
        def meta(strict):
            val = '<xs:enumeration value="X"/>' if strict else '<xs:minLength value="1"/>'
            return (f'<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema" '
                    f'targetNamespace="{md_ns}" version="4.0">'
                    f'<xs:simpleType name="codeType"><xs:restriction base="xs:string">'
                    f'{val}</xs:restriction></xs:simpleType></xs:schema>')
        for path, strict in [(self.reference, True), (self.outside, False)]:
            path.write_text(main, encoding="utf-8")
            (path.parent / "metadatakatalog.xsd").write_text(meta(strict), encoding="utf-8")
        xml = self.root / "sample.xml"
        xml.write_text(f'<root xmlns="{NS}"><code>Y</code></root>', encoding="utf-8")
        result = diagnostic_comparison(xml, self.reference, self.outside)
        self.assertEqual(result["original_error_count"], 1)
        self.assertEqual(result["diagnostic_error_count"], 0)
        self.assertEqual(result["error_occurrences_removed"], 1)
        self.assertEqual(result["original"]["schema_graph_sha256"]["arkivstruktur.xsd"],
                         result["diagnostic"]["schema_graph_sha256"]["arkivstruktur.xsd"])
        self.assertNotEqual(result["original"]["schema_graph_sha256"]["metadatakatalog.xsd"],
                            result["diagnostic"]["schema_graph_sha256"]["metadatakatalog.xsd"])

    def test_refuse_same_schema_as_diagnostic(self):
        xml = self.root / "a.xml"
        xml.write_text(f'<root xmlns="{NS}"><code>X</code></root>')
        with self.assertRaises(ValueError):
            diagnostic_comparison(xml, self.reference, self.reference)

    def test_value_exact(self):
        result = value_candidate("Elektronisk arkiv", ["Elektronisk arkiv"])
        self.assertEqual(result["status"], "exact_reference_value")
        self.assertTrue(result["literal_reference_match"])
        self.assertFalse(result["normative_compliance_approved"])

    def test_value_spacing_case_only_review(self):
        result = value_candidate("elektronisk   ARKIV", ["Elektronisk arkiv"])
        self.assertEqual(result["status"], "formatting_candidate_needs_qa")
        self.assertFalse(result["normative_compliance_approved"])

    def test_value_typo_only_review(self):
        result = value_candidate("Elektronkskarkiv", ["Elektronisk arkiv"])
        self.assertEqual(result["status"], "similar_text_candidate_needs_qa")
        self.assertEqual(result["observed_raw"], "Elektronkskarkiv")

    def test_value_paraphrase_only_review(self):
        result = value_candidate("Besvart i Telefon", ["Besvart på telefon"])
        self.assertEqual(result["status"], "similar_text_candidate_needs_qa")
        self.assertFalse(result["normative_compliance_approved"])

    def test_approved_alias_not_xsd_acceptance(self):
        result = value_candidate("Utgåande dokument", ["Utgående dokument"],
                                 approved_aliases={"Utgåande dokument": "Utgående dokument"})
        self.assertEqual(result["status"], "operator_approved_alias")
        self.assertFalse(result["normative_compliance_approved"])

    def test_aggregate_existing_a6_work_variant_ledgers(self):
        digest = "a" * 64
        for job_number in (1, 2):
            work = self.root / f"work{job_number}"
            ledger = work / "noark5_evidence" / "xsd_variants.json"
            ledger.parent.mkdir(parents=True)
            ledger.write_text(json.dumps({"schema_version": "1.0", "variants": [{
                "variant_id": "v1", "sha256": digest, "filename": "arkivstruktur.xsd",
                "schema_version_declared": "4.0",
            }], "observations": [{"variant_id": "v1"} for _ in range(job_number)]}), encoding="utf-8")
        result = aggregate_existing_work_ledgers([self.root / "work1", self.root / "work2"])
        self.assertEqual(result["unique_raw_sha256_variants"], 1)
        self.assertEqual(result["variant_observations"][0]["jobs_seen"], 2)
        self.assertEqual(result["variant_observations"][0]["observation_count"], 3)
        self.assertFalse(result["variant_observations"][0]["source_file_content_checked"])

    def test_missing_work_ledger_is_not_fake_variant(self):
        result = aggregate_existing_work_ledgers([self.root / "not-there"])
        self.assertEqual(result["unique_raw_sha256_variants"], 0)
        self.assertEqual(result["work_ledgers"][0]["status"], "ledger_not_found")

    def test_metadata_facets_are_source_version_specific(self):
        for version, allowed in (("3.1", 5), ("4.0", 7), ("5.0", 0)):
            path = (self.root / "ref" / "docs" / "kilder" / "noark" / "noark5" /
                    f"v{version}" / "schemas" / "metadatakatalog.xsd")
            path.parent.mkdir(parents=True, exist_ok=True)
            enums = "".join(f'<xs:enumeration value="V{i}"/>' for i in range(allowed))
            details = enums if enums else '<xs:minLength value="1"/>'
            path.write_text(f'<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema" '
                            f'targetNamespace="{NS}" version="{version}">'
                            f'<xs:simpleType name="avskrivningsmaate">'
                            f'<xs:annotation><xs:documentation>M619</xs:documentation></xs:annotation>'
                            f'<xs:restriction base="xs:string">{details}</xs:restriction>'
                            f'</xs:simpleType></xs:schema>', encoding="utf-8")
            record = metadata_type_facets(path, "M619")
            self.assertEqual(len(record["enumeration"]), allowed)
            self.assertEqual(record["custom_values_permitted_by_standard_text"],
                             "requires_separate_specification_qa")
        overview = reference_metadata_overview(self.root / "ref", ("M619",))
        self.assertEqual(overview["versions"]["4.0"]["metadata"]["M619"]["schema_version"], "4.0")
        self.assertEqual(overview["versions"]["5.0"]["metadata"]["M619"]["min_length"], 1)

    def test_enum_crosswalk_tracks_missing_and_differences_without_editing(self):
        ref_root = self.root / "ref"
        for version in ("3.1", "4.0", "5.0"):
            xsd = ref_root / "docs" / "kilder" / "noark" / "noark5" / f"v{version}" / "schemas" / "metadatakatalog.xsd"
            xsd.parent.mkdir(parents=True, exist_ok=True)
            facet = ('<xs:enumeration value="Fysisk medium"/>' if version != "5.0"
                     else '<xs:minLength value="1"/>')
            xsd.write_text(f'<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema" '
                           f'targetNamespace="{NS}" version="{version}">'
                           f'<xs:simpleType name="dokumentmedium"><xs:annotation><xs:documentation>M300</xs:documentation>'
                           f'</xs:annotation><xs:restriction base="xs:string">{facet}</xs:restriction>'
                           f'</xs:simpleType></xs:schema>', encoding="utf-8")
        reg = self.root / "values.json"
        reg.write_text(json.dumps({"versions": {v: {"value_sets": {"M300_dokumentmedium": {
            "metadata_id": "M300", "values": ["Fysisk arkiv"]}}} for v in ("3.1", "4.0", "5.0")}}))
        result = compare_dwm_value_sets(ref_root, reg)
        self.assertEqual(result["versions"]["3.1"]["xsd_enumerated_metadata_count"], 1)
        self.assertEqual(result["versions"]["4.0"]["literal_value_differences"][0]["xsd_only"], ["Fysisk medium"])
        self.assertEqual(result["versions"]["5.0"]["xsd_enumerated_metadata_count"], 0)
        self.assertEqual(result["versions"]["5.0"]["literal_value_differences"], [])

    def test_cli_writes_only_to_explicit_work_and_never_overwrites(self):
        self.outside.write_bytes(self.original_bytes)
        work = self.root / "work"
        work.mkdir()
        output = work / "qa.json"
        argv = ["--reference-root", str(self.root / "ref"),
                "--schema", str(self.outside),
                "--work-root", str(work),
                "--output", str(output)]
        with redirect_stdout(StringIO()):
            self.assertEqual(main(argv), 0)
        report = json.loads(output.read_text(encoding="utf-8"))
        self.assertEqual(report["records"][0]["status"], "line_endings_only")
        baseline = output.read_bytes()
        with redirect_stderr(StringIO()):
            with self.assertRaises(SystemExit):
                main(argv)
        self.assertEqual(output.read_bytes(), baseline)
        with redirect_stderr(StringIO()):
            with self.assertRaises(SystemExit):
                main(argv[:-1] + [str(self.outside.parent / "qa.json")])

    def test_unknown_not_accepted(self):
        result = value_candidate("vilkårlig verdi", ["Elektronisk arkiv"])
        self.assertEqual(result["status"], "unknown_needs_qa")
        self.assertIsNone(result["candidate"])


if __name__ == "__main__":
    unittest.main()
