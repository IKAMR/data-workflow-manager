"""A10 fix: one run identity across Work, raw, events, manifests; PRONOM integrity.

All fixtures are synthetic; the real Test-04 Work was checked separately.
"""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

from noark5_workflow.core.artifact_identity import write_artifact_manifest
from noark5_workflow.core.events import WorkflowEvent
from noark5_workflow.core.job import Job, JobStatus
from noark5_workflow.core.raw_result_store import RawResultStore, persist_operation_raw_result
from noark5_workflow.core.work_job_store import WorkJobStore
from noark5_workflow.external_evidence.arkade5_pronom import (
    attach_arkade5_pronom_evidence,
    load_arkade5_pronom_statistics,
    summarize_arkade5_pronom_statistics,
)
from noark5_workflow.sinks.event_store import GenericEventStoreSink, read_event_store
from app.run_log_history_v018_a8 import RunLogStore


class A10RunIdentityTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.work = self.root / "work" / "dwm"
        self.work.mkdir(parents=True)
        self.uid = str(uuid4())
        self.run_id = "20261104T010203Z-abcdef12"

    def test_work_snapshot_and_events_link_to_one_run(self):
        job = Job("JOB-001", name="One test", status=JobStatus.READY, workflow_ids=["metadata_inventory"])
        job.job_uid = self.uid
        job._active_run_id = self.run_id
        job._active_run_kind = "workflow"
        store = WorkJobStore(self.work)
        store.write(job, event_kind="run.state")
        job.status = JobStatus.OK
        job.progress = 1.0
        job.next_operation_index = 1
        store.write(job, event_kind="run.finished")
        events = [json.loads(line) for line in store.events_path.read_text(encoding="utf-8").splitlines()]
        self.assertEqual([x["run_id"] for x in events], [self.run_id, self.run_id])
        self.assertEqual({x["job_uid"] for x in events}, {self.uid})
        self.assertEqual(json.loads(store.state_path.read_text())["last_run_id"], self.run_id)
        del job._active_run_id
        del job._active_run_kind
        store.write(job, event_kind="job.renamed")
        self.assertEqual(json.loads(store.state_path.read_text())["last_run_id"], self.run_id)
        recovered = store.load()
        self.assertEqual(recovered.status, JobStatus.OK)
        self.assertEqual(recovered.job_uid, self.uid)

    def test_run_log_records_uid_without_renaming_job_folders(self):
        writer = RunLogStore(self.work, "JOB-001").begin(
            job_name="One test", job_list_path="/separate/list.n5jobs", job_uid=self.uid,
        )
        try:
            self.assertEqual(writer.run_id.split("-")[0].endswith("Z"), True)
            meta = json.loads(writer.store.folder.joinpath(writer.run_id + ".json").read_text())
            self.assertEqual(meta["job_uid"], self.uid)
            self.assertEqual(meta["run_id"], writer.run_id)
        finally:
            writer.finish()

    def test_raw_result_keeps_uid_and_run_id_plus_legacy_read(self):
        path = self.work / "wf" / "results" / "raw-results.jsonl"
        item = RawResultStore(path).append(
            operation_id="metadata_inventory", test_id="metadata_inventory",
            definition_version="", ok=True, message="ok", job_id="JOB-001",
            job_uid=self.uid, run_id=self.run_id,
        )
        read = RawResultStore(path).get(item.result_id)
        self.assertEqual((read.job_uid, read.run_id), (self.uid, self.run_id))
        legacy = item.to_dict()
        legacy.pop("job_uid")
        self.assertEqual(type(item).from_dict(legacy).job_uid, "")

    def test_raw_result_from_context_uses_canonical_runtime_settings(self):
        ctx = SimpleNamespace(
            work_operations=self.work, input_root=self.root / "source",
            metadata={"job_id": "JOB-001", "run_id": self.run_id},
            settings={"_current_job_uid": self.uid, "_current_run_id": self.run_id},
            log=lambda message: None,
        )
        op = SimpleNamespace(raw_result_record=True, definition=SimpleNamespace(operation_id="metadata_inventory"))
        result = SimpleNamespace(ok=True, message="OK", data={}, warnings=[], outputs=[])
        envelope = persist_operation_raw_result(op, result, ctx)
        self.assertEqual(envelope.job_uid, self.uid)
        self.assertEqual(result.data["_result_ref"]["run_id"], self.run_id)
        self.assertEqual(result.data["_result_ref"]["job_uid"], self.uid)

    def test_artifact_manifest_has_job_and_run_identity(self):
        ctx = SimpleNamespace(
            work_operations=self.work, extraction_root=self.root / "source",
            metadata={"job_id": "JOB-001", "run_id": self.run_id},
            settings={"_current_job_uid": self.uid, "_current_run_id": self.run_id},
        )
        manifest = write_artifact_manifest(ctx, self.work / "noark5_reports" / "run", operation_id="build_noark5_depot_report")
        value = json.loads(manifest.read_text())
        self.assertEqual((value["job_uid"], value["run_id"]), (self.uid, self.run_id))

    def test_global_event_has_uid_and_run_id_without_schema_break(self):
        out = self.root / "runtime.events.jsonl"
        event = WorkflowEvent.now(
            "operation.completed", job_id="JOB-001", run_id=self.run_id,
            operation_id="metadata_inventory", data={"job_uid": self.uid, "result": {"n": 1}},
        )
        GenericEventStoreSink(out).handle(event)
        entry = read_event_store(out)[0]
        self.assertEqual(entry["schema_version"], 1)
        self.assertEqual((entry["job_uid"], entry["run_id"]), (self.uid, self.run_id))
        self.assertEqual(entry["data"]["result"], {"n": 1})


