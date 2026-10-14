import json
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

from noark5_workflow.reporting.external_report_a18 import collect_job_evidence, render_job_evidence
from noark5_workflow.reporting import job_summary_a16 as summary
from noark5_workflow.reporting import report_package_a16 as package


class DummyJob:
    def __init__(self, name='JOB-001', work_operations=None):
        self.job_id = name
        self.name = name
        self.work_operations = work_operations or "/this-job-has-no-imported-evidence"
        self.status = types.SimpleNamespace(value='Ferdig')
        self.progress = 1.0


class A18ExternalReportTests(unittest.TestCase):
    def setUp(self):
        self.data = {
            'summary': {'archive_part_count': 1, 'folder_count': 1},
            'archive_parts': [{'archive_part': {'title': 'Arkivdel A', 'system_id': 'AP-1'}}],
            'technical_validation': {'status': 'ok', 'summary': {'ok': 2, 'error': 0}, 'reconciliation': {}},
            'external_validation': {'arkade5': {
                'summary': {'imports': 1, 'arkade_errors': 1},
                'imports': [{'import_id': 'ABC', 'source_version': '2.13.1', 'source_file': 'a5.json',
                    'source_sha256': 'a'*64, 'number_of_tests_run': 54, 'number_of_errors': 2,
                    'coverage': {'arkade_control_areas': [{
                        'arkade_test_id': 'N5.47', 'arkade_test_name': 'System-ID',
                        'arkade': {'status': 'error', 'number_of_errors': 2},
                        'relation': 'arkade_only'}]},
                    'pronom': {'available': True, 'statistics': {
                        'total_files': 87, 'unidentified_files': 2,
                        'unique_format_ids': 6, 'row_count': 1,
                        'rows': [{'format_id': 'fmt/18', 'file_type': 'PDF', 'format_version': '1.4', 'raf_220301': 'Gyldig', 'count': 85}],
                        'source': {'original_name': 'formats.csv', 'sha256': 'b'*64}}}}]}}}

    def test_arkade_pronom_embedded_when_no_work_folder(self):
        evidence = collect_job_evidence(DummyJob(), self.data)
        self.assertEqual(len(evidence['arkade5']['imports']), 1)
        html = render_job_evidence(evidence)
        for term in ('N5.47', 'System-ID', 'Siegfried / PRONOM', '87', 'a5.json', 'fmt/18', 'Gyldig'):
            self.assertIn(term, html)
        self.assertIn('KDRS Query', html)
        self.assertIn('KDRS Query', html)

    def test_arkade_absence_and_pronom_are_unknown_not_zero(self):
        self.data['external_validation']['arkade5']['imports'][0]['pronom'] = {'available': False}
        html = render_job_evidence(collect_job_evidence(DummyJob(), self.data))
        self.assertIn('ukjent, ikke null', html)

    def test_per_job_kdrs_and_multiple_imports_from_bank(self):
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, 'external_evidence', 'kdrs_query').mkdir(parents=True)
            fake_bank = {'groups': [
                {'source_system': 'Arkade 5', 'source_import_id': 'ABC',
                 'resources': [{'test_id': 'N5.47', 'test_name': 'System-ID', 'status': 'error',
                                'number_of_errors': 2, 'coverage_classification': 'arkade_only'}]},
                {'source_system': 'KDRS Query', 'source_import_id': 'DEF', 'resources': []},
            ]}
            fake_query = {'resources': [{'report_type': 'u02', 'test_point': 'U2', 'test_name': 'Arkivdel',
                         'archive_part_title': 'Arkivdel A', 'source_file': 'u02.txt',
                         'observations': [{'line': 1, 'text': '4 mapper'}]}], 'summary': {'resources': 1}}
            from sys import modules
            a = types.ModuleType('noark5_workflow.external_evidence.result_bank')
            a.build_external_result_bank = lambda _: fake_bank
            b = types.ModuleType('noark5_workflow.external_evidence.kdrs_query_views')
            b.build_kdrs_query_report_data = lambda _: fake_query
            with patch.dict(modules, {'noark5_workflow.external_evidence.result_bank': a,
                                      'noark5_workflow.external_evidence.kdrs_query_views': b}):
                ev = collect_job_evidence(DummyJob(work_operations=tmp), self.data)
            self.assertEqual(len(ev['arkade5']['imports'][0]['tests']), 1)
            self.assertEqual(ev['kdrs_query']['resources'][0]['observations'][0]['text'], '4 mapper')
            html = render_job_evidence(ev)
            self.assertIn('Arkivdel A', html)
            self.assertIn('4 mapper', html)

    def test_one_and_many_selected_jobs_use_same_renderer(self):
        j1, j2 = DummyJob('JOB-001'), DummyJob('JOB-002')
        opt = summary.ReportOptions(level='Medium', sections=('overview', 'external'))
        with patch.object(summary, '_latest_report', side_effect=lambda _: (self.data, None, '')):
            one = summary.render_selected_jobs_report([j1], opt)
            two = summary.render_selected_jobs_report([j1, j2], opt)
        self.assertEqual(one.count('Noark 5-tester'), 1)
        self.assertEqual(two.count('Noark 5-tester'), 2)
        self.assertEqual(two.count('Siegfried / PRONOM'), 2)
        self.assertIn('JOB-002', two)

    def test_export_json_contains_same_external_evidence_as_html(self):
        job = DummyJob()
        opt = summary.ReportOptions(level='Medium', sections=('external',))
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(summary, '_latest_report', return_value=(self.data, None, '')):
                with patch.object(package, '_latest_report', return_value=(self.data, None, '')):
                    package.write_report_package(tmp, [job], opt, formats=('html', 'json'))
            html = Path(tmp, 'vedlegg-c-teknisk-evidens.html').read_text(encoding='utf8')
            js = json.loads(Path(tmp, 'index.json').read_text(encoding='utf8'))
            self.assertIn('System-ID', html)
            self.assertEqual(js['jobs'][0]['external_evidence']['arkade5']['imports'][0]['source_file'], 'a5.json')
            self.assertIn('PRONOM', html)


if __name__ == '__main__':
    unittest.main()
