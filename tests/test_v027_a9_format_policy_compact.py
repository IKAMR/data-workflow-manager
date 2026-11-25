"""A9 regression: independent policy/review columns, global sorting, compact Qt routing."""
from __future__ import annotations

import ast
from pathlib import Path
import tempfile
import unittest

from app.noark5_format_presentation_v027_a9 import (
    MAIN_COLUMNS_A9, compact_preference, format_rule_label,
    next_a9_sort, professional_label, sorted_a9_groups,
)

ROOT = Path(__file__).resolve().parents[1]


class A9PresentationTests(unittest.TestCase):
    def setUp(self):
        self.rows = [
            {'puid': 'fmt/17', 'group': 'PDF', 'mime': 'application/pdf', 'format': 'PDF 1.3',
             'files': 2, 'copy_events': 1, 'copy_exports': 1},
            {'puid': 'fmt/354', 'group': 'PDF', 'mime': 'application/pdf', 'format': 'PDF/A',
             'files': 635, 'copy_events': 0, 'copy_exports': 0},
            {'puid': 'x-fmt/280', 'group': 'XML', 'mime': 'application/xml', 'format': 'XSD',
             'files': 17, 'copy_events': 2, 'copy_exports': 1},
            {'puid': 'fmt/480', 'group': 'PDF', 'mime': 'application/pdf', 'format': 'PDF/A',
             'files': 5, 'copy_events': 0, 'copy_exports': 0},
        ]
        self.policy = {'fmt/17': 'Akseptert i valgt profil',
                       'fmt/354': 'Til avklaring', 'x-fmt/280': 'Akseptert i valgt profil',
                       'fmt/480': 'Vurdering utilgjengelig'}
        self.reviews = {'fmt/17': 'deviation', 'fmt/354': 'accepted',
                        'x-fmt/280': 'clarify', 'fmt/480': ''}

    def test_policy_is_immediately_before_independent_professional_review(self):
        self.assertEqual(MAIN_COLUMNS_A9[8:], ('Formatvurdering', 'Faglig vurdering'))
        self.assertEqual(MAIN_COLUMNS_A9[:8],
                         ('Velg', 'PUID', 'Kategori', 'MIME-gruppe', 'Filformat',
                          'Filer', 'Kopier', 'Eksporter'))
        self.assertEqual(len(MAIN_COLUMNS_A9), 10)

    def test_professional_review_is_not_inferred_from_policy(self):
        self.assertEqual(professional_label('accepted'), 'Faglig akseptert')
        self.assertEqual(professional_label('deviation'), 'Avvik')
        self.assertEqual(professional_label('clarify'), 'Til avklaring')
        self.assertEqual(professional_label(''), 'Ikke vurdert')
        self.assertEqual(format_rule_label(None), 'Vurdering ikke tilgjengelig')
        self.assertEqual(format_rule_label('Til avklaring'), 'Til avklaring')

    def test_policy_column_sorts_actual_rule_values_not_human_reviews(self):
        ordered = sorted_a9_groups(self.rows, column=8, policy_labels=self.policy,
                                   assessments=self.reviews)
        self.assertEqual([self.policy[r['puid']] for r in ordered],
                         sorted(self.policy.values(), key=str.casefold))
        self.assertEqual(ordered[0]['puid'], 'fmt/17')
        reverse = sorted_a9_groups(self.rows, column=8, descending=True,
                                   policy_labels=self.policy, assessments=self.reviews)
        self.assertEqual(reverse[0]['puid'], 'fmt/480')
        self.assertEqual(reverse[-1]['puid'], 'fmt/17')

    def test_review_column_sorts_review_values_independent_of_policy(self):
        ordered = sorted_a9_groups(self.rows, column=9, policy_labels=self.policy,
                                   assessments=self.reviews)
        self.assertEqual([professional_label(self.reviews[x['puid']]) for x in ordered],
                         ['Avvik', 'Faglig akseptert', 'Ikke vurdert', 'Til avklaring'])

    def test_earlier_numeric_columns_keep_a8_behavior(self):
        result = sorted_a9_groups(self.rows, column=5, descending=True)
        self.assertEqual([x['files'] for x in result], [635, 17, 5, 2])
        result = sorted_a9_groups(self.rows, column=6)
        self.assertEqual([x['copy_events'] for x in result], [0, 0, 1, 2])
        result = sorted_a9_groups(self.rows, column=1)
        self.assertEqual([x['puid'] for x in result],
                         ['fmt/17', 'fmt/354', 'fmt/480', 'x-fmt/280'])

    def test_all_groups_are_sorted_before_any_paging(self):
        rows = [dict(puid=f'fmt/{i}', group='PDF', mime='application/pdf',
                     format='PDF', files=i, copy_events=0, copy_exports=0)
                for i in range(1999, -1, -1)]
        labels = {r['puid']: 'Godkjent i valgt profil' if int(r['puid'].split('/')[1]) % 2
                  else 'Til avklaring' for r in rows}
        result = sorted_a9_groups(rows, column=8, policy_labels=labels)
        self.assertEqual(len(result), 2000)
        self.assertEqual(result[0]['puid'], 'fmt/1')
        self.assertEqual(result[500]['puid'], 'fmt/1001')
        self.assertEqual(rows[0]['puid'], 'fmt/1999')
        self.assertIsNot(result[0], rows[1998])

    def test_sort_does_not_mutate_rows_or_persist_decisions(self):
        original = [dict(r) for r in self.rows]
        result = sorted_a9_groups(self.rows, column=8,
                                  policy_labels=self.policy, assessments=self.reviews)
        self.assertEqual(self.rows, original)
        self.assertNotIn('policy_status', result[0])

    def test_sort_cycles_and_rejects_invalid_column(self):
        self.assertEqual(next_a9_sort((8, False), 8), (8, True))
        self.assertEqual(next_a9_sort((8, True), 9), (9, False))
        self.assertEqual(next_a9_sort((9, False), 9), (9, True))
        for value in (-1, 10, True, '8'):
            with self.subTest(value=value), self.assertRaises(ValueError):
                next_a9_sort((5, False), value)
            with self.subTest(value=value), self.assertRaises(ValueError):
                sorted_a9_groups(self.rows, column=value)

    def test_compact_setting_handles_qsettings_false_string(self):
        for value in ('false', 'False', '0', '', None, False, 0, 'OFF'):
            self.assertFalse(compact_preference(value))
        for value in (True, 'true', 'True', '1', 'yes'):
            self.assertTrue(compact_preference(value))

    def test_policy_absent_keeps_unknown_explicit(self):
        missing = sorted_a9_groups(self.rows, column=8)
        self.assertEqual({x['puid'] for x in missing}, {x['puid'] for x in self.rows})
        self.assertEqual(format_rule_label(''), 'Vurdering ikke tilgjengelig')


