from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from noark5_workflow.analysis.u1_total import run_u1_total
from noark5_workflow.app import build_registry


XML = """<?xml version="1.0" encoding="UTF-8"?>
<arkiv xmlns="urn:test:noark5" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
  <tittel>Testarkiv</tittel>
  <systemID>A1</systemID>
  <opprettetDato>2020-01-01T00:00:00</opprettetDato>
  <avsluttetDato>2024-12-31T00:00:00</avsluttetDato>
  <arkivskaper><arkivskaperNavn>Test kommune</arkivskaperNavn><arkivskaperID>9999</arkivskaperID></arkivskaper>
  <arkivdel>
    <tittel>Del 1</tittel>
    <dokumentmedium>Elektronisk arkiv</dokumentmedium>
    <opprettetDato>2020-01-02T00:00:00</opprettetDato>
    <avsluttetDato>2024-12-30T00:00:00</avsluttetDato>
    <klassifikasjonssystem>
      <klasse>
        <klasseID>K1</klasseID>
        <mappe xsi:type="saksmappe" a="1" b="2">
          <opprettetDato>2021-01-01T00:00:00</opprettetDato>
          <avsluttetDato>2022-01-01T00:00:00</avsluttetDato>
          <saksstatus>Avsluttet</saksstatus>
          <registrering xsi:type="journalpost" a="1" b="2">
            <registreringsID>R1</registreringsID>
            <opprettetDato>2021-02-01T00:00:00</opprettetDato>
            <arkivertDato>2021-02-02T00:00:00</arkivertDato>
            <journaldato>2021-02-03</journaldato>
            <journalposttype>Inngående dokument</journalposttype>
            <journalstatus>Arkivert</journalstatus>
            <dokumentbeskrivelse>
              <tilknyttetRegistreringSom>Hoveddokument</tilknyttetRegistreringSom>
              <dokumentstatus>Dokumentet er ferdigstilt</dokumentstatus>
              <dokumentmedium>Elektronisk arkiv</dokumentmedium>
              <dokumentnummer>1</dokumentnummer>
              <opprettetDato>2021-02-04T00:00:00</opprettetDato>
              <dokumentobjekt>
                <versjonsnummer>1</versjonsnummer>
                <variantformat>Arkivformat</variantformat>
                <filstoerrelse>1234</filstoerrelse>
                <format>PDF/A</format>
              </dokumentobjekt>
            </dokumentbeskrivelse>
          </registrering>
        </mappe>
      </klasse>
    </klassifikasjonssystem>
  </arkivdel>
</arkiv>
"""


class A19U1Tests(unittest.TestCase):
    def test_registry_exposes_u1_as_own_operation(self):
        registry = build_registry()
        operation = registry.get("analyse_noark5_u1")
        self.assertEqual("Noark 5 U1 – samlet opptelling", operation.definition.name)

    def test_u1_counts_whole_extraction(self):
        with tempfile.TemporaryDirectory() as tmp:
            xml = Path(tmp) / "arkivstruktur.xml"
            xml.write_text(XML, encoding="utf-8")
            result = run_u1_total(xml)
        self.assertEqual("whole_extraction", result["scope"])
        self.assertEqual(1, result["archive"]["count"])
        self.assertEqual(1, result["structure"]["archive_part_count"])
        self.assertEqual(1, result["folders"]["count"])
        self.assertEqual(1, result["registrations"]["count"])
        self.assertEqual(1, result["documents"]["description_count"])
        self.assertEqual(1, result["documents"]["object_count"])

    def test_u1_preserves_dynamic_counts(self):
        with tempfile.TemporaryDirectory() as tmp:
            xml = Path(tmp) / "arkivstruktur.xml"
            xml.write_text(XML, encoding="utf-8")
            result = run_u1_total(xml)
        self.assertEqual({"saksmappe": 1}, result["folders"]["type_counts"])
        self.assertEqual({"journalpost": 1}, result["registrations"]["type_counts"])
        self.assertEqual({"Inngående dokument": 1}, result["registrations"]["journalposts"]["type_counts"])
        self.assertEqual({"Arkivformat": 1}, result["documents"]["variant_format_counts"])
        self.assertEqual({"PDF/A": 1}, result["files"]["format_counts"])

    def test_u1_dates_and_file_statistics(self):
        with tempfile.TemporaryDirectory() as tmp:
            xml = Path(tmp) / "arkivstruktur.xml"
            xml.write_text(XML, encoding="utf-8")
            result = run_u1_total(xml)
        self.assertEqual("2021-01-01", result["dates"]["folder_created"]["first"])
        self.assertEqual("2021-02-03", result["dates"]["journal_date"]["first"])
        self.assertEqual(1234, result["files"]["size_sum"])
        self.assertEqual(1, result["files"]["size_buckets"]["1000-1999"])

    def test_reference_files_are_preserved(self):
        root = Path(__file__).resolve().parents[1]
        reference = root / "docs/reference/kdrs-query"
        self.assertTrue((reference / "xml-queries_noark5_2026-05-26_U1.txt").is_file())
        self.assertTrue((reference / "xml-queries_noark5_2026-05-26_U2.txt").is_file())
        self.assertTrue((reference / "xml-queries_noark5_2026-05-26.txt").is_file())
        self.assertTrue((reference / "xml-queries_noark5_2026-05-26_no-journal.txt").is_file())
        self.assertTrue((reference / "xml-queries_noark5_2026-05-26_no-offjournal.txt").is_file())


if __name__ == "__main__":
    unittest.main()
