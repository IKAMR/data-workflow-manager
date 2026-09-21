from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from noark5_workflow.core.job import JobBatch
from noark5_workflow.core.job_store import load_job_list, save_job_list
from noark5_workflow.core.output_subfolder import (
    OutputSubfolderRuleError,
    effective_work_operations,
    render_output_subfolder_rule,
    validate_output_subfolder_rule,
)


class A1647OutputSubfoldersTests(unittest.TestCase):
    def test_supported_tokens(self):
        job = SimpleNamespace(
            job_id="JOB-004",
            name="Test jobb",
            active_extraction_root=Path(r"G:\src\extract-a"),
        )
        self.assertEqual(render_output_subfolder_rule("<jobno>", job, 2), "004")
        self.assertEqual(render_output_subfolder_rule("<jobid>", job, 2), "JOB-004")
        self.assertEqual(render_output_subfolder_rule("<nnn>", job, 2), "002")
        self.assertEqual(render_output_subfolder_rule("test-<jobno>", job, 2), "test-004")
        self.assertEqual(render_output_subfolder_rule("<source>", job, 2), "extract-a")

    def test_literal_collision_is_rejected_for_shared_base(self):
        root = Path("work")
        first = SimpleNamespace(job_id="JOB-001", name="A", active_extraction_root=Path("a"), work_operations=root)
        second = SimpleNamespace(job_id="JOB-002", name="B", active_extraction_root=Path("b"), work_operations=root)
        with self.assertRaises(OutputSubfolderRuleError):
            validate_output_subfolder_rule("test", [first, second])

    def test_jobno_separates_shared_base(self):
        root = Path("work")
        first = SimpleNamespace(job_id="JOB-001", name="A", active_extraction_root=Path("a"), work_operations=root)
        second = SimpleNamespace(job_id="JOB-002", name="B", active_extraction_root=Path("b"), work_operations=root)
        values = validate_output_subfolder_rule("<jobno>", [first, second])
        self.assertEqual(values[0][1], root / "001")
        self.assertEqual(values[1][1], root / "002")

    def test_rule_is_job_list_level_and_roundtrips(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            batch = JobBatch()
            batch.new_job(root / "source-a")
            batch.output_subfolder_rule = "test-<jobno>"
            path = save_job_list(root / "list.n5jobs", batch)
            raw = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(raw["output_subfolder_rule"], "test-<jobno>")
            loaded = load_job_list(path)
            self.assertEqual(loaded.output_subfolder_rule, "test-<jobno>")
            self.assertEqual(loaded.batch.output_subfolder_rule, "test-<jobno>")

    def test_blank_rule_preserves_existing_work_operations(self):
        job = SimpleNamespace(job_id="JOB-001", name="A", active_extraction_root=Path("a"))
        base = Path("work")
        self.assertEqual(effective_work_operations(base, "", job, 1), base)

    def test_runtime_layer_keeps_a36_and_uses_rule_aware_runner(self):
        runtime = (Path(__file__).resolve().parents[1] / "gui" / "persistent_app_a36.py").read_text(encoding="utf-8")
        main = (Path(__file__).resolve().parents[1] / "main.py").read_text(encoding="utf-8")
        self.assertIn("class RuleAwareJobRunner(JobRunner)", runtime)
        self.assertIn("A20JobsWindow(", runtime)
        self.assertIn("from gui.persistent_app_a36 import run_gui", main)


if __name__ == "__main__":
    unittest.main()
