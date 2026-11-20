"""a9: transfer-value rules, complete streaming findings, provenance and safe non-assessment."""
from __future__ import annotations

import csv
import hashlib
import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest

from noark5_workflow.analysis.delivery_validator_v023_a9 import (
    DeliveryValidationError, inject_delivery_html, validate_delivery_values,
)


VALUES = {
    'M051_arkivdelstatus': ['Aktiv periode', 'Avsluttet periode', 'Uaktuelle mapper'],
    'M052_saksstatus': ['Under behandling', 'Avsluttet', 'Utgår'],
    'M053_journalstatus': ['Journalført', 'Ekspedert', 'Arkivert', 'Utgår'],
    'M054_dokumentstatus': ['Dokumentet er under redigering', 'Dokumentet er ferdigstilt'],
}
DELIVERY = {
    'M051': ('arkivdelstatus', ['Avsluttet periode']),
    'M052': ('saksstatus', ['Avsluttet', 'Utgår']),
    'M053': ('journalstatus', ['Arkivert', 'Utgår']),
    'M054': ('dokumentstatus', ['Dokumentet er ferdigstilt']),
}
OK_50 = SimpleNamespace(version='5.0', status='confirmed', schemas=())


def example_xml(arkivdel='Aktiv periode', sak='Under behandling',
                journal='Ekspedert', dokument='Dokumentet er under redigering'):
    return f'''<?xml version="1.0" encoding="UTF-8"?>
<arkiv xmlns="http://www.arkivverket.no/standarder/noark5/arkivstruktur">
  <arkivdel><arkivdelstatus>{arkivdel}</arkivdelstatus>
  <systemID>PART-001</systemID><klassifikasjonssystem><klasse>
  <mappe><saksstatus>{sak}</saksstatus><systemID>MAPPE-003</systemID>
  <registrering><journalstatus>{journal}</journalstatus>
    <systemID>REG-004</systemID>
    <dokumentbeskrivelse><dokumentstatus>{dokument}</dokumentstatus>
    <systemID>DOK-005</systemID></dokumentbeskrivelse>
  </registrering></mappe>
  </klasse></klassifikasjonssystem></arkivdel>
</arkiv>'''


