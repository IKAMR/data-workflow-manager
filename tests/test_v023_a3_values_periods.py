"""v0.2.3-a3: real XML counts, repository value sets, preserved period sources."""
from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import unittest

from app.ks_value_inspection_v023_a3 import (
    count_actual_xml_values, registered_field, load_period_evidence,
    delivery_condition, delivery_relation, period_review_text, value_review_text,
)
from app.ks_workshop_v022_a12 import WorkshopError


BUNDLE = {'versions': {'5.0': {'metadata': [
    {'metadata_id': 'M052', 'name': 'saksstatus', 'registered_value_set_id': 'M052_saksstatus',
     'source_id': 'noark5-metadata'},
    {'metadata_id': 'M053', 'name': 'journalstatus', 'registered_value_set_id': 'M053_journalstatus'},
    {'metadata_id': 'M300', 'name': 'dokumentmedium', 'registered_value_set_id': 'M300_dokumentmedium'},
    {'metadata_id': 'M051', 'name': 'arkivdelstatus', 'registered_value_set_id': 'M051_arkivdelstatus'},
    {'metadata_id': 'M054', 'name': 'dokumentstatus', 'registered_value_set_id': 'M054_dokumentstatus'},
], 'value_sets': {
    'M052_saksstatus': {'values': ['Under behandling', 'Avsluttet', 'Utgår'], 'value_set_role': 'obligatory_values'},
    'M053_journalstatus': {'values': ['Journalført', 'Arkivert', 'Utgår']},
    'M051_arkivdelstatus': {'values': ['Aktiv periode', 'Avsluttet periode']},
    'M054_dokumentstatus': {'values': ['Dokumentet er under redigering', 'Dokumentet er ferdigstilt']},
    'M300_dokumentmedium': {'values': ['Fysisk arkiv', 'Elektronisk arkiv']},
}}}}

SAMPLE = '''<?xml version="1.0" encoding="utf-8"?>
<arkiv>
 <arkivdel><systemID>STHA5</systemID>
  <mappe><systemID>A</systemID><saksstatus>Under behandling</saksstatus>
   <registrering><journalstatus>Journalført</journalstatus></registrering>
  </mappe>
  <mappe><systemID>B</systemID><saksstatus>Avsluttet</saksstatus>
   <registrering><journalstatus>Arkivert</journalstatus></registrering>
  </mappe>
  <mappe><systemID>C</systemID><saksstatus>Under behandling</saksstatus></mappe>
  <dokumentmedium>Elektronisk arkiv</dokumentmedium>
 </arkivdel>
 <arkivdel><systemID>STHA4</systemID>
  <mappe><systemID>D</systemID><saksstatus>Ukjent kode</saksstatus></mappe>
  <dokumentmedium>Fysisk arkiv</dokumentmedium>
 </arkivdel>
</arkiv>
'''


