"""a3: source-scoped version linking, registry consistency, XSD fingerprints."""
from __future__ import annotations

import ast
from contextlib import redirect_stdout
from io import StringIO
import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.noark5_xpath_audit_v021_a1 import load_rows
from app.noark5_xpath_version_qa_v021_a3 import (
    VERSION_STATUSES, _safe_file, _version_registry, build_version_audit,
    filter_version_rows, main, version_record, xsd_version_fingerprints,
)

VERSIONS = ('3.1', '4.0', '5.0')


class Fixture(unittest.TestCase):
    def setUp(self):
        temp = TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.project = Path(temp.name) / 'repo'
        self.project.mkdir()
        self.schemas = Path(temp.name) / 'schemas'
        self.schemas.mkdir()
        self.standards = self.project / 'config/noark5/standards'
        self.standards.mkdir(parents=True)
        self.tests = [self.make_test()]
        self.make_registries()
        self.save_catalog()

    def save(self, relative, doc):
        path = self.project / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding='utf8')

    def make_test(self, *, ident='kdrs.c01', versions=None, checks=None, **extra):
        return {
            'test_id': ident, 'legacy': {'job_id': ident.rsplit('.', 1)[-1].upper()},
            'name': 'Arkiv', 'source_xml': 'arkivstruktur.xml', 'scope': 'source_document',
            'status': 'active', 'version_basis': 'master_query_subtype_needs_qa',
            'noark_versions': list(versions if versions is not None else VERSIONS),
            'execution': {'kind': 'metrics', 'metrics': [
                {'id': 'archive_count', 'type': 'xpath', 'expression': 'count(//arkiv)'}]},
            'standard_value_checks': list(checks if checks is not None else [{
                'id': 'archive_status', 'metric_id': 'archive_status_counts',
                'value_set_id': 'M050_arkivstatus', 'versions': list(VERSIONS)}]),
            **extra,
        }

    def save_catalog(self):
        self.save('config/noark5/tests/xpath_catalog_2026_05_26.json',
                  {'catalog_id': 'fixture', 'tests': self.tests})

    def make_registries(self):
        self.save('config/noark5/standards/sources.json', {'sources': [
            {'source_id': 'source-3.1', 'version': '3.1', 'role': ['authoritative_metadata']},
            {'source_id': 'source-4.0', 'version': '4.0', 'role': ['authoritative_metadata']},
            {'source_id': 'source-5.0', 'version': '5.0', 'role': ['authoritative_metadata']},
            {'source_id': 'core', 'versions': list(VERSIONS), 'role': ['authoritative_requirements']},
            {'source_id': 'ikamar-kdrs-query-2026-05-26', 'role': ['legacy_reference']},
        ]})
        self.save('config/noark5/standards/noark5_standard_values.json', {
            'versions': {v: {'value_sets': {'M050_arkivstatus': {
                'metadata_id': 'M050', 'values': ['Opprettet', 'Avsluttet']}}} for v in VERSIONS},
        })
        for area in ('metadata', 'requirements'):
            self.save(f'config/noark5/standards/{area}/index.json', {
                'versions': {v: f'config/noark5/standards/{area}/{v}.json' for v in VERSIONS}})
        for v in VERSIONS:
            self.save(f'config/noark5/standards/metadata/{v}.json', {
                'noark_version': v, 'status': 'partial_verified_registry',
                'metadata': [{
                    'metadata_id': 'M050', 'name': 'arkivstatus',
                    'standard_value_set_id': 'M050_arkivstatus',
                    'source_id': 'source-' + v,
                    'verification_status': 'verified_for_registered_value_set'}],
            })
            self.save(f'config/noark5/standards/requirements/{v}.json', {
                'noark_version': v, 'status': 'not_yet_populated' if v != '5.0' else 'partial_verified',
                'requirements': ([{'requirement_id': 'req-5', 'noark_version': '5.0',
                                   'source_id': 'core', 'verification_status': 'verified',
                                   'source_location': 'Kap. 2, side 25',
                                   'extract_validation': {'directly_testable_from_extract': False}}]
                                 if v == '5.0' else []),
            })
        self.save('config/noark5/standards/noark5_xsd_signatures_v0114_a5.json', {
            'source_status': 'repo_manifest_digest_not_locally_verified_against_original_files',
            'signatures': [],
        })

    def qa(self):
        self.save_catalog()
        return build_version_audit(self.project, schema_root=self.schemas)


