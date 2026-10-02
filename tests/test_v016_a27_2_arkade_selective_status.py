from __future__ import annotations

import unittest
from pathlib import Path

from noark5_workflow.operations.run_arkade5_cli import (
    Arkade5Noark5TestOperation,
    Arkade5PronomAnalysisOperation,
)

ROOT = Path(__file__).resolve().parents[1]


class A272ArkadeSelectiveStatusContractTests(unittest.TestCase):
    def test_arkade_workflow_operations_persist_raw_results(self):
        self.assertTrue(Arkade5Noark5TestOperation.raw_result_record)
        self.assertTrue(Arkade5PronomAnalysisOperation.raw_result_record)

    def test_auto_import_uses_current_a26_api(self):
        source = (
            ROOT / "noark5_workflow" / "operations" / "run_arkade5_cli.py"
        ).read_text(encoding="utf-8")
        self.assertIn("import_arkade5_run_outputs(", source)
        self.assertIn("on_progress=ctx.log", source)
        self.assertNotIn("settings=ctx.settings", source)


if __name__ == "__main__":
    unittest.main()
