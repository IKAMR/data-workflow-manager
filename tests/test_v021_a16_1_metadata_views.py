"""a16.1: non-duplicating metadata views and evidence mapping for both METS kinds."""
from __future__ import annotations

import json
from hashlib import sha256
from pathlib import Path
import tempfile
import unittest

from test_v021_a16_complete_dias_metadata import AUTHOR, make_xml
from noark5_workflow.reporting.dias_metadata_v021_a16 import (
    FIELD_ROWS, MetadataA16Error, LOC_NS, INNER_NS, import_inner_mets,
    load_metadata, save_field,
)
from noark5_workflow.reporting.dias_metadata_views_v021_a16_1 import (
    expected_references, technical_read_only,
)


class A161MetadataViewTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.work = self.root / 'work'
        (self.work / 'metadata').mkdir(parents=True)
        (self.work / 'job.json').write_text(json.dumps({
            'file_type': 'dwm-work-job', 'job_uid': 'stable-job-uuid',
            'job': {'job_id': 'JOB-001', 'job_uid': 'stable-job-uuid'},
        }), encoding='utf-8')
        self.source = self.root / 'info.xml'
        self.original = make_xml()
        self.source.write_bytes(self.original)
        self.outer = import_inner_mets(self.work, self.source)

    def _load(self, sha=None):
        return load_metadata(self.work, sha)

    def _import_inner(self, data=None):
        path = self.root / 'dias-mets.xml'
        path.write_bytes(data if data is not None else make_xml(INNER_NS))
        return import_inner_mets(self.work, path)

    def test_all_47_fields_have_independent_outer_and_inner_references(self):
        self.assertEqual(len(FIELD_ROWS), 47)
        state = self._load()
        self.assertEqual(len(state['field_references']), 47)
        for key, _, _ in FIELD_ROWS:
            refs = state['field_references'][key]
            self.assertEqual(set(refs), {'outer', 'inner'})
            for role in ('outer', 'inner'):
                self.assertIn('expected', refs[role])
                self.assertIn('status', refs[role])
            self.assertEqual(next(r for r in state['rows'] if r['id'] == 'field:' + key)['references'], refs)

    def test_exact_observed_outer_xpath_and_digest(self):
        ref = self._load()['field_references']['archivist_org']['outer']
        self.assertEqual(ref['status'], 'påvist')
        self.assertIn("/mets:agent[1]/mets:name[1]/text()", ref['actual'])
        self.assertIn("@ROLE='ARCHIVIST'", ref['expected'])
        self.assertEqual(ref['value'], 'Test kommune')
        self.assertEqual(ref['sha256'], sha256(self.original).hexdigest())

    def test_arkade_notes_reference_uses_marker_and_exact_ordinal(self):
        ref = self._load()['field_references']['archivist_address']['outer']
        self.assertEqual(ref['status'], 'påvist')
        self.assertIn('notescontent:Address', ref['expected'])
        self.assertIn('/mets:note[1]/text()', ref['actual'])
        self.assertEqual(ref['value'], 'Kontaktveien 2')

    def test_unimported_inner_does_not_mean_xml_field_missing(self):
        ref = self._load()['field_references']['label']['inner']
        self.assertEqual(ref['status'], 'kilde ikke importert')
        self.assertEqual(ref['expected'], '/dias:mets/@LABEL')
        self.assertIsNone(ref['actual'])
        self.assertFalse(ref['sha256'])

    def test_imported_inner_has_distinct_source_sha_and_xpath(self):
        inner = self._import_inner()
        data = self._load()
        self.assertEqual(set(data['paired_sources']), {'outer', 'inner'})
        refs = data['field_references']['label']
        self.assertEqual(refs['outer']['status'], 'påvist')
        self.assertEqual(refs['inner']['status'], 'påvist')
        self.assertNotEqual(refs['outer']['sha256'], refs['inner']['sha256'])
        self.assertEqual(refs['inner']['sha256'], inner['sha256'])
        self.assertEqual(refs['inner']['actual'], '/dias:mets[1]/@LABEL')
        self.assertEqual(data['paired_differences'], 0)

    def test_inner_selected_still_pairs_outer_with_no_merged_values(self):
        inner = self._import_inner()
        state = self._load(inner['sha256'])
        self.assertEqual(state['selected_source']['sha256'], inner['sha256'])
        self.assertEqual(state['field_references']['archivist_org']['outer']['source_name'], 'info.xml')
        self.assertEqual(state['field_references']['archivist_org']['inner']['source_name'], 'dias-mets.xml')

    def test_imported_field_not_present_is_not_claimed_found(self):
        refs = self._load()['field_references']['project_name']
        self.assertEqual(refs['outer']['status'], 'ikke påvist')
        self.assertEqual(refs['inner']['status'], 'kilde ikke importert')
        self.assertIn('PROJECTNAME', refs['outer']['expected'])
        self.assertIn('Arkade', refs['outer']['note'])

    def test_unapproved_extraction_date_mapping_not_invented(self):
        ref = expected_references('extraction_date')
        self.assertEqual(ref['outer']['expected'], None)
        self.assertEqual(ref['inner']['expected'], None)
        self.assertIn('VERSDATE', ref['inner']['note'])
        data = self._load()['field_references']['extraction_date']
        self.assertEqual(data['inner']['status'], 'ikke kartlagt')

    def test_other_sources_do_not_impersonate_selected_source(self):
        modified = make_xml(INNER_NS).replace(b'Test LABEL', b'Annet LABEL')
        self._import_inner(modified)
        state = self._load()
        row = next(r for r in state['rows'] if r['id'] == 'field:label')
        self.assertEqual(row['historical'], 'Test LABEL')
        self.assertTrue(row['source_conflict'])
        self.assertEqual(state['paired_differences'], 1)
        self.assertEqual(row['references']['outer']['value'], 'Test LABEL')
        self.assertEqual(row['references']['inner']['value'], 'Annet LABEL')
        self.assertEqual(row['status'], 'ikke registrert')  # current Work value absent, not approval

    def test_extended_rows_have_no_primary_canonical_duplicate(self):
        data = self._load()
        extended = data['extended_rows']
        xml = [r for r in data['rows'] if r['kind'] == 'xml']
        self.assertGreater(len(xml), len(extended))
        ext_values = [str(r['historical']) for r in extended]
        self.assertNotIn('Test kommune', ext_values)
        self.assertNotIn('Arkivleder', ext_values)
        self.assertIn('Historisk kommune', ext_values)
        self.assertIn('viktig ekstrafelt', ext_values)
        self.assertEqual(len({r['id'] for r in extended}), len(extended))

    def test_files_are_summarized_one_row_per_object(self):
        data = self._load()
        files = [r for r in data['extended_rows'] if r['group'].startswith('Filfortegnelse')]
        self.assertEqual(len(files), 2)
        self.assertTrue(all(r['kind'] == 'summary' and not r['editable'] for r in files))
        self.assertIn('file:first.xml', files[0]['historical'])
        self.assertIn('Sjekksum', files[0]['historical'])
        self.assertEqual(len([r for r in data['rows'] if r['kind'] == 'xml' and '/mets:fileSec' in r['key']]) > 2, True)

    def test_metadata_categories_are_separate_from_technical_xml(self):
        state = self._load()
        self.assertEqual(len([r for r in state['rows'] if r['kind'] == 'canonical']), 47)
        self.assertEqual(len([r for r in state['rows'] if r['kind'] == 'depot']), 4)
        self.assertFalse(any(r['kind'] == 'canonical' for r in state['extended_rows']))
        self.assertEqual(state['depot_field_count'], 4)

    def test_sha256_and_file_integrity_cannot_be_overridden(self):
        state = self._load()
        row = next(r for r in state['rows'] if r['kind'] == 'xml' and r['key'].endswith('/@CHECKSUM'))
        self.assertTrue(technical_read_only(row['key']))
        self.assertFalse(row['editable'])
        with self.assertRaisesRegex(MetadataA16Error, 'ikke-redigerbart'):
            save_field(self.work, source_sha256=self.outer['sha256'], row_id=row['id'],
                       previous_value=row['current'], new_value='FORGED', comment='Test',
                       author=AUTHOR, expected_metadata_sha256=state['metadata_sha256'])
        self.assertEqual(self.source.read_bytes(), self.original)

    def test_extended_unknown_meta_still_source_editable(self):
        state = self._load()
        row = next(r for r in state['extended_rows'] if r['historical'] == 'viktig ekstrafelt')
        self.assertTrue(row['editable'])
        save_field(self.work, source_sha256=self.outer['sha256'], row_id=row['id'],
                   previous_value=row['current'], new_value='Korrigert i Work', comment='Test',
                   author=AUTHOR, expected_metadata_sha256=state['metadata_sha256'])
        new = next(r for r in self._load()['extended_rows'] if r['id'] == row['id'])
        self.assertEqual(new['historical'], 'viktig ekstrafelt')
        self.assertEqual(new['current'], 'Korrigert i Work')
        self.assertTrue(new['changed'])

    def test_mutating_other_source_is_caught_during_pairing(self):
        inner = self._import_inner()
        (self.work / inner['path']).write_text('FORGED', encoding='utf-8')
        with self.assertRaisesRegex(MetadataA16Error, 'SHA-256'):
            self._load(self.outer['sha256'])

    def test_gui_has_separate_views_and_per_field_reference_columns(self):
        gui = (Path(__file__).resolve().parents[1] / 'gui_qt/dias_metadata_v021_a16.py').read_text(encoding='utf-8')
        self.assertIn('QTableWidget(0, 6', gui)
        self.assertIn('Metadata – 47 Arkade-felt', gui)
        self.assertIn('Utvidede METS-opplysninger', gui)
        self.assertIn('Teknisk XML – alle forekomster', gui)
        self.assertIn('Ytre info.xml', gui)
        self.assertIn('Indre DIAS METS', gui)
        self.assertIn('self.references.setPlainText', gui)
        self.assertNotIn('self.section.addItem("Alle metadatafelt", "all")', gui)


if __name__ == '__main__':
    unittest.main()
