"""A18: source-separated status and main counts, no fabricated Noark PASS."""
from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
import re
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from noark5_workflow.reporting.qa_control_coverage_v023_a18 import (
    ControlCoverageError, _read_arkade, _state, reconcile_controls, MODEL,
)
from noark5_workflow.reporting.qa_complete_report_v023_a13 import _overview_page


def _events(value, prefix=''):
    """Only in tests: event-shape model of ijson.parse, not a production parser."""
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
        event = ('null' if value is None else 'boolean' if type(value) is bool else
                 'string' if isinstance(value, str) else
                 'integer' if type(value) is int else 'number')
        yield prefix, event, value


class FakeIjson:
    JSONError = ValueError

    @staticmethod
    def parse(reader):
        yield from _events(json.load(reader))


class A18Coverage(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.work = Path(self.tmp.name)
        self.path = self.work / 'normalized.json'
        self.origin_sha = 'a' * 64
        mock = patch.dict(sys.modules, {'ijson': FakeIjson})
        mock.start()
        self.addCleanup(mock.stop)

    def master(self):
        return {'format_version': 1, 'source': {'execution_profile': 'normal'},
                'tests': [{'test_id': 'kdrs.c01', 'status': 'ok'},
                          {'test_id': 'kdrs.c02', 'status': 'source_missing'},
                          {'test_id': 'kdrs.c03', 'status': 'error'},
                          {'test_id': 'kdrs.c05', 'status': 'aborted'},
                          {'test_id': 'kdrs.c06', 'status': 'not_run'}]}

    def depot_tests(self):
        return [dict(t) for t in self.master()['tests']]

    def parts(self):
        return [{'system_id': 'a', 'folder_count': 3, 'registration_count': 4},
                {'system_id': 'b', 'folder_count': 2, 'registration_count': 6}]

    def summary(self):
        return {'archive_part_count': 2, 'folder_count': 5, 'registration_count': 10}

    def arkade_doc(self):
        return {'format_version': 2, 'source_system': 'Arkade 5',
                'source': {'sha256': self.origin_sha},
                'summary': {'number_of_tests_run': '4 av 4'},
                'tests': [{'test_id': 'N5.01', 'source_status': 'ok', 'results': []},
                          {'test_id': 'N5.02', 'source_status': 'warning', 'results': []},
                          {'test_id': 'N5.03', 'source_status': 'error', 'number_of_errors': 3},
                          {'test_id': 'N5.04', 'source_status': 'cancelled'}]}

    def write(self, doc):
        self.path.write_text(json.dumps(doc, ensure_ascii=False), encoding='utf-8')
        return sha256(self.path.read_bytes()).hexdigest()

    def coverage(self, *, arkade=False, master=None, depot_tests=None, summary=None, parts=None):
        kwargs = {}
        if arkade:
            kwargs = {'arkade_path': self.path, 'arkade_source_sha256':
                      sha256(self.path.read_bytes()).hexdigest(),
                      'arkade_original_sha256': self.origin_sha}
        return reconcile_controls(master=self.master() if master is None else master,
                                  depot_tests=self.depot_tests() if depot_tests is None else depot_tests,
                                  depot_summary=self.summary() if summary is None else summary,
                                  parts=self.parts() if parts is None else parts,
                                  **kwargs)

    def test_dwm_states_are_not_conflated_with_verified_normative_pass(self):
        got = self.coverage()
        self.assertEqual(got['model_id'], MODEL)
        self.assertEqual(got['dwm_xpath']['by_state']['executed_ok'], 1)
        self.assertEqual(got['dwm_xpath']['by_state']['reported_error'], 1)
        self.assertEqual(got['dwm_xpath']['by_state']['not_run'], 1)
        self.assertEqual(got['dwm_xpath']['by_state']['skipped'], 1)
        self.assertEqual(got['dwm_xpath']['by_state']['interrupted'], 1)
        self.assertEqual(got['dwm_xpath']['observed_master_tests'], 5)
        self.assertIsNone(got['dwm_xpath']['planned_catalog_total'])
        self.assertFalse(got['expected_test_plan_coverage_verified'])
        self.assertFalse(got['automatic_approval'])
        self.assertIsNone(got['total_test_count_across_tools'])
        self.assertIsNone(got['arkade_noark']['observed_test_rows'])

    def test_status_mapping_preserves_unknown_not_false_ok(self):
        examples = {'': 'unknown', 'completed': 'executed_ok',
                    'not_run': 'not_run', 'source_missing': 'skipped',
                    'cancelled': 'interrupted', 'not_applicable': 'not_relevant',
                    'warning': 'reported_warning', 'invalid': 'reported_error',
                    'random_vendor_label': 'unknown'}
        for raw, expected in examples.items():
            self.assertEqual(_state(raw), expected)

    def test_missing_master_rows_in_depot_report_are_visible_not_zero(self):
        report = self.depot_tests()[:2]
        got = self.coverage(depot_tests=report)
        self.assertEqual(len(got['dwm_xpath']['missing_from_depot_report']), 3)
        self.assertEqual(got['dwm_xpath']['distinct_depot_test_ids'], 2)
        self.assertEqual(got['dwm_xpath']['observed_master_tests'], 5)
        self.assertIn('mangler', ' '.join(got['control_issues']))

    def test_duplicate_depot_test_does_not_add_to_unique_controls(self):
        report = self.depot_tests()
        report.append(report[0])
        got = self.coverage(depot_tests=report)
        self.assertEqual(got['dwm_xpath']['reported_depot_test_rows'], 6)
        self.assertEqual(got['dwm_xpath']['distinct_depot_test_ids'], 5)
        self.assertEqual(got['dwm_xpath']['duplicate_depot_test_ids'], ['kdrs.c01'])

    def test_foreign_or_changed_depot_status_fails_closed(self):
        report = self.depot_tests()
        report[0]['status'] = 'error'
        with self.assertRaisesRegex(ControlCoverageError, 'Ulik DWM-teststatus'):
            self.coverage(depot_tests=report)
        report[0]['test_id'] = 'other.job'
        with self.assertRaisesRegex(ControlCoverageError, 'finnes ikke'):
            self.coverage(depot_tests=report)

    def test_archive_parts_sum_and_unknown_not_zero(self):
        got = self.coverage()
        self.assertTrue(got['archive_part_reconciliation']['folder_count']['matches'])
        self.assertIsNone(got['archive_part_reconciliation']['document_object_count']['matches'])
        self.assertIsNone(got['archive_part_reconciliation']['document_object_count']['depot_report_total'])
        self.assertIsNone(got['archive_part_reconciliation']['document_object_count']['sum_of_archive_parts'])
        got = self.coverage(summary={'archive_part_count': 2, 'folder_count': 4},
                            parts=self.parts())
        self.assertFalse(got['archive_part_reconciliation']['folder_count']['matches'])
        self.assertIn('folder_count', ' '.join(got['control_issues']))

    def test_one_missing_part_count_does_not_produce_a_false_sum(self):
        parts = self.parts()
        parts[1].pop('folder_count')
        got = self.coverage(parts=parts)
        self.assertIsNone(got['archive_part_reconciliation']['folder_count']['sum_of_archive_parts'])
        self.assertIsNone(got['archive_part_reconciliation']['folder_count']['matches'])

    def test_arkade_statuses_are_a_separate_non_additive_source(self):
        self.write(self.arkade_doc())
        got = self.coverage(arkade=True)
        ark = got['arkade_noark']
        self.assertEqual(ark['observed_test_rows'], 4)
        self.assertEqual(ark['distinct_test_ids'], 4)
        self.assertEqual(ark['by_state']['reported_error'], 1)
        self.assertEqual(ark['by_state']['reported_warning'], 1)
        self.assertEqual(ark['by_state']['interrupted'], 1)
        self.assertEqual(ark['by_state']['executed_ok'], 1)
        self.assertEqual(ark['reported_test_denominator']['reported_total'], 4)
        self.assertIsNone(got['total_test_count_across_tools'])
        self.assertFalse(got['pronom']['counts_as_noark_tests'])

    def test_arkade_with_more_than_2000_records_is_not_truncated(self):
        doc = self.arkade_doc()
        doc['tests'] = [{'test_id': f'N5.{i:05}', 'source_status': 'ok'} for i in range(2403)]
        doc['summary']['number_of_tests_run'] = '2403 av 2403'
        self.write(doc)
        got = self.coverage(arkade=True)
        self.assertEqual(got['arkade_noark']['observed_test_rows'], 2403)
        self.assertEqual(got['arkade_noark']['distinct_test_ids'], 2403)
        self.assertEqual(got['arkade_noark']['by_state']['executed_ok'], 2403)

    def test_duplicate_arkade_ids_are_flagged_not_silently_double_counted(self):
        doc = self.arkade_doc()
        doc['tests'].append(dict(doc['tests'][0]))
        self.write(doc)
        got = self.coverage(arkade=True)
        self.assertEqual(got['arkade_noark']['distinct_test_ids'], 4)
        self.assertEqual(got['arkade_noark']['observed_test_rows'], 5)
        self.assertEqual(got['arkade_noark']['duplicate_test_ids'], ['N5.01'])
        self.assertIn('Dupliserte Arkade', ' '.join(got['control_issues']))

    def test_arkade_reported_total_mismatch_is_visible(self):
        doc = self.arkade_doc()
        doc['summary']['number_of_tests_run'] = '2 av 4'
        self.write(doc)
        got = self.coverage(arkade=True)
        self.assertIn('avviker', ' '.join(got['arkade_noark']['source_contradictions']))

    def test_status_ok_with_reported_errors_is_not_silent(self):
        doc = self.arkade_doc()
        doc['tests'][0]['number_of_errors'] = 9
        self.write(doc)
        got = self.coverage(arkade=True)
        self.assertIn('N5.01', ' '.join(got['arkade_noark']['source_contradictions']))

    def test_arkade_sha_source_mismatch_rejected(self):
        doc = self.arkade_doc()
        doc['source']['sha256'] = 'b' * 64
        self.write(doc)
        with self.assertRaisesRegex(ControlCoverageError, 'annen originalkilde'):
            self.coverage(arkade=True)

    def test_arkade_file_modified_against_expected_hash_rejected(self):
        doc = self.arkade_doc()
        actual = self.write(doc)
        doc['tests'][0]['source_status'] = 'error'
        self.write(doc)
        with self.assertRaisesRegex(ControlCoverageError, 'endret'):
            _read_arkade(self.path, expected_sha256=actual,
                         expected_original_sha256=self.origin_sha)

    def test_arkade_symlink_and_missing_parser_fail_closed(self):
        self.write(self.arkade_doc())
        link = self.work / 'link.json'
        try:
            link.symlink_to(self.path)
        except (OSError, NotImplementedError):
            self.skipTest('Symlink unsupported')
        with self.assertRaisesRegex(ControlCoverageError, 'Utrygg'):
            _read_arkade(link, expected_sha256=sha256(self.path.read_bytes()).hexdigest(),
                         expected_original_sha256=self.origin_sha)
        with patch.dict(sys.modules, {'ijson': None}):
            with self.assertRaisesRegex(ControlCoverageError, 'ijson'):
                self.coverage(arkade=True)

    def test_large_unrelated_arkade_detail_is_not_retained(self):
        doc = self.arkade_doc()
        doc['tests'][0]['results'] = [{'message': 'x' * 20_000} for _ in range(150)]
        self.write(doc)
        result = self.coverage(arkade=True)
        self.assertLess(len(json.dumps(result)), 12_000)
        self.assertEqual(result['arkade_noark']['observed_test_rows'], 4)

    def test_report_html_contains_source_separated_counts_and_escapes_issue(self):
        got = self.coverage()
        got['control_issues'].append('<script>alert("x")</script>')
        shot = {'work_identity': {'job_id': 'JOB-001', 'job_name': 'Test'},
                'dwm_technical': {'status': 'ok'}, 'control_coverage': got,
                'archive_parts': []}
        index = {'finding_count': 0, 'depot_report_relative': 'depot/report.json',
                 'depot_sha256': 'a' * 64, 'index_relative_path': 'idx',
                 'index_sha256': 'b' * 64}
        html = _overview_page('ks', shot, index, stats={'severity': {}, 'source': {}},
                              reviews_in_scope=0, total_reviews=0,
                              sections=frozenset(('tests',)), recommendation='pending',
                              note='', page_rows=500)
        self.assertIn('Kontrollstatus per kilde', html)
        self.assertIn('Arkade 5 Noark', html)
        self.assertIn('Ikke dokumentert', html)
        self.assertIn('&lt;script&gt;', html)
        self.assertNotIn('<script>', html)

    def test_version_app_and_metadata_agree_a18_or_newer(self):
        repo = Path(__file__).resolve().parents[1]
        space = {}
        exec((repo / 'version.py').read_text(encoding='utf-8'), space)
        num = re.fullmatch(r'0\.2\.3-a(\d+)', space['VERSION'])
        self.assertIsNotNone(num)
        self.assertGreaterEqual(int(num.group(1)), 18)
        proj = (repo / 'pyproject.toml').read_text(encoding='utf-8')
        self.assertRegex(proj, '(?m)^version\\s*=\\s*"' + re.escape(space['VERSION'].replace('-a','a')) + '"\\s*$')


class A18ActualParser(unittest.TestCase):
    def test_actual_ijson_if_installed(self):
        try:
            import ijson  # noqa: F401
        except ImportError:
            self.skipTest('ijson is not installed in local Linux QA environment')
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / 'arkade.json'
            raw = {'format_version': 2, 'source_system': 'Arkade 5',
                   'source': {'sha256': 'f' * 64},
                   'tests': [{'test_id': 'N5.01', 'source_status': 'ok'},
                             {'test_id': 'N5.02', 'source_status': 'interrupted'}]}
            path.write_text(json.dumps(raw), encoding='utf-8')
            result = _read_arkade(path, expected_sha256=sha256(path.read_bytes()).hexdigest(),
                                  expected_original_sha256='f' * 64)
            self.assertEqual(result['observed_test_rows'], 2)
            self.assertEqual(result['by_state']['interrupted'], 1)

class A18RealSavedWorkIntegration(unittest.TestCase):
    """Join actual a17 saved-work bridge with a linked normalized Arkade run."""

    def setUp(self):
        from noark5_workflow.reporting import qa_work_snapshot_v022_a3 as bridge
        self.bridge = bridge
        tmp = TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.work = Path(tmp.name)
        self.run = 'JOB-003__20261120T015500Z-a18'
        self.uid = '99999999-9999-4999-8999-999999999999'
        def put(rel, data):
            path = self.work / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(data, ensure_ascii=False), encoding='utf-8')
            return path
        self.put = put
        put('job.json', {'file_type': 'dwm-work-job', 'format_version': 1,
                         'job_uid': self.uid, 'job': {'job_id': 'JOB-003',
                         'job_uid': self.uid, 'name': 'A18 test'}})
        self.master_rel = f'noark5_tests/xpath/{self.run}/master-results.json'
        put(self.master_rel, {'format_version': 1, 'source': {'execution_profile': 'normal'},
                              'tests': [{'test_id': 'kdrs.c01', 'status': 'ok'},
                                        {'test_id': 'kdrs.c02', 'status': 'error'}]})
        base = 'external_evidence/arkade5/IMPORT-002'
        self.normalized = base + '/normalized/arkade5_results.json'
        self.original = base + '/original/source.json'
        original_sha = sha256(put(self.original, {'original': True}).read_bytes()).hexdigest()
        put(self.normalized, {'format_version': 2, 'source_system': 'Arkade 5',
                              'source': {'sha256': original_sha},
                              'summary': {'number_of_tests_run': '2 av 2'},
                              'tests': [{'test_id': 'N5.01', 'source_status': 'ok', 'results': []},
                                        {'test_id': 'N5.99', 'source_status': 'error',
                                         'number_of_errors': 1, 'results': []}]})
        put(base + '/manifest.json', {'format_version': 2, 'import_id': 'IMPORT-002',
                                     'imported_by': {'job_id': 'JOB-003'},
                                     'normalized_file': self.normalized,
                                     'source': {'preserved_file': self.original,
                                                'sha256': original_sha}})
        self.depot_rel = f'noark5_reports/depot_validation/{self.run}/depot_validation_report.json'
        self.report = put(self.depot_rel, {
            'report_type': 'noark5_depot_validation',
            'summary': {'archive_part_count': 1, 'folder_count': 4,
                        'registration_count': 12},
            'archive_parts': [{'archive_part': {'system_id': 'A-01', 'title': 'A',
                         'status': 'Avsluttet'}, 'folder_count': 4, 'registration_count': 12}],
            'technical_validation': {'status': 'error',
                        'tests': [{'test_id': 'kdrs.c01', 'status': 'ok'},
                                  {'test_id': 'kdrs.c02', 'status': 'error'}]},
            'deviations': [],
            'evidence': {'source_xpath_run': 'C:\\tmp\\' + self.run},
            'external_validation': {'arkade5': {'imports': [{
                'normalized_file': self.normalized, 'source_sha256': original_sha}]}},
        })
        fake = patch.dict(sys.modules, {'ijson': FakeIjson})
        fake.start()
        self.addCleanup(fake.stop)

    def test_status_is_bound_to_selected_depot_and_arkade_not_previous_job(self):
        with patch.object(self.bridge, '_find_depot', return_value=(self.report, self.depot_rel)):
            snapshot = self.bridge.build_saved_work_snapshot(self.work)
        cv = snapshot['control_coverage']
        self.assertEqual(cv['dwm_xpath']['observed_master_tests'], 2)
        self.assertEqual(cv['arkade_noark']['observed_test_rows'], 2)
        self.assertEqual(cv['archive_part_reconciliation']['folder_count']['matches'], True)
        self.assertEqual(cv['dwm_xpath']['by_state']['reported_error'], 1)
        self.assertEqual(cv['arkade_noark']['by_state']['reported_error'], 1)
        self.assertEqual(cv['status'], 'REQUIRES_REVIEW')
        self.assertEqual(snapshot['arkade']['source'], self.normalized)
        self.assertEqual(snapshot['arkade']['finding_count'], 1)
        self.assertIsNone(cv['total_test_count_across_tools'])
        # Reusing the old A3 process to create a result-status finding must
        # not need to reopen a huge depot report after A17 already parsed it.
        from noark5_workflow.reporting import qa_workflow_v022_a3 as workflow
        with patch.object(workflow, '_binding', return_value=(self.uid, 'sha', self.depot_rel)), \
             patch.object(workflow, '_json', side_effect=AssertionError('read old depot')):
            non_ok = workflow._dwm_unfinished_or_failed(self.work, snapshot)
        self.assertEqual(len(non_ok), 1)
        self.assertEqual(non_ok[0]['test_id'], 'kdrs.c02')
        self.assertEqual(non_ok[0]['severity'], 'ERROR')

    def test_selected_depot_path_cannot_be_replaced_by_foreign_copy(self):
        with TemporaryDirectory() as external:
            other = Path(external) / 'depot_validation_report.json'
            other.write_bytes(self.report.read_bytes())
            # Same file bytes and filename are not proof of Work identity.
            with patch.object(self.bridge, '_find_depot',
                              return_value=(other, self.depot_rel)):
                with self.assertRaisesRegex(ValueError, 'Work-evidens'):
                    self.bridge.build_saved_work_snapshot(self.work)

    def test_changed_arkade_normalized_source_fails_closed(self):
        with patch.object(self.bridge, '_find_depot', return_value=(self.report, self.depot_rel)), \
             patch.object(self.bridge, 'reconcile_controls', side_effect=ControlCoverageError('tamper')):
            with self.assertRaisesRegex(ValueError, 'A18 kontrollstatus'):
                self.bridge.build_saved_work_snapshot(self.work)

