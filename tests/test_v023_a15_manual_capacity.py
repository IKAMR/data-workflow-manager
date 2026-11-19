"""A15: large manual KS ledgers, exact Work binding, PRONOM and index provenance.

All files live in isolated temporary Work directories; original Source and
technical Noark/Arkade outcomes are neither read from production nor changed.
"""
from __future__ import annotations

from hashlib import sha256
import importlib.util
import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from uuid import uuid4

from noark5_workflow.reporting.qa_review_v021_a13 import ReviewError
from noark5_workflow.reporting.qa_workflow_v022_a3 import (
    MANUAL_DIR, MANUAL_MODEL, MAX_MANUAL, _canonical, _iter_manual_events,
    _read_manual, _verified_raf_candidates, manual_findings,
    manual_ledger_state, record_manual_finding,
)
from noark5_workflow.reporting.qa_paged_review_v023_a12 import (
    PagedReviewError, build_paged_index, load_review_events, review_page,
)

ROOT = Path(__file__).resolve().parents[1]


def _signed_manual(folder: Path, *, uid: str, digest: str, number: int,
                   older=False, recorded_ns=None) -> Path:
    event_id = str(uuid4())
    doc = {
        'model_id': MANUAL_MODEL,
        'event_id': event_id,
        'created_utc': '2026-11-20T00:00:00+00:00',
        'recorded_ns': number if recorded_ns is None else recorded_ns,
        'job_uid': uid,
        'depot_report_sha256': ('a' * 64) if older else digest,
        'severity': 'REVIEW',
        'message': 'Manuelt kontrollpunkt nr. ' + str(number),
        'context': 'En faglig observasjon',
        'file': '',
        'author': {'user_id': 'qa-user', 'display_name': 'QA'},
        'origin': 'human_observation_not_machine_validation',
    }
    doc['event_sha256'] = sha256(_canonical(doc)).hexdigest()
    path = folder / (event_id + '.json')
    path.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return path


