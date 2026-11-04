"""a12: read-only result index and safe multi-job report selection.

Headless tests deliberately do not require Qt or the old Tk GUI.
"""
from __future__ import annotations

import ast
import json
import tempfile
import unittest
from pathlib import Path
from threading import Lock
from types import SimpleNamespace
from unittest.mock import MagicMock

from app.result_center_v018_a12 import discover_results, depot_facts, archive_part_rows
from noark5_workflow.core.job import Job, JobBatch

ROOT = Path(__file__).resolve().parents[1]


class ResultCatalogTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.work = Path(self.tmp.name) / "Work" / "dwm"
        self.work.mkdir(parents=True)

    def write(self, rel, content="{}"):
        file = self.work / rel
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text(content, encoding="utf-8")
        return file

    def test_empty_and_unavailable_work_are_read_only(self):
        missing = self.work / "missing"
        self.assertFalse(missing.exists())
        state = discover_results(missing)
        self.assertEqual(state.artifacts, ())
        self.assertFalse(missing.exists())
        self.assertEqual(discover_results(self.work).artifacts, ())

    def test_known_dwm_work_results_are_grouped_without_source_scan(self):
        report = self.write("noark5_reports/depot_validation/run/depot_validation_report.json", json.dumps({
            "report_type": "noark5_depot_validation",
            "summary": {"archive_part_count": 2},
            "assessment": {"status": "Vurderes"},
            "archive_parts": [{"archive_part": {"title": "AD 1"}}],
        }))
        paths = (
            "noark5_tests/xpath/run/master-results.json",
            "noark5_tests/schema/run/xml-validation-sample.json",
            "noark5_views/run/whole_extraction_overview.json",
            "external_evidence/arkade5/id/manifest.json",
            "external_evidence/arkade5/id/normalized/pronom_statistics.json",
            "external_evidence/kdrs_query/id/normalized/standard.json",
            "wf/results/raw-results.jsonl",
        )
        for path in paths:
            self.write(path)
        source = self.work / "content" / "DOKUMENT" / "never-visit.json"
        source.parent.mkdir(parents=True)
        source.write_text("private", encoding="utf-8")
        found = discover_results(self.work)
        self.assertEqual(len(found.artifacts), len(paths) + 1)
        self.assertEqual(found.depot_report_path, report.resolve())
        self.assertEqual(archive_part_rows(found.depot_report)[0]["archive_part"]["title"], "AD 1")
        self.assertIn(("Arkivdeler", "2"), depot_facts(found.depot_report))
        self.assertNotIn(source.resolve(), [item.path for item in found.artifacts])
        self.assertTrue(found.by_category["PRONOM"])
        self.assertTrue(found.by_category["KDRS Query"])

    def test_reports_with_invalid_json_are_not_presented_as_valid(self):
        self.write("noark5_reports/depot_validation/run/depot_validation_report.json", "not-json")
        found = discover_results(self.work)
        self.assertIsNone(found.depot_report)
        self.assertTrue(any("ugyldig" in item for item in found.warnings))

    def test_old_report_pronom_count_is_not_passed_off_as_current(self):
        self.write("external_evidence/arkade5/i/normalized/pronom_statistics.json")
        self.write("noark5_reports/depot_validation/run/depot_validation_report.json", json.dumps({
            "report_type": "noark5_depot_validation",
            "external_validation": {"arkade5": {"pronom_summary": {"statistics_imports": 0}}},
        }))
        overview = discover_results(self.work)
        self.assertTrue(overview.by_category["PRONOM"])
        self.assertTrue(any("PRONOM-filer finnes" in warning for warning in overview.warnings))

    def test_symlink_to_source_outside_work_is_rejected(self):
        external = Path(self.tmp.name) / "Source" / "secret.json"
        external.parent.mkdir()
        external.write_text("secret", encoding="utf-8")
        link = self.work / "external_evidence" / "kdrs_query" / "imp" / "normalized" / "outside.json"
        link.parent.mkdir(parents=True)
        try:
            link.symlink_to(external)
        except (NotImplementedError, OSError):
            self.skipTest("Systemet tillater ikke symlinks")
        result = discover_results(self.work)
        self.assertNotIn(external.resolve(), [item.path for item in result.artifacts])

    def test_many_results_are_bounded(self):
        for i in range(270):
            self.write(f"noark5_tests/xpath/run/results/kdrs_{i:04d}.json")
        found = discover_results(self.work)
        self.assertLessEqual(len(found.by_category["XPath / Noark 5"]), 250)
        self.assertTrue(any("avkortet" in warning for warning in found.warnings))


class ReportSelectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = ROOT / "app" / "workbench_api_v018_a3.py"
        source = ast.parse(path.read_text(encoding="utf-8"))
        workbench = next(node for node in source.body if isinstance(node, ast.ClassDef)
                         and node.name == "DwmWorkbenchAPI")
        selected = [node for node in workbench.body
                    if isinstance(node, ast.FunctionDef) and node.name in
                    {"report_candidates", "selected_report_jobs"}]
        cls.assert_methods = set(node.name for node in selected)
        methods = []
        for node in selected:
            node.decorator_list = []
            methods.append(node)
        scope = {"Path": Path, "Iterable": tuple,
                 "DwmApiError": type("DwmApiError", (RuntimeError,), {}),
                 "Job": Job}
        exec(compile(ast.fix_missing_locations(ast.Module(body=methods, type_ignores=[])),
                     str(path), "exec"), scope)
        cls.report_candidates = staticmethod(scope["report_candidates"])
        cls.selected_report_jobs = staticmethod(scope["selected_report_jobs"])

    def _facade(self):
        batch = JobBatch()
        noark = batch.new_job(None)
        noark.name = "Noark 5 uttrekk"
        noark.profile_id = "noark5"
        noark.work_operations = Path("Work/Noark")
        other = batch.new_job(None)
        other.name = "SIARD uttrekk"
        other.profile_id = "siard"
        other.work_operations = Path("Work/Siard")
        fake = SimpleNamespace(
            _guard=Lock(), _batch=batch, _unavailable_work_ids=frozenset(),
            _assert_idle=lambda: None,
            _require_job=lambda job_id: batch.get(job_id) or (_ for _ in ()).throw(ValueError(job_id)),
            _view=lambda job, position: SimpleNamespace(effective_work_operations=str(job.work_operations)),
        )
        return fake, noark, other

    def test_noark_is_selectable_and_siard_is_excluded(self):
        fake, noark, other = self._facade()
        candidates = self.report_candidates(fake)
        self.assertEqual([r["enabled"] for r in candidates], [True, False])
        self.assertEqual([r["profile_id"] for r in candidates], ["noark5", "siard"])
        with self.assertRaises(RuntimeError):
            self.selected_report_jobs(fake, [noark.job_id, other.job_id])

    def test_report_receives_deepcopies_and_effective_work_paths(self):
        fake, noark, _other = self._facade()
        result = self.selected_report_jobs(fake, [noark.job_id])
        self.assertIsNot(result[0], noark)
        self.assertEqual(result[0]._effective_work_operations, noark.work_operations)
        result[0].name = "changed"
        self.assertEqual(noark.name, "Noark 5 uttrekk")

    def test_duplicate_job_and_offline_work_are_rejected(self):
        fake, noark, other = self._facade()
        with self.assertRaises(RuntimeError):
            self.selected_report_jobs(fake, [noark.job_id, noark.job_id])
        fake._unavailable_work_ids = frozenset([noark.job_id])
        with self.assertRaises(RuntimeError):
            self.selected_report_jobs(fake, [noark.job_id])

    def test_multiple_noark_jobs_can_use_same_existing_report_engine(self):
        fake, first, second = self._facade()
        second.profile_id = "noark5"
        selected = self.selected_report_jobs(fake, (first.job_id, second.job_id))
        self.assertEqual(len(selected), 2)
        self.assertEqual([job.job_id for job in selected], [first.job_id, second.job_id])
        self.assertIsNot(selected[0], first)
        self.assertIsNot(selected[1], second)

    def test_report_target_inside_source_or_aip_is_blocked(self):
        gui = ROOT / "gui_qt" / "report_selected_v018_a12.py"
        document = ast.parse(gui.read_text(encoding="utf-8"))
        dialog = next(node for node in document.body if isinstance(node, ast.ClassDef)
                      and node.name == "SelectedReportDialog")
        method = next(node for node in dialog.body if isinstance(node, ast.FunctionDef)
                      and node.name == "_protected_destination")
        method.decorator_list = []
        namespace = {"Path": Path}
        exec(compile(ast.fix_missing_locations(ast.Module(body=[method], type_ignores=[])),
                     str(gui), "exec"), namespace)
        check = namespace["_protected_destination"]
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source = root / "source"; source.mkdir()
            aip = root / "aip"; aip.mkdir()
            export = root / "reports"; export.mkdir()
            job = SimpleNamespace(job_id="JOB-001", active_extraction_root=source,
                                  archive_root=aip, output_root=None)
            self.assertIn("Source", check(source / "DOKUMENT", [job]))
            self.assertIn("AIP", check(aip, [job]))
            self.assertEqual(check(export, [job]), "")

    def test_qt_wiring_reuses_old_a20_reporting_engine(self):
        gui = (ROOT / "gui_qt" / "report_selected_v018_a12.py").read_text(encoding="utf-8")
        main = (ROOT / "gui_qt" / "main_window.py").read_text(encoding="utf-8")
        for needed in ("write_reconnectable_report", "write_report_package",
                       "ReportOptions", "confirm_overwrite=confirm", "selected_report_jobs(ids)",
                       "Lag og åpne rapport", "Velg alle Noark 5-jobber"):
            self.assertIn(needed, gui)
        for needed in ("_a12_open_selected_report", "_a12_open_result_center",
                       "Lag rapport / samlerapport", "Resultatvisninger"):
            self.assertIn(needed, main)
        self.assertNotIn("customtkinter", gui)


if __name__ == "__main__":
    unittest.main()
