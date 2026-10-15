"""KDRS annual facts remain separate from native XPath; manual review is allowed."""
from __future__ import annotations
from pathlib import Path
import tempfile
import unittest
from types import SimpleNamespace, ModuleType
from unittest.mock import patch

from noark5_workflow.reporting.period_kdrs_evidence_a18 import (
    period_evidence_from_pool, load_job_kdrs_period_evidence, format_kdrs_scope,
)
from noark5_workflow.reporting.period_assessment_a16 import review_candidate

ROOT = Path(__file__).resolve().parents[1]


def resource(import_id, report_type, metric, values, *, part=None, title=None, raw_status='exact', source='source.txt'):
    return {'import_id': import_id, 'report_type': report_type,
            'source_file': source, 'archive_part_index': part,
            'archive_part_title': title, 'semantic_lines': [
                {'archive_part_index': part, 'archive_part_title': title,
                 'facts': [{'metric_id': metric, 'mapping_status': raw_status,
                            'value_kind': 'year_count', 'year': int(year), 'value': value}
                           for year, value in values.items()]}]}


class TestA18Fix5PeriodKdrs(unittest.TestCase):
    def test_absent_dwm_span_is_unknown_not_no_review(self):
        value = review_candidate({'period_reconciliation': {'declared_period': {'start_year': 1993, 'end_year': 2099}}})
        self.assertIsNone(value['observed_years'])
        self.assertIsNone(value['needs_review'])
        self.assertEqual(value['evaluation_status'], 'kan_ikke_vurderes')
        self.assertIsNone(value['proposed_years'])

    def test_regular_dwm_disagreement_still_requires_review(self):
        value = review_candidate({'period_reconciliation': {
            'declared_period': {'start_year': 1993, 'end_year': 2099},
            'observed_series': {'registration_created': {'span': {'first_year': 1993, 'last_year': 2022}}}}})
        self.assertTrue(value['needs_review'])
        self.assertEqual(value['observed_years'], [1993, 2022])

    def test_kdrs_year_counts_from_separate_imports_are_not_summed(self):
        pool = {'resources': [
            resource('old', 'standard', 'registrations_by_creation_year', {1993: 2, 2099: 1}),
            resource('new', 'standard', 'registrations_by_creation_year', {1993: 9, 2099: 4}),
        ]}
        result = period_evidence_from_pool(pool)
        self.assertEqual(len(result['runs']), 2)
        self.assertEqual(result['runs'][0]['scopes'][0]['series']['registrations_by_creation_year']['1993'], 2)
        self.assertEqual(result['runs'][1]['scopes'][0]['series']['registrations_by_creation_year']['1993'], 9)
        self.assertEqual(result['runs'][0]['scopes'][0]['period_observed_years'], [1993, 2099])
        self.assertEqual(result['data_role'], 'external_evidence_only')

    def test_years_from_different_sources_standard_u1_u2_separate(self):
        pool = {'resources': [
            resource('one', 'standard', 'registrations_by_creation_year', {1993: 20}),
            resource('one', 'u01', 'folders_by_creation_year', {1994: 1}),
            resource('one', 'u02', 'registrations_by_creation_year', {2010: 4}, part=1, title='A'),
            resource('one', 'u02', 'registrations_by_creation_year', {2011: 2}, part=2, title='B'),
        ]}
        result = period_evidence_from_pool(pool)
        self.assertEqual(len(result['runs']), 3)
        self.assertEqual([len(run['scopes']) for run in result['runs']], [1, 1, 2])
        self.assertNotEqual(result['runs'][2]['scopes'][0]['scope_id'], result['runs'][2]['scopes'][1]['scope_id'])

    def test_only_exact_metric_year_counts_are_interpreted(self):
        pool = {'resources': [
            resource('one', 'standard', 'registrations_by_creation_year', {2000: 12}, raw_status='context_only'),
            resource('one', 'standard', 'unexpected_metric', {2001: 14}),
            resource('one', 'standard', 'registrations_by_creation_year', {2002: -8}),
        ]}
        self.assertEqual(period_evidence_from_pool(pool)['runs'][0]['scopes'], [])

    def test_change_log_is_visible_but_not_period(self):
        result = period_evidence_from_pool({'resources': [
            resource('one', 'standard', 'change_log_events_by_year', {2099: 12}),
            resource('one', 'standard', 'registrations_by_creation_year', {2008: 1}),
        ]})
        part = result['runs'][0]['scopes'][0]
        self.assertEqual(part['period_observed_years'], [2008, 2008])
        text = '\n'.join(format_kdrs_scope(result['runs'][0], part))
        for fragment in ('Endringslogg', '2008', '2099'):
            self.assertIn(fragment, text)

    def test_conflicting_counts_for_same_year_are_flagged_not_added(self):
        result = period_evidence_from_pool({'resources': [
            resource('one', 'standard', 'registrations_by_creation_year', {2000: 10}),
            resource('one', 'standard', 'registrations_by_creation_year', {2000: 20}),
        ]})
        part = result['runs'][0]['scopes'][0]
        self.assertIsNone(part['series']['registrations_by_creation_year']['2000'])
        self.assertTrue(part['conflicts'])
        self.assertIsNone(part['period_observed_years'])

    def test_no_work_folder_is_explicit_unknown(self):
        job = SimpleNamespace(job_id='JOB-002')
        result = load_job_kdrs_period_evidence(job)
        self.assertFalse(result['runs'])
        self.assertIn('Ingen importerte', ' '.join(result['diagnostics']))

    def test_existing_import_is_read_without_modifying_files(self):
        import sys
        with tempfile.TemporaryDirectory() as root:
            base = Path(root) / 'dwm'
            imports = base / 'external_evidence' / 'kdrs_query'
            imports.mkdir(parents=True)
            marker = imports / 'keep.json'
            marker.write_text('source unchanged', encoding='utf-8')
            fake = ModuleType('noark5_workflow.external_evidence.kdrs_query_mapping')
            fake.build_mapped_pool = lambda work: {'resources': [
                resource('import-024', 'standard', 'registrations_by_creation_year',
                         {1993: 2, 2020: 4}, source='KDRS-024.txt')]}
            job = SimpleNamespace(job_id='JOB-002', work_operations=root)
            with patch.dict(sys.modules, {fake.__name__: fake}):
                evidence = load_job_kdrs_period_evidence(job)
            self.assertEqual(evidence['runs'][0]['scopes'][0]['period_observed_years'], [1993, 2020])
            self.assertEqual(evidence['runs'][0]['sources'], ['KDRS-024.txt'])
            self.assertEqual(marker.read_text(encoding='utf-8'), 'source unchanged')

    def test_missing_kdrs_year_observations_are_not_zero_or_period(self):
        result = period_evidence_from_pool({'resources': [
            resource('one', 'u02', 'registration_count', {2017: 5}, part=1, title='Test'),
        ]})
        self.assertEqual(result['runs'][0]['scopes'], [])

    def test_gui_allows_manual_review_with_and_without_dwm_xpath(self):
        source = (ROOT / 'gui/period_assessment_dialog_a16.py').read_text(encoding='utf-8')
        for fragment in ('load_job_kdrs_period_evidence(job)',
                         'save_assessment(job, report', 'save_part_assessment(job, report',
                         'DWM – lagret XPath-årsvolum', 'KDRS Query – separate kilder',
                         'Registreringer per år: Ikke tilgjengelig',
                         'Vurderingsnivå', 'review_scope.configure(command=load_review)'):
            self.assertIn(fragment, source)
        self.assertNotIn('write_mapped_pool(', source)
        self.assertNotIn('run_xpath(', source)

    def test_invalid_and_empty_values_are_not_extrapolated(self):
        result = period_evidence_from_pool({'resources': [
            resource('one', 'standard', 'registrations_by_creation_year', {'1888': 0, '2020': 2}),
        ]})
        self.assertEqual(result['runs'][0]['scopes'][0]['period_observed_years'], [2020, 2020])
        self.assertEqual(result['runs'][0]['scopes'][0]['series']['registrations_by_creation_year']['1888'], 0)
