"""Small-file semantic comparison; one-pass parser does not parse the whole tree."""
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from lxml import etree

from noark5_workflow.analysis.u1_total import run_u1_total
from noark5_workflow.analysis.u1_stream_v027_a12 import run_u1_stream


XML = '''<arkivstruktur xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
  <arkiv><systemID>A</systemID><tittel>Arkiv A</tittel><opprettetDato>2021-01-01</opprettetDato>
    <arkivskaper><arkivskaperNavn>Etaten</arkivskaperNavn></arkivskaper>
    <arkivdel><tittel>Del 1</tittel><arkivdelstatus>Aktiv periode</arkivdelstatus>
      <klassifikasjonssystem><klasse><klasse/><mappe xsi:type="saksmappe">
        <saksstatus>Avsluttet</saksstatus><opprettetDato>2021-03-01</opprettetDato>
        <registrering xsi:type="journalpost"><journalposttype>Inngående dokument</journalposttype>
          <journalstatus>Journalført</journalstatus><journaldato>2021-04-01</journaldato>
          <avskrivning><avskrivningsmaate>TE</avskrivningsmaate></avskrivning>
          <dokumentbeskrivelse><tilknyttetRegistreringSom>Hoveddokument</tilknyttetRegistreringSom>
            <dokumentstatus>Dokumentet er ferdigstilt</dokumentstatus>
            <dokumentmedium>Elektronisk arkiv</dokumentmedium>
            <dokumentobjekt><variantformat>Produksjonsformat</variantformat>
              <format>PDF</format><filstoerrelse>123</filstoerrelse>
              <versjonsnummer>1</versjonsnummer></dokumentobjekt>
          </dokumentbeskrivelse>
        </registrering>
      </mappe></klasse></klassifikasjonssystem>
    </arkivdel>
  </arkiv>
</arkivstruktur>'''


class U1StreamTest(unittest.TestCase):
    def test_matches_legacy_schema_and_values(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'arkivstruktur.xml'
            path.write_text(XML, encoding='utf-8')
            expected = run_u1_total(path)
            actual = run_u1_stream(path)
            self.assertEqual(actual, expected)

    def test_invalid_xml_does_not_return_partial_success(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'arkivstruktur.xml'
            path.write_text('<arkiv><mappe></arkiv>', encoding='utf-8')
            with self.assertRaises(etree.XMLSyntaxError):
                run_u1_stream(path)

    def test_uses_iterparse_not_full_parse(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'arkivstruktur.xml'
            path.write_text(XML, encoding='utf-8')
            with patch('lxml.etree.parse', side_effect=AssertionError('full tree forbidden')):
                self.assertEqual(run_u1_stream(path)['documents']['object_count'], 1)


if __name__ == '__main__':
    unittest.main()
