"""a18: review both extraction and 43 archive parts without promoting imported evidence."""
from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

from noark5_workflow.reporting.period_assessment_a16 import (
    load_assessment, load_part_assessment, part_review_candidate,
    reviewed_years, save_assessment, save_part_assessment,
)
from noark5_workflow.reporting.period_report_a18 import (
    collect_period_sources, render_period_source_annex, render_period_source_overview,
)
from noark5_workflow.reporting.archive_part_annex_a18 import render_archive_part_annex


def _job(root):
    return SimpleNamespace(job_id='JOB-002', work_operations=Path(root) / 'dwm')


def _data(n=43):
    parts = [{'archive_part': {'system_id': f'part-{i:02d}', 'title': f'Arkivdel {i}'}}
             for i in range(1, n + 1)]
    return {'run_id': 'original-report',
            'period_reconciliation': {'declared_period': {'start_year': 1993, 'end_year': 2099},
                                      'archive_parts': [
                 {'archive_part': {'system_id': 'part-01'},
                  'observed_period': {'first_year': 1993, 'last_year': 2019}}]},
            'archive_parts': parts}


def _kdrs():
    return {'diagnostics': [], 'runs': [
        {'import_id': 'historical', 'report_type': 'standard',
         'sources': ['1502_003_mk_standard.txt'],
         'scopes': [{'scope_id': 'whole', 'label': 'Hele uttrekket',
                     'period_observed_years': [1899, 2099],
                     'series': {'folders_by_creation_year': {'1899': 9, '2099': 139}},
                     'conflicts': []}]},
        {'import_id': 'historical', 'report_type': 'u02',
         'sources': ['1502_003_mk_u2.txt'],
         'scopes': [{'scope_id': 'u2:1:Arkivdel 1', 'label': 'U2 arkivdel 1: Arkivdel 1',
                     'period_observed_years': None, 'series': {}, 'conflicts': []}]}]}


