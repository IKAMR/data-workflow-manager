"""a5.3: source-aware Arkade fallback, DWM names and safe generic rendering."""
from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest

from app.result_display_v0110_a5 import (
    arkade_tests_from_depot, default_table_fraction, load_technical_test_names,
    read_work_markdown, readable_html, technical_test_name,
)


def fixture_shot(imports):
    return SimpleNamespace(
        job=SimpleNamespace(name='1547_007 Forum Winsak'),
        depot={'external_validation': {'arkade5': {'imports': imports}}},
        results=SimpleNamespace(depot_report_path=Path('/work/saved-depot-report.json')),
    )


class ArkadeFallbackTests(unittest.TestCase):
    def test_preserves_both_imports_and_only_actual_tests(self):
        def area(test_id, *, present=True, status='ok', errors=0):
            return {
                'arkade_test_id': test_id,
                'arkade_test_name': f'Navn {test_id}',
                'relation': 'partial',
                'arkade': {'present': present, 'status': status,
                           'number_of_errors': errors},
            }
        imports = [
            {'import_id': 'import-1', 'source_version': '2.13.0',
             'date_of_testing': '2026-01-08', 'source_sha256': 'aaa',
             'coverage': {'arkade_control_areas': [
                 area('N5.01', status='error', errors=2),
                 area('N5.02', present=False, status='not_present'),
             ]}},
            {'import_id': 'import-2', 'source_version': '2.13.1',
             'date_of_testing': '2026-10-18', 'source_sha256': 'bbb',
             'coverage': {'arkade_control_areas': [area('N5.01', errors=0)]}},
        ]
        rows = arkade_tests_from_depot([fixture_shot(imports)])
        self.assertEqual(len(rows), 2)
        self.assertEqual([r['import_id'] for r in rows], ['import-1', 'import-2'])
        self.assertEqual([r['status'] for r in rows], ['error', 'ok'])
        self.assertEqual([r['errors'] for r in rows], [2, 0])
        self.assertEqual(rows[0]['title'], 'Navn N5.01')
        self.assertEqual(rows[0]['details']['testdato'], '2026-01-08')
        self.assertEqual(rows[0]['details']['kilde_sha256'], 'aaa')
        self.assertEqual(rows[0]['file'], Path('/work/saved-depot-report.json'))
        self.assertNotIn('N5.02', [r['test_id'] for r in rows])

    def test_import_without_per_test_proof_does_not_manufacture_tests(self):
        rows = arkade_tests_from_depot([fixture_shot([
            {'import_id': 'has-a-report', 'coverage': {'arkade_control_areas': [
                {'arkade_test_id': 'N5.01', 'arkade': {'present': False}}]}},
            {'import_id': 'missing-coverage'},
        ])])
        self.assertEqual(rows, ())

    def test_invalid_shapes_do_not_crash_or_infer_status(self):
        self.assertEqual(arkade_tests_from_depot([fixture_shot([
            {'import_id': 'A', 'coverage': {'arkade_control_areas': 'not a list'}}
        ])]), ())


class TechnicalNamesTests(unittest.TestCase):
    def test_catalog_is_authoritative_for_both_ids(self):
        with tempfile.TemporaryDirectory() as tmp:
            catalog = Path(tmp) / 'catalog.json'
            catalog.write_text(json.dumps({'tests': [
                {'test_id': 'kdrs.c06', 'legacy': {'job_id': 'C06'}, 'name': 'Klasser'},
                {'test_id': 'kdrs.c01', 'legacy': {'job_id': 'C01'},
                 'name': 'Arkiv i arkivstrukturen'},
            ]}), encoding='utf-8')
            names = load_technical_test_names(catalog)
            self.assertEqual(technical_test_name({'test_id': 'kdrs.c06'}, 'C06', names=names), 'Klasser')
            self.assertEqual(technical_test_name({}, 'c01', names=names), 'Arkiv i arkivstrukturen')
            self.assertEqual(technical_test_name({'test_id': 'unknown'}, 'other', names=names),
                             'Navn ikke registrert i testkatalogen')
            self.assertEqual(technical_test_name({'test_point': 'N5.08'}, 'unknown', names=names),
                             'Navn ikke registrert i testkatalogen')


class ReadableAndAdaptiveTests(unittest.TestCase):
    def test_html_escapes_untrusted_values_and_limits_depth(self):
        html = readable_html({'<script>': ['<img src="file:///private">', {'ok': 1}]})
        self.assertIn('&lt;script&gt;', html)
        self.assertIn('&lt;img', html)
        self.assertNotIn('<script>', html)
        self.assertNotIn('<img src=', html)
        limited = readable_html({'many': [1] * 1500}, max_nodes=8)
        self.assertIn('Avkortet', limited)
        self.assertIn('Råtekst / JSON', limited)

    def test_markdown_read_only_inside_work_and_bounded(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            work = root / 'Work'
            work.mkdir()
            md = work / 'rapport.md'
            md.write_text('# Rapport\n\n**Kilde**', encoding='utf-8')
            outsider = root / 'untrusted.md'
            outsider.write_text('hemmelig', encoding='utf-8')
            self.assertEqual(read_work_markdown(md, [work]), '# Rapport\n\n**Kilde**')
            self.assertIsNone(read_work_markdown(outsider, [work]))
            self.assertIsNone(read_work_markdown(md, [work], max_bytes=2))
            self.assertIsNone(read_work_markdown(work / 'missing.md', [work]))
            link = work / 'shortcut.md'
            try:
                link.symlink_to(outsider)
            except (OSError, NotImplementedError):
                pass
            else:
                self.assertIsNone(read_work_markdown(link, [work]))

    def test_auto_split_by_number_of_real_rows(self):
        self.assertEqual(default_table_fraction(1), 0.22)
        self.assertEqual(default_table_fraction(25, tab='Arkivdeler'), 0.55)
        self.assertEqual(default_table_fraction(27, tab='PRONOM'), 0.65)
        self.assertEqual(default_table_fraction(54, tab='Tekniske kontroller'), 0.68)
