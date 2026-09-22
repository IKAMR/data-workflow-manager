from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.resource_strategy import (
    AUTO_STREAMING_FILE_THRESHOLD,
    choose_resource_strategy,
    recommend_worker_count,
)


class ResourceStrategyA3Tests(unittest.TestCase):
    def test_large_xml_is_streamed_even_with_large_ram(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "large.xml"
            with path.open("wb") as stream:
                stream.truncate(AUTO_STREAMING_FILE_THRESHOLD + 1)

            decision = choose_resource_strategy(
                path,
                requested="auto",
                workload="xml_schema_tree",
                environment={
                    "available_memory_bytes": 128 * 1024**3,
                    "cpu_logical_count": 24,
                },
            )
            self.assertEqual(decision.selected, "streaming")

    def test_network_reused_small_file_can_prefer_memory(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "small.xml"
            path.write_bytes(b"x" * 1024)

            with patch("app.resource_strategy.storage_kind", return_value="network"):
                decision = choose_resource_strategy(
                    path,
                    requested="auto",
                    workload="binary_buffer",
                    expected_reuse=3,
                    environment={
                        "available_memory_bytes": 16 * 1024**3,
                        "cpu_logical_count": 8,
                    },
                )
            self.assertEqual(decision.selected, "memory")

    def test_explicit_strategy_is_respected(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "data.bin"
            path.write_bytes(b"abc")
            decision = choose_resource_strategy(path, requested="streaming")
            self.assertEqual(decision.selected, "streaming")
            self.assertIn("eksplisitt", decision.reason)

    def test_worker_recommendation_is_memory_bounded(self):
        workers = recommend_worker_count(
            environment={
                "available_memory_bytes": 4 * 1024**3,
                "cpu_logical_count": 24,
            },
            per_worker_memory_bytes=2 * 1024**3,
        )
        self.assertEqual(workers, 1)


if __name__ == "__main__":
    unittest.main()