class TestSourceVersionQA(Fixture):
    def test_kdrs_query_subtype_not_normative(self):
        report = self.qa()
        for v in VERSIONS:
            record = report['tests']['kdrs.c01']['by_version'][v]
            self.assertEqual(record['status'], 'needs_version_qa')
            self.assertFalse(record['source_verified_applicability'])
        self.assertFalse(report['noark_conformance_verified'])
        self.assertFalse(report['saxon_semantic_equivalence_verified'])

    def test_version_registry_counts_are_not_test_coverage(self):
        report = self.qa()
        self.assertEqual(report['summary']['5.0']['verified_requirement_registry_entries'], 1)
        self.assertEqual(report['summary']['3.1']['verified_requirement_registry_entries'], 0)
        self.assertEqual(report['summary']['4.0']['verified_requirement_registry_entries'], 0)
        self.assertEqual(report['summary']['5.0']['source_verified_version_links'], 0)

    def test_registered_standard_value_set_not_successful_test(self):
        report = self.qa()
        link = report['tests']['kdrs.c01']['by_version']['3.1']['value_set_references'][0]
        self.assertEqual(link['status'], 'registered_value_set_link')
        self.assertEqual(link['scope'], 'registered_value_set_only_not_test_validation')
        self.assertEqual(report['tests']['kdrs.c01']['by_version']['3.1']['status'], 'needs_version_qa')

    def test_evidence_needs_explicit_version_source_and_location(self):
        self.tests[0]['version_evidence'] = {'5.0': {
            'source_id': 'core', 'verification_status': 'verified', 'source_location': 'Side 25'}}
        report = self.qa()
        self.assertEqual(report['tests']['kdrs.c01']['by_version']['5.0']['status'],
                         'source_verified_version_link')
        self.assertEqual(report['tests']['kdrs.c01']['by_version']['4.0']['status'],
                         'needs_version_qa')
        self.assertFalse(report['noark_conformance_verified'])

    def test_source_with_version_but_without_authority_not_promoted(self):
        path = self.standards / 'sources.json'
        data = json.loads(path.read_text(encoding='utf8'))
        data['sources'].append({'source_id': 'run-log', 'version': '5.0',
                                'role': ['local_test_evidence']})
        path.write_text(json.dumps(data), encoding='utf8')
        self.tests[0]['version_evidence'] = {'5.0': {
            'source_id': 'run-log', 'verification_status': 'verified',
            'source_location': 'log line 200'}}
        record = self.qa()['tests']['kdrs.c01']['by_version']['5.0']
        self.assertFalse(record['source_verified_applicability'])
        self.assertEqual(record['status'], 'needs_version_qa')

    def test_legacy_kdrs_source_is_not_normative(self):
        self.tests[0]['version_evidence'] = {'5.0': {
            'source_id': 'ikamar-kdrs-query-2026-05-26',
            'source_location': 'job_id=C01', 'verification_status': 'verified'}}
        report = self.qa()
        self.assertFalse(report['tests']['kdrs.c01']['by_version']['5.0']['source_verified_applicability'])
        self.assertIn('version_evidence_incomplete_or_conflicting',
                      report['tests']['kdrs.c01']['by_version']['5.0']['issues'])

    def test_cross_version_evidence_not_inherited(self):
        self.tests[0]['version_evidence'] = {'3.1': {
            'source_id': 'source-3.1', 'source_location': 'Vedlegg',
            'verification_status': 'verified'}}
        report = self.qa()
        self.assertEqual(report['summary']['3.1']['source_verified_version_links'], 1)
        self.assertEqual(report['summary']['4.0']['source_verified_version_links'], 0)

    def test_missing_source_location_not_promoted(self):
        self.tests[0]['version_evidence'] = {'5.0': {
            'source_id': 'core', 'verification_status': 'verified', 'source_location': ' '}}
        self.assertEqual(self.qa()['tests']['kdrs.c01']['by_version']['5.0']['status'],
                         'needs_version_qa')

    def test_not_declared_and_filter(self):
        self.tests[0]['noark_versions'] = ['5.0']
        report = self.qa()
        self.assertEqual(report['tests']['kdrs.c01']['by_version']['3.1']['status'],
                         'not_declared')
        row = {'row': load_rows(self.project)[0]}
        self.assertEqual(len(filter_version_rows([row], report, version='3.1', state='not_declared')), 1)
        self.assertEqual(len(filter_version_rows([row], report, version='5.0', state='not_declared')), 0)

    def test_partially_registered_metadata_is_not_made_up(self):
        self.tests[0]['standard_value_checks'] = [{
            'id': 'x', 'value_set_id': 'M300_dokumentmedium', 'versions': ['5.0']}]
        report = self.qa()
        value = report['tests']['kdrs.c01']['by_version']['5.0']['value_set_references'][0]
        self.assertEqual(value['status'], 'reference_not_yet_registered')
        self.assertEqual(report['tests']['kdrs.c01']['by_version']['5.0']['status'],
                         'needs_version_qa')

    def test_metadata_provenance_conflict_flagged(self):
        p = self.standards / 'metadata/5.0.json'
        d = json.loads(p.read_text(encoding='utf8'))
        d['metadata'][0]['source_id'] = 'source-3.1'
        p.write_text(json.dumps(d), encoding='utf8')
        report = self.qa()
        row = report['tests']['kdrs.c01']['by_version']['5.0']
        self.assertEqual(row['status'], 'reference_conflict')
        self.assertIn('reference_conflict:M050_arkivstatus', row['issues'])

    def test_requirement_reference_no_extract_pass(self):
        self.tests[0]['normative_requirement_refs'] = ['req-5']
        report = self.qa()
        refs = report['tests']['kdrs.c01']['by_version']['5.0']['normative_requirement_references']
        self.assertEqual(refs[0]['status'], 'source_verified_requirement_reference')
        self.assertFalse(refs[0]['directly_testable_from_extract'])
        self.assertFalse(report['noark_conformance_verified'])

    def test_missing_requirement_reference_is_not_verified(self):
        self.tests[0]['normative_requirement_refs'] = ['missing-ref']
        report = self.qa()
        self.assertEqual(report['tests']['kdrs.c01']['by_version']['5.0']['status'],
                         'needs_version_qa')
        self.assertEqual(report['tests']['kdrs.c01']['by_version']['5.0']['normative_requirement_references'][0]['status'],
                         'not_registered_for_version')

    def test_missing_source_registry_does_not_look_like_bad_source(self):
        (self.standards / 'sources.json').unlink()
        report = self.qa()
        record = report['tests']['kdrs.c01']['by_version']['5.0']
        self.assertEqual(record['status'], 'registry_unavailable')
        self.assertEqual(record['value_set_references'][0]['status'], 'source_registry_unavailable')

    def test_standard_registry_wrong_structure_is_not_trusted(self):
        self.save('config/noark5/standards/noark5_standard_values.json', {'versions': []})
        report = self.qa()
        record = report['tests']['kdrs.c01']['by_version']['5.0']
        self.assertEqual(record['status'], 'registry_unavailable')

    def test_missing_registry_is_explicit(self):
        (self.standards / 'metadata/4.0.json').unlink()
        report = self.qa()
        self.assertEqual(report['tests']['kdrs.c01']['by_version']['4.0']['status'],
                         'registry_unavailable')
        self.assertEqual(report['summary']['4.0']['metadata_registry_state'], 'unavailable')

    def test_duplicate_registry_identifiers(self):
        p = self.standards / 'metadata/3.1.json'
        d = json.loads(p.read_text(encoding='utf8'))
        d['metadata'].append(d['metadata'][0])
        p.write_text(json.dumps(d), encoding='utf8')
        self.assertEqual(_version_registry(self.project, 'metadata', '3.1')['status'],
                         'duplicate_records')
        self.assertEqual(self.qa()['tests']['kdrs.c01']['by_version']['3.1']['status'],
                         'registry_unavailable')

    def test_invalid_path_in_registry_index_is_rejected(self):
        p = self.standards / 'metadata/index.json'
        d = json.loads(p.read_text(encoding='utf8'))
        d['versions']['5.0'] = '../../../../../etc/secret.json'
        p.write_text(json.dumps(d), encoding='utf8')
        self.assertEqual(_version_registry(self.project, 'metadata', '5.0')['status'],
                         'invalid_registry_path')

    def test_invalid_version_filter_rejected(self):
        row = {'row': load_rows(self.project)[0]}
        with self.assertRaises(ValueError):
            filter_version_rows([row], self.qa(), version='9.0')
        with self.assertRaises(ValueError):
            filter_version_rows([row], self.qa(), state='approved')

    def test_read_only_static_audit(self):
        before = sorted((p.relative_to(self.project).as_posix(),
                         hashlib.sha256(p.read_bytes()).hexdigest())
                        for p in self.project.rglob('*') if p.is_file())
        self.qa()
        after = sorted((p.relative_to(self.project).as_posix(),
                        hashlib.sha256(p.read_bytes()).hexdigest())
                       for p in self.project.rglob('*') if p.is_file())
        self.assertEqual(before, after)


