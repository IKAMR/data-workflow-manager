"""Source-first QA audit uses synthetic schema fixtures (no repository data)."""
import hashlib
import json
import contextlib
import io
from pathlib import Path
import tempfile
import unittest
from zipfile import ZipFile

from tools.noark5_internal_source_audit import (
    build_audit, main, manifest_sha_status, read_source_document, xpath_mentions_field,
    xsd_elements, xsd_metadata,
)


class NoarkSourceAuditTests(unittest.TestCase):
    def test_line_endings_match_original_crlf(self):
        text = b"<?xml version='1.0'?>\r\n<root/>\r\n"
        canonical = text.replace(b"\r\n", b"\n")
        h = hashlib.sha256(text).hexdigest()
        self.assertEqual(manifest_sha_status(text, h), "identical_bytes")
        self.assertEqual(manifest_sha_status(canonical, h), "matches_original_after_restoring_crlf")
        self.assertEqual(manifest_sha_status(b"changed", h), "hash_mismatch_qa")

    def test_xsd_types_and_optional_element(self):
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "metadatakatalog.xsd"
            f.write_text("""<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema" version="5.0">
              <xs:simpleType name="dokumentmedium"><xs:annotation><xs:documentation>M300</xs:documentation></xs:annotation>
              <xs:restriction base="xs:string"><xs:enumeration value="Fysisk medium"/></xs:restriction></xs:simpleType>
              <xs:element name="dokumentmedium" type="xs:string" minOccurs="0"/>
              </xs:schema>""", encoding="utf8")
            m = xsd_metadata(f)
            self.assertEqual(m["M300"]["xsd_name"], "dokumentmedium")
            self.assertEqual(m["M300"]["enumerations"], ["Fysisk medium"])
            self.assertEqual(xsd_elements(f)["dokumentmedium"][0]["min_occurs"], "0")

    def test_xpath_quoted_literal_not_a_field(self):
        self.assertFalse(xpath_mentions_field("//a[@name='dokumentmedium']", "dokumentmedium"))
        self.assertTrue(xpath_mentions_field("//dokumentmedium", "dokumentmedium"))
        self.assertFalse(xpath_mentions_field("//dokumentmediumUtvidet", "dokumentmedium"))

    def test_docx_text_from_word_xml(self):
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "doc.docx"
            with ZipFile(f, "w") as z:
                z.writestr("word/document.xml", """<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
                <w:body><w:p><w:r><w:t>M300 dokumentmedium</w:t></w:r></w:p></w:body></w:document>""")
            content, extractor = read_source_document(f)
            self.assertEqual(extractor, "docx_xml")
            self.assertIn("M300", content[0][1])

    def test_xlsx_shared_string(self):
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "req.xlsx"
            with ZipFile(f, "w") as z:
                z.writestr("xl/sharedStrings.xml", """<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
                    <si><t>Krav 6.4.3</t></si></sst>""")
                z.writestr("xl/worksheets/sheet1.xml", """<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
                    <sheetData><row r="1"><c t="s"><v>0</v></c></row></sheetData></worksheet>""")
            content, extractor = read_source_document(f)
            self.assertEqual(extractor, "xlsx_xml")
            self.assertIn("Krav 6.4.3", content[0][1])


    def test_end_to_end_source_first_audit_is_read_only(self):
        with tempfile.TemporaryDirectory() as d:
            parent = Path(d)
            dwm, source = parent / "data-workflow-manager", parent / "digital-archive-workflow"
            spec = source / "docs/kilder/noark/noark5/v3.1"
            schema = spec / "schemas"
            reg = dwm / "config/noark5/standards"
            (reg / "metadata").mkdir(parents=True)
            (reg / "requirements").mkdir(parents=True)
            (dwm / "config/noark5/tests").mkdir(parents=True)
            schema.mkdir(parents=True)
            (spec / "spesifikasjoner").mkdir()
            (spec / "spesifikasjoner/demo.xml").write_text("<root>M300</root>", encoding="utf-8")
            content = ("<xs:schema xmlns:xs='http://www.w3.org/2001/XMLSchema' version='3.1'>"
                       "<xs:simpleType name='dokumentmedium'><xs:annotation>"
                       "<xs:documentation>M300</xs:documentation></xs:annotation>"
                       "<xs:restriction base='xs:string'>"
                       "<xs:enumeration value='Fysisk medium'/>"
                       "</xs:restriction></xs:simpleType></xs:schema>")
            paths = []
            for f in ("arkivstruktur.xsd", "endringslogg.xsd", "loependeJournal.xsd",
                      "metadatakatalog.xsd", "offentligJournal.xsd"):
                p = schema / f
                p.write_text(content, encoding="utf-8")
                paths.append(p)
            manifest = {"files": [{"path": f"noark5/v3.1/schemas/{p.name}",
                                     "sha256": hashlib.sha256(p.read_bytes()).hexdigest()}
                                    for p in paths]}
            (source / "docs/kilder/noark/SOURCE-MANIFEST.json").write_text(
                json.dumps(manifest), encoding="utf-8")
            (reg / "metadata/3.1.json").write_text(json.dumps({"metadata": [
                {"metadata_id": "M300", "name": "dokumentmedium"}]}), encoding="utf-8")
            (reg / "requirements/3.1.json").write_text(json.dumps({"requirements": []}), encoding="utf-8")
            (reg / "noark5_standard_values.json").write_text(json.dumps({"versions": {
                "3.1": {"value_sets": {"M300_dokumentmedium": {
                    "metadata_id": "M300", "values": ["Fysisk arkiv"]}}}}}), encoding="utf-8")
            (dwm / "config/noark5/tests/xpath_catalog_2026_05_26.json").write_text(json.dumps({
                "tests": [{"test_id": "kdrs.c01", "noark_versions": ["3.1"],
                           "version_basis": "master_query_subtype_needs_qa",
                           "execution": {"metrics": [{"expression": "count(//dokumentmedium)"}]}}]}),
                encoding="utf-8")
            before = {str(p): p.read_bytes() for p in paths}
            result = build_audit(dwm, source)
            row = result["versions"]["3.1"]
            self.assertEqual(row["xsd_declared_metadata_count"], 1)
            self.assertEqual(row["xpath_lexical_field_count"], 1)
            self.assertEqual(row["xpath_tests_needing_version_qa"], 1)
            self.assertEqual(row["xsd_value_set_mismatches"][0]["metadata_id"], "M300")
            self.assertTrue(all(x["manifest_integrity"] == "identical_bytes" for x in row["xsd"]))
            self.assertEqual(before, {str(p): p.read_bytes() for p in paths})
            with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                main(["--dwm-root", str(dwm), "--source-root", str(source),
                      "--output-dir", str(source / "incorrect-output")])
            out = parent / "qa-reports"
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(main(["--dwm-root", str(dwm), "--source-root", str(source),
                                       "--output-dir", str(out)]), 0)
            self.assertTrue((out / "noark5-source-audit.json").is_file())
            self.assertEqual(before, {str(p): p.read_bytes() for p in paths})


if __name__ == "__main__":
    unittest.main()
