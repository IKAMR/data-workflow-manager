
from __future__ import annotations

import unittest
from pathlib import Path


class V015A18RecycledJobIdentityTests(unittest.TestCase):
    def test_a21_batch_contract_is_preserved(self):
        root = Path(__file__).resolve().parents[1]
        text = (root / "gui" / "jobs_window_a21.py").read_text(encoding="utf-8")
        self.assertIn('text="Batchkjøring"', text)
        self.assertIn('"Sekvensiell"', text)
        self.assertIn('"Parallell"', text)
        self.assertIn('text="Maks workers"', text)

    def test_latest_jobs_window_tracks_object_identity(self):
        root = Path(__file__).resolve().parents[1]
        text = (root / "gui" / "jobs_window_a28.py").read_text(encoding="utf-8")
        self.assertIn("from .jobs_window_a27 import A27JobsWindow", text)
        self.assertIn("tuple(id(job) for job in jobs)", text)
        self.assertIn("previous_objects != current_objects", text)
        self.assertIn("self._rendered_job_ids = ()", text)

    def test_active_runtime_uses_latest_identity_safe_jobs_window(self):
        root = Path(__file__).resolve().parents[1]
        text = (root / "gui" / "persistent_app_a53.py").read_text(encoding="utf-8")
        self.assertIn("A28JobsWindow", text)
        self.assertIn("get_batch_execution_config=self._get_batch_execution_config", text)
        self.assertIn("get_app_work_subfolder=self._get_app_work_subfolder", text)
        self.assertIn("open_validation_overview=self._open_validation_overview", text)

    def test_mapper_rejects_different_job_object(self):
        root = Path(__file__).resolve().parents[1]
        text = (root / "gui" / "persistent_app_a53.py").read_text(encoding="utf-8")
        self.assertIn('getattr(existing, "job", None) is job', text)


if __name__ == "__main__":
    unittest.main()
