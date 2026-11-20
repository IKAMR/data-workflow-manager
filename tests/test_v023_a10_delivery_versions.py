"""a10: XSD-gated 3.1/4.0/5.0 delivery, period REVIEW, provenance and rollback."""
from __future__ import annotations

import csv
from hashlib import sha256
import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock

import noark5_workflow.analysis.delivery_validator_v023_a9 as delivery


NS = 'http://www.arkivverket.no/standarder/noark5/arkivstruktur'
F = ['M051_arkivdelstatus','M052_saksstatus','M053_journalstatus','M054_dokumentstatus']
COMMON = {
    'M051_arkivdelstatus': ['Aktiv periode','Overlappingsperiode','Avsluttet periode','Uaktuelle mapper'],
    'M052_saksstatus': ['Under behandling','Avsluttet','Utgår'],
    'M054_dokumentstatus': ['Dokumentet er under redigering','Dokumentet er ferdigstilt'],
}
SOURCE_DIGEST = {
    '3.1': '152eeb31e3e0edde94677ea9290cde0fb3b4cea1f7c16b7b8b07a82374c31814',
    '4.0': '77bd31a112c2f0d62d575d9e8843bc0ae59acf9bacaa60760795433d0f85954c',
    '5.0': 'e1f6b7caa24f869d82b21aa30b3452513029875e417b1e351b2b9298578ffd98',
}


def evidence(version, *, status='confirmed', schemas=True):
    return SimpleNamespace(version=version, status=status,
        schemas=(SimpleNamespace(path=Path('arkivstruktur.xsd'),
                                 version=version, digest='a'*64),) if schemas else ())


def xml_document(*, sak='Under behandling', journal='Arkivert',
                 part='Avsluttet periode', doc='Dokumentet er ferdigstilt',
                 begin='', end='', second_part='', foreign='') -> str:
    dates = ''.join(f'<{name}>{value}</{name}>' for name, value in (
        ('arkivperiodeStartDato', begin), ('arkivperiodeSluttDato', end)) if value)
    nested = (f'<klassifikasjonssystem><klasse><mappe><systemID>S-1</systemID>'
              f'<saksstatus>{sak}</saksstatus><registrering><systemID>R-1</systemID>'
              f'<journalstatus>{journal}</journalstatus><dokumentbeskrivelse>'
              f'<systemID>D-1</systemID><dokumentstatus>{doc}</dokumentstatus>'
              '</dokumentbeskrivelse></registrering></mappe></klasse></klassifikasjonssystem>')
    return (f'<arkiv xmlns="{NS}" xmlns:ext="urn:other">'
            f'<arkivdel><systemID>AD-1</systemID><arkivdelstatus>{part}</arkivdelstatus>'
            f'{dates}{nested}{foreign}</arkivdel>{second_part}</arkiv>')


