from __future__ import annotations

from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class A152DiscoveryBatchCreationTests(unittest.TestCase):
    def test_discovery_does_not_use_interactive_new_job_callback(self):
        text = (ROOT / "gui" / "jobs_window_a17.py").read_text(encoding="utf-8")
        discovery = text.split("def _discover_jobs(self) -> None:", 1)[1]
        self.assertNotIn("self.on_create_job(Path(candidate.path))", discovery)
        self.assertIn("self.batch.new_job(", discovery)

    def test_discovery_assigns_storage_roles(self):
        text = (ROOT / "gui" / "jobs_window_a17.py").read_text(encoding="utf-8")
        self.assertIn("materialize_storage_roles(", text)
        self.assertIn("self._apply_roles(job, roles)", text)

    def test_discovery_keeps_noark_profile_assignment(self):
        text = (ROOT / "gui" / "jobs_window_a17.py").read_text(encoding="utf-8")
        self.assertIn('job.profile_id = "noark5"', text)


if __name__ == "__main__":
    unittest.main()
