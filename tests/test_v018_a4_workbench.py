"""a4 regression tests: recent job lists, safe edits and dock UI contracts."""
from __future__ import annotations

import ast
import tempfile
import unittest
from pathlib import Path

from app.workbench_recent_v018_a4 import recent_joblists, remember_joblist
from app.workbench_api_v018_a3 import DwmWorkbenchAPI, DwmApiError
from noark5_workflow.core.job import Job, JobBatch, JobStatus
from noark5_workflow.core.job_store import save_job_list, load_job_list

ROOT = Path(__file__).resolve().parents[1]


class A4RecentJobListTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.qt = self.root / "qt.n5jobs"
        self.legacy = self.root / "legacy.n5jobs"
        self.qt.write_text("test", encoding="utf-8")
        self.legacy.write_text("test", encoding="utf-8")

    def test_new_qt_joblist_precedes_legacy_joblist(self):
        paths = recent_joblists(str(self.qt), [], {"last_job_list_file": str(self.legacy)})
        self.assertEqual(paths, (str(self.qt), str(self.legacy)))

    def test_old_gui_history_used_when_qt_has_no_joblist(self):
        paths = recent_joblists("", [], {"last_job_list_file": str(self.legacy)})
        self.assertEqual(paths, (str(self.legacy),))

    def test_nonexistent_and_non_joblist_paths_are_ignored(self):
        paths = recent_joblists("", [str(self.root / "absent.n5jobs"), str(self.root / "bad.txt"), str(self.qt)])
        self.assertEqual(paths, (str(self.qt),))

    def test_recent_deduplication_and_order_without_writing_file(self):
        before = self.qt.read_bytes()
        paths = remember_joblist(str(self.qt), [str(self.legacy), str(self.qt), str(self.legacy)])
        self.assertEqual(paths, (str(self.qt), str(self.legacy)))
        self.assertEqual(self.qt.read_bytes(), before)

    def test_case_insensitive_windows_path_dedup(self):
        paths = recent_joblists("C:/A/TEST.N5JOBS", [r"c:\a\test.n5jobs"], existing_only=False)
        self.assertEqual(len(paths), 1)


class A4JobEditingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / "source"
        self.source.mkdir()
        self.work = self.root / "work"
        self.work.mkdir()
        self.path = self.root / "preserved.n5jobs"
        batch = JobBatch()
        for i in range(1, 4):
            batch.add(Job(
                job_id=f"JOB-{i:03d}", name=f"Uttrekk {i}",
                source_root=self.source, source_extraction=self.source,
                work_operations=self.work,
                workflow_ids=["metadata_inventory"],
                status=JobStatus.OK if i == 1 else JobStatus.READY,
                next_operation_index=1 if i == 1 else 0,
            ))
        save_job_list(self.path, batch, active_job_id="JOB-002", app_version="0.1.7")
        self.api = DwmWorkbenchAPI(settings={"app_work_subfolder": "dwm"})
        self.api.open_job_list(self.path)

    def test_rename_changes_only_name_and_requires_explicit_save(self):
        original_file = self.path.read_bytes()
        original_paths = self.api.job_details("JOB-002").storage.copy()
        result = self.api.rename_job("JOB-002", "  Nytt navn  ")
        self.assertEqual(result.job.name, "Nytt navn")
        self.assertEqual(result.storage, original_paths)
        self.assertTrue(self.api.dirty)
        self.assertEqual(self.path.read_bytes(), original_file)
        self.api.save_job_list()
        self.assertEqual(load_job_list(self.path).batch.get("JOB-002").name, "Nytt navn")
        self.assertFalse(self.api.dirty)

    def test_reorder_preserves_ids_active_job_and_persisted_source(self):
        before = self.path.read_bytes()
        view = self.api.move_job("JOB-002", -1)
        self.assertEqual([j.job_id for j in view.jobs], ["JOB-002", "JOB-001", "JOB-003"])
        self.assertEqual(view.active_job_id, "JOB-002")
        self.assertEqual(self.path.read_bytes(), before)
        self.assertEqual(self.api.job_details("JOB-001").storage["source_extraction"], str(self.source))

    def test_boundary_reorder_does_not_mark_dirty(self):
        self.api.move_job("JOB-001", -1)
        self.assertFalse(self.api.dirty)

    def test_remove_updates_active_selection_and_never_deletes_files(self):
        original_file = self.path.read_bytes()
        marker = self.work / "sensitive-result.txt"
        marker.write_text("bevar", encoding="utf-8")
        view = self.api.remove_job("JOB-002")
        self.assertEqual(view.active_job_id, "JOB-003")
        self.assertEqual([j.job_id for j in view.jobs], ["JOB-001", "JOB-003"])
        self.assertEqual(marker.read_text(encoding="utf-8"), "bevar")
        self.assertEqual(self.path.read_bytes(), original_file)
        self.assertTrue(self.api.dirty)

    def test_name_placeholder_prevents_silent_work_path_change(self):
        self.api._batch.output_subfolder_rule = "<name>"
        original = self.api.job_details("JOB-002")
        with self.assertRaisesRegex(DwmApiError, "Work"):
            self.api.rename_job("JOB-002", "Ny rapportmappe")
        self.assertEqual(self.api.job_details("JOB-002"), original)
        self.assertFalse(self.api.dirty)

    def test_position_placeholder_prevents_reorder_and_remove(self):
        self.api._batch.output_subfolder_rule = "<nnn>"
        before = self.api.workspace()
        with self.assertRaisesRegex(DwmApiError, "Work"):
            self.api.move_job("JOB-002", -1)
        with self.assertRaisesRegex(DwmApiError, "Work"):
            self.api.remove_job("JOB-001")
        self.assertEqual(self.api.workspace(), before)
        self.assertFalse(self.api.dirty)
        # Deleting the last job doesn't change any remaining job position.
        self.assertEqual(len(self.api.remove_job("JOB-003").jobs), 2)

    def test_running_joblist_cannot_be_edited(self):
        self.api._running = True
        self.addCleanup(setattr, self.api, "_running", False)
        with self.assertRaises(DwmApiError):
            self.api.rename_job("JOB-002", "No")
        with self.assertRaises(DwmApiError):
            self.api.move_job("JOB-002", 1)
        with self.assertRaises(DwmApiError):
            self.api.remove_job("JOB-002")


class A4QtSourceTests(unittest.TestCase):
    def test_qt_is_separate_from_legacy(self):
        text = (ROOT / "gui_qt/main_window.py").read_text(encoding="utf-8")
        ast.parse(text)
        self.assertIn("QDockWidget", text)
        self.assertNotIn("from gui.persistent_app", text)
        self.assertIn("_restore_settings", text)
        self.assertIn("_recover_windows", text)

    def test_history_and_job_actions_are_wired_to_api(self):
        text = (ROOT / "gui_qt/main_window.py").read_text(encoding="utf-8")
        for name in (
            "_recent_paths", "_refresh_recent_menu", "_open_recent",
            "job_search.textChanged.connect(self._filter_jobs)",
            "self.api.rename_job(", "self.api.move_job(", "self.api.remove_job(",
            "_update_job_actions", "qt/skip_auto_reopen",
            "self.layout_tool", "self.complexity_tool",
        ):
            self.assertIn(name, text)

    def test_new_and_legacy_launchers_stay_separate(self):
        qt = (ROOT / "start.bat").read_text(encoding="utf-8")
        legacy = (ROOT / "start-legacy.bat").read_text(encoding="utf-8")
        self.assertIn("-m gui_qt", qt)
        self.assertIn("py main.py", legacy)


if __name__ == "__main__":
    unittest.main()