class A10PronomRepairTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.work = self.root / "work" / "dwm"
        self.import_id = "20261104-deadbeefcafe"
        self.import_root = self.work / "external_evidence" / "arkade5" / self.import_id
        self.import_root.mkdir(parents=True)
        self.manifest = self.import_root / "manifest.json"
        self.manifest.write_text(json.dumps({"import_id": self.import_id, "source": {"sha256": "old"}}))
        self.report = self.root / "arkade5_v2.13.1" / "noark5" / "arkade-report.json"
        self.report.parent.mkdir(parents=True)
        self.report.write_text("{}")
        self.stats = self.root / "arkade5_v2.13.1" / "pronom" / "filformatinfo-statistikk.csv"
        self.stats.parent.mkdir(parents=True)
        self.stats.write_text(
            "Format-ID,Filtype,Formatversjon,RAF-220301,Antall\n"
            "fmt/354,PDF/A,1b,Gyldig,1\n"
            "fmt/101,XML,1.0,Gyldig*,6\n"
            "x-fmt/280,XSD,,Gyldig,7\n", encoding="utf-8",
        )

    def _read(self):
        manifest = json.loads(self.manifest.read_text(encoding="utf-8"))
        normalized = load_arkade5_pronom_statistics(self.work, manifest)
        return manifest, summarize_arkade5_pronom_statistics(normalized, manifest=manifest)

    def test_discovery_of_report_without_csv_does_not_wipe_pronom(self):
        first = attach_arkade5_pronom_evidence(self.stats, work_operations=self.work, import_id=self.import_id)
        self.assertTrue(first["statistics_imported"])
        again = attach_arkade5_pronom_evidence(self.report, work_operations=self.work, import_id=self.import_id)
        self.assertTrue(again["statistics_imported"])
        manifest, summary = self._read()
        self.assertTrue(manifest["pronom_evidence"]["statistics"]["found"])
        self.assertEqual(summary["statistics"]["total_files"], 14)
        self.assertEqual(summary["statistics"]["row_count"], 3)

    def test_legacy_manifest_false_recovers_preserved_evidence(self):
        attach_arkade5_pronom_evidence(self.stats, work_operations=self.work, import_id=self.import_id)
        original = json.loads(self.manifest.read_text())
        original["pronom_evidence"]["statistics"] = {"found": False, "imported": False}
        self.manifest.write_text(json.dumps(original))
        manifest, summary = self._read()
        self.assertEqual(summary["statistics"]["total_files"], 14)
        res = attach_arkade5_pronom_evidence(self.report, work_operations=self.work, import_id=self.import_id)
        self.assertTrue(res["statistics_imported"])
        self.assertTrue(json.loads(self.manifest.read_text())["pronom_evidence"]["statistics"]["imported"])

    def test_tampered_preserved_csv_is_not_counted(self):
        attach_arkade5_pronom_evidence(self.stats, work_operations=self.work, import_id=self.import_id)
        copy = self.import_root / "source" / "filformatinfo-statistikk.csv"
        copy.write_text("corrupted", encoding="utf-8")
        manifest, summary = self._read()
        self.assertFalse(summary["available"])
        res = attach_arkade5_pronom_evidence(self.report, work_operations=self.work, import_id=self.import_id)
        self.assertFalse(res["statistics_imported"])

    def test_other_import_cannot_borrow_this_pronom_evidence(self):
        attach_arkade5_pronom_evidence(self.stats, work_operations=self.work, import_id=self.import_id)
        foreign = self.work / "external_evidence" / "arkade5" / "other-import"
        foreign.mkdir()
        (foreign / "manifest.json").write_text(json.dumps({"import_id": "other-import"}))
        result = attach_arkade5_pronom_evidence(self.report, work_operations=self.work, import_id="other-import")
        self.assertFalse(result["statistics_imported"])
        self.assertIsNone(load_arkade5_pronom_statistics(self.work, json.loads((foreign / "manifest.json").read_text())))


if __name__ == "__main__":
    unittest.main()
