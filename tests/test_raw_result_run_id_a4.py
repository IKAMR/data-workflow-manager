from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from noark5_workflow.core.raw_result_store import RawResultStore


class RawResultRunIdA4Tests(unittest.TestCase):
    def test_schema_v2_roundtrip_preserves_run_id(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "raw.jsonl"
            store = RawResultStore(path)
            item = store.append(
                operation_id="op",
                test_id="test",
                definition_version="1",
                ok=True,
                message="ok",
                run_id="RUN-123",
                job_id="JOB-001",
            )
            loaded = store.get(item.result_id)
            self.assertEqual(loaded.run_id, "RUN-123")

            record = json.loads(path.read_text(encoding="utf-8").splitlines()[0])
            self.assertEqual(record["schema_version"], 2)
            self.assertEqual(record["run_id"], "RUN-123")

    def test_schema_v1_remains_readable(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "raw.jsonl"
            record = {
                "schema_version": 1,
                "result_id": "old",
                "recorded_at": "2026-01-01T00:00:00+00:00",
                "operation_id": "op",
                "test_id": "test",
                "definition_version": "1",
                "ok": True,
                "message": "old",
                "data": {},
                "warnings": [],
                "outputs": [],
                "source_root": "",
                "job_id": "JOB-001",
            }
            path.write_text(
                json.dumps(record, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            item = RawResultStore(path).get("old")
            self.assertIsNotNone(item)
            self.assertEqual(item.run_id, "")


if __name__ == "__main__":
    unittest.main()
