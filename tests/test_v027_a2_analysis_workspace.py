"""v0.2.7-a2: Analyse is a scope-aware read-only projection, not a new runner."""
from __future__ import annotations

from pathlib import Path
import json
from tempfile import TemporaryDirectory
import unittest

from app.analysis_workspace_v027_a2 import (
    annual_rows, delivery_rules, find_report, format_rows, load_analysis,
    observed_span, rule_findings, summary_counts,
)


class AnalysisModelTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.work = Path(self.temp.name) / 'work'
        self.work.mkdir()
        self.parent = self.work / 'noark5_reports/depot_validation'
        self.report_dir = self.parent / 'JOB-001__20261124T120000Z-run1'
        self.report_dir.mkdir(parents=True)
        self.uid = 'uid-001'
        self.write('noark5_reports/depot_validation/JOB-001__20261124T120000Z-run1/artifact_manifest.json', {
            'job_id': 'JOB-001', 'job_uid': self.uid,
        })
        self.report = {
            'report_type': 'noark5_depot_validation',
            'summary': {'archive_count': 1, 'archive_part_count': 2,
                        'folder_count': 7, 'registration_count': 10,
                        'journalpost_count': 10, 'document_object_count': 12},
            'archive_parts': [
                {'archive_part': {'system_id': 'A-1', 'title': 'Papir'},
                 'folder_count': 3, 'registration_count': 4,
                 'journalpost_count': 4, 'document_object_count': 5,
                 'yearly_volume': {'folder': {'2010': 3},
                                   'registration': {'2010': 4},
                                   'journal': {'2011': 4},
                                   'document_description': {'2010': 5},
                                   'document_object': {'2010': 5}}},
                {'archive_part': {'system_id': 'A-2', 'title': 'Elektronisk'},
                 'folder_count': 4, 'registration_count': 6,
                 'journalpost_count': 6, 'document_object_count': 7,
                 'yearly_volume': {'folder': {'2024': 4},
                                   'registration': {'2024': 6},
                                   'journal': {'2024': 6},
                                   'document_description': {'2024': 7},
                                   'document_object': {'2024': 7}}},
            ],
            'technical_validation': {'summary': {'ok': 2, 'error': 0},
                                     'status': 'error'},
            'delivery_validation': {
                'version': '5.0', 'finding_count': 2,
                'source_reference': {'title': 'Kilde X', 'source_status': 'not_documented'},
                'rules': [
                    {'metadata_id': 'M052', 'xml_field': 'saksstatus',
                     'observed_count': 10, 'delivery_deviations': 2,
                     'standard_value_counts': {'Avsluttet': 8, 'Under behandling': 2},
                     'allowed_at_delivery': ['Avsluttet'], 'source_page': 12},
                ],
            },
        }
        self.write('noark5_reports/depot_validation/JOB-001__20261124T120000Z-run1/depot_validation_report.json', self.report)
        self.findings_rel = ('noark5_reports/depot_validation/'
                             'JOB-001__20261124T120000Z-run1/delivery-funn.jsonl')
        path = self.work / self.findings_rel
        path.write_text('\n'.join(json.dumps({'metadata_id': 'M052', 'value': 'Under behandling',
                                               'archive_part_id': 'A-2', 'object_id': str(n)})
                                   for n in range(2)) + '\n', encoding='utf-8')
        self.write('metadata/depot_metadata.json', {
            'job_id': 'JOB-001', 'current': {'period_start': '2010-01-01',
                                           'period_end': '2024-12-31'},
        })
        self.write('external_evidence/siegfried/20261124T110000Z-abc/pronom_statistics.json', {
            'format_groups': [{'puid': 'fmt/354', 'format': 'PDF/A', 'count': 6, 'version': '1b'},
                              {'puid': 'fmt/43', 'format': 'JPEG', 'count': 1, 'version': '1.01'}],
            'files_total': 7,
        })

    def write(self, rel, obj):
        p = self.work / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(obj, ensure_ascii=False), encoding='utf-8')

    def shot(self):
        return load_analysis(self.work, 'JOB-001', 'Demo', self.uid)

    def test_report_identity_verified_and_no_other_job_reused(self):
        self.assertIsNotNone(find_report(self.work, 'JOB-001', self.uid))
        self.assertIsNone(find_report(self.work, 'JOB-002', self.uid))
        self.assertIsNone(find_report(self.work, 'JOB-001', 'another-uid'))
        self.assertIsNone(find_report(self.work, '../JOB-001'))

    def test_rejects_newer_mismatched_run(self):
        newer = self.parent / 'JOB-001__20261124T130000Z-run2'
        newer.mkdir()
        self.write('noark5_reports/depot_validation/JOB-001__20261124T130000Z-run2/artifact_manifest.json',
                   {'job_id': 'JOB-001', 'job_uid': 'unrelated'})
        self.write('noark5_reports/depot_validation/JOB-001__20261124T130000Z-run2/depot_validation_report.json',
                   self.report)
        self.assertEqual(find_report(self.work, 'JOB-001', self.uid),
                         self.report_dir / 'depot_validation_report.json')

    def test_annual_scope_retains_independent_date_definitions(self):
        shot = self.shot()
        self.assertEqual([x[0] for x in annual_rows(shot)], ['2010', '2011', '2024'])
        self.assertEqual(annual_rows(shot, 0, '2011'), (('2011', (0, 0, 4, 0, 0)),))
        self.assertEqual(annual_rows(shot, 1, '2024'), (('2024', (4, 6, 6, 7, 7)),))
        self.assertEqual(observed_span(shot, 1), '2024-2024')
        self.assertEqual(summary_counts(shot, 1, '2024')['objects'], 7)
        self.assertEqual(summary_counts(shot, None, '')['objects'], 12)
        self.assertEqual(summary_counts(shot, 0, '2024')['objects'], None)

    def test_findings_scoped_without_invented_part_value_counts(self):
        shot = self.shot()
        whole = delivery_rules(shot)[0]
        one = delivery_rules(shot, 0)[0]
        two = delivery_rules(shot, 1)[0]
        self.assertEqual((whole['observed'], whole['deviations']), (10, 2))
        self.assertEqual((one['observed'], one['deviations']), (None, 0))
        self.assertEqual((two['observed'], two['deviations']), (None, 2))
        self.assertFalse(two['production_distribution'])
        self.assertEqual(len(rule_findings(shot, 'M052', 1)), 2)
        self.assertEqual(rule_findings(shot, 'M052', 0), ())
        self.assertEqual(whole['source_status'], 'not_documented')

    def test_missing_or_partial_findings_is_unknown_not_zero(self):
        (self.work / self.findings_rel).unlink()
        shot = self.shot()
        self.assertFalse(shot.findings_complete)
        self.assertIsNone(delivery_rules(shot, 0)[0]['deviations'])
        (self.work / self.findings_rel).write_text(
            json.dumps({'metadata_id': 'M052', 'archive_part_id': 'A-2'}) + '\n', encoding='utf-8')
        self.assertFalse(self.shot().findings_complete)

    def test_format_inventory_is_not_implicitly_part_scoped(self):
        shot = self.shot()
        self.assertEqual([(v['puid'], v['count']) for v in format_rows(shot)],
                         [('fmt/354', 6), ('fmt/43', 1)])

    def test_report_loading_never_changes_source_bytes(self):
        path = self.report_dir / 'depot_validation_report.json'
        original = path.read_bytes()
        self.shot()
        self.assertEqual(path.read_bytes(), original)


class IntegrationContractTests(unittest.TestCase):
    def test_new_surface_is_additive_and_classic_route_preserved(self):
        root = Path(__file__).resolve().parents[1]
        entry = (root / 'gui_qt/__main__.py').read_text(encoding='utf-8')
        ui = (root / 'gui_qt/analysis_workspace_v027_a2.py').read_text(encoding='utf-8')
        self.assertIn('install_depot_process_results_class(window)', entry)
        self.assertIn('install_analysis_workspace(window)', entry)
        self.assertIn('install_canonical_results_menu(window)', entry)
        self.assertIn("legacy = window._a12_open_result_center", ui)
        self.assertIn('window._analysis_classic_result_center = legacy', ui)
        self.assertIn("if depot:", ui)
        self.assertIn("return legacy(_checked, depot=True)", ui)
        self.assertIn("Resultatvisninger (klassisk)", ui)
        self.assertIn('menu.insertAction(window.result_center_action, new_action)', ui)
        self.assertNotIn('write_text(', (root / 'app/analysis_workspace_v027_a2.py').read_text())


if __name__ == '__main__':
    unittest.main()
