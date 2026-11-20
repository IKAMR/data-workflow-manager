"""A17: complete large depot projection, source immutability and fail-closed KS joining."""
from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from noark5_workflow.reporting.qa_depot_stream_v023_a17 import (
    DepotStreamError, project_depot_report,
)


def _events(value, prefix=''):
    """Test-only model of the public ijson.parse event format."""
    if isinstance(value, dict):
        yield prefix, 'start_map', None
        for key, item in value.items():
            yield prefix, 'map_key', key
            yield from _events(item, prefix + '.' + key if prefix else key)
        yield prefix, 'end_map', None
    elif isinstance(value, list):
        yield prefix, 'start_array', None
        for item in value:
            yield from _events(item, prefix + '.item')
        yield prefix, 'end_array', None
    else:
        event = ('null' if value is None else
                 'boolean' if type(value) is bool else
                 'string' if isinstance(value, str) else
                 'integer' if type(value) is int else 'number')
        yield prefix, event, value


class _FakeIjson:
    class JSONError(ValueError):
        pass

    @staticmethod
    def parse(stream):
        doc = json.load(stream)
        yield from _events(doc)


class A17DepotProjection(unittest.TestCase):
    def setUp(self):
        tmp = TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.path = self.root / 'depot_validation_report.json'
        p = patch.dict(sys.modules, {'ijson': _FakeIjson})
        p.start()
        self.addCleanup(p.stop)

    def sample(self):
        return {
            'report_type': 'noark5_depot_validation',
            'summary': {'archive_part_count': 2, 'folder_count': 8},
            'technical_validation': {
                'status': 'warning',
                'summary': {'ok': 3, 'warning': 1},
                'reconciliation': {'folder_count': {'whole': 8, 'parts': 8}},
                'tests': [
                    {'test_id': 'kdrs.c01', 'status': 'ok', 'large_details': []},
                    {'test_id': 'kdrs.c02', 'status': 'warning', 'large_details': []},
                ],
            },
            'archive_parts': [
                {'archive_part': {'system_id': 'part-001', 'title': 'Arkivdel A',
                                  'status': 'Avsluttet periode', 'document_medium': 'Elektronisk',
                                  'archive_period_start_date': '2010-01-01',
                                  'archive_period_end_date': '2020-12-31'},
                 'folder_count': 5, 'registration_count': 9, 'document_object_count': 11},
                {'archive_part': {'system_id': 'part-002', 'title': 'Arkivdel B',
                                  'status': 'Aktiv periode'},
                 'folder_count': 3, 'registration_count': 4, 'document_object_count': 6},
            ],
            'deviations': [
                {'category': 'period_divergence', 'severity': 'review',
                 'summary': 'Årstall avviker', 'requires_review': True},
            ],
            'evidence': {'source_xpath_run': r'C:\temp\JOB-001__20261120T120000Z-test'},
            'external_validation': {'arkade5': {'imports': [
                {'normalized_file': 'external_evidence/arkade5/IMPORT-1/normalized/arkade5_results.json',
                 'source_sha256': 'a' * 64, 'other_details': 'not needed'},
            ]}},
            'unused_large_technical_detail': {'some': 'not retained'},
        }

    def write(self, doc):
        self.path.write_text(json.dumps(doc, ensure_ascii=False), encoding='utf-8')

    def test_normal_projection_retains_every_relevant_row_and_status(self):
        self.write(self.sample())
        projection, digest = project_depot_report(self.path)
        self.assertEqual(digest, sha256(self.path.read_bytes()).hexdigest())
        self.assertEqual(projection['summary']['folder_count'], 8)
        self.assertEqual(projection['technical_validation']['status'], 'warning')
        self.assertEqual(projection['technical_validation']['reconciliation']['folder_count']['parts'], 8)
        self.assertEqual(len(projection['archive_parts']), 2)
        self.assertEqual(projection['archive_parts'][0]['archive_part']['system_id'], 'part-001')
        self.assertEqual(projection['archive_parts'][0]['folder_count'], 5)
        self.assertEqual(projection['deviations'][0]['summary'], 'Årstall avviker')
        self.assertEqual(projection['technical_validation']['tests'],
                         [{'test_id': 'kdrs.c01', 'status': 'ok'},
                          {'test_id': 'kdrs.c02', 'status': 'warning'}])
        self.assertEqual(len(projection['external_validation']['arkade5']['imports']), 1)
        self.assertNotIn('large_details', str(projection))
        self.assertNotIn('unused_large_technical_detail', projection)

    def test_large_depot_26_mib_ignores_only_unused_test_payload(self):
        doc = self.sample()
        doc['technical_validation']['tests'][0]['large_details'] = [
            {'message': 'x' * 10_000} for _ in range(2800)]
        self.write(doc)
        self.assertGreater(self.path.stat().st_size, 24 * 1024 * 1024)
        before = sha256(self.path.read_bytes()).hexdigest()
        projection, digest = project_depot_report(self.path)
        self.assertEqual(before, digest)
        self.assertEqual(before, sha256(self.path.read_bytes()).hexdigest())
        self.assertEqual(projection['technical_validation']['status'], 'warning')
        self.assertEqual(len(projection['technical_validation']['tests']), 2)
        self.assertEqual(len(projection['archive_parts']), 2)
        self.assertEqual(len(projection['deviations']), 1)
        self.assertLess(len(json.dumps(projection)), 8000)

    def test_over_2000_archive_parts_not_truncated(self):
        doc = self.sample()
        doc['archive_parts'] = [
            {'archive_part': {'system_id': f'archive-{i:06}', 'title': f'Part {i}',
                              'status': 'Avsluttet periode'}, 'folder_count': i}
            for i in range(2401)]
        doc['summary']['archive_part_count'] = len(doc['archive_parts'])
        self.write(doc)
        projection, _ = project_depot_report(self.path)
        self.assertEqual(len(projection['archive_parts']), 2401)
        self.assertEqual(projection['archive_parts'][-1]['folder_count'], 2400)

    def test_missing_test_list_rejected(self):
        doc = self.sample()
        doc['technical_validation'].pop('tests')
        self.write(doc)
        with self.assertRaisesRegex(DepotStreamError, 'påkrevd'):
            project_depot_report(self.path)

    def test_malformed_json_rejected(self):
        self.path.write_text('{"report_type": "noark5_depot_validation",', encoding='utf-8')
        with self.assertRaises(DepotStreamError):
            project_depot_report(self.path)

    def test_invalid_top_level_report_identity_rejected(self):
        doc = self.sample()
        doc['report_type'] = 'unrelated_document'
        self.write(doc)
        with self.assertRaisesRegex(DepotStreamError, 'påkrevd'):
            project_depot_report(self.path)

    def test_unsafe_symlink_rejected(self):
        self.write(self.sample())
        linked = self.root / 'link.json'
        try:
            linked.symlink_to(self.path)
        except (OSError, NotImplementedError):
            self.skipTest('Symlink unavailable')
        with self.assertRaisesRegex(DepotStreamError, 'utrygg'):
            project_depot_report(linked)

    def test_unused_overlarge_scalar_fails_closed(self):
        doc = self.sample()
        doc['unused_large_technical_detail']['some'] = 'x' * (8 * 1024 * 1024 + 1)
        self.write(doc)
        with self.assertRaisesRegex(DepotStreamError, 'stort tekstfelt'):
            project_depot_report(self.path)

    def test_large_summary_rejected_without_unbounded_memory(self):
        doc = self.sample()
        doc['technical_validation']['reconciliation']['huge'] = ['x' * 1024] * 3100
        self.write(doc)
        with self.assertRaisesRegex(DepotStreamError, 'overstiger sikker grense'):
            project_depot_report(self.path)

    def test_nested_value_in_required_scalar_is_rejected_not_silently_omitted(self):
        doc = self.sample()
        doc['deviations'][0]['severity'] = {'unexpected': 'nested'}
        self.write(doc)
        with self.assertRaisesRegex(DepotStreamError, 'Ugyldig type'):
            project_depot_report(self.path)

    def test_nonobject_archive_part_rejected(self):
        doc = self.sample()
        doc['archive_parts'].append('not a record')
        self.write(doc)
        with self.assertRaisesRegex(DepotStreamError, 'JSON-objekt'):
            project_depot_report(self.path)

    def test_missing_source_run_rejected(self):
        doc = self.sample()
        doc['evidence'].pop('source_xpath_run')
        self.write(doc)
        with self.assertRaisesRegex(DepotStreamError, 'påkrevd'):
            project_depot_report(self.path)

    def test_json_extra_trailing_content_rejected(self):
        self.write(self.sample())
        with self.path.open('a', encoding='utf-8') as stream:
            stream.write(' {"another_root": true}')
        with self.assertRaises(DepotStreamError):
            project_depot_report(self.path)

    def test_duplicate_root_key_fails_closed(self):
        doc = self.sample()
        class DuplicatedRoot:
            JSONError = ValueError
            @staticmethod
            def parse(stream):
                for event in _events(json.load(stream)):
                    yield event
                    if event == ('', 'map_key', 'report_type'):
                        yield event
        self.write(doc)
        with patch.dict(sys.modules, {'ijson': DuplicatedRoot}):
            with self.assertRaisesRegex(DepotStreamError, 'Duplisert rotfelt'):
                project_depot_report(self.path)

    def test_missing_production_parser_fails_closed(self):
        self.write(self.sample())
        with patch.dict(sys.modules, {'ijson': None}):
            with self.assertRaisesRegex(DepotStreamError, 'ijson'):
                project_depot_report(self.path)

    def test_scalar_decimal_handles_json_number_semantics(self):
        doc = self.sample()
        doc['technical_validation']['reconciliation']['ratio'] = 0.5
        self.write(doc)
        projection, _ = project_depot_report(self.path)
        self.assertEqual(projection['technical_validation']['reconciliation']['ratio'], .5)


