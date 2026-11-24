"""v0.2.7-a3: independently dated charts, filters and preserved GUI routing."""
from __future__ import annotations

import ast
from pathlib import Path
import unittest

from app.analysis_workspace_v027_a2 import AnalysisSnapshot
from app.analysis_workspace_v027_a3 import (
    ANNUAL_FAMILIES, FILTERS, annual_chart_data, favorite_key,
    matches_filter, period_review_rows, result_state,
)

ROOT = Path(__file__).resolve().parents[1]


class AnalysisA3DataTests(unittest.TestCase):
    def setUp(self):
        self.snapshot = AnalysisSnapshot(
            work=Path('work'), job_id='JOB-001', job_name='Demo',
            job_uid='uid-001', report_path=Path('report.json'),
            report={
                'summary': {'archive_count': 1},
                'archive_parts': [
                    {'archive_part': {'system_id': 'p-1', 'title': 'Papir'},
                     'yearly_volume': {'folder': {'2003': 2},
                                       'registration': {'2003': 3},
                                       'journal': {'2004': 3},
                                       'document_description': {'2003': 7},
                                       'document_object': {'2003': 9}}},
                    {'archive_part': {'system_id': 'p-2', 'title': 'Elektronisk'},
                     'yearly_volume': {'folder': {'2024': 1},
                                       'registration': {'2024': 6},
                                       'journal': {'2024': 5},
                                       'document_description': {'2024': 14},
                                       'document_object': {'2024': 14}}},
                ],
                'deviations': [
                    {'category': 'period_source_divergence', 'severity': 'review',
                     'requires_review': True, 'summary': 'Kildene oppgir ulike sluttår'},
                    {'category': 'document_activity_without_folder_or_journal',
                     'severity': 'review', 'requires_review': True,
                     'summary': '2003: dokumentaktivitet',
                     'year_evidence': {'year': '2003'}},
                    {'category': 'delivery_value_M053', 'severity': 'serious',
                     'requires_review': True, 'summary': '20 statusfunn'},
                ],
            }, metadata={}, findings=(
                {'metadata_id': 'M053', 'archive_part_id': 'p-2'},
            ), findings_complete=True, format_statistics={},
        )

    def test_charts_keep_five_distinct_date_series_and_three_families(self):
        self.assertEqual(len(ANNUAL_FAMILIES), 3)
        self.assertEqual([item for _, group in ANNUAL_FAMILIES for item in group],
                         ['folder', 'registration', 'journal',
                          'document_description', 'document_object'])
        first = annual_chart_data(self.snapshot, 0)
        self.assertEqual(first[0]['folder'], 2)
        self.assertEqual(first[0]['registration'], 3)
        self.assertEqual(first[0]['journal'], 0)
        self.assertEqual(first[0]['document_description'], 7)
        self.assertEqual(first[0]['document_object'], 9)
        self.assertEqual(first[1]['year'], 2004)
        self.assertEqual(first[1]['journal'], 3)
        self.assertEqual(annual_chart_data(self.snapshot, 1, '2024')[0]['folder'], 1)
        self.assertEqual(annual_chart_data(self.snapshot, 1, '2003'), ())
        self.assertEqual([r['year'] for r in annual_chart_data(self.snapshot)],
                         [2003, 2004, 2024])

    def test_metadata_deviations_filterable_but_not_approval(self):
        record = {'metadata_id': 'M053', 'deviations': 20}
        self.assertEqual(result_state(self.snapshot, 'metadata', record),
                         ('error', 'Avvik – faglig vurdering'))
        self.assertEqual(result_state(self.snapshot, 'metadata',
                                      {'metadata_id': 'M054', 'deviations': 0})[0], 'none')
        self.assertEqual(result_state(self.snapshot, 'metadata',
                                      {'metadata_id': 'M052', 'deviations': None})[0], 'unknown')
        self.assertTrue(matches_filter('error', 'review'))
        self.assertTrue(matches_filter('error', 'error'))
        self.assertFalse(matches_filter('unknown', 'review'))
        self.assertFalse(matches_filter('warning', 'error'))
        self.assertTrue(matches_filter('unknown', 'favorite', True))
        self.assertFalse(matches_filter('error', 'favorite', False))
        self.assertEqual({key for _, key in FILTERS},
                         {'all', 'error', 'warning', 'review', 'favorite'})

    def test_archive_part_findings_are_scoped(self):
        self.assertEqual(result_state(self.snapshot, 'part', 0)[0], 'unknown')
        self.assertEqual(result_state(self.snapshot, 'part', 1)[0], 'review')
        self.assertEqual(favorite_key(self.snapshot, 'part', 1), 'part:p-2')
        self.assertEqual(favorite_key(self.snapshot, 'metadata',
                                      {'metadata_id': 'M053'}), 'metadata:M053')
        self.assertEqual(favorite_key(self.snapshot, 'format',
                                      {'puid': 'fmt/354'}), 'format:fmt/354')

    def test_global_period_warning_is_not_relabelled_as_part_error(self):
        whole = period_review_rows(self.snapshot, None)
        self.assertEqual(len(whole), 2)
        self.assertEqual(period_review_rows(self.snapshot, 1), ())
        only2003 = period_review_rows(self.snapshot, None, '2003')
        self.assertEqual(len(only2003), 1)
        self.assertEqual(only2003[0]['year_evidence']['year'], '2003')
        self.assertEqual(period_review_rows(self.snapshot, None, '2024'), ())
        self.assertEqual(result_state(self.snapshot, 'period_finding', whole[0])[0],
                         'warning')

    def test_format_id_is_not_assumed_to_be_validated_or_approved(self):
        self.assertEqual(result_state(self.snapshot, 'format',
                                      {'puid': 'fmt/354'})[0], 'unknown')


class AnalysisA3WiringTests(unittest.TestCase):
    def test_entrypoint_injects_a3_after_a2_without_removing_classic(self):
        entry = (ROOT / 'gui_qt/__main__.py').read_text(encoding='utf-8')
        ast.parse(entry)
        self.assertLess(entry.index('install_analysis_workspace(window)'),
                        entry.index('install_analysis_workspace_v3(window)'))
        self.assertIn('install_canonical_results_menu(window)', entry)
        self.assertIn('install_depot_process_results_class(window)', entry)
        a2 = (ROOT / 'gui_qt/analysis_workspace_v027_a2.py').read_text(encoding='utf-8')
        self.assertIn("getattr(window, '_analysis_dialog_class', AnalysisWorkspaceDialog)", a2)
        self.assertIn("window._analysis_classic_result_center = legacy", a2)
        self.assertIn('Resultatvisninger (klassisk)', a2)
        a3 = (ROOT / 'gui_qt/analysis_workspace_v027_a3.py').read_text(encoding='utf-8')
        ast.parse(a3)
        self.assertIn('window._analysis_dialog_class = AnalysisWorkspaceDialogV3', a3)
        self.assertIn('YearBarChart', a3)
        self.assertIn('QSplitter', a3)
        self.assertIn('QSettings', a3)
        self.assertNotIn('.write_text(', a3)
        self.assertNotIn('.write_bytes(', a3)

    def test_release_consistency(self):
        from version import VERSION

        self.assertIn(f'VERSION = "{VERSION}"',
                      (ROOT / 'version.py').read_text(encoding='utf-8'))
        self.assertIn(f'version = "{VERSION.replace("-a", "a")}"',
                      (ROOT / 'pyproject.toml').read_text(encoding='utf-8'))


if __name__ == '__main__':
    unittest.main()