class A15ManualCapacity(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.work = Path(tmp.name) / 'Work'
        self.work.mkdir()
        self.uid = 'A15-JOB-001'
        self.report_rel = 'noark5_reports/depot_validation/JOB-001__RUN-01/depot_validation_report.json'
        self.report = self.work / self.report_rel
        self.report.parent.mkdir(parents=True)
        self.report.write_text('{"report_type":"noark5_depot_validation"}', encoding='utf-8')
        self.digest = sha256(self.report.read_bytes()).hexdigest()
        (self.work / 'job.json').write_text(json.dumps({
            'file_type': 'dwm-work-job', 'job_uid': self.uid,
            'job': {'job_id': 'JOB-001'},
        }), encoding='utf-8')
        self.snapshot = {
            'model_id': 'ikamr.dwm.noark5.qa-decision.a12.v1',
            'work_identity': {'job_uid': self.uid},
            'evidence_manifest': [{'kind': 'dwm_depot',
                                   'path': self.report_rel,
                                   'sha256': self.digest}],
            'findings': [],
        }
        self.folder = self.work / MANUAL_DIR
        self.folder.mkdir(parents=True)
        self.actor = SimpleNamespace(user_id='qa-user', as_dict=lambda: {
            'user_id': 'qa-user', 'display_name': 'KS reviewer',
        })

    def write_manual(self, count, *, older=False):
        return [_signed_manual(self.folder, uid=self.uid, digest=self.digest,
                               number=i + 1, older=older) for i in range(count)]

    def test_no_2000_limit_for_existing_and_new_manually_recorded_findings(self):
        self.assertIsNone(MAX_MANUAL)
        self.write_manual(2201)
        before = {p.name: sha256(p.read_bytes()).hexdigest() for p in self.folder.iterdir()}
        new = record_manual_finding(self.work, self.snapshot,
                                    severity='WARNING', message='Ny kontroll etter 2201',
                                    user=self.actor)
        records = manual_findings(self.work, self.snapshot)
        self.assertEqual(len(records), 2202)
        self.assertEqual(len({r['manual_event_id'] for r in records}), 2202)
        self.assertEqual(records[-1]['manual_event_id'], new['event_id'])
        self.assertEqual(records[-1]['severity'], 'WARNING')
        self.assertEqual({p.name: sha256(p.read_bytes()).hexdigest()
                          for p in self.folder.iterdir() if p.name in before}, before)
        self.assertEqual(self.report.read_text(), '{"report_type":"noark5_depot_validation"}')

    def test_streaming_iterator_reads_3000_without_materializing_file_list(self):
        self.write_manual(3001)
        result = _iter_manual_events(self.work)
        self.assertFalse(isinstance(result, (list, tuple)))
        self.assertEqual(sum(1 for _ in result), 3001)

    def test_legacy_reader_preserves_timestamp_order(self):
        for index in (90, 10, 70, 50):
            _signed_manual(self.folder, uid=self.uid, digest=self.digest,
                           number=index, recorded_ns=index)
        self.assertEqual([e['recorded_ns'] for e in _read_manual(self.work)],
                         [10, 50, 70, 90])

    def test_old_report_and_different_job_do_not_leak_into_current_snapshot(self):
        self.write_manual(2)
        self.write_manual(3, older=True)
        _signed_manual(self.folder, uid='OTHER-JOB', digest=self.digest, number=20)
        self.assertEqual(len(manual_findings(self.work, self.snapshot)), 2)
        state = manual_ledger_state(self.work, job_uid=self.uid, depot_sha256=self.digest)
        self.assertEqual((state['count'], state['current_count']), (6, 2))
        self.assertEqual(len(state['sha256']), 64)
        self.assertEqual(len(state['current_ids_sha256']), 64)

    def test_manual_ledger_tracks_same_signed_event_after_json_reformatting(self):
        path = self.write_manual(1)[0]
        previous = manual_ledger_state(self.work, job_uid=self.uid, depot_sha256=self.digest)
        doc = json.loads(path.read_text(encoding='utf-8'))
        path.write_text(json.dumps(doc, ensure_ascii=False, sort_keys=True) + '\n', encoding='utf-8')
        current = manual_ledger_state(self.work, job_uid=self.uid, depot_sha256=self.digest)
        self.assertEqual(current['current_ids_sha256'], previous['current_ids_sha256'])
        self.assertNotEqual(current['sha256'], previous['sha256'])

    def test_changed_event_blocks_complete_ledger(self):
        path = self.write_manual(4)[0]
        doc = json.loads(path.read_text(encoding='utf-8'))
        doc['message'] = 'Tuklet uten å oppdatere checksum'
        path.write_text(json.dumps(doc), encoding='utf-8')
        with self.assertRaises(ReviewError):
            list(_iter_manual_events(self.work))
        with self.assertRaises(ReviewError):
            manual_findings(self.work, self.snapshot)

    def test_a260_fallback_includes_all_manually_registered_findings(self):
        from noark5_workflow.reporting.qa_a260_v023_a6 import _manual_and_depot_findings
        self.write_manual(2110)
        records = list(_manual_and_depot_findings(
            self.work, {'job_uid': self.uid}, self.report,
            self.report_rel, {'deviations': [], 'technical_validation': {'tests': []}},
        ))
        self.assertEqual(len(records), 2110)
        self.assertTrue(all(row['source'] == 'Manuell observasjon (DWM)' for row in records))

    def test_unknown_file_fails_closed(self):
        self.write_manual(2)
        (self.folder / 'notes.txt').write_text('not an event', encoding='utf-8')
        with self.assertRaisesRegex(ReviewError, 'Ukjent fil'):
            manual_findings(self.work, self.snapshot)

    @unittest.skipIf(os.name == 'nt', 'Windows symlink creation may require permissions')
    def test_symlink_in_manual_ledger_is_rejected(self):
        self.write_manual(1)
        (self.folder / 'linked.json').symlink_to(next(self.folder.iterdir()))
        with self.assertRaisesRegex(ReviewError, 'Ukjent fil'):
            manual_ledger_state(self.work, job_uid=self.uid, depot_sha256=self.digest)

    def test_oversized_event_is_rejected_even_above_two_thousand(self):
        path = self.write_manual(1)[0]
        path.write_bytes(b'x' * 14001)
        with self.assertRaisesRegex(ReviewError, 'størrelsesgrensen'):
            manual_findings(self.work, self.snapshot)

    def test_pronom_2601_rows_are_not_refused_by_old_count_limit(self):
        rel = 'external_evidence/arkade5/IMP/normalized/pronom_statistics.json'
        path = self.work / rel
        path.parent.mkdir(parents=True)
        rows = [{'RAF-220301': 'Gyldig', 'Format-ID': f'fmt/{i}', 'Antall': '1'}
                for i in range(2601)]
        rows[-1].update({'RAF-220301': 'Ikke gyldig', 'Format-ID': 'fmt/2600'})
        path.write_text(json.dumps({
            'evidence_type': 'arkade5_pronom_format_statistics',
            'csv': {'rows': rows}, 'source': {'original_name': 'pronom.csv'},
        }), encoding='utf-8')
        self.snapshot['arkade'] = {
            'source': 'external_evidence/arkade5/IMP/normalized/arkade5_results.json',
        }
        self.snapshot['evidence_manifest'].append({
            'kind': 'external', 'path': rel,
            'sha256': sha256(path.read_bytes()).hexdigest(),
        })
        hits = _verified_raf_candidates(self.work, self.snapshot)
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0]['test_id'], 'RAF-220301:fmt/2600')
        self.assertEqual(hits[0]['severity'], 'REVIEW')
        self.assertFalse(hits[0].get('automatic_approval', False))

    def test_invalid_pronom_rows_still_fail(self):
        rel = 'external_evidence/arkade5/IMP/normalized/pronom_statistics.json'
        path = self.work / rel
        path.parent.mkdir(parents=True)
        path.write_text(json.dumps({'evidence_type':'arkade5_pronom_format_statistics',
                                    'csv': {'rows': 'not a list'}}), encoding='utf-8')
        self.snapshot['arkade'] = {'source': 'external_evidence/arkade5/IMP/normalized/arkade5_results.json'}
        self.snapshot['evidence_manifest'].append({'kind':'external', 'path':rel,
                          'sha256':sha256(path.read_bytes()).hexdigest()})
        with self.assertRaises(ReviewError):
            _verified_raf_candidates(self.work, self.snapshot)

    def test_version_and_distribution_metadata_match(self):
        import re
        from version import VERSION
        match = re.fullmatch(r'0\.2\.3-a([0-9]+)', VERSION)
        self.assertIsNotNone(match)
        self.assertGreaterEqual(int(match.group(1)), 15)
        metadata = (ROOT/'pyproject.toml').read_text(encoding='utf-8')
        self.assertRegex(metadata, r'(?m)^version\s*=\s*"' +
                         re.escape(VERSION.replace('-a', 'a')) + r'"\s*$')


