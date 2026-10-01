from __future__ import annotations

import re
import tempfile
import unittest
from pathlib import Path

from noark5_workflow.core.job import Job
from noark5_workflow.job_batch_actions import fill_missing_storage_suggestions


class A246JobBatchActionsTests(unittest.TestCase):
    def test_batch_fill_uses_storage_profile_and_preserves_existing_values(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "1502_003_AIC-1"
            extraction = root / "content" / "sip" / "content" / "part-001" / "avleveringspakke"
            existing_work = root / "custom-work"
            job = Job(
                "JOB-001",
                source_root=root,
                source_extraction=extraction,
                work_root=existing_work,
            )

            result = fill_missing_storage_suggestions(
                [job],
                layout_id="ikamr_standard",
            )

            self.assertEqual(job.work_root, existing_work)
            self.assertGreaterEqual(result.selected_jobs, 1)
            self.assertEqual(result.changed_jobs, 1)
            self.assertGreater(result.filled_fields, 0)
            self.assertIn("work_root", result.job_results[0].preserved)

    def test_jobs_without_anchor_are_not_modified(self):
        job = Job("JOB-001")
        result = fill_missing_storage_suggestions([job], layout_id="ikamr_standard")
        self.assertEqual(result.changed_jobs, 0)
        self.assertEqual(result.filled_fields, 0)
        self.assertEqual(result.jobs_without_suggestions, 1)

    def test_none_profile_does_not_invent_work_or_storage(self):
        extraction = Path("C:/example/avleveringspakke")
        job = Job("JOB-001", source_extraction=extraction)
        result = fill_missing_storage_suggestions([job], layout_id="none")
        self.assertIsNone(job.work_root)
        self.assertIsNone(job.work_operations)
        self.assertIsNone(job.archive_root)
        self.assertEqual(result.filled_fields, 0)

    def test_gui_layer_exposes_reusable_selected_job_action(self):
        source = Path('gui/jobs_window_a31.py').read_text(encoding='utf-8')
        self.assertIn('Jobbhandlinger...', source)
        self.assertIn('JobBatchActionDialog', source)
        self.assertIn('on_fill_storage_suggestions', source)

    def test_selection_dialog_has_all_clear_and_fill_action(self):
        source = Path('gui/job_batch_action_dialog.py').read_text(encoding='utf-8')
        self.assertIn('Velg alle', source)
        self.assertIn('Tøm', source)
        self.assertIn('Fyll mappeforslag', source)
        self.assertIn('Valgt:', source)

    def test_runtime_preserves_a24_and_version_has_not_regressed(self):
        main = Path('main.py').read_text(encoding='utf-8')
        version = Path('version.py').read_text(encoding='utf-8')
        self.assertIn('from gui.persistent_app_a24_5 import run_gui', main)
        match = re.search(r'VERSION\s*=\s*"0\.1\.6-a(\d+)(?:\.(\d+))?"', version)
        self.assertIsNotNone(match)
        self.assertGreaterEqual(int(match.group(1)), 24)


if __name__ == '__main__':
    unittest.main()
