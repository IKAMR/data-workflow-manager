"""a5: multiple bounded Siegfried processes with ordered, resumable evidence.

All tests use a small in-memory fake `sf` boundary; no Windows sf.exe needed.
The stream implementation is exercised with real temporary Work/Source folders.
"""
from __future__ import annotations

from pathlib import Path
import hashlib
import json
import os
import threading
import time
import tempfile
import unittest
from unittest.mock import patch

from noark5_workflow.operations import siegfried_stream_v022_a4 as stream


class ParallelSiegfriedTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.source = self.root / 'source'
        self.docs = self.source / 'DOKUMENT'
        self.docs.mkdir(parents=True)
        self.work = self.root / 'work'
        self.work.mkdir()
        self.sf = self.root / ('sf.exe' if os.name == 'nt' else 'sf')
        self.sf.write_bytes(b'fake')

    def make_files(self, n):
        for i in range(n):
            (self.docs / f'file-{i:04d}.pdf').write_bytes(b'PDF')

    @staticmethod
    def rows(paths):
        return [{'filename': path, 'matches': [{'id': 'fmt/354', 'format': 'PDF/A',
                                                 'version': '1b'}]} for path in paths]

    def scan(self, *, workers=2, cancelled_cb=None, progress_cb=None, log_cb=None):
        return stream.scan_document_tree(
            source=self.source, work=self.work, executable=str(self.sf),
            version='siegfried 1.11', signature='PRONOM 123',
            job_id='JOB-001', job_uid='uid-A', workers=workers,
            cancelled_cb=cancelled_cb, progress_cb=progress_cb, log_cb=log_cb,
        )

    def partials(self):
        path = self.work / 'external_evidence' / 'siegfried'
        return sorted(path.glob('.partial-*')) if path.exists() else []

    def test_two_processes_run_concurrently_without_reordering_work_evidence(self):
        self.make_files(205)
        active = 0
        highest = 0
        completion_order = []
        gate = threading.Barrier(2, timeout=5)
        lock = threading.Lock()

        def sf(_exe, paths, *, cancelled_cb=None):
            nonlocal active, highest
            first = Path(paths[0]).name
            with lock:
                active += 1
                highest = max(highest, active)
            if first in ('file-0000.pdf', 'file-0100.pdf'):
                gate.wait()
            # Deliberately finish the second batch first.
            time.sleep(.08 if first == 'file-0000.pdf' else .003)
            with lock:
                completion_order.append(first)
                active -= 1
            return self.rows(paths)

        events = []
        with patch.object(stream, '_run_sf_batch', side_effect=sf):
            result = self.scan(progress_cb=lambda n, total: events.append(n))

        self.assertEqual(highest, 2)
        self.assertEqual(completion_order[:2], ['file-0100.pdf', 'file-0000.pdf'])
        self.assertEqual(events, [0, 100, 200, 205])
        raw = result['target'] / 'siegfried_files.jsonl'
        saved = [json.loads(line)['filename'] for line in raw.read_text(encoding='utf-8').splitlines()]
        self.assertEqual(saved, sorted(saved))
        self.assertEqual(len(saved), 205)
        self.assertEqual(result['model']['identified'], 205)
        model = json.loads((result['target'] / 'pronom_statistics.json').read_text('utf-8'))
        self.assertEqual(model['format_groups'][0]['count'], 205)
        manifest = json.loads((result['target'] / 'manifest.json').read_text('utf-8'))
        self.assertEqual(manifest['raw_sha256'], hashlib.sha256(raw.read_bytes()).hexdigest())
        self.assertEqual(manifest['siegfried_process_workers'], 2)
        self.assertEqual(self.partials(), [])

    def test_never_more_than_selected_workers_are_in_flight(self):
        self.make_files(505)
        lock = threading.Lock()
        active = maximum = 0
        def sf(_exe, paths, *, cancelled_cb=None):
            nonlocal active, maximum
            with lock:
                active += 1
                maximum = max(maximum, active)
            time.sleep(.018)
            with lock:
                active -= 1
            return self.rows(paths)
        with patch.object(stream, '_run_sf_batch', side_effect=sf):
            result = self.scan(workers=3)
        self.assertEqual(maximum, 3)
        self.assertEqual(result['model']['files_total'], 505)
        self.assertEqual(len(result['model']['format_groups']), 1)

    def test_out_of_order_siegfried_rows_are_normalized_for_resume(self):
        self.make_files(105)
        def sf(_exe, paths, *, cancelled_cb=None):
            return list(reversed(self.rows(paths)))
        with patch.object(stream, '_run_sf_batch', side_effect=sf):
            result = self.scan(workers=2)
        raw = result['target'] / 'siegfried_files.jsonl'
        filenames = [json.loads(line)['filename'] for line in raw.read_text('utf-8').splitlines()]
        self.assertEqual(filenames, sorted(filenames))
        self.assertEqual(len(filenames),105)

    def test_error_in_second_concurrent_batch_keeps_committed_prefix(self):
        self.make_files(205)
        failed = [True]
        seen = []
        lock = threading.Lock()

        def sf(_exe, paths, *, cancelled_cb=None):
            first = Path(paths[0]).name
            with lock:
                seen.append(first)
            if first == 'file-0100.pdf' and failed[0]:
                raise RuntimeError('batch 2 failed')
            return self.rows(paths)

        with patch.object(stream, '_run_sf_batch', side_effect=sf):
            with self.assertRaisesRegex(RuntimeError, 'batch 2 failed'):
                self.scan()
            self.assertEqual(len(self.partials()), 1)
            stage = self.partials()[0]
            checkpoint = json.loads((stage / 'checkpoint.json').read_text('utf-8'))
            self.assertEqual(checkpoint['files_processed'], 100)
            self.assertEqual(len((stage / 'siegfried_files.jsonl').read_text('utf-8').splitlines()), 100)
            failed[0] = False
            completed = self.scan(workers=3)
        self.assertTrue(completed['resumed'])
        self.assertEqual(completed['files_total'], 205)
        self.assertEqual(seen.count('file-0000.pdf'), 1)
        self.assertEqual(self.partials(), [])

    def test_cancel_interrupts_outstanding_workers_and_can_resume(self):
        self.make_files(205)
        cancelled = threading.Event()
        stopped = []

        def sf(_exe, paths, *, cancelled_cb=None):
            first = Path(paths[0]).name
            if first == 'file-0100.pdf':
                for _ in range(100):
                    if cancelled_cb and cancelled_cb():
                        stopped.append(first)
                        raise InterruptedError('cancelled sf worker')
                    time.sleep(.004)
            return self.rows(paths)

        def progress(done, total):
            if done == 100:
                cancelled.set()

        with patch.object(stream, '_run_sf_batch', side_effect=sf):
            with self.assertRaises(InterruptedError):
                self.scan(cancelled_cb=cancelled.is_set, progress_cb=progress)
            self.assertEqual(len(self.partials()), 1)
            state = json.loads((self.partials()[0] / 'checkpoint.json').read_text('utf-8'))
            self.assertEqual(state['files_processed'], 100)
            self.assertFalse(any(not p.name.startswith('.partial-') for p in self.partials()))
            cancelled.clear()
            result = self.scan(workers=1, cancelled_cb=cancelled.is_set)
        self.assertTrue(result['resumed'])
        self.assertEqual(result['files_total'], 205)
        self.assertEqual(self.partials(), [])

    def test_a4_sequential_checkpoint_resumes_with_parallel_workers(self):
        self.make_files(201)
        seen = []
        failed = [True]
        def sf(_exe, paths, *, cancelled_cb=None):
            first = Path(paths[0]).name
            seen.append(first)
            if first == 'file-0100.pdf' and failed[0]:
                raise RuntimeError('synthetic interruption')
            return self.rows(paths)
        with patch.object(stream, '_run_sf_batch', side_effect=sf):
            with self.assertRaises(RuntimeError):
                self.scan(workers=1)
            failed[0] = False
            result = self.scan(workers=2)
        self.assertEqual(result['files_total'], 201)
        self.assertTrue(result['resumed'])
        self.assertEqual(seen.count('file-0000.pdf'), 1)
        self.assertEqual(len((result['target'] / 'siegfried_files.jsonl').read_text('utf-8').splitlines()),201)

    def test_invalid_worker_limits_rejected_before_touching_work(self):
        self.make_files(1)
        for workers in (0, 9, -1, True, '2'):
            with self.subTest(workers=workers), self.assertRaises(ValueError):
                self.scan(workers=workers)
        self.assertFalse((self.work / 'external_evidence').exists())

    @unittest.skipIf(os.name == 'nt', 'Real fake sf subprocess has a POSIX shebang; Windows is tested separately')
    def test_real_subprocesses_overlap_without_shell_or_source_writes(self):
        """Prove subprocess parallelism, not merely overlapping Python mocks."""
        import sys
        self.make_files(201)
        log = self.root / 'process-events.jsonl'
        self.sf.write_text('#!' + sys.executable + '\n' + r"""import json,os,sys,time
files=sys.argv[4:]
with open(os.environ['DWM_A5_PROCESSES'], 'a', encoding='utf-8') as out:
    out.write(json.dumps({'event':'start', 'pid':os.getpid(), 't':time.monotonic()}) + '\n')
time.sleep(.22)
with open(os.environ['DWM_A5_PROCESSES'], 'a', encoding='utf-8') as out:
    out.write(json.dumps({'event':'end', 'pid':os.getpid(), 't':time.monotonic()}) + '\n')
print(json.dumps({'files':[{'filename':p,'matches':[{'id':'fmt/354', 'format':'PDF/A'}]}
                          for p in files]}))
""", encoding="utf-8")
        self.sf.chmod(0o755)
        with patch.dict(os.environ, {'DWM_A5_PROCESSES':str(log)}):
            result = self.scan(workers=2)
        events = [json.loads(line) for line in log.read_text('utf-8').splitlines()]
        starts = [e for e in events if e['event']=='start']
        ends = [e for e in events if e['event']=='end']
        self.assertEqual(len(starts), 3)
        self.assertEqual(len({x['pid'] for x in starts}), 3)
        self.assertEqual(len(ends), 3)
        self.assertLess(starts[1]['t'], min(e['t'] for e in ends))
        self.assertEqual(result['files_total'],201)

    def test_one_worker_still_uses_legacy_sequential_path(self):
        self.make_files(201)
        count = []
        def sf(_exe, paths, *, cancelled_cb=None):
            count.append(len(paths))
            return self.rows(paths)
        with patch.object(stream, '_run_sf_batch', side_effect=sf):
            result = self.scan(workers=1)
        self.assertEqual(count,[100,100,1])
        self.assertEqual(result['files_total'],201)

    def test_operation_passes_worker_count_and_rejects_bad_setup(self):
        from app.siegfried_tool_v0111_a3 import SiegfriedCheck
        from noark5_workflow.core.context import OperationContext
        from noark5_workflow.operations import run_siegfried_pronom as adapter
        good = SiegfriedCheck(True, str(self.sf), 'siegfried 1.11', 'PRONOM 123')
        captured = []
        with patch.object(adapter, 'inspect_siegfried', return_value=good), \
             patch.object(adapter, 'scan_document_tree') as scan:
            scan.return_value = {'run_id':'fake','target':self.work, 'resumed':False,
                                 'model':{'identified':1,'unidentified':0,'ambiguous':0,
                                          'files_total':1,'format_groups':[],
                                          'source_scope':'DOKUMENT','evidence_type':'dwm_siegfried_pronom_identification'}}
            for setting in ({}, {'siegfried_max_workers':4}, {'siegfried_max_workers':1},
                            {'siegfried_max_workers':'3'}):
                ctx = OperationContext(self.source, work_operations=self.work,
                                       settings=setting,metadata={'job_id':'JOB-001'})
                self.assertTrue(adapter.SiegfriedPronomOperation().run(ctx).ok)
                captured.append(scan.call_args.kwargs['workers'])
            self.assertEqual(captured, [2,4,1,3])
            for invalid in (9, 2.5, True, '2.5'):
                ctx = OperationContext(self.source, work_operations=self.work,
                                       settings={'siegfried_max_workers':invalid})
                result = adapter.SiegfriedPronomOperation().run(ctx)
                self.assertFalse(result.ok)
                self.assertIn('1 til 8', result.message)
            self.assertEqual(len(captured),4)


if __name__=='__main__':
    unittest.main()
