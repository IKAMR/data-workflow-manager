"""Headless workbench API and UI integration contracts for v0.1.8-a3."""
from __future__ import annotations

import ast
import json
import tempfile
import unittest
from pathlib import Path

from app.workbench_api_v018_a3 import DwmApiError, DwmWorkbenchAPI, STORAGE_FIELDS
from noark5_workflow.core.job import Job, JobBatch, JobStatus
from noark5_workflow.core.job_store import load_job_list, save_job_list

ROOT = Path(__file__).resolve().parents[1]


class V018A3ApiTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / "source"
        self.source.mkdir()
        self.work = self.root / "work-operations"
        self.content = self.root / "separate-content"
        self.archive = self.root / "separate-aip"
        self.path = self.root / "workshop.n5jobs"
        self.settings = {"app_work_subfolder": "dwm", "noark5_discovery_workflow": "noark5_standard"}

    def _existing(self, *, completed=False):
        batch = JobBatch()
        batch.add(Job(
            job_id="JOB-001", name="1502_024",
            source_root=self.source, source_extraction=self.source,
            work_root=self.root / "other-work", work_content=self.content,
            work_operations=self.work, archive_root=self.archive,
            workflow_ids=["metadata_inventory"],
            status=JobStatus.OK if completed else JobStatus.READY,
            next_operation_index=1 if completed else 0,
        ))
        save_job_list(self.path, batch, active_job_id="JOB-001", app_version="0.1.7")

    def test_no_gui_imports_in_workbench_api(self):
        source = (ROOT / "app" / "workbench_api_v018_a3.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        names = [node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)]
        self.assertFalse(any(str(name).startswith(("gui", "PySide6", "tkinter")) for name in names))

    def test_existing_joblist_load_is_readonly(self):
        self._existing()
        before = self.path.read_bytes()
        api = DwmWorkbenchAPI(settings=self.settings)
        api.open_job_list(self.path)
        self.assertFalse(api.dirty)
        details = api.job_details("JOB-001")
        self.assertEqual(self.path.read_bytes(), before)
        self.assertEqual(details.storage["work_content"], str(self.content))
        self.assertEqual(details.storage["archive_root"], str(self.archive))
        self.assertEqual(details.job.effective_work_operations, str(self.work / "dwm"))

    def test_independent_paths_survive_save_and_reopen(self):
        self._existing()
        api = DwmWorkbenchAPI(settings=self.settings)
        api.open_job_list(self.path)
        roles = {
            "source_extraction": str(self.source),
            "work_content": str(self.content / "changed"),
            "work_operations": str(self.work / "updated"),
            "archive_root": str(self.archive / "aip"),
        }
        api.update_storage("JOB-001", roles)
        self.assertTrue(api.dirty)
        self.assertFalse((self.work / "updated").exists())
        api.save_job_list()
        self.assertFalse(api.dirty)
        loaded = load_job_list(self.path)
        job = loaded.batch.get("JOB-001")
        self.assertEqual(str(job.source_extraction), roles["source_extraction"])
        self.assertEqual(str(job.work_content), roles["work_content"])
        self.assertEqual(str(job.work_operations), roles["work_operations"])
        self.assertEqual(str(job.archive_root), roles["archive_root"])

    def test_new_list_is_not_saved_over_existing(self):
        self._existing()
        api = DwmWorkbenchAPI(settings=self.settings)
        api.open_job_list(self.path)
        previous = self.path.read_bytes()
        view = api.new_job_list()
        self.assertEqual(view.jobs, ())
        self.assertIsNone(view.job_list_path)
        self.assertEqual(self.path.read_bytes(), previous)

    def test_new_job_uses_configured_sequence(self):
        api = DwmWorkbenchAPI(settings=self.settings)
        view = api.create_job(source_extraction=self.source, work_operations=self.work)
        self.assertEqual(view.job_id, "JOB-001")
        self.assertEqual(view.source_extraction, str(self.source))
        self.assertEqual(view.work_operations, str(self.work))
        self.assertGreater(view.operation_count, 0)
        self.assertTrue(api.dirty)
        self.assertFalse(self.work.exists())

    def test_unknown_storage_role_fails_without_mutation(self):
        self._existing()
        api = DwmWorkbenchAPI(settings=self.settings)
        api.open_job_list(self.path)
        with self.assertRaises(DwmApiError):
            api.update_storage("JOB-001", {"work_wrong": "C:/fake"})
        self.assertFalse(api.dirty)
        self.assertEqual(api.job_details("JOB-001").storage["work_operations"], str(self.work))

    def test_workflow_edit_preserves_existing_job_identity(self):
        self._existing(completed=True)
        api = DwmWorkbenchAPI(settings=self.settings)
        api.open_job_list(self.path)
        catalog = api.available_operations()
        sequence = [op.operation_id for op in catalog[:2]]
        self.assertEqual(len(sequence), 2)
        details = api.set_workflow("JOB-001", sequence)
        self.assertEqual(details.job.job_id, "JOB-001")
        self.assertEqual(details.job.current_operation, 0)
        self.assertEqual(details.job.status, "Klar")
        self.assertIn("Konfigurasjon endret", details.message)
        self.assertEqual([x.operation_id for x in details.operations], sequence)

    def test_storage_contract_includes_distinct_roles(self):
        self.assertIn("source_extraction", STORAGE_FIELDS)
        self.assertIn("work_content", STORAGE_FIELDS)
        self.assertIn("work_operations", STORAGE_FIELDS)
        self.assertIn("archive_root", STORAGE_FIELDS)


class V018A3QtSourceTests(unittest.TestCase):
    def test_qt_is_a_separate_frontend(self):
        source = (ROOT / "gui_qt" / "main_window.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        imports = [node.module or "" for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)]
        self.assertTrue(any(name.startswith("PySide6") for name in imports))
        self.assertFalse(any(name.startswith("gui.persistent_app") for name in imports))
        self.assertIn("DwmWorkbenchAPI", source)

    def test_dock_layout_can_hide_float_and_persist(self):
        source = (ROOT / "gui_qt" / "main_window.py").read_text(encoding="utf-8")
        for expected in (
            "QDockWidget", "AllDockWidgetAreas", "toggleViewAction", "setFloating",
            "saveState(3)", "restoreState(", "_save_named_layout", "_recover_windows",
            '"Laptop"', '"Analyse"', '"Depot"', '"Workshop"',
            '"Enkel"', '"Standard"', '"Avansert"',
        ):
            self.assertIn(expected, source)

    def test_worker_keeps_gui_event_loop_nonblocking(self):
        source = (ROOT / "gui_qt" / "main_window.py").read_text(encoding="utf-8")
        self.assertIn("Thread(target=run", source)
        self.assertIn("self.api.poll_events(150)", source)
        self.assertIn("self.api.request_cancel()", source)
        self.assertIn("if self._worker is not None:", source)

    def test_qt_and_legacy_launchers_are_separate(self):
        qt = (ROOT / "start.bat").read_text(encoding="utf-8")
        legacy = (ROOT / "start-legacy.bat").read_text(encoding="utf-8")
        self.assertIn("py %QT_PY_FLAG% -m gui_qt", qt)
        self.assertIn("Py_GIL_DISABLED", qt)
        self.assertIn("Py_GIL_DISABLED", (ROOT / "install.bat").read_text(encoding="utf-8"))
        # v0.1.8-a4 uses a dedicated entrypoint to keep the classic GUI,
        # while earlier versions launched the same frontend through main.py.
        self.assertTrue(
            "py main.py" in legacy
            or "py -m gui.legacy_runtime_v018_a4" in legacy,
            "Legacy launcher must start the CustomTkinter frontend.",
        )
        self.assertNotIn("-m gui_qt", legacy)
        self.assertIn("PySide6", (ROOT / "requirements-gui.txt").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
