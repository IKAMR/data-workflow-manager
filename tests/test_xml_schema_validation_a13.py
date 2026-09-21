from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from noark5_workflow.analysis.xml_schema_validation import (
    resolve_local_schema,
    validate_xml_against_xsd,
)
from noark5_workflow.core.context import OperationContext
from noark5_workflow.operations.validate_xml_schema import ValidateXmlSchemaOperation
from noark5_workflow.sources.noark5_extraction import Noark5Extraction


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


class XmlSchemaValidationA13Tests(unittest.TestCase):
    def _files(self, root: Path, xml_text: str):
        xsd = root / "arkivstruktur.xsd"
        xml = root / "arkivstruktur.xml"
        xsd.write_text(XSD, encoding="utf-8")
        xml.write_text(xml_text, encoding="utf-8")
        return xml, xsd

    def _ctx(self, root: Path, work_operations: Path):
        source = Noark5Extraction.detect(root)
        ctx = OperationContext(
            extraction_root=root,
            source=source,
            work_operations=work_operations,
            settings={"_current_run_id": "RUN-TEST-001"},
        )
        ctx.metadata["job_id"] = "JOB-001"
        ctx.metadata["run_id"] = "RUN-TEST-001"
        return ctx

    def test_lxml_accepts_valid_xml_against_xsd(self):
        with tempfile.TemporaryDirectory() as temp:
            xml, xsd = self._files(Path(temp), VALID_XML)
            result = validate_xml_against_xsd(xml, xsd)
            self.assertTrue(result.valid)
            self.assertEqual(result.errors, [])

    def test_lxml_returns_structured_xsd_errors(self):
        with tempfile.TemporaryDirectory() as temp:
            xml, xsd = self._files(Path(temp), INVALID_XML)
            result = validate_xml_against_xsd(xml, xsd)
            self.assertFalse(result.valid)
            self.assertGreater(len(result.errors), 0)
            self.assertIn("message", result.errors[0])
            self.assertIn("line", result.errors[0])

    def test_schema_is_resolved_from_local_schema_location(self):
        with tempfile.TemporaryDirectory() as temp:
            xml, xsd = self._files(Path(temp), VALID_XML)
            resolved = resolve_local_schema(xml, [xsd])
            self.assertEqual(resolved, xsd.resolve())

    def test_operation_writes_unique_json_report_to_work_operations(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "source"
            work_operations = Path(temp) / "work_operations"
            root.mkdir()
            work_operations.mkdir()
            self._files(root, VALID_XML)

            result = ValidateXmlSchemaOperation().run(self._ctx(root, work_operations))

            self.assertTrue(result.ok)
            report = Path(result.data["report"])
            self.assertTrue(report.is_file())
            self.assertIn("JOB-001__RUN-TEST-001", str(report.parent))
            self.assertTrue((report.parent / "artifact_manifest.json").is_file())
            data = json.loads(report.read_text(encoding="utf-8"))
            self.assertTrue(data["valid"])
            self.assertEqual(data["validation_id"], "arkivstruktur-xsd")

    def test_invalid_xml_still_writes_report(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "source"
            work_operations = Path(temp) / "work_operations"
            root.mkdir()
            work_operations.mkdir()
            self._files(root, INVALID_XML)

            result = ValidateXmlSchemaOperation().run(self._ctx(root, work_operations))

            self.assertFalse(result.ok)
            report = Path(result.data["report"])
            self.assertTrue(report.is_file())
            data = json.loads(report.read_text(encoding="utf-8"))
            self.assertFalse(data["valid"])
            self.assertGreater(len(data["errors"]), 0)

    def test_operation_refuses_to_write_without_work_operations(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self._files(root, VALID_XML)
            source = Noark5Extraction.detect(root)
            ctx = OperationContext(extraction_root=root, source=source)
            allowed, reason = ValidateXmlSchemaOperation().can_run(ctx)
            self.assertFalse(allowed)
            self.assertIn("Arbeid", reason)


if __name__ == "__main__":
    unittest.main()