class DeliveryA10Tests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.source = self.root/'Source'
        self.source.mkdir()
        self.out = self.root/'Work'
        self.out.mkdir()
        self.xml = self.source/'arkivstruktur.xml'
        values = {}
        for version in ('3.1','4.0','5.0'):
            fields = dict(COMMON)
            fields['M053_journalstatus'] = (
                ['Journalført','Ferdigstilt fra saksbehandler','Godkjent av leder','Ekspedert','Arkivert','Utgår']
                if version in ('3.1','4.0') else ['Journalført','Ekspedert','Arkivert','Utgår'])
            values[version] = {'value_sets': {field: {'metadata_id': field.split('_')[0], 'values': vv}
                            for field,vv in fields.items()}}
        self.values = self.root/'standard-values.json'
        self.values.write_text(json.dumps({'versions': values},ensure_ascii=False),encoding='utf-8')
        self.rules = delivery.RULES_FILE

    def scan(self, version='4.0', *, evidence_obj=None, rule_path=None):
        return delivery.validate_delivery_values(
            self.source, self.out, source_ref='reports/RUN-1/delivery-funn.jsonl',
            version_evidence=evidence_obj if evidence_obj is not None else evidence(version),
            rules_path=rule_path or self.rules, values_path=self.values)

    def rows(self):
        return [json.loads(row) for row in (self.out/'delivery-funn.jsonl').read_text(encoding='utf-8').splitlines()]

    def test_versions_have_independent_pinned_source_references(self):
        rules = json.loads(self.rules.read_text(encoding='utf-8'))
        self.assertEqual(set(rules['versions']), {'3.1','4.0','5.0'})
        for ver in ('3.1','4.0','5.0'):
            with self.subTest(ver=ver):
                self.assertEqual(rules['versions'][ver]['source']['sha256'], SOURCE_DIGEST[ver])
                self.assertIn('/v'+ver+'/', rules['versions'][ver]['source']['file'])
                self.assertEqual(set(r['metadata_id'] for r in rules['versions'][ver]['rules']),
                                 {'M051','M052','M053','M054'})
        self.assertEqual(rules['source_commit'], '8d28e312e1e38af8cb93bfe05cecef11e09af34f')

    def test_31_and_40_historical_production_only_values_become_delivery_findings(self):
        for ver in ('3.1','4.0'):
            with self.subTest(version=ver):
                self.xml.write_text(xml_document(journal='Godkjent av leder'),encoding='utf-8')
                data = self.scan(ver)
                self.assertEqual(data['version'],ver)
                self.assertEqual(data['finding_count'],2)  # M052, M053
                self.assertEqual(data['source_reference']['sha256'],SOURCE_DIGEST[ver])
                j=next(r for r in self.rows() if r['metadata_id']=='M053')
                self.assertTrue(j['standard_value'])
                self.assertFalse(j['delivery_value'])
                self.assertEqual(j['object_id'],'R-1')
                self.assertEqual(j['archive_part_id'],'AD-1')
                for fname in ('delivery-funn.jsonl','delivery-funn.csv','delivery-validation.json'):
                    (self.out/fname).unlink()

    def test_50_historical_journalstatus_is_outside_its_production_set(self):
        self.xml.write_text(xml_document(journal='Godkjent av leder'),encoding='utf-8')
        report=self.scan('5.0')
        m=next(x for x in report['rules'] if x['metadata_id']=='M053')
        self.assertEqual(m['outside_production_set'],1)
        finding=next(x for x in self.rows() if x['metadata_id']=='M053')
        self.assertFalse(finding['standard_value'])

    def test_historic_version_without_actual_xsd_evidence_stays_unassessed(self):
        self.xml.write_text(xml_document(),encoding='utf-8')
        for ver in ('3.1','4.0'):
            d=self.scan(ver,evidence_obj=evidence(ver,schemas=False))
            self.assertEqual(d['status'],'not_assessed')
            self.assertIsNone(d['finding_count'])
            self.assertFalse((self.out/'delivery-funn.jsonl').exists())

    def test_mismatched_or_partial_version_does_not_approve(self):
        self.xml.write_text(xml_document(),encoding='utf-8')
        for obj in [evidence('3.1',status='partial'), evidence('6.0'),
                    evidence('4.0',status='conflict')]:
            with self.subTest(v=obj.version):
                d=self.scan('3.1',evidence_obj=obj)
                self.assertEqual(d['status'],'not_assessed')
                self.assertEqual(d['rules_checked'],0)
                self.assertFalse((self.out/'delivery-funn.jsonl').exists())

    def test_closed_part_with_reversed_period_is_review_not_technical_error(self):
        self.xml.write_text(xml_document(sak='Avsluttet',begin='2022-01-01',end='2021-12-31'),encoding='utf-8')
        result=self.scan('4.0')
        self.assertEqual(result['period_review_findings'],1)
        self.assertEqual(result['delivery_value_findings'],0)
        self.assertEqual(result['finding_count'],1)
        self.assertEqual(result['status'],'completed_with_period_reviews')
        finding=self.rows()[0]
        self.assertEqual(finding['severity'],'REVIEW')
        self.assertEqual(finding['metadata_id'],'M107/M108')
        self.assertEqual(finding['archive_part_id'],'AD-1')
        model={'technical_validation':{'status':'ok','summary':{'ok':10}},'deviations':[]}
        amended=delivery.attach_delivery_to_depot_model(model,result)
        self.assertEqual(amended['technical_validation']['status'],'ok')
        self.assertEqual(amended['technical_validation']['summary']['delivery_value_deviations'],0)
        self.assertEqual(amended['deviations'][0]['severity'],'review')

    def test_period_missing_optional_date_cannot_be_called_failure_or_pass(self):
        self.xml.write_text(xml_document(sak='Avsluttet',begin='2020-01-01'),encoding='utf-8')
        result=self.scan('3.1')
        self.assertEqual(result['finding_count'],0)
        self.assertEqual(result['period_chronology']['with_one_date_field'],1)
        self.assertEqual(result['period_chronology']['status'],'no_observed_reversals')

    def test_two_archiveparts_keep_period_boundaries_separate(self):
        second=('<arkivdel><systemID>AD-2</systemID><arkivdelstatus>Avsluttet periode</arkivdelstatus>'
                '<arkivperiodeStartDato>2005-01-01</arkivperiodeStartDato>'
                '<arkivperiodeSluttDato>2004-12-31</arkivperiodeSluttDato></arkivdel>')
        self.xml.write_text(xml_document(sak='Avsluttet',begin='2000-01-01',end='2010-01-01',second_part=second),encoding='utf-8')
        r=self.scan('3.1')
        self.assertEqual(r['period_chronology']['archive_parts_seen'],2)
        self.assertEqual(r['period_chronology']['chronologically_ordered'],1)
        self.assertEqual(r['period_review_findings'],1)
        self.assertEqual(self.rows()[0]['archive_part_id'],'AD-2')

    def test_non_noark_namespace_status_is_not_counted(self):
        injected='<ext:mappe><ext:saksstatus>Under behandling</ext:saksstatus></ext:mappe>'
        self.xml.write_text(xml_document(sak='Avsluttet',foreign=injected),encoding='utf-8')
        r=self.scan('4.0')
        self.assertEqual(r['finding_count'],0)
        self.assertEqual(next(x for x in r['rules'] if x['metadata_id']=='M052')['observed_count'],1)

    def test_legacy_v5_and_current_catalogue_cannot_diverge(self):
        self.xml.write_text(xml_document(sak='Avsluttet'),encoding='utf-8')
        copy=self.root/'legacy-a3.json'
        copy.write_text(delivery.LEGACY_RULES_FILE.read_text(encoding='utf-8'),encoding='utf-8')
        legacy=json.loads(copy.read_text())
        legacy['rules'][0]['delivery_values']=['Aktiv periode']
        copy.write_text(json.dumps(legacy),encoding='utf-8')
        with mock.patch.object(delivery,'LEGACY_RULES_FILE',copy):
            with self.assertRaisesRegex(delivery.DeliveryValidationError, 'avviker fra a3'):
                self.scan('5.0')
        self.assertFalse((self.out/'delivery-validation.json').exists())

    def test_source_rename_or_fake_sha_fails_closed(self):
        self.xml.write_text(xml_document(),encoding='utf-8')
        copy=self.root/'a10-edit.json'
        d=json.loads(self.rules.read_text(encoding='utf-8'))
        d['versions']['4.0']['source']['sha256']='WRONG'
        copy.write_text(json.dumps(d,ensure_ascii=False),encoding='utf-8')
        with self.assertRaisesRegex(delivery.DeliveryValidationError,'kildeidentitet'):
            self.scan('4.0',rule_path=copy)
        self.assertFalse((self.out/'delivery-validation.json').exists())

    def test_version_specific_register_cannot_be_the_a3_v5_register_for_31(self):
        self.xml.write_text(xml_document(),encoding='utf-8')
        with self.assertRaisesRegex(delivery.DeliveryValidationError,'gjelder ikke valgt Noark-versjon'):
            self.scan('3.1',rule_path=delivery.LEGACY_RULES_FILE)

    def test_source_unchanged_after_period_and_delivery_checks(self):
        self.xml.write_text(xml_document(begin='2020-02-02',end='2019-02-01'),encoding='utf-8')
        digest=sha256(self.xml.read_bytes()).hexdigest()
        result=self.scan('4.0')
        self.assertEqual(sha256(self.xml.read_bytes()).hexdigest(),digest)
        self.assertEqual(result['finding_count'],2)
        with (self.out/'delivery-funn.csv').open(encoding='utf-8',newline='') as inp:
            self.assertEqual(len(list(csv.DictReader(inp,delimiter=';'))),2)

    def test_not_assessed_does_not_modify_previous_technical_status(self):
        model={'technical_validation':{'status':'error','summary':{}},'deviations':[]}
        data={'status':'not_assessed','complete':False,'finding_count':None}
        out=delivery.attach_delivery_to_depot_model(model,data)
        self.assertEqual(out['technical_validation']['status'],'error')
        self.assertFalse(out['deviations'])

    def test_html_names_version_source_and_period_review(self):
        self.xml.write_text(xml_document(sak='Avsluttet',begin='2023-01-01',
                                         end='2022-01-01'),encoding='utf-8')
        report=self.scan('3.1')
        page=self.out/'depot.html'
        page.write_text('<html><body><p>Gamle data</p></body></html>',encoding='utf-8')
        delivery.inject_delivery_html(page,report)
        content=page.read_text(encoding='utf-8')
        self.assertIn('Gamle data',content)
        self.assertIn('Noark v3.1',content)
        self.assertIn('Arkivdeler undersøkt: 1',content)
        self.assertIn(SOURCE_DIGEST['3.1'],content)
        self.assertIn('manifeststatus: not_documented',content)

    def test_real_delivery_deviations_mark_technical_error_not_approval(self):
        self.xml.write_text(xml_document(),encoding='utf-8')
        d=self.scan('4.0')
        mod={'technical_validation':{'status':'ok','summary':{}},'deviations':[]}
        delivery.attach_delivery_to_depot_model(mod,d)
        self.assertEqual(mod['technical_validation']['status'],'error')
        self.assertEqual(mod['deviations'][0]['category'],'delivery_value_M052')
        self.assertFalse(d['automatic_approval'])


    def test_existing_complete_evidence_is_never_deleted_by_failed_run(self):
        self.xml.write_text(xml_document(), encoding='utf-8')
        previous = self.out/'delivery-validation.json'
        previous.write_text('{"protected":"previous-run"}',encoding='utf-8')
        with self.assertRaisesRegex(delivery.DeliveryValidationError,'eksisterer allerede'):
            self.scan('4.0')
        self.assertEqual(previous.read_text(encoding='utf-8'),'{"protected":"previous-run"}')
        self.assertFalse((self.out/'delivery-funn.jsonl').exists())

    def test_failed_second_publish_rolls_back_only_new_artifacts(self):
        self.xml.write_text(xml_document(), encoding='utf-8')
        real_replace = os.replace
        called = 0
        def fail_second(src, dst):
            nonlocal called
            called += 1
            if called == 2:
                raise OSError('simulated failure while publishing csv')
            return real_replace(src, dst)
        with mock.patch.object(delivery.os, 'replace', side_effect=fail_second):
            with self.assertRaisesRegex(delivery.DeliveryValidationError, 'simulated failure'):
                self.scan('4.0')
        for name in ('delivery-funn.jsonl','delivery-funn.csv','delivery-validation.json'):
            self.assertFalse((self.out/name).exists())

    def test_uncertain_period_format_is_not_falsely_compared(self):
        self.xml.write_text(xml_document(sak='Avsluttet',begin='2022-01-01Z',
                                         end='2021-12-31Z'),encoding='utf-8')
        result=self.scan('4.0')
        self.assertEqual(result['finding_count'],0)
        self.assertEqual(result['period_chronology']['uncomparable_date_formats'],1)
        self.assertEqual(result['period_review_findings'],0)

    def test_50_requires_primary_schema_when_an_actual_schema_list_exists(self):
        self.xml.write_text(xml_document(),encoding='utf-8')
        bad=SimpleNamespace(status='confirmed',version='5.0',
            schemas=(SimpleNamespace(path=Path('endringslogg.xsd'),version='5.0',digest='a'*64),))
        report=self.scan('5.0',evidence_obj=bad)
        self.assertEqual(report['status'],'not_assessed')
        self.assertFalse((self.out/'delivery-validation.json').exists())

    def test_mixed_status_and_period_review_have_separate_severity(self):
        self.xml.write_text(xml_document(begin='2023-01-01',end='2022-12-31'),encoding='utf-8')
        r=self.scan('4.0')
        self.assertEqual(r['finding_count'],2)
        self.assertEqual(r['delivery_value_findings'],1)
        self.assertEqual(r['period_review_findings'],1)
        rows=self.rows()
        self.assertEqual({row['severity'] for row in rows},{'ERROR','REVIEW'})
        model={'technical_validation':{'status':'ok','summary':{}},'deviations':[]}
        delivery.attach_delivery_to_depot_model(model,r)
        self.assertEqual(model['technical_validation']['status'],'error')
        self.assertEqual(len(model['deviations']),2)


if __name__ == '__main__':
    unittest.main()
