"""a4 regression: versioned metadata/requirement crosswalk, NOT normative passes."""
from __future__ import annotations

import ast
from contextlib import redirect_stdout
from io import StringIO
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.noark5_xpath_audit_v021_a1 import load_rows
from app.noark5_xpath_metadata_qa_v021_a4 import (
    _xpath_field_mentioned, build_metadata_qa, filter_metadata_rows, main,
)

VERSIONS = ('3.1', '4.0', '5.0')


class Fixture(unittest.TestCase):
    def setUp(self):
        tmp = TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.project = Path(tmp.name)
        self.tests = [
            self.make_test_def('kdrs.c01', 'C01', [
                {'id': 'archive', 'type': 'xpath', 'expression': 'count(//arkiv)'},
                {'id': 'status', 'type': 'group_text', 'select': '//arkiv/arkivstatus'},
            ], checks=[{'id': 'status', 'metric_id': 'status',
                        'value_set_id': 'M050_arkivstatus', 'versions': list(VERSIONS)}]),
            self.make_test_def('kdrs.c02', 'C02', [
                {'id': 'folder_medium', 'type': 'group_text',
                 'select': '//arkivdel/dokumentmedium'},
            ]),
            self.make_test_def('kdrs.c03', 'C03', [
                {'id': 'title', 'type': 'rows', 'select': '//klasse',
                 'fields': {'class_id': 'string(klasseID)'}},
            ]),
            self.make_test_def('kdrs.c04', 'C04', [
                {'id': 'magic', 'type': 'xpath',
                 'expression': 'count(//mappe[not(@type="M300")])'},
            ], versions=['5.0']),
        ]
        self.write_sources()
        self.save_catalog()

    @staticmethod
    def make_test_def(test_id, legacy, metrics, checks=None, versions=None, **extras):
        return {'test_id': test_id, 'legacy': {'job_id': legacy},
                'name': 'Test ' + legacy, 'source_xml': 'arkivstruktur.xml',
                'scope': 'source_document', 'status': 'active',
                'noark_versions': list(versions if versions is not None else VERSIONS),
                'execution': {'kind': 'metrics', 'metrics': metrics},
                'standard_value_checks': list(checks or []), **extras}

    def save(self, relative, value):
        dest = self.project / relative
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n', encoding='utf8')

    def save_catalog(self):
        self.save('config/noark5/tests/xpath_catalog_2026_05_26.json',
                  {'catalog_id': 'fixture', 'tests': self.tests})

    def write_sources(self):
        self.save('config/noark5/standards/sources.json', {'sources': [
            {'source_id': 'source-3.1', 'version': '3.1', 'role': ['authoritative_metadata']},
            {'source_id': 'source-4.0', 'version': '4.0', 'role': ['authoritative_metadata']},
            {'source_id': 'source-5.0', 'version': '5.0', 'role': ['authoritative_metadata']},
            {'source_id': 'legacy', 'versions': list(VERSIONS), 'role': ['legacy_reference']},
        ]})
        self.save('config/noark5/standards/noark5_standard_values.json', {
            'versions': {v: {'value_sets': {'M050_arkivstatus': {
                'values': ['Opprettet', 'Avsluttet'], 'metadata_id': 'M050'}}} for v in VERSIONS},
        })
        for area in ('metadata', 'requirements'):
            self.save('config/noark5/standards/' + area + '/index.json', {
                'versions': {v: f'config/noark5/standards/{area}/{v}.json' for v in VERSIONS}})
        for v in VERSIONS:
            self.save(f'config/noark5/standards/metadata/{v}.json', {
                'noark_version': v, 'status': 'partial_verified_registry', 'metadata': [
                    {'metadata_id': 'M050', 'name': 'arkivstatus', 'source_id': 'source-' + v,
                     'verification_status': 'verified_for_registered_value_set',
                     'standard_value_set_id': 'M050_arkivstatus'},
                    {'metadata_id': 'M300', 'name': 'dokumentmedium', 'source_id': 'source-' + v,
                     'verification_status': 'verified_for_registered_value_set'},
                    {'metadata_id': 'M002', 'name': 'klasseID', 'source_id': 'source-' + v,
                     'source_location': f'Vedlegg 1 M002 v{v}',
                     'verification_status': 'verified'},
                ]})
            self.save(f'config/noark5/standards/requirements/{v}.json', {
                'noark_version': v, 'requirements': ([
                    {'requirement_id': 'v5-class-id', 'noark_version': '5.0',
                     'source_id': 'source-5.0', 'source_location': 'Vedlegg M002 side 4',
                     'verification_status': 'verified', 'normative_summary': 'klasseID kreves',
                     'xml_field_name': 'klasseID',
                     'extract_validation': {'directly_testable_from_extract': True}},
                    {'requirement_id': 'v5-authorize', 'noark_version': '5.0',
                     'source_id': 'source-5.0', 'source_location': 'Kapittel 2',
                     'verification_status': 'verified', 'normative_summary': 'Autorisasjon kreves',
                     'extract_validation': {'directly_testable_from_extract': False}},
                ] if v == '5.0' else [])})

    def report(self):
        self.save_catalog()
        return build_metadata_qa(self.project)


