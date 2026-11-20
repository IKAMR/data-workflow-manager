"""v0.2.3-a7: Arkade A220 counts, bounded preview and SHA-bound full source.

Optional costly stress test (not part of ordinary test.bat):
    set DWM_A7_STRESS=1
    py -m unittest tests.test_v023_a7_capacity -v
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest

try:
    import ijson  # noqa: F401
except ImportError:
    ijson = None


@unittest.skipUnless(ijson is not None, 'ijson installeres via requirements-core.txt')
class A7ArkadeStreamingTests(unittest.TestCase):
    REL = 'external_evidence/arkade5/test/normalized/arkade5_results.json'

    def _make(self, count: int, *, result_type: str = 'Error',
              tests: int = 1) -> tuple[Path, tempfile.TemporaryDirectory]:
        tmp = tempfile.TemporaryDirectory()
        path = Path(tmp.name) / 'arkade5_results.json'
        with path.open('w', encoding='utf-8') as fh:
            fh.write('{"format_version":2,"evidence_type":"external_validation_report",'
                     '"source_system":"Arkade 5","source_version":"2.13.1",'
                     '"summary":{"number_of_tests_run":' + str(tests) + '},"tests":[')
            for j in range(tests):
                if j:
                    fh.write(',')
                fh.write('{"test_id":"N5.TEST-' + str(j) + '","test_name":"Test",'
                         '"test_type":"Noark 5","source_status":"error",'
                         '"number_of_errors":' + (str(count) if result_type == 'Error' else '0')
                         + ',"results":[')
                for i in range(count):
                    if i:
                        fh.write(',')
                    fh.write('{"result_type":"' + result_type + '",'
                             '"message":"Dokumentert forekomst ' + str(i) + '",'
                             '"result_set_path":["STHA5"],'
                             '"location":{"line_number":' + str(i + 1) + '}}')
                fh.write(']}')
            fh.write(']}')
        return path, tmp

    def _inspect(self, path: Path, limit: int | None = None) -> dict:
        from noark5_workflow.analysis.streaming_arkade import inspect_arkade_stream
        return inspect_arkade_stream(path, self.REL, max_items=limit,
                                     max_output=128 * 1024 * 1024)

    def test_zero_three_hundred_three_hundred_one(self):
        for count in (0, 300, 301):
            with self.subTest(count=count):
                path, tmp = self._make(count)
                try:
                    before = hashlib.sha256(path.read_bytes()).hexdigest()
                    output = self._inspect(path)
                    self.assertEqual(output['record_count'], 1)
                    record = output['records'][0]
                    self.assertEqual(record['reported_result_counts']['Error'], count)
                    self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), before)
                    if count == 0:
                        self.assertEqual(len(record['reported_issues']), 0)
                        self.assertNotIn('reported_issues_complete', record)
                    else:
                        self.assertEqual(len(record['reported_issues']), min(count, 250))
                        if count > 250:
                            self.assertIs(record['reported_issues_complete'], False)
                            self.assertEqual(record['reported_issues_total'], count)
                            self.assertEqual(record['complete_evidence_work_relative_path'], self.REL)
                finally:
                    tmp.cleanup()

    def test_ten_thousand_results_and_no_arbitrary_limit(self):
        path, tmp = self._make(10_000)
        try:
            output = self._inspect(path)
            self.assertEqual(output['records'][0]['reported_result_counts']['Error'], 10_000)
            self.assertEqual(output['records'][0]['reported_issues_total'], 10_000)
            self.assertEqual(len(output['records'][0]['reported_issues']), 250)
        finally:
            tmp.cleanup()

    def test_two_independently_counted_arkade_tests(self):
        path, tmp = self._make(3, result_type='Warning', tests=2)
        try:
            output = self._inspect(path)
            self.assertEqual(output['record_count'], 2)
            self.assertEqual(len(output['records']), 2)
            self.assertEqual([r['external_test_id'] for r in output['records']],
                             ['N5.TEST-0', 'N5.TEST-1'])
            self.assertEqual([r['reported_result_counts']['Warning'] for r in output['records']], [3, 3])
            self.assertTrue(all('reported_issues_complete' not in r for r in output['records']))
        finally:
            tmp.cleanup()

    def test_explicit_small_safety_limit_still_enforced(self):
        from noark5_workflow.analysis.streaming_arkade import ArkadeStreamError
        # Two *results* in one test must be reported as a per-test result limit.
        path, tmp = self._make(2, tests=2)
        try:
            with self.assertRaisesRegex(ArkadeStreamError, 'Resultatposter per test overstiger 1'):
                self._inspect(path, limit=1)
        finally:
            tmp.cleanup()
        # Two tests with one result each must trigger the separate test limit.
        path, tmp = self._make(1, tests=2)
        try:
            with self.assertRaisesRegex(ArkadeStreamError, 'Antall testposter overstiger 1'):
                self._inspect(path, limit=1)
        finally:
            tmp.cleanup()

    def test_malformed_json_is_rejected(self):
        from noark5_workflow.analysis.streaming_arkade import ArkadeStreamError
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / 'arkade5_results.json'
            source.write_text('{"source_system":"Arkade 5","tests":[', encoding='utf-8')
            with self.assertRaises(ArkadeStreamError):
                self._inspect(source)

    @unittest.skipUnless(os.environ.get('DWM_A7_STRESS') == '1',
                         'Aktiver DWM_A7_STRESS=1 for 100 001/200 001-forekomster')
    def test_one_hundred_and_two_hundred_thousand_plus_one(self):
        for count in (100_001, 200_001):
            with self.subTest(count=count):
                path, tmp = self._make(count)
                try:
                    output = self._inspect(path)
                    record = output['records'][0]
                    self.assertEqual(record['reported_result_counts']['Error'], count)
                    self.assertEqual(record['reported_issues_total'], count)
                    self.assertEqual(len(record['reported_issues']), 250)
                finally:
                    tmp.cleanup()


class A7PreviewAccountingTests(unittest.TestCase):
    def test_legacy_html_counts_full_source_not_only_preview(self):
        try:
            from noark5_workflow.analysis.canonical_qa_report_v0115_a12 import _issues
        except ModuleNotFoundError:
            self.skipTest('Denne integrasjonstesten krever DWMs komplette kildekode')
        rel = 'external_evidence/arkade5/r/normalized/arkade5_results.json'
        external = {
            'sources': {rel: 'analyzed'},
            'analysis': {'sources': [{
                'evidence': {'work_relative_path': rel, 'sha256': 'a' * 64},
                'analysis': {'source_format': 'arkade_normalized_v2',
                             'records': [{
                                 'external_test_id': 'N5.15', 'reported_status': 'error',
                                 'reported_result_counts': {'Error': 301},
                                 'reported_issues_total': 301,
                                 'reported_issues_complete': False,
                                 'reported_issues': [
                                     {'result_type': 'Error', 'message': 'status',
                                      'result_set_path': ['STHA5']}
                                 ]}]}}]}}
        preview, total = _issues(external)
        self.assertEqual(total, 301)
        self.assertEqual(len(preview), 1)
        self.assertEqual(preview[0]['test_id'], 'N5.15')

    def test_legacy_html_small_report_keeps_existing_counts(self):
        try:
            from noark5_workflow.analysis.canonical_qa_report_v0115_a12 import _issues
        except ModuleNotFoundError:
            self.skipTest('Denne integrasjonstesten krever DWMs komplette kildekode')
        rel = 'external_evidence/arkade5/r/normalized/arkade5_results.json'
        external = {'sources': {rel: 'analyzed'}, 'analysis': {'sources': [
            {'evidence': {'work_relative_path': rel},
             'analysis': {'source_format': 'arkade_normalized_v2', 'records': [
                 {'external_test_id': 'N5.22', 'reported_status': 'error',
                  'reported_result_counts': {'Error': 2},
                  'reported_issues': [{'result_type': 'Error', 'message': 'A'},
                                      {'result_type': 'Error', 'message': 'B'}]}]}}]}}
        preview, total = _issues(external)
        self.assertEqual((len(preview), total), (2, 2))


if __name__ == '__main__':
    unittest.main()
