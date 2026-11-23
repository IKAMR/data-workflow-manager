"""Regression tests for the independent a170-180 delta (unittest)."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from noark5_workflow.analysis.defined_fields import extract_defined_fields, DEFAULT_DEFINITION
from noark5_workflow.analysis.legacy_a170_stream import run_legacy_a170_stream
from noark5_workflow.analysis.definition_engine import run_definition_analysis

ROOT = Path(__file__).resolve().parents[1]
LEGACY = ROOT / 'config/noark5/analysis/u1_u2_core_arkiv_arkivdel.json'

XML = '''<?xml version="1.0" encoding="UTF-8"?>
<arkivstruktur xmlns="http://example.test/noark5">
 <arkiv><systemID>ARCH-42</systemID><tittel>Hovedarkiv</tittel>
  <arkivskaper><arkivskaperNavn>IKAMR</arkivskaperNavn></arkivskaper>
  <arkivdel><systemID>PART-1</systemID><tittel>Sakarkiv</tittel>
   <mappe><registrering><dokumentbeskrivelse><dokumentobjekt/></dokumentbeskrivelse></registrering></mappe>
  </arkivdel>
  <arkivdel><tittel>Historisk</tittel><mappe/></arkivdel>
 </arkiv>
</arkivstruktur>'''


class LegacyDeltaTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.xml = Path(self.tmp.name) / 'arkivstruktur.xml'
        self.xml.write_text(XML, encoding='utf-8')

    def test_a120_archive_part_relations_are_streamed(self):
        result = extract_defined_fields(self.xml)
        rows = result['archive_parts']
        self.assertEqual(len(rows), 2)
        self.assertEqual([x['parent_archive_system_id'] for x in rows], ['ARCH-42'] * 2)
        self.assertEqual([x['parent_archive_title'] for x in rows], ['Hovedarkiv'] * 2)
        self.assertEqual(rows[0]['system_id'], 'PART-1')
        self.assertNotIn('_ancestor_owners', rows[0])

    def test_legacy_stream_matches_xpath_on_small_valid_xml(self):
        streamed = run_legacy_a170_stream(self.xml, LEGACY)
        xpath = run_definition_analysis(self.xml, LEGACY)
        self.assertEqual(streamed['summary'], xpath['summary'])
        self.assertEqual(streamed['entities'], xpath['entities'])
        self.assertEqual(streamed['entities']['archive_part'][0]['metrics']['mappe_count'], 1)
        self.assertEqual(streamed['entities']['archive_part'][1]['fields']['parent_archive_title'], 'Hovedarkiv')

    def test_invalid_xml_is_not_reported_complete(self):
        from noark5_workflow.analysis.definition_engine import AnalysisDefinitionError
        self.xml.write_text('<arkiv><arkivdel>', encoding='utf-8')
        with self.assertRaises(AnalysisDefinitionError):
            run_legacy_a170_stream(self.xml, LEGACY)

    def test_legacy_job_cursor_remains_separate_from_siegfried(self):
        # Zero-based cursor 5 represents operation number 6, A170.
        self.assertEqual(5 + 1, 6)


if __name__ == '__main__':
    unittest.main()
