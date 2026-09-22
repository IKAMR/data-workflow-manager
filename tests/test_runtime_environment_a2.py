from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from app.runtime_environment import capture_runtime_environment
from noark5_workflow.core.artifact_identity import write_artifact_manifest


class RuntimeEnvironmentA2Tests(unittest.TestCase):
    def test_capture_is_generic_and_contains_resource_fields(self):
        env = capture_runtime_environment()
        self.assertEqual(env["schema_version"], 1)
        self.assertIn("system", env)
        self.assertIn("python_version", env)
        self.assertIn("cpu_logical_count", env)
        self.assertIn("cpu_physical_count", env)
        self.assertIn("physical_memory_bytes", env)
        self.assertIn("available_memory_bytes", env)

    def test_artifact_manifest_carries_run_environment(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            ctx = SimpleNamespace(
                metadata={"job_id": "JOB-001", "run_id": "RUN-TEST"},
                settings={
                    "_current_run_id": "RUN-TEST",
                    "_current_run_environment": {
                        "schema_version": 1,
                        "system": "TestOS",
                        "cpu_logical_count": 8,
                    },
                },
                extraction_root=root / "source",
                work_operations=root / "work",
            )
            out = root / "artifact"
            manifest = write_artifact_manifest(
                ctx,
                out,
                operation_id="test_operation",
            )
            data = json.loads(manifest.read_text(encoding="utf-8"))
            self.assertEqual(data["schema_version"], 2)
            self.assertEqual(data["run_id"], "RUN-TEST")
            self.assertEqual(data["run_environment"]["system"], "TestOS")
            self.assertEqual(data["run_environment"]["cpu_logical_count"], 8)

    def test_run_overview_captures_environment_once(self):
        source = (
            Path(__file__).resolve().parents[1]
            / "app"
            / "run_overview_log.py"
        ).read_text(encoding="utf-8")
        self.assertIn("capture_runtime_environment()", source)
        self.assertIn('settings["_current_run_environment"]', source)
        self.assertIn('"environment": self.environment', source)


if __name__ == "__main__":
    unittest.main()
