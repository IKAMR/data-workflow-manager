from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from app.batch_resource_strategy import recommend_batch_execution


class _Job:
    def __init__(self, root):
        self.active_extraction_root = Path(root)
        self.source_root = Path(root)


class BatchResourceStrategyA5Tests(unittest.TestCase):
    def test_single_job_is_always_sequential(self):
        with tempfile.TemporaryDirectory() as td:
            job = _Job(td)
            decision = recommend_batch_execution(
                [job],
                environment={
                    "cpu_logical_count": 24,
                    "available_memory_bytes": 64 * 1024**3,
                },
                requested_mode="parallel",
            )
            self.assertEqual(decision.workers, 1)
            self.assertEqual(decision.selected_mode, "sequential")

    def test_sequential_mode_forces_one_worker(self):
        with tempfile.TemporaryDirectory() as td:
            a = Path(td) / "a"
            b = Path(td) / "b"
            a.mkdir()
            b.mkdir()
            (a / "data.xml").write_bytes(b"x" * 1024)
            (b / "data.xml").write_bytes(b"x" * 1024)

            decision = recommend_batch_execution(
                [_Job(a), _Job(b)],
                environment={
                    "cpu_logical_count": 24,
                    "available_memory_bytes": 64 * 1024**3,
                },
                requested_mode="sequential",
            )
            self.assertEqual(decision.workers, 1)
            self.assertEqual(decision.selected_mode, "sequential")

    def test_auto_respects_user_worker_cap(self):
        with tempfile.TemporaryDirectory() as td:
            jobs = []
            for index in range(4):
                root = Path(td) / str(index)
                root.mkdir()
                (root / "data.xml").write_bytes(b"x" * 1024)
                jobs.append(_Job(root))

            decision = recommend_batch_execution(
                jobs,
                environment={
                    "cpu_logical_count": 24,
                    "available_memory_bytes": 64 * 1024**3,
                },
                requested_mode="auto",
                max_workers=2,
            )
            self.assertLessEqual(decision.workers, 2)


if __name__ == "__main__":
    unittest.main()
