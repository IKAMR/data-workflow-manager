"""a18-fix8: read-only import inventory for selected/all Noark 5 jobs."""
from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest

from noark5_workflow.external_evidence.batch_status_a18 import (
    inspect_job, inspect_jobs, _referenced_path,
)


def _dump(path: Path, value: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False), encoding='utf-8')


def _job(root: Path, job_id='JOB-002'):
    return SimpleNamespace(job_id=job_id, name='1502_024', work_operations=root)


def _imports(work: Path):
    kd = 'kdrs-123'
    kdrs = {
        'import_id': kd, 'imported_at': '2026-10-14T14:00:00',
        'report_types': ['standard', 'u01', 'u02'],
        'files': [{'report_type': t, 'original_name': t + '.txt',
                   'normalized_file': f'external_evidence/kdrs_query/{kd}/normalized/{t}.json'}
                  for t in ('standard', 'u01', 'u02')],
    }
    _dump(work / 'external_evidence' / 'kdrs_query' / kd / 'manifest.json', kdrs)
    for t in ('standard', 'u01', 'u02'):
        _dump(work / f'external_evidence/kdrs_query/{kd}/normalized/{t}.json', {'report_type': t})
    aid = '20261014-abc'
    arkade = {
        'import_id': aid, 'imported_at': '2026-10-14',
        'normalized_file': f'external_evidence\\arkade5\\{aid}\\normalized\\arkade5_results.json',
        'source': {'original_name': 'a5.json', 'sha256': 'a' * 64},
        'pronom_evidence': {'statistics': {'imported': True,
            'normalized_file': f'external_evidence\\arkade5\\{aid}\\normalized\\pronom_statistics.json'}},
    }
    _dump(work / 'external_evidence' / 'arkade5' / aid / 'manifest.json', arkade)
    _dump(work / 'external_evidence' / 'arkade5' / aid / 'normalized' / 'arkade5_results.json', {'tests': []})
    _dump(work / 'external_evidence' / 'arkade5' / aid / 'normalized' / 'pronom_statistics.json',
          {'csv': {'rows': [
              {'Format-ID':'fmt/40', 'Filtype':'PDF','Formatversjon':'1.4','RAF-220301':'', 'Antall':'12'},
              {'Format-ID':'unknown', 'Filtype':'ukjent','Formatversjon':'','RAF-220301':'', 'Antall':'2'},
          ]}})
    return aid