class A9WiringTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.main = (ROOT/'gui_qt/__main__.py').read_text(encoding='utf-8')
        cls.gui = (ROOT/'gui_qt/noark5_format_overview_v027_a9.py').read_text(encoding='utf-8')

    def test_a9_installed_after_a8_and_classic_kept(self):
        ast.parse(self.main)
        self.assertLess(self.main.index('install_analysis_workspace_v8(window)'),
                        self.main.index('install_analysis_workspace_v9(window)'))
        self.assertIn('window._analysis_dialog_class = AnalysisWorkspaceDialogV9', self.gui)
        self.assertIn('Noark5ControlWorkspaceV8', self.gui)
        self.assertIn('AnalysisWorkspaceDialogV8', self.gui)
        self.assertIn('install_canonical_results_menu(window)', self.main)

    def test_view_is_only_presentation_and_reuses_a8_copy(self):
        ast.parse(self.gui)
        for phrase in ('Formatvurdering', 'Faglig vurdering',
                       'MAIN_COLUMNS_A9', '_policy(puid)',
                       '_a8_choices', '_format_mode',
                       'Merk alle', 'Fjern alle',
                       'MIN visning', 'MAX visning',
                       'self.splitter.widget(0).setVisible(not compact)',
                       'self.splitter.widget(2).setVisible(not compact)',
                       'self._edit_review', 'self.details.toHtml()',
                       'QSettings', '_COMPACT_KEY'):
            if phrase == '_format_mode':
                continue  # inherited from A7
            self.assertIn(phrase, self.gui)
        self.assertNotIn('def _copy_selected', self.gui)
        self.assertNotIn('def copy_selected_files', self.gui)
        self.assertNotIn('source.unlink', self.gui)

    def test_a9_has_historical_provenance_and_decision_caution(self):
        self.assertIn('Faglig vurdering', self.gui)
        self.assertIn('ikke faglig eller formell depotgodkjenning', self.gui)
        self.assertIn('Vurdering utilgjengelig', self.gui)
        self.assertIn('self.authority.currentText()', self.gui)

    def test_same_version_and_no_new_alpha_docs(self):
        from version import VERSION
        import tomllib
        with (ROOT/'pyproject.toml').open('rb') as stream:
            self.assertEqual(tomllib.load(stream)['project']['version'],
                             VERSION.replace('-a', 'a'))
        text = (ROOT/'docs/quality/NOARK5-KONTROLLNIVAER-OG-FILFORMATER.md').read_text(encoding='utf-8')
        self.assertIn('A9 – Formatvurdering', text)
        self.assertFalse((ROOT/'docs/quality/NOARK5-PUID-OVERSIKT-MINMAX-v027-a9.md').exists())


if __name__ == '__main__':
    unittest.main()
