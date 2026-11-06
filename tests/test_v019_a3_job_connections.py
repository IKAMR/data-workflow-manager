"""a3: real Work identity, offline links and consent-based Source/Work reconnection.

Small temporary directories only. No user's extraction files or network access.
"""
from __future__ import annotations

import ast
import json
import shutil
import tempfile
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

from app.application_api import DwmApiError
from app.job_connections_v019_a3 import (
    _same_path, apply_source_link, apply_work_link, inspect_job_locations,
    preview_source_link, preview_work_link,
)
from noark5_workflow.core.job import Job, JobBatch, JobStatus
from noark5_workflow.core.work_job_store import WorkJobStore

ROOT = Path(__file__).resolve().parents[1]


class TinyWorkbench:
    """Minimal API adapter backed by the *real* WorkJobStore contract."""

    def __init__(self, job, manifest):
        self._guard = threading.Lock()
        self._batch = JobBatch()
        self._batch.add(job)
        self._work_references = {job.job_id: Path(manifest)}
        self._unavailable_work_ids = frozenset()
        self._path = Path(manifest).parent.parent / "lists" / "active.n5jobs"
        self._active_job_id = job.job_id
        self._dirty = False
        self._running = False
        self.events = []

    def _assert_idle(self):
        if self._running:
            raise DwmApiError("Jobb kjører")

    def _require_job(self, job_id):
        result = self._batch.get(job_id)
        if result is None:
            raise DwmApiError("Ukjent jobb")
        return result

    def _view(self, job, position):
        return SimpleNamespace(
            job_id=job.job_id, name=job.name, status=job.status.value,
            progress=job.progress, source_root=str(job.source_root or ""),
            source_extraction=str(job.source_extraction or ""),
            effective_work_operations=(str(self._work_references[job.job_id].parent)
                                       if job.job_id in self._work_references else ""),
        )

    def workspace(self):
        return SimpleNamespace(jobs=[self._view(job, i) for i, job in enumerate(self._batch.jobs(), 1)])

    def work_job_info(self, job_id):
        job = self._require_job(job_id)
        ref = self._work_references.get(job_id)
        return {"job_uid": job.job_uid, "work_manifest": str(ref or ""),
                "work_is_authoritative": bool(ref)}

    def update_storage(self, job_id, changes):
        with self._guard:
            self._assert_idle()
            job = self._require_job(job_id)
            for key, value in changes.items():
                setattr(job, key, Path(value) if value else None)
            WorkJobStore(self._work_references[job_id].parent).write(
                job, event_kind="job.storage_changed",
            )
            self._dirty = True
        return job

    def _emit(self, kind, job=None, *, message=""):
        self.events.append((kind, message))


