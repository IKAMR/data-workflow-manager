from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from noark5_workflow.analysis.xml_schema_validation import validate_xml_against_xsd


XSD = """<?xml version="1.0" encoding="UTF-8"?>
<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">
  <xs:element name="root" type="xs:string"/>
</xs:schema>
"""

XML = """<?xml version="1.0" encoding="UTF-8"?><root>ok</root>"""


class XmlSchemaResourceStrategyA3Tests(unittest.TestCase):
    def test_memory_mode_is_reported(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            xml = root / "a.xml"
            xsd = root / "a.xsd"
            xml.write_text(XML, encoding="utf-8")
            xsd.write_text(XSD, encoding="utf-8")

            result = validate_xml_against_xsd(
                xml,
                xsd,
                resource_strategy="memory",
                environment={"available_memory_bytes": 8 * 1024**3},
            )
            self.assertTrue(result.valid)
            self.assertEqual(result.validation_mode, "memory-tree")
            self.assertEqual(result.resource_decision["selected"], "memory")

    def test_streaming_mode_is_reported(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            xml = root / "a.xml"
            xsd = root / "a.xsd"
            xml.write_text(XML, encoding="utf-8")
            xsd.write_text(XSD, encoding="utf-8")

            result = validate_xml_against_xsd(
                xml,
                xsd,
                resource_strategy="streaming",
                environment={"available_memory_bytes": 8 * 1024**3},
            )
            self.assertTrue(result.valid)
            self.assertEqual(result.validation_mode, "streaming-iterparse")
            self.assertEqual(result.resource_decision["selected"], "streaming")


if __name__ == "__main__":
    unittest.main()