class ObservedValueTests(unittest.TestCase):
    def setUp(self):
        tmp = TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.xml = self.root / 'arkivstruktur.xml'
        self.xml.write_text(SAMPLE, encoding='utf-8')
        self.source = patch('app.ks_value_inspection_v023_a3.resolve_source_xml', return_value=self.xml)
        self.source.start()
        self.addCleanup(self.source.stop)

    def test_m52_and_standard_values_are_separate_from_arkade_status(self):
        record = registered_field(BUNDLE, '5.0', 'M052')
        self.assertEqual(record['xml_field'], 'saksstatus')
        self.assertIn('Under behandling', record['allowed'])
        results = count_actual_xml_values(self.root, BUNDLE, '5.0', 'M052', archive_part_id='STHA5')
        self.assertTrue(results['complete'])
        self.assertEqual(results['observed_total'], 4)
        self.assertEqual(results['inside_registered_set'], 3)
        self.assertEqual(results['outside_registered_set'], 1)
        rows = {r['value']: r for r in results['values']}
        self.assertEqual(rows['Under behandling']['total'], 2)
        self.assertEqual(rows['Under behandling']['archive_part'], 2)
        self.assertEqual(rows['Avsluttet']['archive_part'], 1)
        self.assertEqual(rows['Ukjent kode']['archive_part'], 0)
        self.assertEqual(rows['Utgår']['total'], 0)
        self.assertEqual(rows['Ukjent kode']['reference_relation'], 'Ikke i registrert verdisett')
        self.assertIn('IKKE angitt', rows['Under behandling']['delivery_relation'])
        self.assertIn('Angitt som tillatt', rows['Avsluttet']['delivery_relation'])
        self.assertEqual(results['eligible_at_delivery'], 1)
        self.assertEqual(results['not_eligible_at_delivery'], 3)
        self.assertIn('ikke godkjent', results['provenance_note'])

    def test_verified_delivery_requirements_are_not_confused_with_standard_set(self):
        for mid, permitted, nonpermitted in (
            ('M051', 'Avsluttet periode', 'Aktiv periode'),
            ('M052', 'Avsluttet', 'Under behandling'),
            ('M053', 'Arkivert', 'Journalført'),
            ('M054', 'Dokumentet er ferdigstilt', 'Dokumentet er under redigering'),
        ):
            with self.subTest(mid=mid):
                rule = delivery_condition(BUNDLE, '5.0', mid)
                self.assertIsNotNone(rule)
                self.assertIn(permitted, rule['delivery_values'])
                self.assertNotIn(nonpermitted, rule['delivery_values'])
                self.assertIn('Angitt som tillatt', delivery_relation(permitted, rule))
                self.assertIn('IKKE angitt', delivery_relation(nonpermitted, rule))
                self.assertIn('nasjonalarkivet.no', rule['source_url'])

    def test_older_versions_never_inherit_undocumented_delivery_rule(self):
        self.assertIsNone(delivery_condition(BUNDLE, '3.1', 'M052'))
        self.assertIsNone(delivery_condition(BUNDLE, '4.0', 'M052'))
        self.assertIn('Ingen dokumentert', delivery_relation('Under behandling', None))

    def test_other_status_fields_do_not_inflate_saksstatus(self):
        status = count_actual_xml_values(self.root, BUNDLE, '5.0', 'M053')
        self.assertEqual(status['observed_total'], 2)
        self.assertEqual({x['value'] for x in status['values'] if x['total']},
                         {'Journalført', 'Arkivert'})

    def test_m300_actual_values(self):
        record = count_actual_xml_values(self.root, BUNDLE, '5.0', 'M300')
        self.assertEqual(record['observed_total'], 2)
        self.assertEqual(record['inside_registered_set'], 2)

    def test_unknown_mfield_is_not_guessed(self):
        with self.assertRaises(WorkshopError):
            count_actual_xml_values(self.root, BUNDLE, '5.0', 'M999')

    def test_user_cancel_never_returns_partial_values(self):
        with self.assertRaisesRegex(WorkshopError, 'avbrutt'):
            count_actual_xml_values(self.root, BUNDLE, '5.0', 'M052', cancel=lambda: True)

    def test_invalid_xml_is_not_reported_as_zero(self):
        self.xml.write_text('<arkiv><mappe><saksstatus>Under behandling</mappe></arkiv>', encoding='utf-8')
        with self.assertRaises(WorkshopError):
            count_actual_xml_values(self.root, BUNDLE, '5.0', 'M052')

    def test_missing_source_is_not_reported_as_empty(self):
        self.xml.unlink()
        with self.assertRaises(WorkshopError):
            count_actual_xml_values(self.root, BUNDLE, '5.0', 'M052')

    def test_long_value_is_rejected_not_silently_truncated(self):
        self.xml.write_text('<arkiv><mappe><saksstatus>' + 'x' * 2100 + '</saksstatus></mappe></arkiv>')
        with self.assertRaises(WorkshopError):
            count_actual_xml_values(self.root, BUNDLE, '5.0', 'M052')

    def test_source_change_while_scanning_is_rejected(self):
        # When scanning starts, the original source is read-only. A changed
        # file must never yield a purportedly complete evidence inventory.
        original = self.xml.stat().st_size
        count = count_actual_xml_values(self.root, BUNDLE, '5.0', 'M052')
        self.assertEqual(count['source_size'], original)
        self.assertIn('automatisk normativ godkjenning', value_review_text(count).lower())

    def test_wrong_scope_never_becomes_another_archive_part(self):
        record = count_actual_xml_values(self.root, BUNDLE, '5.0', 'M052', archive_part_id='NEVER')
        self.assertEqual(sum(r['archive_part'] for r in record['values']), 0)
        self.assertEqual(record['observed_total'], 4)


