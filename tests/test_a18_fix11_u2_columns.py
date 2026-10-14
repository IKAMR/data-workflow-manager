"""A18 fix11: display imported U2 figures alongside DWM, never auto-promote."""
import unittest
from types import SimpleNamespace

from noark5_workflow.reporting.archive_u2_a18 import (
    collect_u2_archive_parts, render_u2_archive_parts,
)


def job(ident):
    return SimpleNamespace(job_id=ident)


def depot(ident='sys-a', title='Saksarkiv', count=None):
    return {'archive_parts': [
        {'archive_part': {'title': title, 'system_id': ident},
         'folder_count': count, 'registration_count': None},
    ]}


def evidence(title='Saksarkiv', import_id='imp1'):
    return {'kdrs_query': {'resources': [{
        'report_type': 'u02', 'archive_part_title': title,
        'archive_part_index': 88, 'test_id': 'kdrs.u02',
        'test_point': 'N5.102', 'source_import_id': import_id,
        'source_file': 'U02.txt', 'source_sha256': 'a' * 64,
        'observations': [{'line': 1, 'text': '[.2] Mappe typer: Alle: 6848'}],
    }]}, 'arkade5': {'imports': []}}


def fact(value, metric='folder_count', title='Saksarkiv', sid='sys-a', import_id='imp1'):
    return {'scope': 'arkivdel', 'archive_part': title,
            'archive_part_system_id': sid, 'metric_id': metric,
            'kdrs_value': value, 'dwm_value': None,
            'comparison': 'DWM mangler', 'kdrs_type': 'u02',
            'source_import_id': import_id, 'source_file': 'U02.txt',
            'source_sha256': 'a' * 64, 'source_line': 15}


def comparison(ident, facts):
    return {'jobs': [{'job_id': ident, 'kdrs_query': {'exact_comparisons': facts}}]}


class U2DisplayTests(unittest.TestCase):
    def test_source_model_populates_five_observed_columns_without_promoting(self):
        fs = [fact(6848), fact(41467, 'registration_count'),
              fact(41254, 'journalpost_count'),
              fact(49926, 'document_description_count'),
              fact(121728, 'document_object_count')]
        model = collect_u2_archive_parts(
            [(job('JOB-002'), depot(), None, '')],
            evidence_by_job={'JOB-002': evidence()},
            source_comparison=comparison('JOB-002', fs))
        row = model['archive_parts'][0]
        self.assertEqual(row['kdrs_u2_observations']['folder_count']['value'], 6848)
        self.assertEqual(row['kdrs_u2_observations']['registration_count']['value'], 41467)
        self.assertEqual(row['metrics']['folder_count']['report'], None)
        self.assertIsNone(row['metrics']['registration_count']['report'])
        html = render_u2_archive_parts(model, detailed=True)
        self.assertIn('6 848', html)
        self.assertIn('41 467', html)
        self.assertIn('41 254', html)
        self.assertIn('49 926', html)
        self.assertIn('121 728', html)
        self.assertIn('Rapportverdi', html)
        self.assertIn('Ukjent', html)  # DWM still missing
        self.assertIn('SHA-256', html)

    def test_real_zero_is_not_unknown(self):
        model = collect_u2_archive_parts(
            [(job('JOB-002'), depot(title='Voksenopplæring'), None, '')],
            evidence_by_job={'JOB-002': evidence('Voksenopplæring')},
            source_comparison=comparison('JOB-002', [fact(0, title='Voksenopplæring')]))
        row = model['archive_parts'][0]['kdrs_u2_observations']['folder_count']
        self.assertEqual(row['value'], 0)
        self.assertEqual(row['status'], 'kildedokumentert')
        self.assertIn('>0</td>', render_u2_archive_parts(model))

    def test_two_conflicting_imports_not_silently_preferred(self):
        model = collect_u2_archive_parts(
            [(job('JOB-002'), depot(), None, '')],
            evidence_by_job={'JOB-002': evidence()},
            source_comparison=comparison('JOB-002', [fact(5), fact(7, import_id='imp2')]))
        got = model['archive_parts'][0]['kdrs_u2_observations']['folder_count']
        self.assertIsNone(got['value'])
        self.assertEqual(got['status'], 'motstrid')
        self.assertEqual(len(got['sources']), 2)
        self.assertIn('Motstrid', render_u2_archive_parts(model))

    def test_mismatched_scope_and_other_job_are_not_used(self):
        model = collect_u2_archive_parts(
            [(job('JOB-002'), depot(), None, '')],
            evidence_by_job={'JOB-002': evidence()},
            source_comparison={'jobs': [
                {'job_id': 'JOB-001', 'kdrs_query': {'exact_comparisons': [fact(777)]}},
                {'job_id': 'JOB-002', 'kdrs_query': {'exact_comparisons': [
                    fact(100, sid='wrong-id'),
                    {**fact(101), 'scope': 'ikke_tilordnet'},
                    {**fact(102), 'kdrs_type': 'standard'},
                ]}},
            ]})
        got = model['archive_parts'][0]['kdrs_u2_observations']['folder_count']
        self.assertIsNone(got['value'])
        self.assertEqual(got['sources'], [])

    def test_dwm_keeps_its_native_report_count(self):
        model = collect_u2_archive_parts(
            [(job('JOB-002'), depot(count=10), None, '')],
            evidence_by_job={'JOB-002': evidence()},
            source_comparison=comparison('JOB-002', [fact(6848)]))
        row = model['archive_parts'][0]
        self.assertEqual(row['metrics']['folder_count']['report'], 10)
        self.assertEqual(row['kdrs_u2_observations']['folder_count']['value'], 6848)
        self.assertIn('6 848', render_u2_archive_parts(model))


if __name__ == '__main__':
    unittest.main()