class TestMetadataAndRequirements(Fixture):
    def test_versions_are_isolated(self):
        report = self.report()
        self.assertEqual(report['versions']['3.1']['summary']['registered_requirements'], 0)
        self.assertEqual(report['versions']['4.0']['summary']['registered_requirements'], 0)
        self.assertEqual(report['versions']['5.0']['summary']['registered_requirements'], 2)
        self.assertFalse(report['noark_conformance_verified'])

    def test_m300_is_only_xpath_candidate(self):
        report = self.report()
        entry = next(x for x in report['versions']['5.0']['metadata'] if x['metadata_id']=='M300')
        self.assertEqual(entry['mapping_state'], 'xpath_candidate')
        self.assertEqual([x['test_id'] for x in entry['xpath_candidates']], ['kdrs.c02'])
        self.assertFalse(entry['conformance_verified'])
        self.assertFalse(entry['explicit_value_set_references'])

    def test_direct_value_set_link_still_not_mandatory_validation(self):
        report = self.report()
        entry = next(x for x in report['versions']['3.1']['metadata'] if x['metadata_id']=='M050')
        self.assertEqual(entry['mapping_state'], 'explicit_value_set_reference')
        self.assertEqual(entry['source_scope'], 'verified_registered_value_set_only')
        self.assertEqual(entry['explicit_value_set_references'][0]['references'][0]['status'],
                         'registered_value_set_reference')
        self.assertFalse(entry['conformance_verified'])
        self.assertEqual(report['versions']['3.1']['summary']['metadata_with_explicit_value_set_link'], 1)

    def test_unknown_metadata_source_not_promoted(self):
        path = self.project / 'config/noark5/standards/metadata/5.0.json'
        doc = json.loads(path.read_text('utf8'))
        doc['metadata'][0]['source_id'] = 'source-4.0'
        self.save('config/noark5/standards/metadata/5.0.json', doc)
        entry = next(x for x in self.report()['versions']['5.0']['metadata']
                     if x['metadata_id'] == 'M050')
        status = entry['explicit_value_set_references'][0]['references'][0]['status']
        self.assertEqual(status, 'value_set_source_not_confirmed')

    def test_unknown_metric_id_not_promoted(self):
        self.tests[0]['standard_value_checks'][0]['metric_id'] = 'nonexistent'
        link = next(x for x in self.report()['versions']['5.0']['metadata']
                    if x['metadata_id']=='M050')['explicit_value_set_references'][0]['references'][0]
        self.assertEqual(link['status'], 'referenced_metric_not_found')

    def test_requirement_is_candidate_not_executed_rule(self):
        entry = next(x for x in self.report()['versions']['5.0']['requirements']
                     if x['requirement_id']=='v5-class-id')
        self.assertEqual(entry['source_status'], 'xpath_candidate_no_rule_check')
        self.assertTrue(entry['source_verified'])
        self.assertEqual(entry['xpath_candidates'][0]['test_id'], 'kdrs.c03')
        self.assertFalse(entry['conformance_verified'])
        self.assertEqual(entry['explicit_catalogue_references'], [])

    def test_functional_requirement_not_extract_testable(self):
        entry = next(x for x in self.report()['versions']['5.0']['requirements']
                     if x['requirement_id']=='v5-authorize')
        self.assertEqual(entry['source_status'], 'not_directly_testable_from_extract')
        self.assertFalse(entry['directly_testable_from_extract'])

    def test_source_in_wrong_version_not_source_verified(self):
        path = self.project / 'config/noark5/standards/requirements/5.0.json'
        doc = json.loads(path.read_text('utf8'))
        doc['requirements'][0]['source_id'] = 'source-4.0'
        self.save('config/noark5/standards/requirements/5.0.json', doc)
        entry = next(x for x in self.report()['versions']['5.0']['requirements']
                     if x['requirement_id']=='v5-class-id')
        self.assertEqual(entry['source_status'], 'normative_source_not_verified')

    def test_missing_source_location_not_source_verified(self):
        path = self.project / 'config/noark5/standards/requirements/5.0.json'
        doc = json.loads(path.read_text('utf8'))
        doc['requirements'][0].pop('source_location')
        self.save('config/noark5/standards/requirements/5.0.json', doc)
        entry = next(x for x in self.report()['versions']['5.0']['requirements']
                     if x['requirement_id']=='v5-class-id')
        self.assertEqual(entry['source_status'], 'normative_source_not_verified')

    def test_legacy_source_cannot_authorize_normative_rule(self):
        path = self.project / 'config/noark5/standards/requirements/5.0.json'
        doc = json.loads(path.read_text('utf8'))
        doc['requirements'][0]['source_id'] = 'legacy'
        self.save('config/noark5/standards/requirements/5.0.json', doc)
        entry = next(x for x in self.report()['versions']['5.0']['requirements']
                     if x['requirement_id']=='v5-class-id')
        self.assertFalse(entry['source_verified'])

    def test_real_v5_additions_use_registered_source(self):
        # Exercise the *delivered registry files*, not duplicated fixture data.
        import shutil
        for area in ('metadata', 'requirements'):
            original = ROOT / f'config/noark5/standards/{area}/5.0.json'
            destination = self.project / f'config/noark5/standards/{area}/5.0.json'
            shutil.copyfile(original, destination)
        self.save('config/noark5/standards/sources.json', {'sources': [
            {'source_id': 'source-3.1', 'version': '3.1', 'role': ['authoritative_metadata']},
            {'source_id': 'source-4.0', 'version': '4.0', 'role': ['authoritative_metadata']},
            {'source_id': 'noark5-5.0-metadata-catalog', 'version': '5.0',
             'role': ['authoritative_metadata', 'authoritative_standard_values']},
            {'source_id': 'noark5-core-specifications', 'versions': list(VERSIONS),
             'role': ['authoritative_requirements']},
        ]})
        report = self.report()
        v5 = report['versions']['5.0']
        self.assertEqual(v5['summary']['registered_metadata'], 23)
        self.assertEqual(v5['summary']['registered_requirements'], 6)
        id_info = next(x for x in v5['metadata'] if x['metadata_id'] == 'M002')
        self.assertEqual(id_info['source_scope'], 'selected_properties_source_verified')
        self.assertEqual([x['test_id'] for x in id_info['xpath_candidates']], ['kdrs.c03'])
        req = next(x for x in v5['requirements']
                   if x['requirement_id'] == 'noark5.v5.class.class_id_mandatory')
        self.assertTrue(req['source_verified'])
        self.assertEqual(req['source_status'], 'xpath_candidate_no_rule_check')
        self.assertFalse(req['conformance_verified'])

    def test_explicit_requirement_reference_not_an_approval(self):
        self.tests[2]['normative_requirement_refs'] = ['v5-class-id']
        entry = next(x for x in self.report()['versions']['5.0']['requirements']
                     if x['requirement_id']=='v5-class-id')
        self.assertEqual(entry['source_status'], 'explicit_catalogue_reference_not_executed_as_rule')
        self.assertFalse(entry['conformance_verified'])

    def test_quoted_literals_do_not_make_field_matches(self):
        self.assertFalse(_xpath_field_mentioned('concat("dokumentmedium", "x")', 'dokumentmedium'))
        self.assertFalse(_xpath_field_mentioned('count(//dokumentmediumSubtype)', 'dokumentmedium'))
        self.assertTrue(_xpath_field_mentioned('string(dokumentmedium)', 'dokumentmedium'))
        self.assertTrue(_xpath_field_mentioned('//arkivdel/dokumentmedium', 'dokumentmedium'))

    def test_selected_version_does_not_match_undeclared_test(self):
        report = self.report()
        rows = [{'row': row} for row in load_rows(self.project)]
        filtered = filter_metadata_rows(rows, report, version='3.1', state='no_metadata_candidate')
        self.assertNotIn('kdrs.c04', [x['row'].test_id for x in filtered])
        with self.assertRaises(ValueError):
            filter_metadata_rows(rows, report, version='2.0')
        with self.assertRaises(ValueError):
            filter_metadata_rows(rows, report, state='approved')

    def test_filter_by_mapping_kind(self):
        report = self.report()
        rows = [{'row': row} for row in load_rows(self.project)]
        ids = [x['row'].test_id for x in filter_metadata_rows(
            rows, report, version='5.0', state='xpath_candidate')]
        self.assertIn('kdrs.c02', ids)
        self.assertIn('kdrs.c03', ids)
        self.assertNotIn('kdrs.c04', ids)
        req_ids = [x['row'].test_id for x in filter_metadata_rows(
            rows, report, version='5.0', state='requirement_candidate')]
        self.assertEqual(req_ids, ['kdrs.c03'])

    def test_read_only(self):
        before = sorted((str(p.relative_to(self.project)), p.read_bytes())
                        for p in self.project.rglob('*.json'))
        self.report()
        after = sorted((str(p.relative_to(self.project)), p.read_bytes())
                       for p in self.project.rglob('*.json'))
        self.assertEqual(before, after)

    def test_cli_summary(self):
        stream = StringIO()
        with redirect_stdout(stream):
            self.assertEqual(main(['--project', str(self.project), '--summary', '--version', '5.0']), 0)
        result = json.loads(stream.getvalue())
        self.assertEqual(list(result['versions']), ['5.0'])
        self.assertNotIn('tests', result)
        self.assertEqual(result['versions']['5.0']['summary']['registered_requirements'], 2)

    def test_missing_version_registry_must_not_look_complete(self):
        (self.project / 'config/noark5/standards/requirements/4.0.json').unlink()
        report = self.report()
        self.assertEqual(report['versions']['4.0']['state'], 'incomplete_registries')
        self.assertEqual(report['versions']['4.0']['requirements'], [])
        self.assertEqual(report['versions']['5.0']['state'], 'loaded')