class A17Bridge(unittest.TestCase):
    """The normal saved Work path must use the projector only for large depot evidence."""

    def setUp(self):
        from noark5_workflow.reporting import qa_work_snapshot_v022_a3 as bridge
        self.bridge = bridge
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.uid = '11111111-2222-4333-8444-555555555555'
        self.run = 'JOB-001__20261120T120000Z-test'
        self.report_rel = f'noark5_reports/depot_validation/{self.run}/depot_validation_report.json'
        self.master_rel = f'noark5_tests/xpath/{self.run}/master-results.json'
        self.report = self.root / self.report_rel
        self.report.parent.mkdir(parents=True)
        master = self.root / self.master_rel
        master.parent.mkdir(parents=True, exist_ok=True)
        master.write_text(json.dumps({'format_version': 1,
             'source': {'execution_profile': 'normal'},
             'tests': [{'test_id': 'kdrs.c01', 'status': 'warning'}]}))
        self.job = {
            'file_type': 'dwm-work-job', 'format_version': 1,
            'job_uid': self.uid,
            'job': {'job_id': 'JOB-001', 'job_uid': self.uid, 'name': 'Large QA'},
        }
        (self.root / 'job.json').write_text(json.dumps(self.job))
        source = {
            'report_type': 'noark5_depot_validation',
            'summary': {'archive_part_count': 1, 'folder_count': 5},
            'technical_validation': {
                'status': 'warning', 'summary': {'warning': 1},
                'tests': [{'test_id': 'kdrs.c01', 'status': 'warning',
                           'unused_details': [{'result': 'x' * 12_000} for _ in range(2200)]}],
                'reconciliation': {},
            },
            'archive_parts': [{'archive_part': {'system_id': 'A1', 'title': 'A',
                                                'status': 'Avsluttet periode'},
                               'folder_count': 5}],
            'deviations': [{'category': 'dwm.review', 'severity': 'review',
                            'summary': 'Review required', 'requires_review': True}],
            'evidence': {'source_xpath_run': 'C:\\temp\\' + self.run},
            'external_validation': {'arkade5': {'imports': []}},
        }
        self.report.write_text(json.dumps(source), encoding='utf-8')
        self.assertGreater(self.report.stat().st_size, 24 * 1024 * 1024)
        fake = patch.dict(sys.modules, {'ijson': _FakeIjson})
        fake.start()
        self.addCleanup(fake.stop)

    def _source(self, root, rel, expected_hash=None, *, limit=20 * 1024 * 1024, **kwargs):
        file = Path(root) / rel
        if file.stat().st_size > limit:
            raise ValueError('source too large')
        digest = sha256(file.read_bytes()).hexdigest()
        if expected_hash and expected_hash != digest:
            raise ValueError('source hash mismatch')
        return {'path': rel, 'sha256': digest, 'bytes': file.stat().st_size,
                'state': 'sha256_verified' if expected_hash else 'hashed_now'}

    def _run(self, *, source=None, project=None):
        bridge = self.bridge
        master = {'format_version': 1, 'source': {'execution_profile': 'normal'},
                  'tests': [{'test_id': 'kdrs.c01', 'status': 'warning'}]}
        if source is None:
            source = self._source
        with patch.object(bridge, '_source', side_effect=source) as sha_calls, \
             patch.object(bridge, '_find_depot', return_value=(self.report, self.report_rel)), \
             patch.object(bridge, 'project_xpath_master', return_value=master), \
             patch.object(bridge, '_kdrs', return_value={'status': 'not_selected'}), \
             patch.object(bridge, '_assessments', return_value={'status': 'not_registered'}), \
             patch.object(bridge, '_extraction_label', return_value='utt-1'):
            if project is None:
                result = bridge.build_saved_work_snapshot(self.root)
            else:
                with patch.object(bridge, 'project_depot_report', side_effect=project):
                    result = bridge.build_saved_work_snapshot(self.root)
        return result, sha_calls

    def test_large_original_report_joins_exact_hash_and_all_ks_rows(self):
        doc, calls = self._run()
        self.assertEqual(doc['dwm_technical']['status'], 'warning')
        self.assertEqual(doc['work_identity']['job_uid'], self.uid)
        self.assertEqual(doc['archive_parts'][0]['system_id'], 'A1')
        self.assertEqual(len(doc['findings']), 1)
        self.assertTrue(doc['findings_complete'])
        self.assertIn('A17: Stor depotrapport', ' '.join(doc['limitations']))
        self.assertEqual(doc['evidence_manifest'][-1]['sha256'],
                         sha256(self.report.read_bytes()).hexdigest())
        self.assertTrue(any(call.args[1] == self.report_rel and
                            call.kwargs['limit'] > 24 * 1024 * 1024
                            for call in calls.call_args_list))

    def test_modified_report_between_parser_and_manifest_fails_closed(self):
        from noark5_workflow.reporting.qa_decision_v021_a12 import ReportInputError
        with self.assertRaisesRegex(ReportInputError, 'endret mellom'):
            self._run(project=lambda path: ({'report_type': 'noark5_depot_validation',
                'summary': {'archive_part_count': 0},
                'technical_validation': {'tests': [{'test_id': 'kdrs.c01', 'status': 'warning'}]},
                'evidence': {'source_xpath_run': 'C:\\temp\\' + self.run}}, '0' * 64))

    def test_small_report_uses_existing_json_reader(self):
        doc = json.loads(self.report.read_text())
        doc['technical_validation']['tests'][0].pop('unused_details')
        self.report.write_text(json.dumps(doc))
        self.assertLess(self.report.stat().st_size, 24 * 1024 * 1024)
        result, _ = self._run(project=lambda _: self.fail('Should use the existing small-file reader'))
        self.assertEqual(result['dwm_technical']['status'], 'warning')


