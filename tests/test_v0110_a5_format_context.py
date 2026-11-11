"""a5: dated provenance and independent PRONOM/RAF vs PUID rule evidence."""
from __future__ import annotations

import csv
import json
from pathlib import Path
import tempfile
import unittest
from types import SimpleNamespace

from app.format_context_v0110_a5 import (
    comparison_labels, export_comparison_csv, read_pronom_import_context,
)
from app.format_policy_v0110_a4 import load_format_policy

ROOT = Path(__file__).resolve().parents[1]


class FormatContextA5Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.policy = load_format_policy(ROOT / 'config' / 'formats' /
                                        'nasjonalarkivet_2026-11-10.json')

    def test_independent_dates_and_source_identifiers_follow_export(self):
        policy = self.policy
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / 'formats.csv'
            rows = [{
                'job': 'Test', 'format_id': 'fmt/101', 'file_type': 'XML',
                'version': '1.0', 'count': '12', 'raf': 'Ikke gyldig',
                'evidence_source': 'import-a', 'imported_at': '2026-10-20T12:00:00+00:00',
                'original_csv': 'filformatinfo-statistikk.csv',
                'original_csv_sha256': '1' * 64,
            }, {
                'job': 'Test', 'format_id': 'fmt/999999', 'count': 3,
                'raf': 'Gyldig', 'evidence_source': 'import-a',
            }]
            export_comparison_csv(output, rows, policy)
            with output.open('r', encoding='utf-8-sig', newline='') as handle:
                data = list(csv.DictReader(handle, delimiter=';'))
            self.assertEqual(data[0]['Arkade RAF (historisk observasjon)'], 'Ikke gyldig')
            self.assertEqual(data[0]['Vurdering'], 'Akseptert i valgt profil')
            self.assertEqual(data[0]['Arkade importert (ikke testdato)'], '2026-10-20T12:00:00+00:00')
            self.assertEqual(data[0]['Profil kopidato (ikke ikrafttredelsesdato)'],
                             policy.captured_at)
            self.assertEqual(data[0]['PRONOM kilde SHA-256'], '1' * 64)
            self.assertEqual(data[0]['Profil SHA-256'], policy.sha256)
            self.assertEqual(data[0]['Kilde URL'], policy.source_url)
            self.assertEqual(data[1]['Arkade RAF (historisk observasjon)'], 'Gyldig')
            self.assertEqual(data[1]['Vurdering'], 'Til avklaring')
            with self.assertRaises(FileExistsError):
                export_comparison_csv(output, rows, policy)

    def test_empty_policy_keeps_raf_but_no_approval(self):
        with tempfile.TemporaryDirectory() as temp:
            dest = Path(temp) / 'no-policy.csv'
            export_comparison_csv(dest, [{
                'format_id': 'fmt/101', 'raf': 'Gyldig', 'count': 2,
            }], None)
            with dest.open(encoding='utf-8-sig', newline='') as handle:
                record = next(csv.DictReader(handle, delimiter=';'))
            self.assertEqual(record['Vurdering'], 'Ikke vurdert')
            self.assertEqual(record['Arkade RAF (historisk observasjon)'], 'Gyldig')
            self.assertEqual(record['Profil SHA-256'], '')

    def test_strict_manifest_link_is_required_for_import_date(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / 'external_evidence' / 'arkade5' / 'import-a'
            normalized = root / 'normalized' / 'pronom_statistics.json'
            normalized.parent.mkdir(parents=True)
            normalized.write_text('{}', encoding='utf-8')
            manifest = root / 'manifest.json'
            manifest.write_text(json.dumps({
                'import_id': 'import-a', 'imported_at': '2026-11-10T09:00:00Z',
                'pronom_evidence': {'statistics': {
                    'original_name': 'filformatinfo-statistikk.csv',
                    'sha256': '1' * 64,
                }},
            }), encoding='utf-8')
            result = read_pronom_import_context(normalized, 'import-a')
            self.assertEqual(result['imported_at'], '2026-11-10T09:00:00Z')
            self.assertEqual(result['original_csv'], 'filformatinfo-statistikk.csv')
            self.assertEqual(result['original_csv_sha256'], '1' * 64)
            self.assertEqual(read_pronom_import_context(normalized, 'another')['imported_at'], '')
            self.assertEqual(read_pronom_import_context(root / 'manifest.json', 'import-a')['imported_at'], '')
            manifest.write_text('{ invalid json', encoding='utf-8')
            self.assertEqual(read_pronom_import_context(normalized, 'import-a')['imported_at'], '')

    def test_source_context_disambiguates_dates(self):
        a, b = comparison_labels(self.policy, ['2026-11-10T00:00:00Z'])
        self.assertIn('Importtid: 2026-11-10', a)
        self.assertIn('ikke testdato', a)
        self.assertIn('Datert kopi: 2026-11-10', b)
        self.assertIn('ikke ikrafttredelsesdato', b)
        _, none = comparison_labels(None, [])
        self.assertIn('Ingen', none)


if __name__ == '__main__':
    unittest.main()
