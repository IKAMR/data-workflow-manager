from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class A11SourceWorkStorageTests(unittest.TestCase):
    def test_storage_dialog_uses_generic_english_role_names(self):
        text = (ROOT / "gui" / "storage_roles_dialog_a11.py").read_text(encoding="utf-8")
        self.assertIn('"Source - root"', text)
        self.assertIn('"Work - root"', text)
        self.assertIn('"Storage - root"', text)
        self.assertNotIn('"Arbeid -', text)
        self.assertNotIn('"Arkiv -', text)

    def test_storage_is_not_assumed_to_be_inside_work(self):
        text = (ROOT / "gui" / "storage_roles_dialog_a11.py").read_text(encoding="utf-8")
        self.assertNotIn('work_root / "aip"', text)
        self.assertNotIn('work_root / "storage"', text)

    def test_new_job_list_creates_first_job_and_uses_default_profile(self):
        text = (ROOT / "gui" / "persistent_app_a21.py").read_text(encoding="utf-8")
        self.assertIn("created = super()._new_job_list()", text)
        self.assertIn("self._apply_profile(None, persist=False)", text)
        self.assertIn("job = self._create_job(None)", text)
        self.assertIn("job.profile_id = None", text)

    def test_new_job_list_reuses_job_creation_mapper_behaviour(self):
        text = (ROOT / "gui" / "persistent_app_a21.py").read_text(encoding="utf-8")
        self.assertIn("self._create_job(None)", text)
        base = (ROOT / "gui" / "persistent_app_a13.py").read_text(encoding="utf-8")
        self.assertIn("self.after(0, lambda j=job: self._show_storage_roles(j))", base)

    def test_main_uses_a21_runtime(self):
        text = (ROOT / "main.py").read_text(encoding="utf-8")
        self.assertIn("persistent_app_a20", text)
        self.assertIn("persistent_app_a21", text)

    def test_documented_role_contract(self):
        text = (ROOT / "docs" / "SOURCE-WORK-STORAGE.md").read_text(encoding="utf-8")
        for term in ("Source", "Work", "Storage", "JOB-001", "Default"):
            self.assertIn(term, text)


if __name__ == "__main__":
    unittest.main()