class A3JobConnectionTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.source = self.root / "source" / "extract-001"
        self.source.mkdir(parents=True)
        (self.source / "info.xml").write_text("<info>001</info>", encoding="utf-8")
        self.aip = self.root / "aip"
        self.aip.mkdir()
        self.work = self.root / "work" / "repository_operations" / "dwm"
        self.work.mkdir(parents=True)
        self.job = Job(
            job_id="JOB-001", name="Uttrekk 001", profile_id="noark5",
            source_root=self.source, source_extraction=self.source,
            work_root=self.root / "work", work_operations=self.work.parent,
            archive_root=self.aip, workflow_ids=["metadata_inventory", "validate_xml_schema"],
        )
        self.job.job_uid = str(uuid4())
        self.job.status = JobStatus.OK
        self.job.progress = 1.0
        self.job.next_operation_index = 2
        self.ref = WorkJobStore(self.work).write(self.job, event_kind="run.finished")
        self.api = TinyWorkbench(self.job, self.ref)

    def _move_work(self):
        new_base = self.root / "new-volume" / "repository_operations"
        new_base.parent.mkdir(parents=True, exist_ok=True)
        self.work.parent.rename(new_base)
        self.new_work = new_base / "dwm"
        return self.new_work

    def test_status_distinguishes_connected_source_and_work(self):
        health = inspect_job_locations(self.api)[0]
        self.assertEqual(health.work_label, "Tilkoblet")
        self.assertEqual(health.source_label, "Tilgjengelig")
        self.assertEqual(health.job_uid, self.job.job_uid)
        self.assertEqual(health.last_known_status, JobStatus.OK.value)

    def test_offline_work_never_becomes_approved_or_current_by_assumption(self):
        self._move_work()
        health = inspect_job_locations(self.api)[0]
        self.assertEqual(health.work_label, "Frakoblet")
        self.assertIn("sist kjente", health.work_detail)
        self.assertEqual(self.job.status, JobStatus.OK)
        self.assertFalse(self.ref.exists())

    def test_returned_work_needs_explicit_reconnection(self):
        self.api._unavailable_work_ids = frozenset({"JOB-001"})
        self.assertEqual(inspect_job_locations(self.api)[0].work_label, "Gjenåpne")
        preview = preview_work_link(self.api, "JOB-001", self.work)
        with self.assertRaises(DwmApiError):
            apply_work_link(self.api, preview)
        result = apply_work_link(self.api, preview, consent=True)
        self.assertEqual(result.job_id, "JOB-001")
        self.assertFalse(self.api._unavailable_work_ids)
        self.assertEqual(inspect_job_locations(self.api)[0].work_label, "Tilkoblet")

    def test_moved_work_recovery_preserves_uid_status_and_history(self):
        new_work = self._move_work()
        preview = preview_work_link(self.api, "JOB-001", new_work)
        self.assertEqual(preview.job_uid, self.job.job_uid)
        self.assertTrue(_same_path(Path(preview.work_operations_after), new_work.parent))
        self.assertFalse(self.api._dirty)
        result = apply_work_link(self.api, preview, consent=True)
        self.assertEqual(result.job_id, "JOB-001")
        stored = WorkJobStore(new_work).load()
        self.assertEqual(stored.job_uid, self.job.job_uid)
        self.assertEqual(stored.status, JobStatus.OK)
        self.assertEqual(stored.next_operation_index, 2)
        self.assertEqual(stored.workflow_ids, self.job.workflow_ids)
        self.assertTrue(_same_path(stored.work_operations, new_work.parent))
        self.assertTrue(self.api._dirty)  # .n5jobs must be saved explicitly
        self.assertTrue(_same_path(self.api._work_references["JOB-001"], new_work / "job.json"))
        self.assertEqual((self.source / "info.xml").read_text(), "<info>001</info>")

    def test_preview_work_is_read_only(self):
        new_work = self._move_work()
        manifest_before = (new_work / "job.json").read_bytes()
        state_before = (new_work / "job-state.json").read_bytes()
        events_before = (new_work / "job-events.jsonl").read_bytes()
        preview_work_link(self.api, "JOB-001", new_work)
        self.assertEqual((new_work / "job.json").read_bytes(), manifest_before)
        self.assertEqual((new_work / "job-state.json").read_bytes(), state_before)
        self.assertEqual((new_work / "job-events.jsonl").read_bytes(), events_before)
        self.assertFalse(self.api._dirty)

    def test_different_uid_cannot_steal_a_work_reference(self):
        other = self.root / "other" / "dwm"
        other.mkdir(parents=True)
        foreign = Job(job_id="JOB-001", name="Other", profile_id="noark5",
                      work_operations=other.parent)
        foreign.job_uid = str(uuid4())
        WorkJobStore(other).write(foreign, event_kind="created")
        with self.assertRaisesRegex(DwmApiError, "ID"):
            preview_work_link(self.api, "JOB-001", other)
        self.assertEqual(self.api._work_references["JOB-001"], self.ref)

    def test_copied_work_is_not_mistaken_for_moved_work(self):
        copied = self.root / "copied" / "repository_operations" / "dwm"
        copied.parent.mkdir(parents=True)
        shutil.copytree(self.work, copied)
        with self.assertRaisesRegex(DwmApiError, "fremdeles tilgjengelig"):
            preview_work_link(self.api, "JOB-001", copied)

    def test_wrong_work_structure_cannot_be_guessed(self):
        new_work = self._move_work()
        wrong = new_work.parent / "renamed-subfolder"
        new_work.rename(wrong)
        with self.assertRaisesRegex(DwmApiError, "interne struktur"):
            preview_work_link(self.api, "JOB-001", wrong)

    def test_changed_manifest_after_preview_is_rejected(self):
        new_work = self._move_work()
        preview = preview_work_link(self.api, "JOB-001", new_work)
        p = new_work / "job.json"
        p.write_text(p.read_text(encoding="utf-8") + "\n", encoding="utf-8")
        with self.assertRaisesRegex(DwmApiError, "endret"):
            apply_work_link(self.api, preview, consent=True)
        self.assertEqual(self.api._work_references["JOB-001"], self.ref)

    def test_source_preview_and_relink_preserve_job_identity(self):
        new_source = self.root / "new-source" / "extract-001"
        new_source.parent.mkdir()
        self.source.rename(new_source)
        preview = preview_source_link(self.api, "JOB-001", new_source)
        self.assertEqual(preview.info_check, "Ikke sammenlignbar")
        self.assertIn("source_extraction", dict(preview.updates))
        self.assertIn("source_root", dict(preview.updates))
        self.assertFalse(self.api._dirty)
        with self.assertRaises(DwmApiError):
            apply_source_link(self.api, preview)
        apply_source_link(self.api, preview, consent=True)
        self.assertEqual(self.job.job_uid, self.api._require_job("JOB-001").job_uid)
        self.assertTrue(_same_path(self.api._require_job("JOB-001").source_extraction, new_source))
        self.assertTrue(_same_path(self.api._require_job("JOB-001").source_root, new_source))
        self.assertTrue(_same_path(WorkJobStore(self.work).load().source_extraction, new_source))
        self.assertTrue(self.api._dirty)

    def test_changed_info_xml_between_available_sources_is_rejected(self):
        new_source = self.root / "new-source"
        new_source.mkdir()
        (new_source / "info.xml").write_text("<info>different</info>", encoding="utf-8")
        with self.assertRaisesRegex(DwmApiError, "info.xml"):
            preview_source_link(self.api, "JOB-001", new_source)
        self.assertEqual(self.job.source_extraction, self.source)

    def test_matching_info_xml_is_evidence_not_automatic_verification(self):
        new_source = self.root / "new-source"
        new_source.mkdir()
        shutil.copy2(self.source / "info.xml", new_source / "info.xml")
        preview = preview_source_link(self.api, "JOB-001", new_source)
        self.assertIn("SHA-256", preview.info_check)
        self.assertTrue(preview.warnings)
        self.assertFalse(self.api._dirty)

    def test_source_preview_rejects_work_and_aip_overlap(self):
        with self.assertRaisesRegex(DwmApiError, "overlappe"):
            preview_source_link(self.api, "JOB-001", self.work)
        with self.assertRaisesRegex(DwmApiError, "overlappe"):
            preview_source_link(self.api, "JOB-001", self.aip)

    def test_reconnection_does_not_touch_offline_status_placeholders(self):
        self.api._unavailable_work_ids = frozenset({"JOB-001"})
        with self.assertRaisesRegex(DwmApiError, "Work"):
            preview_source_link(self.api, "JOB-001", self.source)

    def test_source_changed_during_confirmation_must_be_rechecked(self):
        new_source = self.root / "new-source"
        new_source.mkdir()
        info = new_source / "info.xml"
        info.write_text("<info>001</info>", encoding="utf-8")
        preview = preview_source_link(self.api, "JOB-001", new_source)
        info.write_text("<info>001 changed</info>", encoding="utf-8")
        with self.assertRaises(DwmApiError):
            apply_source_link(self.api, preview, consent=True)
        self.assertEqual(self.job.source_extraction, self.source)

    def test_work_status_detects_replaced_manifest(self):
        manifest = self.work / "job.json"
        value = json.loads(manifest.read_text(encoding="utf-8"))
        value["job_uid"] = str(uuid4())
        manifest.write_text(json.dumps(value), encoding="utf-8")
        self.assertEqual(inspect_job_locations(self.api)[0].work_label, "ID-konflikt")
        self.assertEqual(self.api._work_references["JOB-001"], self.ref)

    def test_same_work_cannot_be_claimed_by_two_list_jobs(self):
        new_work = self._move_work()
        duplicate = Job(job_id="JOB-002", name="Other", profile_id="noark5")
        duplicate.job_uid = self.job.job_uid
        self.api._batch.add(duplicate)
        with self.assertRaisesRegex(DwmApiError, "samme varige Work-ID"):
            preview_work_link(self.api, "JOB-001", new_work)

    def test_manifest_symlink_outside_work_is_rejected(self):
        foreign = self.root / "foreign.json"
        shutil.copy2(self.ref, foreign)
        self.ref.unlink()
        try:
            self.ref.symlink_to(foreign)
        except (OSError, NotImplementedError):
            self.skipTest("Filsymbolske lenker krever ekstra rettigheter her")
        self.assertEqual(inspect_job_locations(self.api)[0].work_label, "Ugyldig")
        with self.assertRaises(DwmApiError):
            preview_work_link(self.api, "JOB-001", self.work)

    def test_draft_work_status_is_explicit(self):
        self.api._work_references.clear()
        health = inspect_job_locations(self.api)[0]
        self.assertEqual(health.work_label, "Utkast")
        self.assertIn("ikke registrert", health.work_detail)

    def test_running_job_cannot_relink(self):
        self.api._running = True
        with self.assertRaisesRegex(DwmApiError, "kjører"):
            preview_work_link(self.api, "JOB-001", self.work)
        with self.assertRaisesRegex(DwmApiError, "kjører"):
            preview_source_link(self.api, "JOB-001", self.source)