class TestA18Fix8EvidenceStatus(unittest.TestCase):
    def test_no_work_directory_is_explicitly_unknown(self):
        row = inspect_job(SimpleNamespace(job_id='JOB-001', name='Uttrekk', work_operations=None))
        self.assertEqual(row['kdrs']['count'], 0)
        self.assertEqual(row['arkade']['count'], 0)
        self.assertEqual(row['pronom']['count'], 0)
        self.assertTrue(row['issues'])

    def test_kdrs_arkade_pronom_and_report_all_visible(self):
        with TemporaryDirectory() as tmp:
            work = Path(tmp) / 'repository_operations' / 'dwm'
            _imports(work)
            _dump(work / 'noark5_reports/depot_validation/JOB-002__RUN-1/depot_validation_report.json', {'summary':{}})
            row = inspect_job(_job(work))
            self.assertEqual(row['kdrs']['count'], 1)
            self.assertEqual(row['kdrs']['types'], ['Standard', 'U1', 'U2'])
            self.assertEqual(row['arkade']['count'], 1)
            self.assertEqual(row['pronom']['count'], 1)
            self.assertEqual(row['pronom']['files'], 14)
            self.assertEqual(row['pronom']['unidentified'], 2)
            self.assertTrue(row['depot_report'])
            self.assertFalse(row['issues'], row['issues'])

    def test_missing_normalized_results_are_not_a_successful_import(self):
        with TemporaryDirectory() as tmp:
            work = Path(tmp) / 'dwm'
            _imports(work)
            p = work / 'external_evidence/arkade5/20261014-abc/normalized/pronom_statistics.json'
            p.unlink()
            q = work / 'external_evidence/kdrs_query/kdrs-123/normalized/u02.json'
            q.unlink()
            row = inspect_job(_job(work))
            self.assertEqual(row['pronom']['count'], 0)
            self.assertEqual(row['kdrs']['count'], 1)  # recorded, but flagged as incomplete
            self.assertTrue(any('PRONOM' in x for x in row['issues']))
            self.assertTrue(any('KDRS' in x for x in row['issues']))

    def test_invalid_manifest_is_reported_not_silently_ignored(self):
        with TemporaryDirectory() as tmp:
            work = Path(tmp) / 'dwm'
            bad = work / 'external_evidence/kdrs_query/kdrs-broken/manifest.json'
            bad.parent.mkdir(parents=True)
            bad.write_text('{invalid', encoding='utf-8')
            row = inspect_job(_job(work))
            self.assertEqual(row['kdrs']['count'], 0)
            self.assertTrue(any('manifest' in x for x in row['issues']))

    def test_jobs_are_kept_separate(self):
        with TemporaryDirectory() as tmp:
            first, second = Path(tmp) / 'a' / 'dwm', Path(tmp) / 'b' / 'dwm'
            _imports(first)
            summary = inspect_jobs((_job(first, 'JOB-001'), _job(second, 'JOB-002')))
            self.assertEqual(summary['count'], 2)
            self.assertEqual(summary['with_kdrs'], 1)
            self.assertEqual(summary['with_arkade'], 1)
            self.assertEqual(summary['with_pronom'], 1)
            self.assertEqual(summary['jobs'][1]['kdrs']['count'], 0)

    def test_effective_work_directory_is_prioritized(self):
        with TemporaryDirectory() as tmp:
            current, old = Path(tmp) / 'dwm', Path(tmp) / 'other' / 'dwm'
            _imports(current)
            job = _job(old)
            job._effective_work_operations = current
            row = inspect_job(job)
            self.assertEqual(row['work'], str(current))
            self.assertEqual(row['kdrs']['count'], 1)

    def test_missing_preserved_pronom_source_is_reported(self):
        with TemporaryDirectory() as tmp:
            work = Path(tmp) / 'dwm'
            aid = _imports(work)
            manifest_path = work / 'external_evidence/arkade5' / aid / 'manifest.json'
            manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
            manifest['pronom_evidence']['statistics']['preserved_file'] = 'external_evidence/missing.csv'
            _dump(manifest_path, manifest)
            row = inspect_job(_job(work))
            self.assertEqual(row['pronom']['count'], 1)
            self.assertTrue(any('PRONOM bevart originalfil' in x for x in row['issues']))

    def test_broken_pronom_json_marks_issue_without_crash(self):
        with TemporaryDirectory() as tmp:
            work = Path(tmp) / 'dwm'
            _imports(work)
            p = work / 'external_evidence/arkade5/20261014-abc/normalized/pronom_statistics.json'
            p.write_text('{not JSON', encoding='utf-8')
            row = inspect_job(_job(work))
            self.assertEqual(row['pronom']['count'], 0)
            self.assertTrue(any('PRONOM' in x for x in row['issues']))

    def test_rejects_parent_traversal_and_absolute_references(self):
        root = Path('/tmp/dwm')
        self.assertIsNone(_referenced_path(root, '../other/secret.json'))
        self.assertIsNone(_referenced_path(root, '/other/secret.json'))
        self.assertIsNone(_referenced_path(root, r'\other\secret.json'))
        self.assertIsNone(_referenced_path(root, r'C:\other\secret.json'))
        self.assertIsNone(_referenced_path(root, r'C:other\secret.json'))
        self.assertIsNone(_referenced_path(root, r'\\server\share\secret.json'))
        self.assertIsNone(_referenced_path(root, 'external_evidence/../secret.json'))
        self.assertEqual(_referenced_path(root, 'external_evidence\\a.json'), root/'external_evidence/a.json')

    def test_gui_action_keeps_kdrs_import_separate(self):
        source = (Path(__file__).resolve().parents[1] / 'gui/jobs_window_v017_a2.py').read_text(encoding='utf-8')
        self.assertIn("text='Evidensstatus'", source)
        self.assertIn('selected if selected else tuple(self.batch.jobs())', source)
        self.assertIn('open_evidence_status_dialog(self, chosen', source)
        self.assertNotIn('import_kdrs_query_reports', source)

    def test_import_inventory_does_not_start_analysis(self):
        source = (Path(__file__).resolve().parents[1] / 'noark5_workflow/external_evidence/batch_status_a18.py').read_text(encoding='utf-8')
        self.assertNotIn('write_external_result_bank(', source)
        self.assertNotIn('run_arkade5_cli', source)
        self.assertNotIn('run_xpath', source)


if __name__ == '__main__':
    unittest.main()
