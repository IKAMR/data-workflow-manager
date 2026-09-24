
from __future__ import annotations

import unittest
from pathlib import Path

from noark5_workflow.core.job import JobBatch


class V015A18NewJobListMapperResetTests(unittest.TestCase):
    def test_fresh_job_batch_job_has_blank_storage_roles(self):
        batch = JobBatch()
        old = batch.new_job(Path(r"H:\old"))
        old.source_extraction = Path(r"H:\old\content\sip\content")
        old.work_root = Path(r"H:\old")
        old.work_content = Path(r"H:\old\content")
        old.work_operations = Path(r"H:\old\repository_operations")
        old.archive_root = Path(r"H:\old\aip")

        batch.clear()
        fresh = batch.new_job(None)

        self.assertEqual(fresh.job_id, "JOB-001")
        self.assertTrue(fresh.is_unused_draft())
        self.assertIsNone(fresh.source_root)
        self.assertIsNone(fresh.source_tar)
        self.assertIsNone(fresh.source_unzipped)
        self.assertIsNone(fresh.source_extraction)
        self.assertIsNone(fresh.work_root)
        self.assertIsNone(fresh.work_content)
        self.assertIsNone(fresh.work_operations)
        self.assertIsNone(fresh.archive_root)

    def test_a53_closes_tracked_and_orphaned_mapper_windows(self):
        root = Path(__file__).resolve().parents[1]
        text = (root / "gui" / "persistent_app_a53.py").read_text(encoding="utf-8")
        self.assertIn("def _mapper_toplevels", text)
        self.assertIn("def _close_all_storage_roles_dialogs", text)
        self.assertIn("isinstance(child, StorageRolesDialog)", text)
        self.assertIn("dialog.destroy()", text)

    def test_destroy_binding_only_forgets_mapper_when_toplevel_dies(self):
        root = Path(__file__).resolve().parents[1]
        text = (root / "gui" / "persistent_app_a53.py").read_text(encoding="utf-8")
        self.assertIn('getattr(event, "widget", None) is not dialog', text)
        self.assertIn("_storage_dialog_destroyed", text)

    def test_mapper_is_reused_only_for_same_job_instance(self):
        root = Path(__file__).resolve().parents[1]
        text = (root / "gui" / "persistent_app_a53.py").read_text(encoding="utf-8")
        self.assertIn('getattr(existing, "job", None) is job', text)
        self.assertIn('getattr(dialog, "job", None) is job', text)

    def test_main_activates_a53_runtime(self):
        root = Path(__file__).resolve().parents[1]
        text = (root / "main.py").read_text(encoding="utf-8")
        self.assertIn("from gui.persistent_app_a53 import run_gui", text)


if __name__ == "__main__":
    unittest.main()