class PeriodSourcesTests(unittest.TestCase):
    def setUp(self):
        tmp = TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        for d in ('metadata/source_evidence/x/source', 'noark5_reports/depot_validation/JOB-003__run'):
            (self.root / d).mkdir(parents=True)
        self.xml = self.root / 'metadata/source_evidence/x/source/info.xml'
        self.xml.write_text('<mets/>', encoding='utf-8')
        self.job = {'file_type': 'dwm-work-job', 'job_uid': 'uid-003',
                    'job': {'job_id': 'JOB-003', 'name': '1525_006 (2004-2023)'}}
        (self.root / 'job.json').write_text(json.dumps(self.job), encoding='utf-8')
        self.meta = {'job_id': 'JOB-003', 'source_imports': [{
            'kind': 'dias-mets', 'sha256': sha256(self.xml.read_bytes()).hexdigest(),
            'preserved_file': 'metadata/source_evidence/x/source/info.xml',
            'fields': {'period_start': '2004-01-01', 'period_end': '2009-12-31',
                       'label': '1525_006 (2004-2023)'}}]}
        (self.root / 'metadata/depot_metadata.json').write_text(json.dumps(self.meta), encoding='utf-8')
        self.relative = 'noark5_reports/depot_validation/JOB-003__run/depot_validation_report.json'
        self.report = {'period_reconciliation': {
            'declared_period': {'source': 'arkivuttrekk.xml', 'start_date': '2004-02-04',
                                'end_date': '2024-11-12'},
            'observed_series': {'folder_created': {'span': {'last_year': '2024'},
                                                  'counts': {'2024': 19}}}},
            'archive_parts': [{'archive_part': {'system_id': 'STHA5', 'title': 'STHA5',
                                               'status': 'Aktiv periode',
                                               'archive_period_start_date': '2010-01-01',
                                               'archive_period_end_date': ''}}]}
        (self.root / self.relative).write_text(json.dumps(self.report), encoding='utf-8')
        self.snapshot = {'work_identity': {'job_uid': 'uid-003'},
                         'evidence_manifest': [{'kind': 'dwm_depot', 'path': self.relative,
                                                'sha256': sha256((self.root / self.relative).read_bytes()).hexdigest()}]}

    def test_period_sources_are_kept_separate(self):
        data = load_period_evidence(self.root, self.snapshot)
        self.assertEqual(data['outer_end'], '2009-12-31')
        self.assertEqual(data['label_end'], '2023')
        self.assertEqual(data['inner_end'], '2024-11-12')
        self.assertEqual(data['archive_parts'][0]['status'], 'Aktiv periode')

    def test_year_2024_is_within_inner_but_outside_outer(self):
        data = load_period_evidence(self.root, self.snapshot)
        xml = {'fields': [{'field': 'saksdato', 'value': '2024-08-25'},
                          {'field': 'saksaar', 'value': '2024'}]}
        text = period_review_text(data, xml, archive_part_id='STHA5')
        self.assertIn('INNENFOR indre angitte datoer', text)
        self.assertIn('UTENFOR ytre info.xml-periode', text)
        self.assertIn('Arkivdel: STHA5 (Aktiv periode)', text)
        self.assertIn('19', text)
        self.assertIn('LABEL er ikke en kontrollgrense', text)

    def test_december_2024_is_outside_inner_exact_date_limit(self):
        data = load_period_evidence(self.root, self.snapshot)
        result = period_review_text(data, {'fields': [{'field': 'saksdato', 'value': '2024-12-25'}]})
        self.assertIn('UTENFOR indre angitte datoer', result)

    def test_report_tampering_is_rejected(self):
        (self.root / self.relative).write_text('{}', encoding='utf-8')
        with self.assertRaisesRegex(WorkshopError, 'SHA-256'):
            load_period_evidence(self.root, self.snapshot)

    def test_preserved_info_hash_mismatch_is_rejected(self):
        self.xml.write_text('<changed/>', encoding='utf-8')
        with self.assertRaisesRegex(WorkshopError, 'info.xml'):
            load_period_evidence(self.root, self.snapshot)

    def test_wrong_work_identity_is_rejected(self):
        self.snapshot['work_identity']['job_uid'] = 'other'
        with self.assertRaisesRegex(WorkshopError, 'identitet'):
            load_period_evidence(self.root, self.snapshot)


if __name__ == '__main__':
    unittest.main()