class A18LargeDepotDelivery(unittest.TestCase):
    """Old A11/A12 readers must not reject or unbounded-load an A17 depot report."""

    def setUp(self):
        from noark5_workflow.reporting.qa_depot_stream_v023_a17 import project_depot_report
        self.project_depot_report = project_depot_report
        tmp = TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.uid = '77777777-7777-4777-8777-777777777777'
        self.run = 'JOB-007__20261120T020500Z-a18'
        self.rel = 'noark5_reports/depot_validation/' + self.run + '/depot_validation_report.json'
        self.path = self.root / self.rel
        self.path.parent.mkdir(parents=True, exist_ok=True)
        (self.root / 'job.json').write_text(json.dumps({'file_type': 'dwm-work-job',
            'job_uid': self.uid, 'format_version': 1,
            'job': {'job_id': 'JOB-007', 'job_uid': self.uid}}), encoding='utf-8')
        (self.path.parent / 'delivery-funn.jsonl').write_bytes(b'')
        (self.path.parent / 'delivery-funn.csv').write_bytes(b'')
        empty_hash = sha256(b'').hexdigest()
        self.delivery = {
            'model_id': 'dwm.noark5.delivery-validation.a10.v1',
            'status': 'completed_with_findings', 'complete': True, 'version': '5.0',
            'automatic_approval': False, 'finding_count': 0,
            'delivery_value_findings': 0, 'period_review_findings': 0,
            'finding_file': 'delivery-funn.jsonl', 'finding_csv': 'delivery-funn.csv',
            'findings_relative': self.path.parent.relative_to(self.root).as_posix() + '/delivery-funn.jsonl',
            'finding_file_sha256': empty_hash, 'finding_csv_sha256': empty_hash,
            'source_sha256': 'f' * 64,
            'rules': [{'metadata_id': x, 'delivery_deviations': 0}
                      for x in ('M051', 'M052', 'M053', 'M054')],
        }
        sample = {
            'report_type': 'noark5_depot_validation',
            'summary': {'archive_part_count': 1, 'folder_count': 4},
            'archive_parts': [{'archive_part': {'system_id': 'Part-A', 'title': 'A', 'status': 'Avsluttet'},
                               'folder_count': 4}],
            'deviations': [],
            'technical_validation': {'status': 'ok', 'summary': {'ok': 1},
                'tests': [{'test_id': 'kdrs.c01', 'status': 'ok',
                           'unused_long_test_data': [{'message': 'v' * 10_000} for _ in range(2600)]}]},
            'evidence': {'source_xpath_run': 'C:\\temp\\' + self.run},
            'delivery_validation': self.delivery,
        }
        self.path.write_text(json.dumps(sample), encoding='utf-8')
        self.digest = sha256(self.path.read_bytes()).hexdigest()
        self.assertGreater(self.path.stat().st_size, 24 * 1024 * 1024)
        fake = patch.dict(sys.modules, {'ijson': FakeIjson})
        fake.start();self.addCleanup(fake.stop)
        self.snapshot = {
            'model_id': 'ikamr.dwm.noark5.qa-decision.a12.v1',
            'work_identity': {'job_uid': self.uid},
            'evidence_manifest': [{'kind': 'dwm_depot', 'path': self.rel,
                                   'sha256': self.digest}],
            'findings': [], 'findings_complete': True, 'full_finding_count': 0,
        }

    def test_large_depot_projector_preserves_delivery_binding(self):
        result, digest = self.project_depot_report(self.path)
        self.assertEqual(digest, self.digest)
        self.assertEqual(result['delivery_validation'], self.delivery)
        self.assertNotIn('unused_long_test_data', str(result))

    def test_a11_complete_delivery_can_attach_without_loading_large_json(self):
        from noark5_workflow.reporting.qa_delivery_v023_a11 import attach_delivery_to_snapshot
        original_read_text = Path.read_text
        def forbid_large_text_read(path, *args, **kwargs):
            if path == self.path:
                raise AssertionError('unbounded read_text of large depot report')
            return original_read_text(path, *args, **kwargs)
        with patch.object(Path, 'read_text', forbid_large_text_read):
            updated = attach_delivery_to_snapshot(self.root, self.snapshot)
        self.assertEqual(updated['delivery_qa']['finding_count'], 0)
        self.assertTrue(updated['findings_complete'])
        self.assertEqual(updated['evidence_manifest'][0]['sha256'], self.digest)

    def test_a12_index_accepts_large_depot_with_delivery_binding(self):
        from noark5_workflow.reporting.qa_delivery_v023_a11 import attach_delivery_to_snapshot
        from noark5_workflow.reporting.qa_paged_review_v023_a12 import build_paged_index
        updated = attach_delivery_to_snapshot(self.root, self.snapshot)
        index = build_paged_index(self.root, updated)
        self.assertEqual(index['finding_count'], 0)
        self.assertTrue(index['complete'])
        self.assertEqual(index['depot_sha256'], self.digest)

    def test_wrong_delivery_binding_hash_fails_even_on_large_report(self):
        from noark5_workflow.reporting.qa_delivery_v023_a11 import attach_delivery_to_snapshot
        modified = dict(self.snapshot)
        modified['evidence_manifest'] = [{**self.snapshot['evidence_manifest'][0],
                                          'sha256': '0' * 64}]
        with self.assertRaisesRegex(ValueError, 'endret'):
            attach_delivery_to_snapshot(self.root, modified)

