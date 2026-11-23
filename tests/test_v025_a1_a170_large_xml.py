"""v0.2.5-a1: A170 must not materialise enormous XPath node sets."""
from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from lxml import etree
from noark5_workflow.analysis import definition_engine as engine


ROOT = Path(__file__).resolve().parents[1]
A170_DEFINITION = ROOT / 'config/noark5/analysis/u1_u2_core_arkiv_arkivdel.json'


def _fixture_definition(path: Path) -> Path:
    """A small, independent fixture using the published A170 XPath grammar."""
    definition = {
        'format_version': 1, 'definition_id': 'test.a170', 'basis': {'source_material': ['U1', 'U2']},
        'entities': [
            {'id': 'archive', 'select': "//*[local-name()='arkiv']",
             'fields': {'title': "string(./*[local-name()='tittel'][1])",
                        'system_id': "string(./*[local-name()='systemID'][1])"},
             'children': [{'id': 'creators', 'select': ".//*[local-name()='arkivskaper']",
                           'fields': {'name': "string(./*[local-name()='arkivskaperNavn'][1])"}}],
             'metrics': [{'id': 'archive_part_count',
                          'expression': "count(.//*[local-name()='arkivdel'])", 'type': 'integer'}]},
            {'id': 'archive_part', 'select': "//*[local-name()='arkivdel']",
             'fields': {'title': "string(./*[local-name()='tittel'][1])",
                        'system_id': "string(./*[local-name()='systemID'][1])",
                        'parent_archive_system_id': "string(ancestor::*[local-name()='arkiv'][1]/*[local-name()='systemID'][1])"},
             'metrics': [
                 {'id': name + '_count', 'expression': f"count(.//*[local-name()='{name}'])", 'type': 'integer'}
                 for name in ('mappe', 'registrering', 'dokumentbeskrivelse', 'dokumentobjekt')
             ]},
        ],
    }
    path.write_text(json.dumps(definition, ensure_ascii=False), encoding='utf-8')
    return path


class A170LargeXmlTests(unittest.TestCase):
    def setUp(self):
        temp = TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.definition = _fixture_definition(self.root / 'a170-definition.json')
        self.xml = self.root / 'arkivstruktur.xml'

    def _write_source(self, namespace: bool, folders: int = 4):
        tag = lambda value: '{urn:noark5}' + value if namespace else value
        root = etree.Element(tag('arkiv'), nsmap={None: 'urn:noark5'} if namespace else None)
        etree.SubElement(root, tag('systemID')).text = 'ARK-1'
        etree.SubElement(root, tag('tittel')).text = 'Testarkiv'
        etree.SubElement(etree.SubElement(root, tag('arkivskaper')), tag('arkivskaperNavn')).text = 'Arkivskaper A'
        for part_i in range(2):
            part = etree.SubElement(root, tag('arkivdel'))
            etree.SubElement(part, tag('systemID')).text = f'DEL-{part_i+1}'
            etree.SubElement(part, tag('tittel')).text = f'Arkivdel {part_i+1}'
            for _ in range(folders):
                folder = etree.SubElement(part, tag('mappe'))
                reg = etree.SubElement(folder, tag('registrering'))
                desc = etree.SubElement(reg, tag('dokumentbeskrivelse'))
                etree.SubElement(desc, tag('dokumentobjekt'))
        self.xml.write_bytes(etree.tostring(root, encoding='utf-8', xml_declaration=True))

    def test_namespace_and_non_namespace_preserve_canonical_fields_counts_and_order(self):
        for namespaced in (False, True):
            with self.subTest(namespace=namespaced):
                self._write_source(namespaced)
                out = engine.run_definition_analysis(self.xml, self.definition)
                self.assertEqual(out['model_format_version'], 1)
                self.assertEqual(out['summary']['entity_counts'], {'archive': 1, 'archive_part': 2})
                archive = out['entities']['archive'][0]
                self.assertEqual(archive['fields']['title'], 'Testarkiv')
                self.assertEqual(archive['metrics']['archive_part_count'], 2)
                self.assertEqual(archive['children']['creators'][0]['fields']['name'], 'Arkivskaper A')
                for n, part in enumerate(out['entities']['archive_part'], 1):
                    self.assertEqual(part['fields']['system_id'], f'DEL-{n}')
                    self.assertEqual(part['fields']['parent_archive_system_id'], 'ARK-1')
                    self.assertEqual(part['index'], n)
                    self.assertEqual(part['metrics'], {
                        'mappe_count': 4, 'registrering_count': 4,
                        'dokumentbeskrivelse_count': 4, 'dokumentobjekt_count': 4,
                    })

    def test_production_definition_uses_all_optimised_selectors_and_counts(self):
        if not A170_DEFINITION.is_file():
            self.skipTest('Local test harness lacks full repository config; included in repo regression')
        definition = engine.load_analysis_definition(A170_DEFINITION)
        self.assertEqual(definition['definition_id'], 'noark5.u1_u2.core.arkiv_arkivdel.v1')
        for entity in definition['entities']:
            self.assertIsNotNone(engine._LOCAL_NAME_SELECT.fullmatch(entity['select']))
            for child in entity.get('children', []):
                self.assertIsNotNone(engine._LOCAL_NAME_SELECT.fullmatch(child['select']))
            for metric in entity.get('metrics', []):
                self.assertIsNotNone(engine._LOCAL_NAME_COUNT.fullmatch(metric['expression']))

    def test_large_xml_never_uses_libxml2_for_broad_selectors_or_counts(self):
        # 25k source folders -> 100k+ descendants. The baseline A170 path
        # called a broad lxml xpath for entities and each count metric.
        self._write_source(True, folders=12_500)
        orig = engine._fallback_xpath
        unsafe = []

        def reject_broad(node, expression):
            if (engine._LOCAL_NAME_SELECT.fullmatch(expression.strip())
                    or engine._LOCAL_NAME_COUNT.fullmatch(expression.strip())):
                unsafe.append(expression)
                raise AssertionError('Large XPath nodeset was materialised: ' + expression)
            return orig(node, expression)

        with patch.object(engine, '_fallback_xpath', side_effect=reject_broad):
            out = engine.run_definition_analysis(self.xml, self.definition)
        self.assertFalse(unsafe)
        self.assertEqual(out['summary']['entity_counts']['archive_part'], 2)
        self.assertEqual(out['entities']['archive'][0]['metrics']['archive_part_count'], 2)
        for part in out['entities']['archive_part']:
            self.assertEqual(part['metrics']['mappe_count'], 12500)
            self.assertEqual(part['metrics']['dokumentobjekt_count'], 12500)

    def test_generic_xpath_remains_supported_without_rewrite(self):
        doc = etree.fromstring('<arkiv><mappe/><mappe/><tittel>A</tittel></arkiv>')
        self.assertEqual(engine._evaluate(doc, 'count(./mappe)'), 2)
        self.assertEqual(engine._evaluate(doc, 'string(./tittel)'), 'A')
        self.assertEqual(engine._evaluate(doc, "count(.//*[local-name()='mappe'])"), 2)

    def test_xpath_engine_error_fails_a170_instead_of_silently_returning_empty_result(self):
        self._write_source(False)
        broken = json.loads(self.definition.read_text(encoding='utf-8'))
        broken['entities'][0]['metrics'][0]['expression'] = 'this-is-not-an-xpath(())'
        self.definition.write_text(json.dumps(broken), encoding='utf-8')
        with self.assertRaisesRegex(engine.AnalysisDefinitionError, 'A170 feilet'):
            engine.run_definition_analysis(self.xml, self.definition)


if __name__ == '__main__':
    unittest.main()
