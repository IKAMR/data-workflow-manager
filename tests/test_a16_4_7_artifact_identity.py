from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from noark5_workflow.core.artifact_identity import (
    artifact_belongs_to_context,
    artifact_run_dir,
    write_artifact_manifest,
)
from noark5_workflow.core.context import OperationContext


class A1647ArtifactIdentityTests(unittest.TestCase):
    def test_job_and_run_are_part_of_artifact_folder_and_manifest(self):
        with tempfile.TemporaryDirectory() as temp:
            work = Path(temp)
            ctx = OperationContext(
                extraction_root=work / "source",
                work_operations=work / "ops",
                settings={"_current_run_id": "RUN-20260921-120000-abcd1234"},
            )
            ctx.metadata["job_id"] = "JOB-004"
            ctx.metadata["run_id"] = "RUN-20260921-120000-abcd1234"

            out = artifact_run_dir(ctx, "noark5_tests", "schema", operation_id="validate_xml_schema")
            self.assertIn("JOB-004__RUN-20260921-120000-abcd1234", out.name)

            manifest = write_artifact_manifest(ctx, out, operation_id="validate_xml_schema")
            data = json.loads(manifest.read_text(encoding="utf-8"))
            self.assertEqual(data["job_id"], "JOB-004")
            self.assertEqual(data["run_id"], "RUN-20260921-120000-abcd1234")
            self.assertEqual(data["source_extraction"], str(ctx.extraction_root))
            self.assertTrue(artifact_belongs_to_context(out, ctx))


if __name__ == "__main__":
    unittest.main()