class A18LargeA260Export(unittest.TestCase):
    """A260 reuses A17 streaming projection, not legacy 24 MiB _json."""

    def test_a260_exports_selected_large_depot_without_unbounded_json(self):
        from types import ModuleType
        from noark5_workflow.reporting.qa_a260_v023_a6 import build_qa_basis_a6
        from noark5_workflow.reporting import qa_decision_v021_a12 as decision
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            uid = '66666666-6666-4666-8666-666666666666'
            run = 'JOB-006__20261120T030000Z-test'
            report_rel = f'noark5_reports/depot_validation/{run}/depot_validation_report.json'
            depot = root / report_rel
            depot.parent.mkdir(parents=True)
            (root / 'job.json').write_text(json.dumps({'file_type': 'dwm-work-job',
                'job_uid': uid, 'job': {'job_id': 'JOB-006', 'job_uid': uid}}))
            report = {
                'report_type': 'noark5_depot_validation',
                'summary': {'archive_part_count': 1},
                'technical_validation': {'status': 'error', 'tests': [
                    {'test_id': 'kdrs.c01', 'status': 'source_missing',
                     'big_unused': [{'detail': 'u' * 10000} for _ in range(2600)]}]},
                'archive_parts': [{'archive_part': {'system_id': 'A-01',
                    'title': 'Archive', 'status': 'Avsluttet'}}],
                'deviations': [], 'evidence': {'source_xpath_run': 'C:\\tmp\\' + run},
            }
            depot.write_text(json.dumps(report), encoding='utf-8')
            self.assertGreater(depot.stat().st_size, 24 * 1024 * 1024)
            evidence = root / 'noark5_evidence'
            evidence.mkdir()
            (evidence / 'evidence-audit.json').write_text(json.dumps({'job_uid': uid}))
            (evidence / 'canonical-results.json').write_text(json.dumps({
                'extraction': {'stable_id': uid}, 'a7_evidence_sources': {}}))
            adapter = ModuleType('noark5_workflow.operations.canonical_evidence_v022_a7')
            adapter.ROOT_NAME = 'noark5_evidence'
            adapter._read = lambda p: json.loads(Path(p).read_text())
            adapter._work_identity = lambda p, job: (root, {'job_uid': uid, 'job_id': 'JOB-006'})
            with patch.dict(sys.modules, {'ijson': FakeIjson,
                                          'noark5_workflow.operations.canonical_evidence_v022_a7': adapter}), \
                 patch.object(decision, '_find_depot', return_value=(depot, report_rel)):
                result = build_qa_basis_a6(root, job_id='JOB-006')
            self.assertFalse(result['automatic_approval'])
            self.assertTrue((evidence / 'qa-basis-draft.json').is_file())
            self.assertTrue((evidence / 'qa-basis-draft.html').is_file())
            self.assertEqual(result['summary']['total'], 1)
            self.assertEqual(result['summary']['reviewed'], 0)
            jsonl_rel = result['exports']['jsonl']
            rows = (root / jsonl_rel).read_text(encoding='utf-8').splitlines()
            self.assertEqual(len(rows), 1)
            self.assertEqual(json.loads(rows[0])['test_id'], 'kdrs.c01')