class A3WiringTests(unittest.TestCase):
    def test_new_qt_api_is_real_entrypoint(self):
        qt = (ROOT / "gui_qt" / "__main__.py").read_text(encoding="utf-8")
        main = (ROOT / "gui_qt" / "main_window.py").read_text(encoding="utf-8")
        ast.parse(qt)
        ast.parse(main)
        # a3 commands remain available through later facade subclasses.
        # Do not freeze the Qt entrypoint to one historical alpha version.
        self.assertRegex(qt, r"from app\.workbench_api_v019_a\d+ import DwmWorkbenchAPI")
        a3_api = (ROOT / "app" / "workbench_api_v019_a3.py").read_text(encoding="utf-8")
        self.assertIn("class DwmWorkbenchAPI", a3_api)
        for marker in (
            "job_location_health()", "preview_work_reconnection", "reconnect_work(",
            "preview_source_reconnection", "reconnect_source(",
            "Work- og Source-status", "Koble til frakoblet Work", "Tilknytning…",
        ):
            self.assertIn(marker, main)
        self.assertNotIn("customtkinter", main)

    def test_existing_a10_recovery_and_gui_structure_remain(self):
        main = (ROOT / "gui_qt" / "main_window.py").read_text(encoding="utf-8")
        for label in ("self.api.recover_job_from_work(selected)",
                      "self.api.migrate_job_to_work(self._active_id)",
                      "on_generate_report=self._a12_open_selected_report", "_a12_open_result_center"):
            self.assertIn(label, main)


if __name__ == "__main__":
    unittest.main()