class TestXsdFingerprint(Fixture):
    def test_local_hash_match_and_mismatch(self):
        f = self.schemas / 'v5.0/schemas/arkivstruktur.xsd'
        f.parent.mkdir(parents=True)
        f.write_bytes(b'<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema"/>')
        d = {'source_status': 'repo_manifest_digest_not_locally_verified_against_original_files',
             'signatures': [{'version': '5.0', 'filename': 'arkivstruktur.xsd',
                             'sha256': hashlib.sha256(f.read_bytes()).hexdigest()}]}
        self.save('config/noark5/standards/noark5_xsd_signatures_v0114_a5.json', d)
        found = xsd_version_fingerprints(self.project, self.schemas)
        self.assertEqual(found['versions']['5.0']['arkivstruktur.xsd']['status'],
                         'registered_hash_matches')
        self.assertIn('repo_manifest_digest_not_locally_verified', found['signature_provenance_status'])
        f.write_text('<changed/>', encoding='utf8')
        changed = xsd_version_fingerprints(self.project, self.schemas)
        self.assertEqual(changed['versions']['5.0']['arkivstruktur.xsd']['status'], 'hash_mismatch')

    def test_no_local_schema_not_passed(self):
        found = xsd_version_fingerprints(self.project, schema_root=None)
        self.assertEqual(found['versions']['3.1']['arkivstruktur.xsd']['status'],
                         'local_schema_not_connected')

    def test_symlink_escape_is_rejected(self):
        outside = self.schemas / 'outside.json'
        outside.write_text('secret', encoding='utf8')
        target = self.standards / 'metadata/link.json'
        try:
            target.symlink_to(outside)
        except (OSError, NotImplementedError):
            self.skipTest('Creating symlinks requires OS privileges on this system')
        self.assertIsNone(_safe_file(self.project, Path('config/noark5/standards/metadata/link.json')))