class A17Version(unittest.TestCase):
    def test_app_distribution_version_match_without_pinning_future_stage(self):
        import re
        root = Path(__file__).resolve().parents[1]
        namespace = {}
        exec((root / 'version.py').read_text(encoding='utf-8'), namespace)
        version = namespace['VERSION']
        from tests.version_assertions import assert_release_at_least
        assert_release_at_least(self, f'VERSION = "{version}"', '0.2.3', 17)
        project = (root / 'pyproject.toml').read_text(encoding='utf-8')
        versions = re.findall(r'(?m)^version\s*=\s*"([^"]+)"\s*$', project)
        self.assertEqual(versions, [version.replace('-a', 'a')])


class A17ActualIjson(unittest.TestCase):
    def test_real_ijson_when_installed(self):
        try:
            import ijson  # noqa: F401
        except ImportError:
            self.skipTest('ijson not installed in local Linux QA environment')
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / 'report.json'
            path.write_text(json.dumps({
                'report_type': 'noark5_depot_validation',
                'summary': {'archive_part_count': 1},
                'technical_validation': {'tests': [{'test_id': 'kdrs.c01', 'status': 'ok',
                    'unused': [{'detail': 'x'*10000} for _ in range(2700)]}]},
                'archive_parts': [{'archive_part': {'system_id': 'A1'}}],
                'evidence': {'source_xpath_run': r'C:\temp\JOB-001__demo'},
            }), encoding='utf-8')
            self.assertGreater(path.stat().st_size, 24*1024*1024)
            data, digest = project_depot_report(path)
            self.assertEqual(digest, sha256(path.read_bytes()).hexdigest())
            self.assertEqual(data['technical_validation']['tests'][0]['status'], 'ok')


if __name__ == '__main__':
    unittest.main()
