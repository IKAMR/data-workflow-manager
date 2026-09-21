from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from noark5_workflow.analysis import xml_schema_validation as xsv


XSD = """<?xml version="1.0" encoding="UTF-8"?>
<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema"
           targetNamespace="urn:test:noark5"
           xmlns="urn:test:noark5"
           elementFormDefault="qualified">
  <xs:element name="arkivstruktur">
    <xs:complexType>
      <xs:sequence>
        <xs:element name="arkiv" minOccurs="1" maxOccurs="1">
          <xs:complexType>
            <xs:sequence>
              <xs:element name="tittel" type="xs:string"/>
            </xs:sequence>
          </xs:complexType>
        </xs:element>
      </xs:sequence>
    </xs:complexType>
  </xs:element>
</xs:schema>
"""

VALID_XML = """<?xml version="1.0" encoding="UTF-8"?>
<arkivstruktur xmlns="urn:test:noark5"
 xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
 xsi:schemaLocation="urn:test:noark5 arkivstruktur.xsd">
  <arkiv><tittel>Test</tittel></arkiv>
</arkivstruktur>
"""

INVALID_XML = """<?xml version="1.0" encoding="UTF-8"?>
<arkivstruktur xmlns="urn:test:noark5"
 xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
 xsi:schemaLocation="urn:test:noark5 arkivstruktur.xsd">
  <arkiv/>
</arkivstruktur>
"""


class A16483LargeXmlStreamingTests(unittest.TestCase):
    def _files(self, root: Path, xml_text: str):
        xsd = root / "arkivstruktur.xsd"
        xml = root / "arkivstruktur.xml"
        xsd.write_text(XSD, encoding="utf-8")
        xml.write_text(xml_text, encoding="utf-8")
        return xml, xsd

    def test_schema_location_reads_root_without_etree_parse(self):
        with tempfile.TemporaryDirectory() as temp:
            xml, _xsd = self._files(Path(temp), VALID_XML)
            with patch.object(
                xsv.etree,
                "parse",
                side_effect=AssertionError(
                    "schema_location_candidates must not parse the complete XML"
                ),
            ):
                self.assertEqual(
                    xsv.schema_location_candidates(xml),
                    ["arkivstruktur.xsd"],
                )

    def test_validation_uses_streaming_iterparse_and_records_size(self):
        with tempfile.TemporaryDirectory() as temp:
            xml, xsd = self._files(Path(temp), VALID_XML)
            result = xsv.validate_xml_against_xsd(xml, xsd)

            self.assertTrue(result.valid)
            self.assertEqual(result.errors, [])
            self.assertEqual(result.validation_mode, "streaming-iterparse")
            self.assertEqual(result.file_size_bytes, xml.stat().st_size)

    def test_streaming_validation_still_reports_xsd_errors(self):
        with tempfile.TemporaryDirectory() as temp:
            xml, xsd = self._files(Path(temp), INVALID_XML)
            result = xsv.validate_xml_against_xsd(xml, xsd)

            self.assertFalse(result.valid)
            self.assertGreater(len(result.errors), 0)
            self.assertTrue(
                any(
                    row.get("domain") in {"SCHEMASV", "XML"}
                    for row in result.errors
                )
            )

    def test_source_contains_no_full_xml_etree_parse(self):
        source = Path(xsv.__file__).read_text(encoding="utf-8")
        stream_block = source.split("def _stream_validate_xml", 1)[1]
        self.assertIn("etree.iterparse(", stream_block)
        self.assertIn('xml_path.open("rb")', stream_block)
        self.assertNotIn("etree.parse(str(xml_path)", source)


if __name__ == "__main__":
    unittest.main()
