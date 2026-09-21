from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from noark5_workflow.analysis.defined_fields import (
    DefinedFieldExtractionError,
    extract_defined_fields,
)
from noark5_workflow.operations.analyse_arkivstruktur import (
    AnalyseArkivstrukturOperation,
)


class A161DefinedFieldRobustnessTests(unittest.TestCase):
    def test_bad_xpath_reports_entity_field_expression(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            xml = root / "arkivstruktur.xml"
            definition = root / "definition.json"
            xml.write_text("<arkiv><tittel>Test</tittel></arkiv>", encoding="utf-8")
            definition.write_text(
                json.dumps(
                    {
                        "definition_id": "a16.1.test",
                        "entities": {
                            "archive": {
                                "scope": "single",
                                "select": "//*[local-name()='arkiv']",
                                "fields": {
                                    "title": "string(./*[local-name()='tittel'][1]"
                                },
                            }
                        },
                    }
                ),
                encoding="utf-8",
            )

            with self.assertRaises(DefinedFieldExtractionError) as caught:
                extract_defined_fields(xml, definition)

            exc = caught.exception
            self.assertEqual("archive", exc.entity_id)
            self.assertEqual("title", exc.field_id)
            self.assertEqual("field", exc.phase)
            self.assertIn("local-name()='tittel'", exc.expression or "")
            self.assertIn("archive.title", str(exc))

    def test_bad_entity_selector_reports_context(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            xml = root / "arkivstruktur.xml"
            definition = root / "definition.json"
            xml.write_text("<arkiv/>", encoding="utf-8")
            definition.write_text(
                json.dumps(
                    {
                        "definition_id": "a16.1.test",
                        "entities": {
                            "archive_parts": {
                                "scope": "many",
                                "select": "//*[local-name()='arkivdel'",
                                "fields": {},
                            }
                        },
                    }
                ),
                encoding="utf-8",
            )

            with self.assertRaises(DefinedFieldExtractionError) as caught:
                extract_defined_fields(xml, definition)

            exc = caught.exception
            self.assertEqual("archive_parts", exc.entity_id)
            self.assertIsNone(exc.field_id)
            self.assertEqual("entity_select", exc.phase)

    def test_operation_continues_when_defined_fields_xpath_fails(self):
        analysis = SimpleNamespace(
            total_elements=10,
            key_counts={
                "arkiv": 1,
                "arkivdel": 1,
                "mappe": 2,
                "registrering": 3,
                "dokumentbeskrivelse": 2,
                "dokumentobjekt": 1,
            },
            as_dict=lambda: {
                "total_elements": 10,
                "key_counts": {
                    "arkiv": 1,
                    "arkivdel": 1,
                    "mappe": 2,
                    "registrering": 3,
                    "dokumentbeskrivelse": 2,
                    "dokumentobjekt": 1,
                },
            },
        )
        extraction = SimpleNamespace(
            metadata_files={"arkivstruktur": Path("arkivstruktur.xml")},
            is_noark5_candidate=True,
        )
        progress = []
        logs = []
        ctx = SimpleNamespace(
            source=extraction,
            extraction_root=Path("."),
            progress=lambda value, message: progress.append((value, message)),
            log=lambda message: logs.append(message),
        )
        error = DefinedFieldExtractionError(
            "XPath-feil i archive.title: Invalid expression",
            entity_id="archive",
            field_id="title",
            expression="string(//*[",
            phase="field",
        )

        with patch(
            "noark5_workflow.operations.analyse_arkivstruktur.analyse_arkivstruktur",
            return_value=analysis,
        ), patch(
            "noark5_workflow.operations.analyse_arkivstruktur.extract_defined_fields",
            side_effect=error,
        ):
            result = AnalyseArkivstrukturOperation().run(ctx)

        self.assertTrue(result.ok)
        self.assertTrue(result.warnings)
        self.assertIn("defined_fields_error", result.data)
        self.assertEqual(
            "archive",
            result.data["defined_fields_error"]["entity_id"],
        )
        self.assertEqual({}, result.data["defined_fields"])
        self.assertTrue(any("ADVARSEL:" in line for line in logs))
        self.assertEqual(1.0, progress[-1][0])


if __name__ == "__main__":
    unittest.main()