class A18CompleteReportExport(unittest.TestCase):
    def test_source_separated_coverage_is_visible_in_full_ks_and_depot_exports(self):
        from importlib.util import module_from_spec, spec_from_file_location
        from noark5_workflow.reporting.qa_complete_report_v023_a13 import export_complete_reports
        from noark5_workflow.reporting.qa_paged_review_v023_a12 import build_paged_index
        here = Path(__file__).resolve().parents[0] / 'test_v023_a13_complete_report.py'
        spec = spec_from_file_location('_a18_a13_fixture', here)
        module = module_from_spec(spec)
        spec.loader.exec_module(module)
        fixture = module._a12_fixture()
        self.addCleanup(fixture.doCleanups)
        with patch.dict(sys.modules, module._old_api_modules([])):
            snapshot = fixture.create(2, 2)
            snapshot['control_coverage'] = reconcile_controls(
                master={'tests': [{'test_id': 'kdrs.c01', 'status': 'source_missing'}]},
                depot_tests=[{'test_id': 'kdrs.c01', 'status': 'source_missing'}],
                depot_summary={'archive_part_count': 0}, parts=[])
            index = build_paged_index(fixture.work, snapshot)
            dest = fixture.root / 'qa-a18-full-export'
            result = export_complete_reports(fixture.work, snapshot, index, dest, page_rows=3)
        self.assertTrue(result['manifest'].is_file())
        data = json.loads((dest/'rapportgrunnlag.json').read_text(encoding='utf-8'))
        self.assertEqual(data['control_coverage']['model_id'], MODEL)
        self.assertIsNone(data['control_coverage']['total_test_count_across_tools'])
        self.assertFalse(data['automatic_approval'])
        for file in ('ks-rapport-utkast.html', 'depot-rapport-utkast.html'):
            body = (dest / file).read_text(encoding='utf-8')
            self.assertIn('Kontrollstatus per kilde', body)
            self.assertIn('Ikke kjørt', body)
            self.assertIn('IKKE GODKJENT', body)


if __name__ == '__main__':
    unittest.main()
