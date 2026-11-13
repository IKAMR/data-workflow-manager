"""a5-fix1: XSD declaration and changelog evidence are distinct from byte hashes."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from app.noark_xsd_version_v0114_a5 import inspect_source_version, comparison_label


def schema(version, comment=''):
    return (f'<?xml version="1.0"?><xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema" '
            f'targetNamespace="http://www.arkivverket.no/standarder/noark5/arkivstruktur" '
            f'version="{version}"><!-- {comment} --></xs:schema>').encode('utf-8')

class XsdDeclaredVersionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def inspect(self):
        with patch('app.noark_xsd_version_v0114_a5._signatures', return_value={}):
            return inspect_source_version(self.root)

    def test_v5_unknown_hash_is_identified_from_actual_schema(self):
        (self.root/'arkivstruktur.xsd').write_bytes(schema('5.0'))
        result = self.inspect()
        self.assertEqual((result.status, result.version), ('confirmed', '5.0'))
        self.assertIn('ukjent SHA-256', result.schemas[0].status)

    def test_changelog_550_is_maintenance_of_standard_50(self):
        (self.root/'arkivstruktur.xsd').write_bytes(schema('5.0', '2023-11-09 - Endringer i versjon 5.5.0 - Vedlikehold'))
        result = self.inspect()
        self.assertEqual(result.version, '5.0')
        self.assertIn('5.5.0', result.schemas[0].maintenance_note)
        self.assertNotIn('5.5', result.display)

    def test_conflicting_known_schema_versions_are_not_silently_selected(self):
        (self.root/'arkivstruktur.xsd').write_bytes(schema('5.0'))
        (self.root/'metadatakatalog.xsd').write_bytes(schema('4.0'))
        result = self.inspect()
        self.assertEqual(result.status, 'conflict')
        self.assertIsNone(result.version)

    def test_addml_older_than_xsd_is_a_warning_not_authoritative(self):
        (self.root/'arkivstruktur.xsd').write_bytes(schema('5.0'))
        (self.root/'arkivuttrekk.xml').write_text('<root><noarkversjon>3.1</noarkversjon></root>',encoding='utf8')
        result = self.inspect()
        self.assertEqual(result.version, '5.0')
        self.assertTrue(any('oppgir v3.1' in w for w in result.warnings))

    def test_arbitrary_namespace_not_mistaken_for_noark(self):
        (self.root/'arkivstruktur.xsd').write_text('<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema" version="5.0" targetNamespace="https://example.org/custom"/>')
        self.assertEqual(self.inspect().status,'unknown')

    def test_one_known_one_unversioned_is_partial(self):
        (self.root/'arkivstruktur.xsd').write_bytes(schema('5.0'))
        (self.root/'metadatakatalog.xsd').write_text('<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema"/>')
        result = self.inspect()
        self.assertEqual((result.status,result.version),('partial','5.0'))
        self.assertIn('ikke fullt verifisert',comparison_label(result,'5.0'))

    def test_metadata_header_is_visible_in_gui(self):
        gui = (Path(__file__).resolve().parents[1]/'gui_qt'/'standard_values_v0114_a2.py').read_text(encoding='utf8')
        self.assertIn('rec.declared_version',gui)
        self.assertIn('rec.maintenance_note',gui)

if __name__ == '__main__': unittest.main()
