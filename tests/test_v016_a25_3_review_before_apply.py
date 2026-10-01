from __future__ import annotations

import unittest
from pathlib import Path

from noark5_workflow.core.job import Job
from noark5_workflow.job_batch_actions import preview_missing_storage_suggestions


class A253ReviewBeforeApplyTests(unittest.TestCase):
    def test_storage_preview_is_non_mutating_and_lists_fillable_roles(self):
        root = Path("C:/AIC")
        extraction = root / "content" / "sip" / "content" / "part" / "avleveringspakke"
        job = Job("JOB-001", source_root=root, source_extraction=extraction)
        rows = preview_missing_storage_suggestions([job], layout_id="ikamr_standard")
        self.assertEqual(len(rows), 1)
        self.assertTrue(rows[0].fillable)
        self.assertIsNone(job.work_root)
        self.assertIsNone(job.work_operations)
        self.assertIsNone(job.archive_root)

    def test_storage_preview_dialog_has_all_none_and_apply(self):
        source = Path("gui/storage_suggestion_preview_dialog.py").read_text(encoding="utf-8")
        self.assertIn('text="Alle"', source)
        self.assertIn('text="Ingen"', source)
        self.assertIn('text="Bruk forslag"', source)
        self.assertIn("Eksisterende mappevalg overskrives ikke", source)

    def test_arkade_result_dialog_has_report_checklist_and_accept(self):
        source = Path("gui/arkade5_batch_discovery_dialog.py").read_text(encoding="utf-8")
        self.assertTrue(
            "ctk.BooleanVar(value=True)" in source
            or "ctk.BooleanVar(value=not imported)" in source
        )
        self.assertTrue('text="Alle"' in source or 'text="Alle nye"' in source)
        self.assertIn('text="Ingen"', source)
        self.assertTrue(
            'text="Fortsett med valgte"' in source
            or 'text="Importer valgte"' in source
            or 'text="Importer nye valgte"' in source
        )
        self.assertIn("on_accept", source)

    def test_a253_layer_remains_non_importing(self):
        source = Path("gui/persistent_app_a25_3.py").read_text(encoding="utf-8")
        self.assertIn("_a253_selected_arkade5_results", source)
        self.assertIn("Ingen resultater er importert eller kopiert", source)
        self.assertNotIn("import_arkade5_report", source)
        self.assertNotIn("import_discovered_arkade5_reports", source)

    def test_runtime_activates_a253(self):
        main = Path("main.py").read_text(encoding="utf-8")
        version = Path("version.py").read_text(encoding="utf-8")
        self.assertIn("from gui.persistent_app_a25_3 import run_gui", main)
        import re
        match = re.search(r'VERSION\s*=\s*"0\.1\.6-a(\d+)(?:\.(\d+))?"', version)
        self.assertIsNotNone(match)
        alpha = int(match.group(1))
        increment = int(match.group(2) or 0)
        self.assertTrue(alpha > 25 or (alpha == 25 and increment >= 3))


if __name__ == "__main__":
    unittest.main()
