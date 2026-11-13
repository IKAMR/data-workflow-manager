"""Read-only standard-value evidence and actual saved finding count."""
from __future__ import annotations
import ast
from pathlib import Path
import unittest
from types import SimpleNamespace
from app.standard_value_findings_v0114_a2 import (
    extract_standard_value_findings, findings_from_snapshots, source_location_present,
)

ROOT = Path(__file__).resolve().parents[1]


def sample():
    return {'standard_values': {'tests': [
        {'test_id': 'kdrs.c15', 'test_point': 'M053', 'checks': {
            'journal_status': {'versions': {
                '4.0': {'status': 'all_observed_values_standard'},
                '5.0': {'status': 'additional_observed_values',
                        'additional_observed_values': {'Godkjent av leder': 2},
                        'standard_values': ['Arkivert', 'Journalført'],
                        'standard_value_counts': {'Arkivert': 5},
                        'additional_observed_count': 2}}}}},
        {'test_id': 'kdrs.c16', 'checks': {'document_type': {'versions': {
            '5.0': {'status': 'additional_observed_values',
                    'additional_observed_values': {'Annet': 3}}}}}},
    ]}}


class StandardValueFindingsTests(unittest.TestCase):
    def test_only_actual_extra_statuses(self):
        findings = extract_standard_value_findings(sample(), job_name='Uttrekk')
        self.assertEqual(len(findings), 2)
        self.assertEqual(findings[0].field, 'journal_status')
        self.assertEqual(findings[0].version, '5.0')
        self.assertEqual(findings[0].extra, {'Godkjent av leder': 2})
        self.assertEqual(findings[0].extra_total, 2)
        self.assertEqual(findings[1].test_id, 'kdrs.c16')

    def test_no_fabricated_source_location(self):
        self.assertFalse(source_location_present(extract_standard_value_findings(sample())[0]))

    def test_empty_or_old_report(self):
        self.assertEqual(extract_standard_value_findings(None), ())
        self.assertEqual(extract_standard_value_findings({'standard_values': {}}), ())

    def test_multiple_snapshots_are_not_merged(self):
        def shot(uid):
            return SimpleNamespace(job=SimpleNamespace(job_uid=uid,name=uid),
                                   depot=sample(), results=SimpleNamespace(depot_report_path=Path('/not-real/report.json')))
        findings = findings_from_snapshots([shot('a'),shot('b')])
        self.assertEqual(len(findings), 4)
        self.assertEqual({f.job_uid for f in findings}, {'a','b'})

    def test_no_source_writes_and_read_only_integration(self):
        gui=(ROOT/'gui_qt/standard_values_v0114_a2.py').read_text('utf-8')
        self.assertIn('install_standard_values_link',gui)
        self.assertIn('Vis standardverdikontroller',gui)
        self.assertIn('QDesktopServices.openUrl',gui)
        app=(ROOT/'gui_qt/basic_main_v0113_a2.py').read_text('utf-8')
        self.assertIn('install_standard_values_link(viewer)',app)
        ast.parse(gui)

if __name__ == '__main__': unittest.main()