class DeliveryA9Tests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.source = self.root/'Source'
        self.source.mkdir()
        self.work = self.root/'Work'/'noark5_reports'/'depot_validation'/'RUN-001'
        self.work.mkdir(parents=True)
        rules = {'format_version': 1, 'model': 'dwm.noark5.delivery-value-commentary.v1',
                 'reference_version': '5.0', 'source': {'title': 'Noark 5 v5 Vedlegg 1',
                                                    'url': 'https://example.invalid/source.pdf'},
                 'rules': [{'metadata_id': mid, 'xml_field': key, 'delivery_values': values,
                            'applies_to': 'avlevering', 'page': i + 11}
                           for i, (mid, (key, values)) in enumerate(DELIVERY.items())]}
        prod = {'versions': {'5.0': {'value_sets': {
            key: {'metadata_id': key.split('_')[0], 'values': items}
            for key, items in VALUES.items()}}}}
        self.rules = self.root/'rules.json'
        self.values = self.root/'values.json'
        self.rules.write_text(json.dumps(rules, ensure_ascii=False), encoding='utf-8')
        self.values.write_text(json.dumps(prod, ensure_ascii=False), encoding='utf-8')
        self.xml = self.source/'arkivstruktur.xml'
        self.xml.write_text(example_xml(), encoding='utf-8')

    def scan(self, version=OK_50, cancel=None):
        return validate_delivery_values(self.source, self.work,
                                        source_ref='noark5_reports/depot_validation/RUN-001/delivery-funn.jsonl',
                                        rules_path=self.rules, values_path=self.values,
                                        version_evidence=version, cancel=cancel)

    def test_distinguishes_production_from_delivery_and_preserves_each_occurrence(self):
        result = self.scan()
        self.assertEqual(result['status'], 'completed_with_deviations')
        self.assertEqual(result['rules_checked'], 4)
        self.assertEqual(result['finding_count'], 4)
        self.assertTrue(result['complete'])
        rows = [json.loads(line) for line in (self.work/'delivery-funn.jsonl').read_text().splitlines()]
        self.assertEqual([x['metadata_id'] for x in rows], ['M054', 'M053', 'M052', 'M051'])
        self.assertTrue(all(x['standard_value'] for x in rows))
        self.assertTrue(all(x['delivery_value'] is False for x in rows))
        self.assertEqual(rows[0]['object_id'], 'DOK-005')
        self.assertEqual(rows[1]['object_id'], 'REG-004')
        self.assertEqual(rows[2]['object_id'], 'MAPPE-003')
        self.assertEqual(rows[3]['archive_part_id'], 'PART-001')
        self.assertTrue(all(x['file'] == 'arkivstruktur.xml' for x in rows))
        self.assertTrue(all(x['lines'][0] > 0 and "local-name()" in x['xpath'] for x in rows))
        self.assertEqual(result['source_sha256'], hashlib.sha256(self.xml.read_bytes()).hexdigest())
        self.assertEqual(result['finding_file_sha256'], hashlib.sha256(
            (self.work/'delivery-funn.jsonl').read_bytes()).hexdigest())
        self.assertFalse(result['automatic_approval'])
        self.assertEqual(json.loads((self.work/'delivery-validation.json').read_text())['finding_count'], 4)

    def test_all_delivery_values_valid_still_not_automatic_approval(self):
        self.xml.write_text(example_xml('Avsluttet periode','Avsluttet','Arkivert',
                                         'Dokumentet er ferdigstilt'), encoding='utf-8')
        result = self.scan()
        self.assertEqual(result['status'], 'completed_without_observed_deviations')
        self.assertEqual(result['finding_count'], 0)
        self.assertFalse(result['automatic_approval'])
        self.assertTrue(all(r['status'] == 'no_observed_delivery_deviation' for r in result['rules']))

    def test_unknown_value_is_not_silently_production_approved(self):
        self.xml.write_text(example_xml(sak='UPLUKKET'), encoding='utf-8')
        result = self.scan()
        sak = next(x for x in result['rules'] if x['metadata_id']=='M052')
        self.assertEqual(sak['outside_production_set'], 1)
        row = next(json.loads(x) for x in (self.work/'delivery-funn.jsonl').read_text().splitlines()
                   if 'M052' in x)
        self.assertFalse(row['standard_value'])

    def test_unconfirmed_or_other_version_never_gets_pass(self):
        for version in (SimpleNamespace(version='5.0', status='partial'),
                        SimpleNamespace(version='4.0', status='confirmed'),
                        SimpleNamespace(version=None, status='conflict')):
            with self.subTest(version=version):
                result = self.scan(version)
                self.assertEqual(result['status'], 'not_assessed')
                self.assertFalse(result['complete'])
                self.assertIsNone(result['finding_count'])
                self.assertFalse((self.work/'delivery-funn.jsonl').exists())

    def test_300_301_boundary_is_not_a_finding_ceiling(self):
        for count in (300, 301):
            with self.subTest(count=count):
                xml = '<arkiv xmlns="http://www.arkivverket.no/standarder/noark5/arkivstruktur">'
                xml += '<arkivdel><systemID>PART-1</systemID>'
                xml += ''.join('<mappe><saksstatus>Under behandling</saksstatus></mappe>'
                               for _ in range(count))
                xml += '</arkivdel></arkiv>'
                self.xml.write_text(xml, encoding='utf-8')
                result = self.scan()
                self.assertEqual(result['finding_count'], count)
                for name in ('delivery-funn.jsonl', 'delivery-funn.csv', 'delivery-validation.json'):
                    (self.work/name).unlink()

    def test_wrong_root_or_namespace_fails_closed(self):
        self.xml.write_text('<arkiv xmlns="urn:not-noark"><arkivdel/></arkiv>',encoding='utf-8')
        with self.assertRaisesRegex(DeliveryValidationError, 'namespace'):
            self.scan()
        self.assertFalse((self.work/'delivery-validation.json').exists())

    def test_second_permitted_values_for_m052_and_m053(self):
        self.xml.write_text(example_xml('Avsluttet periode','Utgår','Utgår',
                                         'Dokumentet er ferdigstilt'),encoding='utf-8')
        result = self.scan()
        self.assertEqual(result['finding_count'], 0)

    def test_full_streaming_over_old_300_issue_limit(self):
        count = 1250
        xml = '<arkiv xmlns="http://www.arkivverket.no/standarder/noark5/arkivstruktur"><arkivdel><systemID>PART-1</systemID>'
        xml += '<arkivdelstatus>Avsluttet periode</arkivdelstatus>'
        xml += '<klassifikasjonssystem><klasse>'
        xml += ''.join(f'<mappe><systemID>M-{i}</systemID><saksstatus>Under behandling</saksstatus></mappe>'
                       for i in range(count))
        xml += '</klasse></klassifikasjonssystem></arkivdel></arkiv>'
        self.xml.write_text(xml, encoding='utf-8')
        result = self.scan()
        self.assertEqual(result['finding_count'], count)
        lines = (self.work/'delivery-funn.jsonl').read_text().splitlines()
        self.assertEqual(len(lines), count)
        self.assertEqual(json.loads(lines[-1])['object_id'], 'M-1249')
        self.assertEqual(len({json.loads(x)['finding_uid'] for x in lines}), count)
        with (self.work/'delivery-funn.csv').open(encoding='utf-8', newline='') as f:
            self.assertEqual(len(list(csv.DictReader(f, delimiter=';'))), count)

    @unittest.skipUnless(os.environ.get('DWM_A9_STRESS') == '1', '100,000-forekomsttest krever DWM_A9_STRESS=1')
    def test_hundred_thousand_source_issues_stress(self):
        count = 100_000
        with self.xml.open('w',encoding='utf-8') as f:
            f.write('<arkiv xmlns="http://www.arkivverket.no/standarder/noark5/arkivstruktur"><arkivdel><systemID>PART-1</systemID>')
            for i in range(count):
                f.write('<mappe><saksstatus>Under behandling</saksstatus></mappe>')
            f.write('</arkivdel></arkiv>')
        result = self.scan()
        self.assertEqual(result['finding_count'], count)

    def test_cancellation_has_no_published_partial_claim(self):
        with self.assertRaisesRegex(DeliveryValidationError, 'avbrutt'):
            self.scan(cancel=lambda: True)
        self.assertFalse((self.work/'delivery-validation.json').exists())
        self.assertFalse((self.work/'delivery-funn.jsonl').exists())

    def test_malformed_xml_has_no_complete_report(self):
        self.xml.write_text('<arkiv xmlns="http://www.arkivverket.no/standarder/noark5/arkivstruktur"><mappe>', encoding='utf-8')
        with self.assertRaises(DeliveryValidationError):
            self.scan()
        self.assertFalse((self.work/'delivery-validation.json').exists())
        self.assertFalse((self.work/'delivery-funn.csv').exists())

    def test_conflicting_rule_and_production_set_fails_closed(self):
        obj = json.loads(self.rules.read_text())
        obj['rules'][0]['delivery_values'] = ['FANTASI']
        self.rules.write_text(json.dumps(obj), encoding='utf-8')
        with self.assertRaisesRegex(DeliveryValidationError, 'mangler i standardverdisett'):
            self.scan()
        self.assertFalse((self.work/'delivery-validation.json').exists())

    def test_missing_or_unknown_fields_are_not_auto_pass(self):
        self.xml.write_text('<arkiv xmlns="http://www.arkivverket.no/standarder/noark5/arkivstruktur"><arkivdel><systemID>A</systemID></arkivdel></arkiv>',encoding='utf-8')
        result = self.scan()
        self.assertEqual(result['finding_count'], 0)
        self.assertTrue(all(r['status']=='not_observed' for r in result['rules']))

    def test_html_injects_source_bound_summary_and_escapes(self):
        p = self.work/'report.html'
        p.write_text('<html><body>Behold meg</body></html>',encoding='utf-8')
        result = self.scan()
        inject_delivery_html(p, result)
        html = p.read_text(encoding='utf-8')
        self.assertIn('Behold meg',html)
        self.assertIn('M052',html)
        self.assertIn('delivery-funn.jsonl',html)
        self.assertIn('Ingen automatisk godkjenning',html)

    def test_output_will_not_overwrite_existing_evidence(self):
        (self.work/'delivery-funn.jsonl').write_text('SAVED',encoding='utf-8')
        with self.assertRaisesRegex(DeliveryValidationError, 'eksisterer allerede'):
            self.scan()
        self.assertEqual((self.work/'delivery-funn.jsonl').read_text(), 'SAVED')


if __name__ == '__main__':
    unittest.main()