class A15IndexedManualEvidence(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixture_path = ROOT / 'tests/test_v023_a12_paged_review.py'
        spec = importlib.util.spec_from_file_location('_a15_test_fixture_a12', fixture_path)
        cls.fixture_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.fixture_module)

    def setUp(self):
        self.fixture = self.fixture_module.PagedReviewTests(
            methodName='test_all_DWM_and_arkade_findings_are_present_beyond_preview')
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.work = self.fixture.work
        self.snapshot = self.fixture.create(0, 0)
        self.folder = self.work / MANUAL_DIR
        self.folder.mkdir(parents=True)
        self.report_sha = self.snapshot['evidence_manifest'][0]['sha256']

    def populate(self, n):
        for i in range(n):
            _signed_manual(self.folder, uid=self.fixture.uid, digest=self.report_sha,
                           number=i + 1)
        found = manual_findings(self.work, self.snapshot)
        self.snapshot['findings'] += found
        self.snapshot['full_finding_count'] += len(found)
        return found

    def test_index_counts_and_filters_all_manual_occurrences(self):
        self.populate(13)
        info = build_paged_index(self.work, self.snapshot)
        self.assertEqual(info['finding_count'], 14)
        self.assertEqual(info['manual_ledger']['current_count'], 13)
        page = review_page(self.work, info, source='Manuell observasjon (DWM)')
        self.assertEqual(page['total'], 13)
        self.assertEqual(len({row['finding_key'] for row in page['rows']}), 13)
        self.assertEqual(info['source_counts']['Manuell observasjon (DWM)'], 13)

    def test_cached_index_reused_when_manual_files_are_identical(self):
        self.populate(3)
        first = build_paged_index(self.work, self.snapshot)
        second = build_paged_index(self.work, self.snapshot)
        self.assertEqual(first['index_sha256'], second['index_sha256'])
        self.assertEqual(first['index_relative_path'], second['index_relative_path'])

    def test_forged_same_content_bytes_are_detected_before_review_loading(self):
        found = self.populate(3)
        info = build_paged_index(self.work, self.snapshot)
        path = self.folder / (found[0]['manual_event_id'] + '.json')
        doc = json.loads(path.read_text(encoding='utf-8'))
        path.write_text(json.dumps(doc, sort_keys=True, ensure_ascii=False) + '\n', encoding='utf-8')
        with self.assertRaisesRegex(PagedReviewError, 'Manuell evidens'):
            load_review_events(self.work, info)

    def test_recorded_manual_after_snapshot_is_not_silently_omitted(self):
        info = build_paged_index(self.work, self.snapshot)
        _signed_manual(self.folder, uid=self.fixture.uid, digest=self.report_sha, number=1)
        with self.assertRaisesRegex(PagedReviewError, 'Manuelle funn'):
            build_paged_index(self.work, self.snapshot)
        with self.assertRaisesRegex(PagedReviewError, 'Manuell evidens'):
            load_review_events(self.work, info)

    def test_older_or_other_job_manual_record_is_not_treated_as_current(self):
        self.populate(2)
        info = build_paged_index(self.work, self.snapshot)
        _signed_manual(self.folder, uid=self.fixture.uid, digest=self.report_sha,
                       number=3, older=True)
        with self.assertRaisesRegex(PagedReviewError, 'Manuell evidens'):
            load_review_events(self.work, info)
        fresh = build_paged_index(self.work, self.snapshot)
        self.assertEqual(fresh['finding_count'], 3)
        self.assertNotEqual(info['index_relative_path'], fresh['index_relative_path'])

    def test_complete_ks_and_depot_report_includes_more_than_2000_manual_findings(self):
        from noark5_workflow.reporting.qa_complete_report_v023_a13 import export_complete_reports
        self.populate(2107)
        info = build_paged_index(self.work, self.snapshot)
        directory = self.fixture.root / 'a15-output'
        directory.mkdir()
        target = directory / 'REPORT'
        result = export_complete_reports(self.work, self.snapshot, info, target,
                                         page_rows=300)
        self.assertEqual(result['finding_count'], 2108)
        for scope in ('ks', 'depot'):
            path = target / (scope + '-funn.jsonl')
            rows = [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines()]
            self.assertEqual(len(rows), 2108)
            self.assertEqual(sum(row['source'] == 'Manuell observasjon (DWM)'
                                 for row in rows), 2107)
        self.assertFalse(json.loads((target / 'evidensmanifest.json').read_text(encoding='utf-8'))['automatic_approval'])

    def test_deleted_manual_before_index_creation_is_rejected(self):
        found = self.populate(2)
        (self.folder / (found[0]['manual_event_id'] + '.json')).unlink()
        with self.assertRaisesRegex(PagedReviewError, 'Manuelle funn'):
            build_paged_index(self.work, self.snapshot)


if __name__ == '__main__':
    unittest.main()