class TestCliAndGui(Fixture):
    def test_cli_read_only_and_explicit_version(self):
        self.save_catalog()
        stream = StringIO()
        with redirect_stdout(stream):
            result = main(['--project', str(self.project), '--version', '5.0',
                           '--schema-root', str(self.schemas)])
        self.assertEqual(result, 0)
        doc = json.loads(stream.getvalue())
        self.assertEqual(list(doc['summary']), ['5.0'])
        self.assertEqual(list(doc['tests']['kdrs.c01']['by_version']), ['5.0'])

    def test_cli_cannot_write_into_repository(self):
        with self.assertRaises(SystemExit) as cm:
            main(['--project', str(self.project), '--output', str(self.project / 'audit.json')])
        self.assertEqual(cm.exception.code, 2)
        self.assertFalse((self.project / 'audit.json').exists())

    def test_cli_does_not_overwrite(self):
        out = self.schemas.parent / 'exists.json'
        out.write_text('existing', encoding='utf8')
        with self.assertRaises(SystemExit):
            main(['--project', str(self.project), '--output', str(out)])
        self.assertEqual(out.read_text(encoding='utf8'), 'existing')

    def test_gui_filter_and_details_reuse_existing_window(self):
        src = (ROOT / 'gui_qt/noark5_xpath_audit_v021_a1.py').read_text(encoding='utf8')
        ast.parse(src)
        self.assertIn('Versjons-QA:', src)
        self.assertIn('NOARK-VERSJON: KILDEKONTROLL', src)
        self.assertIn('filter_version_rows(', src)
        self.assertIn('KDRS-formelkobling:', src)
        self.assertNotIn('new_xpath_motor', src)

    def test_version_fields_synchronized(self):
        from version import VERSION
        self.assertRegex(VERSION, r'^0\.2\.1(?:-a(?:[3-9]|[1-9][0-9]+))?$')
        text = (ROOT / 'pyproject.toml').read_text(encoding='utf8')
        self.assertIn('version = "' + VERSION.replace('-a', 'a') + '"', text)

    def test_status_is_finite(self):
        self.assertEqual(len(VERSION_STATUSES), len(set(VERSION_STATUSES)))
        self.assertIn('needs_version_qa', VERSION_STATUSES)
        self.assertNotIn('approved', VERSION_STATUSES)


class FullRepoAvailability(unittest.TestCase):
    def test_actual_version_registers_if_available(self):
        expected = ROOT / 'config/noark5/standards/requirements/5.0.json'
        if not expected.exists() or not (ROOT / 'config/noark5/tests/xpath_catalog_2026_05_26.json').exists():
            self.skipTest('Full repo unavailable in delta-only test directory')
        report = build_version_audit(ROOT)
        self.assertEqual(report['summary']['3.1']['verified_requirement_registry_entries'], 0)
        self.assertEqual(report['summary']['4.0']['verified_requirement_registry_entries'], 0)
        self.assertGreaterEqual(report['summary']['5.0']['verified_requirement_registry_entries'], 2)
        self.assertFalse(report['noark_conformance_verified'])


if __name__ == '__main__':
    unittest.main()
