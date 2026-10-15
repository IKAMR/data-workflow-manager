"""a18-fix7 regression: KDRS periods remain independent evidence in report/JSON.

The historic 'Kan ikke vurderes – DWM XPath mangler' expectation was corrected
in a18: an operator can review KDRS year evidence without DWM XPath.
"""
from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

from noark5_workflow.reporting.period_report_a18 import (
    collect_period_sources, render_period_source_annex, render_period_source_overview,
)
from noark5_workflow.reporting.report_package_a16 import write_report_package
from noark5_workflow.reporting.job_summary_a16 import ReportOptions


def _job(jobid, base):
    return SimpleNamespace(job_id=jobid, name=jobid, status=SimpleNamespace(value='Ferdig'),
                           progress=1.0, work_operations=Path(base) / jobid / 'dwm')


def _kdrs_evidence():
    return {'runs': [
        {'import_id': 'import-024', 'report_type': 'standard',
         'sources': ['1502_024_standard.txt'],
         'scopes': [{'scope_id': 'whole', 'label': 'Hele uttrekket',
                     'period_observed_years': [1993, 2020],
                     'series': {'registrations_by_creation_year': {'1993': 4, '2020': 7},
                                'change_log_events_by_year': {'2099': 5}},
                     'conflicts': []}]},
        {'import_id': 'import-024', 'report_type': 'u02',
         'sources': ['1502_024_u2.txt'],
         'scopes': [{'scope_id': 'u2:1:Arkivdel A', 'label': 'U2 arkivdel 1: Arkivdel A',
                     'period_observed_years': None,
                     'series': {'registrations_by_creation_year': {'2020': None}},
                     'conflicts': ['Registreringer (opprettet) 2020: ulike KDRS-verdier']}]},
        ], 'diagnostics': []}


class TestA18Fix7PeriodReport(TestCase):
    def test_one_or_many_jobs_use_same_reader_without_promoting_external_years(self):
        with TemporaryDirectory() as folder:
            j1, j2 = _job('JOB-001', folder), _job('JOB-002', folder)
            dwm = {'period_reconciliation': {'declared_period': {'start_year': 1993, 'end_year': 2099}}}
            with patch('noark5_workflow.reporting.period_report_a18.load_job_kdrs_period_evidence',
                       side_effect=lambda job: _kdrs_evidence() if job.job_id == 'JOB-002' else {'runs': [], 'diagnostics': []}):
                model = collect_period_sources([(j1, {}, None, 'DWM mangler'), (j2, dwm, 'DWM-002.json', '')])
            self.assertEqual(len(model['jobs']), 2)
            self.assertIsNone(model['jobs'][1]['dwm_observed_years'])
            self.assertIsNone(model['jobs'][0]['dwm_report_file'])
            self.assertEqual(model['jobs'][1]['dwm_declared_years'], [1993, 2099])
            self.assertEqual(len(model['jobs'][1]['kdrs_runs']), 2)
            html = render_period_source_annex(model)
            self.assertIn('Krever faglig vurdering – KDRS Query tilgjengelig', html)
            self.assertNotIn('Kan ikke vurderes – DWM XPath mangler', html)
            for text in ('1502_024_standard.txt', 'Registreringer (opprettet)',
                         'Endringslogg (ikke arkivperiode)', 'Konflikt', '2020', 'Arkivdel A'):
                self.assertIn(text, html)
            overview = render_period_source_overview(model)
            self.assertIn('2 import-/rapportkilder', overview)
            self.assertIn('1 med observerte ytterår', overview)
            self.assertIn('1 motstridende årsobservasjoner', overview)

    def test_html_escaped_provenance_and_separate_conflicts(self):
        entry = {'jobs': [{'job_id': 'JOB-002', 'dwm_observed_years': None,
                           'dwm_declared_years': None, 'kdrs_runs': [
                               {'import_id': '<unsafe>', 'report_type': 'u02', 'source_files': ['A&B.txt'],
                                'scopes': [{'label': '<Arkivdel>', 'period_observed_years': None,
                                            'series': {'registrations_by_creation_year': {'2020': None}},
                                            'conflicts': ['Mangler <verdi>']}]}],
                           'kdrs_diagnostics': []}]}
        html = render_period_source_annex(entry)
        self.assertNotIn('<unsafe>', html)
        self.assertIn('&lt;unsafe&gt;', html)
        self.assertIn('A&amp;B.txt', html)
        self.assertIn('Konflikt', html)
        self.assertIn('Ikke tilgjengelig', html)

    def test_shared_export_for_one_job_keeps_native_report_and_adds_period_json(self):
        with TemporaryDirectory() as directory:
            job = _job('JOB-002', directory)
            native = {'summary': {'folder_count': 1}, 'archive_parts': [],
                      'period_reconciliation': {'declared_period': {'start_year': 1993, 'end_year': 2099}}}
            work = job.work_operations
            reportdir = work / 'noark5_reports' / 'depot_validation' / 'JOB-002__RUN-1'
            reportdir.mkdir(parents=True)
            report_path = reportdir / 'depot_validation_report.json'
            report_path.write_text(json.dumps(native), encoding='utf-8')
            original = report_path.read_bytes()
            with patch('noark5_workflow.reporting.period_report_a18.load_job_kdrs_period_evidence',
                       return_value=_kdrs_evidence()):
                target = Path(directory) / 'output'
                exported = write_report_package(target, [job], ReportOptions('Full'), formats=('html', 'json'))
            self.assertEqual(exported, target / 'index.html')
            main = exported.read_text(encoding='utf-8')
            annex = (target / 'vedlegg-d-periodevurdering.html').read_text(encoding='utf-8')
            parsed = json.loads((target / 'index.json').read_text(encoding='utf-8'))
            self.assertIn('Periodegrunnlag – DWM og KDRS Query', main)
            self.assertIn('KDRS Query – importerte årsserier', annex)
            self.assertIn('1502_024_standard.txt', annex)
            self.assertEqual(len(parsed['period_source_evidence']['jobs']), 1)
            self.assertEqual(parsed['period_source_evidence']['jobs'][0]['kdrs_runs'][0]['scopes'][0]['period_observed_years'], [1993, 2020])
            self.assertIsNone(parsed['period_source_evidence']['jobs'][0]['dwm_observed_years'])
            self.assertEqual(report_path.read_bytes(), original)

    def test_multiple_jobs_do_not_merge_source_years(self):
        with TemporaryDirectory() as directory:
            jobs = [_job('JOB-001', directory), _job('JOB-002', directory)]
            with patch('noark5_workflow.reporting.period_report_a18.load_job_kdrs_period_evidence',
                       side_effect=lambda job: _kdrs_evidence() if job.job_id == 'JOB-002' else {'runs': [], 'diagnostics': ['Ikke importert']}):
                model = collect_period_sources([(j, {}, None, 'Ingen') for j in jobs])
            self.assertEqual(model['jobs'][0]['kdrs_runs'], [])
            self.assertEqual(model['jobs'][1]['kdrs_runs'][0]['scopes'][0]['period_observed_years'], [1993, 2020])
            self.assertIn('Ikke importert', render_period_source_annex(model))
