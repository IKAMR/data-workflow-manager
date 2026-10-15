"""a18-fix1: annual KDRS evidence must be readable before a manual period review."""
from __future__ import annotations

import ast
from pathlib import Path
from unittest import TestCase

from noark5_workflow.reporting.period_year_profile_a18 import (
    format_year_profile, has_period_year_series, preferred_source_label,
)

ROOT = Path(__file__).resolve().parents[1]


def _scope():
    return {
        'scope_id': 'whole', 'label': 'Hele uttrekket',
        'period_observed_years': [1899, 2099],
        'series': {
            'folders_by_creation_year': {'1899': 9, '2005': 10000, '2099': 139},
            'registrations_by_creation_year': {'2005': 20000, '2006': 15000},
            'journalposts_by_journal_year': {'2005': 17500, '2006': 16000},
            'change_log_events_by_year': {'2099': 200000},
        }, 'conflicts': [],
    }


class YearProfileTests(TestCase):
    def test_earliest_and_latest_have_counts_with_same_series_denominator(self):
        run = {'report_type': 'standard', 'import_id': 'kdrs-import', 'sources': ['mk_standard.txt']}
        text = '\n'.join(format_year_profile(run, _scope()))
        self.assertIn('1899: 9 / 10 148 kjente totalt', text)
        self.assertIn('2099: 139 / 10 148 kjente totalt', text)
        self.assertIn('2005', text)
        self.assertIn('Registr.', text)
        self.assertIn('JP dato', text)
        self.assertIn('mk_standard.txt', text)
        self.assertIn('IKKE automatisk arkivperiode', text)

    def test_zero_absent_and_conflict_are_separate(self):
        scope = {'series': {
            'folders_by_creation_year': {'2000': 0, '2001': 100, '2002': None},
            'registrations_by_creation_year': {'2001': 55},
        }, 'conflicts': ['Kildekonflikt 2002']}
        output = '\n'.join(format_year_profile({'report_type': 'u01'}, scope))
        self.assertIn('0 = observert null', output)
        self.assertIn('! = motstridende kildeverdier', output)
        self.assertIn('Kildekonflikt 2002', output)
        self.assertIn('KILDEKONFLIKTER', output)

    def test_changelog_alone_never_becomes_period(self):
        scope = {'series': {'change_log_events_by_year': {'2099': 500}}}
        self.assertFalse(has_period_year_series(scope))
        result = '\n'.join(format_year_profile({'report_type': 'standard'}, scope))
        self.assertIn('Ingen sikre positive årsverdier', result)

    def test_missing_native_prefers_kdrs_standard_whole_with_annual_data(self):
        standard = {'report_type': 'standard'}
        u01 = {'report_type': 'u01'}
        u02 = {'report_type': 'u02'}
        sources = {
            'KDRS u02': (u02, {'scope_id': 'u2:1:Arkivdel', 'series': {'folders_by_creation_year': {'2000': 5}}}),
            'KDRS u01': (u01, _scope()),
            'KDRS standard': (standard, _scope()),
        }
        labels = ['Samlet uttrekk', 'DWM arkivdel 1', *sources]
        result = preferred_source_label(labels, sources, has_dwm_years=False)
        self.assertEqual('KDRS standard', result)
        self.assertEqual('Samlet uttrekk', preferred_source_label(labels, sources, has_dwm_years=True))

    def test_source_with_only_zeros_does_not_hide_useful_u01_years(self):
        standard = {'report_type': 'standard'}
        u01 = {'report_type': 'u01'}
        sources = {
            'KDRS standard': (standard, {'scope_id': 'whole', 'series':
                                       {'folders_by_creation_year': {'2099': 0}}}),
            'KDRS u01': (u01, _scope()),
        }
        self.assertEqual('KDRS u01', preferred_source_label(
            ['Samlet uttrekk', *sources], sources, has_dwm_years=False))

    def test_native_archive_part_cannot_inherit_u2_by_ordinal(self):
        sources = {'KDRS u02': ({'report_type': 'u02'},
                               {'scope_id': 'u2:1:A', 'series': {'folders_by_creation_year': {'2010': 2}}})}
        chosen = preferred_source_label(['Samlet uttrekk', 'DWM arkivdel 1', 'KDRS u02'], sources,
                                        has_dwm_years=False, review_system_id='native-X',
                                        part_source_labels={'native-X': 'DWM arkivdel 1'})
        self.assertEqual('DWM arkivdel 1', chosen)

    def test_standard_and_u01_annual_values_never_combined(self):
        first = '\n'.join(format_year_profile({'report_type': 'standard'}, _scope()))
        second_scope = {'series': {'folders_by_creation_year': {'1899': 6, '2099': 5}}}
        second = '\n'.join(format_year_profile({'report_type': 'u01'}, second_scope))
        self.assertIn('10 148', first)
        self.assertNotIn('10 148', second)
        self.assertIn('6 / 11', second)

    def test_gui_defaults_to_readable_source_and_never_writes_approved_years(self):
        source = (ROOT / 'gui' / 'period_assessment_dialog_a16.py').read_text(encoding='utf-8')
        ast.parse(source)
        self.assertIn('preferred_source_label(', source)
        self.assertIn('format_year_profile(run, part)', source)
        self.assertIn('show_source(default_source)', source)
        self.assertIn('save_part_assessment(job, report, system_id', source)
        self.assertNotIn('years = scope.get(\'period_observed_years\')', source)


if __name__ == '__main__':
    import unittest
    unittest.main()
