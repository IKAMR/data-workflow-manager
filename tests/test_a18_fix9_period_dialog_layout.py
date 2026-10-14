"""a18-fix9: resizable period evidence and separately selectable KDRS sources."""
from __future__ import annotations

import ast
from pathlib import Path
import unittest

from noark5_workflow.reporting.period_kdrs_evidence_a18 import (
    format_kdrs_scope, summarize_kdrs_period_sources,
)

ROOT = Path(__file__).resolve().parents[1]


class TestA18Fix9PeriodDialog(unittest.TestCase):
    def test_source_index_does_not_double_count_standard_and_u1(self):
        same_years = {'folders_by_creation_year': {'1899': 9, '2099': 139}}
        runs = [
            {'report_type': 'standard', 'import_id': 'kdrs-024',
             'scopes': [{'scope_id': 'whole', 'label': 'Hele uttrekket',
                         'series': same_years, 'period_observed_years': [1899, 2099], 'conflicts': []}]},
            {'report_type': 'u01', 'import_id': 'kdrs-024',
             'scopes': [{'scope_id': 'whole', 'label': 'Hele uttrekket',
                         'series': same_years, 'period_observed_years': [1899, 2099], 'conflicts': []}]},
        ]
        lines = summarize_kdrs_period_sources(runs)
        self.assertEqual(2, len(lines))
        self.assertIn('standard / Hele uttrekket: 1899–2099', lines[0])
        self.assertIn('u01 / Hele uttrekket: 1899–2099', lines[1])
        self.assertNotIn('278', ' '.join(lines))  # 139 + 139 is not a combined total.

    def test_u2_summary_is_scope_count_not_number_of_dwm_parts(self):
        run = {'report_type': 'u02', 'import_id': 'old', 'scopes': [
            {'scope_id': 'u2:1:A', 'period_observed_years': [2005, 2019]},
            {'scope_id': 'u2:2:B', 'period_observed_years': [2008, 2020]},
        ]}
        self.assertEqual(['  u02: 2 arkivdelvise kildeområder (import old)'],
                         summarize_kdrs_period_sources([run]))

    def test_ambiguous_sources_never_create_a_year_span(self):
        run = {'report_type': 'standard', 'import_id': 'i', 'scopes': [
            {'scope_id': 'whole', 'period_observed_years': None,
             'conflicts': ['Registreringer 2099: ulike verdier']},
        ]}
        lines = summarize_kdrs_period_sources([run])
        self.assertIn('ikke tilgjengelig', lines[0])
        self.assertIn('Motstridende årstall: 1', lines[1])

    def test_full_source_evidence_remains_accessible(self):
        run = {'report_type': 'standard', 'import_id': 'kdrs-024',
               'sources': ['1502_003_mk_2TB_noark5-xpath-report.txt']}
        scope = {'label': 'Hele uttrekket', 'period_observed_years': [1899, 2099],
                 'series': {'folders_by_creation_year': {'1899': 9, '2099': 139}}}
        formatted = '\n'.join(format_kdrs_scope(run, scope))
        self.assertIn('1899: 9', formatted)
        self.assertIn('2099: 139', formatted)
        self.assertIn('1502_003_mk_2TB', formatted)

    def test_gui_uses_draggable_splitter_and_independent_year_window(self):
        source = (ROOT / 'gui/period_assessment_dialog_a16.py').read_text(encoding='utf-8')
        ast.parse(source)
        self.assertIn('tk.PanedWindow(window, orient=tk.VERTICAL', source)
        self.assertIn('panes.add(upper, minsize=160', source)
        self.assertIn('panes.add(lower, minsize=160', source)
        self.assertIn("volume.pack(fill='both', expand=True", source)
        self.assertIn("body = ctk.CTkScrollableFrame(upper)", source)
        self.assertIn('summarize_kdrs_period_sources(runs)', source)
        self.assertIn('kdrs_scopes[label] = (run, part)', source)
        self.assertNotIn("if part.get('scope_id') == 'whole':\n                    continue", source)


if __name__ == '__main__':
    unittest.main()
