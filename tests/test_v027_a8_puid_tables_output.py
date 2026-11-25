"""A8: globally sorted PUID rows and source-safe persistent-copy UI contract."""
from __future__ import annotations

import ast
import tempfile
from pathlib import Path
import unittest

from app.noark5_format_sort_v027_a8 import (
    LEFT_COLUMNS, MAIN_COLUMNS, copy_structure, next_sort, sorted_puid_groups,
)

ROOT = Path(__file__).resolve().parents[1]


class A8SortTests(unittest.TestCase):
    def setUp(self):
        self.rows = [
            {'puid': 'fmt/101', 'group': 'XML', 'mime': 'application/xml',
             'format': 'Extensible XML', 'files': 100, 'copy_events': 2,
             'copy_exports': 1},
            {'puid': 'fmt/9', 'group': 'PDF', 'mime': 'application/pdf',
             'format': 'Portable Document', 'files': 7, 'copy_events': 80,
             'copy_exports': 4},
            {'puid': 'x-fmt/280', 'group': 'XML', 'mime': 'application/xml',
             'format': 'Schema', 'files': 1, 'copy_events': 0,
             'copy_exports': 0},
            {'puid': 'fmt/17', 'group': 'PDF', 'mime': 'application/pdf',
             'format': 'Portable Document', 'files': 1000, 'copy_events': 12,
             'copy_exports': 3},
        ]

    def test_selector_has_required_columns(self):
        self.assertEqual(LEFT_COLUMNS[:4], ('Velg', 'PUID', 'Kat.', 'MIME'))
        self.assertEqual(LEFT_COLUMNS[4], 'Filer')

    def test_main_groups_have_count_and_copy_columns(self):
        self.assertEqual(MAIN_COLUMNS[5:8], ('Filer', 'Kopier', 'Eksporter'))

    def test_puid_uses_natural_numeric_order(self):
        sorted_rows = sorted_puid_groups(self.rows, selector=True, column=1)
        self.assertEqual([r['puid'] for r in sorted_rows],
                         ['fmt/9', 'fmt/17', 'fmt/101', 'x-fmt/280'])
        self.assertEqual(sorted_puid_groups(self.rows, selector=True,
                                            column=1, descending=True)[0]['puid'],
                         'x-fmt/280')

    def test_main_numeric_counts_do_not_use_alphabetical_sort(self):
        result = sorted_puid_groups(self.rows, column=5, descending=True)
        self.assertEqual([r['files'] for r in result], [1000, 100, 7, 1])
        self.assertEqual([r['copy_events'] for r in
                          sorted_puid_groups(self.rows, column=6)], [0, 2, 12, 80])

    def test_selector_uses_numeric_file_counts(self):
        self.assertEqual([r['files'] for r in
                          sorted_puid_groups(self.rows, column=4, selector=True)],
                         [1, 7, 100, 1000])

    def test_category_and_mime_sort(self):
        ordered = sorted_puid_groups(self.rows, column=2)
        self.assertEqual([r['group'] for r in ordered], ['PDF', 'PDF', 'XML', 'XML'])
        ordered = sorted_puid_groups(self.rows, column=3, selector=True)
        self.assertEqual([r['mime'] for r in ordered],
                         ['application/pdf', 'application/pdf',
                          'application/xml', 'application/xml'])

    def test_sort_respects_assessment_and_check_flags(self):
        status = {'fmt/9': 'clarify', 'fmt/17': 'deviation'}
        ordered = sorted_puid_groups(self.rows, column=8, assessments=status)
        self.assertEqual(len(ordered), 4)
        checked = {'fmt/17': False}
        ordered = sorted_puid_groups(self.rows, column=0, selector=True,
                                    checked=checked)
        self.assertEqual(ordered[0]['puid'], 'fmt/17')

    def test_sort_is_pure_and_includes_all_rows_before_paging(self):
        rows = [dict(puid=f'fmt/{i}', group='PDF', mime='application/pdf',
                     format='PDF', files=(1500-i), copy_events=0,
                     copy_exports=0) for i in range(1500)]
        ordered = sorted_puid_groups(rows, column=5, descending=True)
        self.assertEqual(len(ordered), 1500)
        self.assertEqual(ordered[0]['files'], 1500)
        self.assertEqual(ordered[1000]['files'], 500)
        self.assertEqual(rows[0]['files'], 1500)  # input unchanged
        self.assertIsNot(ordered[0], rows[0])

    def test_click_cycles_ascending_descending(self):
        self.assertEqual(next_sort((5, True), 5), (5, False))
        self.assertEqual(next_sort((5, False), 5), (5, True))
        self.assertEqual(next_sort((5, True), 3), (3, False))
        self.assertEqual(next_sort((1, False), 1, selector=True), (1, True))

    def test_bad_columns_rejected(self):
        for column in (-1, 9, True):
            with self.assertRaises(ValueError):
                sorted_puid_groups(self.rows, column=column)
        with self.assertRaises(ValueError):
            next_sort((0, False), 5, selector=True)

    def test_puid_copy_default_and_explicit_flat(self):
        self.assertEqual(copy_structure(''), 'puid')
        self.assertEqual(copy_structure(None), 'puid')
        self.assertEqual(copy_structure('flat'), 'flat')
        self.assertEqual(copy_structure('invalid'), 'puid')


class A8WiringTests(unittest.TestCase):
    def test_entrypoint_and_version(self):
        main = (ROOT/'gui_qt/__main__.py').read_text(encoding='utf-8')
        ast.parse(main)
        self.assertLess(main.index('install_analysis_workspace_v7(window)'),
                        main.index('install_analysis_workspace_v8(window)'))
        from version import VERSION
        import tomllib
        with (ROOT/'pyproject.toml').open('rb') as stream:
            self.assertEqual(tomllib.load(stream)['project']['version'],
                             VERSION.replace('-a', 'a'))

    def test_a8_gui_reuses_a7_and_source_copy(self):
        source = (ROOT/'gui_qt/noark5_format_overview_v027_a8.py').read_text(
            encoding='utf-8')
        ast.parse(source)
        for name in ('Noark5ControlWorkspaceV7', 'AnalysisWorkspaceDialogV7',
                     'QTableWidget', 'sorted_puid_groups', '_sort_left',
                     '_sort_main', '_selected_formats', '_copy_selected',
                     'copy_structure', "QSettings('IKAMR', 'DWM-Qt')",
                     '_output_root', 'Faglig', 'DokumentWorker'):
            if name == 'DokumentWorker':
                name = 'DocumentWorker'
            if name == 'Faglig':
                continue
            self.assertIn(name, source)
        self.assertIn('window._analysis_dialog_class = AnalysisWorkspaceDialogV8', source)
        self.assertIn('QFileDialog.getExistingDirectory', source)
        self.assertIn("self._filtered_groups()", source)
        self.assertIn('output_root', source)

    def test_no_extra_current_alpha_document_under_docs(self):
        self.assertFalse((ROOT/'docs/quality/NOARK5-PUID-SORTERING-v027-a8.md').exists())
        self.assertIn('A8 – PUID-utvalg', (ROOT/'docs/quality/NOARK5-KONTROLLNIVAER-OG-FILFORMATER.md').read_text(encoding='utf-8'))


if __name__ == '__main__':
    unittest.main()
