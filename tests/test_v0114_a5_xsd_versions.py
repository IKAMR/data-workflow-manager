"""a5: authoritative XSD signatures, conflict handling, and rule-version boundaries."""
from __future__ import annotations
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.noark_xsd_version_v0114_a5 import (
    SIGNATURES, _signatures, comparison_label, inspect_source_version,
    source_from_report, inspect_report_version,
)


class XsdVersionEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.xsd5 = b'<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema" />'
        self.xsd4 = b'<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema" version="other" />'
        self.hashes = {
            hashlib.sha256(self.xsd5).hexdigest(): {'version': '5.0', 'filename': 'arkivstruktur.xsd', 'repository_path': 'noark5/v5.0/schemas/arkivstruktur.xsd'},
            hashlib.sha256(self.xsd4).hexdigest(): {'version': '4.0', 'filename': 'metadatakatalog.xsd', 'repository_path': 'noark5/v4.0/schemas/metadatakatalog.xsd'},
        }

    def inspect(self, folder=None):
        with patch('app.noark_xsd_version_v0114_a5._signatures', return_value=self.hashes):
            return inspect_source_version(folder or self.root)

    def test_exact_hash_establishes_version_not_filename_alone(self):
        (self.root/'arkivstruktur.xsd').write_bytes(self.xsd5)
        result = self.inspect()
        self.assertEqual(result.version, '5.0')
        self.assertEqual(result.status, 'confirmed')
        self.assertEqual(result.schemas[0].reference, 'noark5/v5.0/schemas/arkivstruktur.xsd')
        self.assertIn('samsvarer', comparison_label(result, '5.0'))
        self.assertIn('Historisk sammenligning', comparison_label(result, '3.1'))

    def test_different_xsd_versions_do_not_select_a_winner(self):
        (self.root/'arkivstruktur.xsd').write_bytes(self.xsd5)
        (self.root/'metadatakatalog.xsd').write_bytes(self.xsd4)
        result = self.inspect()
        self.assertEqual(result.status, 'conflict')
        self.assertIsNone(result.version)
        self.assertIn('uavklart', comparison_label(result,'4.0').lower())

    def test_bad_addml_does_not_override_exact_xsd(self):
        (self.root/'arkivstruktur.xsd').write_bytes(self.xsd5)
        (self.root/'arkivuttrekk.xml').write_text('<root><noarkversjon>3.1</noarkversjon></root>', encoding='utf-8')
        result = self.inspect()
        self.assertEqual(result.version, '5.0')
        self.assertEqual(result.addml_version, '3.1')
        self.assertTrue(any('oppgir v3.1' in warning for warning in result.warnings))

    def test_addml_alone_or_unknown_xsd_never_confirms(self):
        (self.root/'arkivuttrekk.xml').write_text('<root><noarkversjon>5.0</noarkversjon></root>', encoding='utf-8')
        self.assertEqual(self.inspect().status, 'unknown')
        (self.root/'arkivstruktur.xsd').write_bytes(b'<xs:schema/>')
        self.assertEqual(self.inspect().status, 'unknown')
        self.assertIsNone(self.inspect().version)

    def test_generic_addml_version_is_not_noark_version(self):
        (self.root/'arkivuttrekk.xml').write_text('<addml version="3.1"><version>4.0</version></addml>', encoding='utf-8')
        self.assertIsNone(self.inspect().addml_version)

    def test_root_xsd_above_selected_sip_content(self):
        (self.root/'arkivstruktur.xsd').write_bytes(self.xsd5)
        selected = self.root/'content'/'sip'/'content'
        selected.mkdir(parents=True)
        self.assertEqual(self.inspect(selected).version, '5.0')

    def test_work_job_source_is_read_only_and_recovered(self):
        source = self.root/'source'; source.mkdir()
        (source/'arkivstruktur.xsd').write_bytes(self.xsd5)
        work = self.root/'work'; (work/'noark5_reports'/'depot_validation'/'run').mkdir(parents=True)
        (work/'job.json').write_text(json.dumps({'source_extraction': str(source)}), encoding='utf8')
        report = work/'noark5_reports'/'depot_validation'/'run'/'depot_validation_report.json'
        report.write_text('{}', encoding='utf8')
        self.assertEqual(source_from_report(report), source)
        with patch('app.noark_xsd_version_v0114_a5._signatures', return_value=self.hashes):
            self.assertEqual(inspect_report_version(report).version, '5.0')
        self.assertEqual(report.read_text(), '{}')
        self.assertTrue((source/'arkivstruktur.xsd').is_file())

    def test_shipped_catalog_has_exact_ikamr_source_reference(self):
        obj=json.loads(SIGNATURES.read_text(encoding='utf8'))
        self.assertEqual(obj['source_repository'], 'https://github.com/IKAMR/digital-archive-workflow')
        entries=obj['signatures']
        self.assertEqual(len(entries),20)
        assert all(len(row['sha256'])==64 for row in entries)
        self.assertEqual(len(set(row['sha256'] for row in entries)),20)
        self.assertTrue(any(x['version']=='5.0' and x['filename']=='arkivstruktur.xsd' for x in entries))


if __name__ == '__main__':
    unittest.main()
