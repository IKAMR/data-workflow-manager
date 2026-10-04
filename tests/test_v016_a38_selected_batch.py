from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class V016A38SelectedBatchTests(unittest.TestCase):
    def setUp(self):
        self.runtime = (
            ROOT / "gui" / "persistent_app_a38_runtime.py"
        ).read_text(encoding="utf-8")

    def test_a38_builds_on_a37_without_reimplementing_a37_features(self):
        self.assertIn(
            "persistent_app_a37_runtime import WorkflowApp as A37WorkflowApp",
            self.runtime,
        )
        self.assertIn("class WorkflowApp(A37WorkflowApp):", self.runtime)

    def test_start_selected_snapshots_exact_checked_jobs(self):
        self.assertIn(
            "selected = tuple(self.jobs_window._selected_jobs_for_run())",
            self.runtime,
        )
        self.assertIn(
            "selected_ids = frozenset(job.job_id for job in selected)",
            self.runtime,
        )

    def test_preflight_receives_only_selected_jobs(self):
        method = self.runtime.split("def _start_selected_jobs", 1)[1]
        self.assertIn(
            'self._batch_preflight(\n            selected,\n            action_label="Start valgte"',
            method,
        )

    def test_preflight_cannot_expand_selection(self):
        self.assertIn(
            "if job.job_id in selected_ids",
            self.runtime,
        )

    def test_rerun_confirmation_receives_only_filtered_candidates(self):
        self.assertIn("self._confirm_rerun(candidates)", self.runtime)
        self.assertNotIn("self._confirm_rerun(self.jobs.jobs()", self.runtime)

    def test_worker_has_final_selection_guard(self):
        self.assertIn(
            "if job.job_id not in selected_ids:\n                        continue",
            self.runtime,
        )

    def test_current_runtime_delegates_to_a38(self):
        source = (
            ROOT / "gui" / "persistent_app_a27_2.py"
        ).read_text(encoding="utf-8")
        self.assertIn("persistent_app_a38_runtime", source)

    def test_version_is_a38(self):
        source = (ROOT / "version.py").read_text(encoding="utf-8")
        self.assertIn('VERSION = "0.1.6-a38"', source)


if __name__ == "__main__":
    unittest.main()
