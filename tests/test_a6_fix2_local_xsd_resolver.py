from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from noark5_workflow.analysis.xml_schema_validation import (
    validate_xml_against_xsd,
)


class A6Fix2LocalXsdResolverTests(unittest.TestCase):
    def test_broken_relative_import_resolves_by_unique_local_basename(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)

            imported = root / "virksomhetsspesifikkeMetadata.xsd"
            imported.write_text(
                """<?xml version="1.0" encoding="UTF-8"?>
<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema"
 targetNamespace="urn:business"
 xmlns:b="urn:business"
 elementFormDefault="qualified">
  <xs:simpleType name="BusinessText">
    <xs:restriction base="xs:string"/>
  </xs:simpleType>
</xs:schema>
""",
                encoding="utf-8",
            )

            main = root / "arkivstruktur.xsd"
            main.write_text(
                """<?xml version="1.0" encoding="UTF-8"?>
<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema"
 xmlns:b="urn:business">
  <xs:import namespace="urn:business"
   schemaLocation="drift/virksomhetsspesifikkemetadata.xsd"/>
  <xs:element name="root" type="xs:string"/>
</xs:schema>
""",
                encoding="utf-8",
            )

            xml = root / "arkivstruktur.xml"
            xml.write_text(
                '<?xml version="1.0" encoding="UTF-8"?><root>ok</root>',
                encoding="utf-8",
            )

            result = validate_xml_against_xsd(
                xml,
                main,
                resource_strategy="disk",
                available_xsds=[main, imported],
            )
            self.assertTrue(result.valid, result.errors)


if __name__ == "__main__":
    unittest.main()
