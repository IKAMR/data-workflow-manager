from __future__ import annotations

import threading
import time
import unittest
from pathlib import Path

from noark5_workflow.core.batch_runner import BatchRunner
from noark5_workflow.core.job import Job, JobStatus


class _ParallelProbe:
    def __init__(self):
        self.lock = threading.Lock()
        self.active = 0
        self.max_active = 0

    def enter(self):
        with self.lock:
            self.active += 1
            self.max_active = max(self.max_active, self.active)

    def leave(self):
        with self.lock:
            self.active -= 1


class _Runner:
    def __init__(self, probe):
        self.probe = probe

    def run(self, job, **kwargs):
        self.probe.enter()
        try:
            time.sleep(0.08)
            job.status = JobStatus.OK
            job.progress = 1.0
        finally:
            self.probe.leave()


class ParallelBatchA4Tests(unittest.TestCase):
    def test_parallel_runner_executes_more_than_one_job_at_once(self):
        probe = _ParallelProbe()
        base = _Runner(probe)
        batch = BatchRunner(
            base,
            parallel_runner_factory=lambda: _Runner(probe),
        )
        jobs = [
            Job(job_id=f"JOB-{n:03d}", source_root=Path(f"source-{n}"))
            for n in range(1, 5)
        ]

        outcome = batch.run_parallel(jobs, max_workers=2)

        self.assertEqual(outcome.finished, 4)
        self.assertGreaterEqual(probe.max_active, 2)

    def test_one_worker_preserves_sequential_contract(self):
        probe = _ParallelProbe()
        base = _Runner(probe)
        batch = BatchRunner(base)
        jobs = [
            Job(job_id=f"JOB-{n:03d}", source_root=Path(f"source-{n}"))
            for n in range(1, 3)
        ]

        outcome = batch.run_parallel(jobs, max_workers=1)

        self.assertEqual(outcome.finished, 2)
        self.assertEqual(probe.max_active, 1)


if __name__ == "__main__":
    unittest.main()