class TestA18PeriodScopes(TestCase):
    def test_can_approve_extraction_without_dwm_xpath(self):
        with TemporaryDirectory() as root:
            job = _job(root)
            data = _data()
            self.assertEqual('kan_ikke_vurderes',
                __import__('noark5_workflow.reporting.period_assessment_a16',
                           fromlist=['review_candidate']).review_candidate(data)['evaluation_status'])
            save_assessment(job, data, status='godkjent', years=[1993, 2020],
                            comment='1899 og 2099 undersøkt som avvik')
            saved = load_assessment(job)
            self.assertEqual((1993, 2020), reviewed_years(saved))
            self.assertEqual('1899 og 2099 undersøkt som avvik', saved['comment'])
            self.assertEqual(1, saved['schema_version'])

    def test_43_part_decisions_are_independent_of_whole(self):
        with TemporaryDirectory() as root:
            job, data = _job(root), _data()
            save_assessment(job, data, status='godkjent', years=[1993, 2020])
            save_part_assessment(job, data, 'part-01', status='godkjent',
                                 years=[2005, 2019], comment='Vurdert arkivdel 1')
            save_part_assessment(job, data, 'part-43', status='godkjent', years=[2000, 2018])
            self.assertEqual((1993, 2020), reviewed_years(load_assessment(job)))
            self.assertEqual((2005, 2019), reviewed_years(load_part_assessment(job, 'part-01')))
            self.assertEqual((2000, 2018), reviewed_years(load_part_assessment(job, 'part-43')))
            self.assertIsNone(load_part_assessment(job, 'part-02'))
            save_assessment(job, data, comment='Revidert hovedbegrunnelse')
            self.assertEqual((2005, 2019), reviewed_years(load_part_assessment(job, 'part-01')))
            self.assertEqual(len(load_assessment(job)['archive_part_assessments']), 2)

    def test_part_edit_does_not_replace_whole_or_neighbor(self):
        with TemporaryDirectory() as root:
            job, data = _job(root), _data(2)
            save_part_assessment(job, data, 'part-01', status='godkjent', years=[1993, 2019])
            save_part_assessment(job, data, 'part-02', status='undersokes', comment='Kontroll pågår')
            save_part_assessment(job, data, 'part-01', status='godkjent', years=[1993, 2020])
            self.assertEqual([1993, 2020], load_part_assessment(job, 'part-01')['selected_years'])
            self.assertEqual('undersokes', load_part_assessment(job, 'part-02')['status'])
            self.assertEqual('ikke_vurdert', load_assessment(job)['status'])

    def test_invalid_years_or_unknown_archive_part_rejected(self):
        with TemporaryDirectory() as root:
            job, data = _job(root), _data(1)
            with self.assertRaises(ValueError):
                save_part_assessment(job, data, 'unknown', status='godkjent', years=[2000, 2020])
            with self.assertRaises(ValueError):
                save_part_assessment(job, data, 'part-01', status='godkjent', years=[2099, 1899])
            self.assertIsNone(load_assessment(job))

    def test_legacy_v1_assessment_remains_readable(self):
        with TemporaryDirectory() as root:
            job, data = _job(root), _data(2)
            save_assessment(job, data, status='godkjent', years=[2000, 2020])
            path = Path(root) / 'dwm/noark5_reports/period_assessments/JOB-002.json'
            snapshot = json.loads(path.read_text('utf-8'))
            self.assertNotIn('archive_part_assessments', snapshot)
            save_part_assessment(job, data, 'part-01', status='godkjent', years=[2001, 2019])
            self.assertEqual((2000, 2020), reviewed_years(load_assessment(job)))

    def test_native_part_observed_years_do_not_copy_extraction_years(self):
        c = part_review_candidate(_data(2), 'part-01')
        self.assertEqual([1993, 2019], c['dwm_observed_years'])
        self.assertIsNone(part_review_candidate(_data(2), 'part-02')['dwm_observed_years'])

    def test_extraction_and_43_parts_in_json_html_without_claiming_kdrs_is_dwm(self):
        with TemporaryDirectory() as root:
            job, data = _job(root), _data()
            save_assessment(job, data, status='godkjent', years=[1993, 2020])
            save_part_assessment(job, data, 'part-01', status='godkjent', years=[2005, 2019])
            with patch('noark5_workflow.reporting.period_report_a18.load_job_kdrs_period_evidence',
                       return_value=_kdrs()):
                model = collect_period_sources([(job, data, None, '')])
            item = model['jobs'][0]
            self.assertEqual([1993, 2020], item['approved_years'])
            self.assertEqual(43, len(item['archive_parts']))
            self.assertEqual([2005, 2019], item['archive_parts'][0]['approved_years'])
            self.assertIsNone(item['archive_parts'][1]['approved_years'])
            self.assertIsNone(item['dwm_observed_years'])
            self.assertEqual([1899, 2099], item['kdrs_runs'][0]['scopes'][0]['period_observed_years'])
            self.assertIn('Godkjent – faglig vurdert 1993–2020', render_period_source_overview(model))
            annex = render_period_source_annex(model)
            self.assertIn('periodevurdering per arkivdel', annex)
            self.assertIn('2005–2019', annex)
            self.assertIn('KDRS Query', annex)
            self.assertIn('1899', annex)
            self.assertEqual('read_only_comparison', model['data_role'])

    def test_compact_part_annex_displays_approved_period_only_for_matching_system_id(self):
        with TemporaryDirectory() as root:
            job, data = _job(root), _data(2)
            save_part_assessment(job, data, 'part-02', status='godkjent', years=[2005, 2019])
            html = render_archive_part_annex([(job, data, None, '')],
                                            {'archive_parts': [], 'diagnostics': []})
            self.assertEqual(2, html.count('<section class="appendix">'))
            self.assertEqual(1, html.count('2005–2019'))
            self.assertEqual(1, html.count('Godkjent'))
            self.assertIn('Ikke vurdert', html)

    def test_kdrs_period_source_without_approval_is_reviewable(self):
        with TemporaryDirectory() as root:
            job = _job(root)
            with patch('noark5_workflow.reporting.period_report_a18.load_job_kdrs_period_evidence',
                       return_value=_kdrs()):
                model = collect_period_sources([(job, _data(1), None, '')])
            status = render_period_source_overview(model)
            self.assertIn('Krever faglig vurdering – KDRS Query tilgjengelig', status)
            self.assertNotIn('Kan ikke vurderes – DWM XPath mangler', status)