class TestRepoIntegration(unittest.TestCase):
    def test_gui_syntax_and_single_window(self):
        path = ROOT / 'gui_qt/noark5_xpath_audit_v021_a1.py'
        source = path.read_text('utf8')
        ast.parse(source)
        self.assertIn('Metadata og krav', source)
        self.assertIn('QTabWidget', source)
        self.assertIn('build_metadata_qa', source)
        self.assertIn('filter_metadata_rows(', source)
        self.assertIn('Vis alle XPath-kontroller', source)
        self.assertIn('NOARK-VERSJON: KILDEKONTROLL', source)

    def test_versions_match(self):
        from version import VERSION
        # Historical a4 test must remain valid for later alphas/releases.
        self.assertRegex(VERSION, r'^0\.2\.1(?:-a(?:[4-9]|[1-9][0-9]+))?$')
        self.assertIn(f'version = "{VERSION.replace("-", "")}"',
                      (ROOT / 'pyproject.toml').read_text('utf8'))

    def test_registered_v5_requirements_are_versioned_if_repo_present(self):
        file = ROOT / 'config/noark5/standards/requirements/5.0.json'
        reg = json.loads(file.read_text('utf8'))
        ids = {x['requirement_id'] for x in reg['requirements']}
        self.assertEqual(len(ids), 6)
        self.assertTrue({'noark5.v5.class.authorized_creation',
                         'noark5.v5.class.class_id_mandatory',
                         'noark5.v5.folder.folder_id_mandatory',
                         'noark5.v5.document_object.version_number_mandatory',
                         'noark5.v5.document_description.document_number_mandatory'} <= ids)
        self.assertTrue(all(x['noark_version'] == '5.0' for x in reg['requirements']))

    def test_registered_v5_metadata_preserves_prior_entries(self):
        file = ROOT / 'config/noark5/standards/metadata/5.0.json'
        reg = json.loads(file.read_text('utf8'))
        ids = {x['metadata_id'] for x in reg['metadata']}
        self.assertEqual(len(ids), 23)
        self.assertTrue({'M001','M002','M003','M005','M007','M300','M700'} <= ids)
        self.assertTrue(all(x.get('source_id') == 'noark5-5.0-metadata-catalog'
                            for x in reg['metadata']))

    def test_full_legacy_catalogue_if_available(self):
        if not (ROOT / 'config/noark5/tests/xpath_catalog_2026_05_26.json').is_file():
            self.skipTest('Full GitHub repo unavailable in delta-only environment')
        report = build_metadata_qa(ROOT)
        self.assertEqual(len(report['tests']), 60)
        self.assertEqual(report['versions']['5.0']['summary']['registered_metadata'], 23)
        self.assertEqual(report['versions']['5.0']['summary']['registered_requirements'], 6)
        self.assertFalse(report['noark_conformance_verified'])


if __name__ == '__main__':
    unittest.main()
