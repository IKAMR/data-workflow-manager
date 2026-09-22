from pathlib import Path
from types import SimpleNamespace
import unittest

from app.work_output_layout import (
    AppWorkSubfolderError,
    effective_work_operations,
    validate_app_work_subfolder,
)


class WorkOutputLayoutA6Tests(unittest.TestCase):
    def _job(self, job_id="JOB-001"):
        return SimpleNamespace(
            job_id=job_id,
            name="Test",
            active_extraction_root=Path("source"),
            work_operations=Path("repository_operations"),
        )

    def test_default_dwm_plus_job_rule_is_two_levels(self):
        job = self._job()
        path = effective_work_operations(
            Path("repository_operations"),
            "dwm",
            "_test-<nnn>",
            job,
            1,
        )
        self.assertEqual(
            path,
            Path("repository_operations") / "dwm" / "_test-001",
        )

    def test_blank_app_root_uses_work_directly(self):
        job = self._job()
        path = effective_work_operations(
            Path("repository_operations"),
            "",
            "_test-<nnn>",
            job,
            1,
        )
        self.assertEqual(
            path,
            Path("repository_operations") / "_test-001",
        )

    def test_both_blank_use_work_root_directly(self):
        job = self._job()
        path = effective_work_operations(
            Path("repository_operations"),
            "",
            "",
            job,
            1,
        )
        self.assertEqual(path, Path("repository_operations"))

    def test_app_root_is_one_component(self):
        with self.assertRaises(AppWorkSubfolderError):
            validate_app_work_subfolder(r"dwm\sub")
        with self.assertRaises(AppWorkSubfolderError):
            validate_app_work_subfolder("dwm/sub")


if __name__ == "__main__":
    unittest.main()
