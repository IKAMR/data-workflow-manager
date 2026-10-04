from __future__ import annotations

import re
import unittest
from pathlib import Path

from noark5_workflow.app import build_registry
from noark5_workflow.core.job import Job, JobStatus
from app.operation_metadata import display_category, short_name
from app.workflow_sequence import load_workflow_sequences

ROOT = Path(__file__).resolve().parents[1]


class V016A272ArkadeWorkflowOperationTests(unittest.TestCase):
    def test_arkade_cli_operations_are_registered_in_noark5_profile(self):
        ids = {op.definition.operation_id for op in build_registry().all()}
        self.assertIn("arkade5_noark5_test", ids)
        self.assertIn("arkade5_pronom_analysis", ids)

    def test_catalog_has_short_names_and_categories(self):
        self.assertEqual(short_name("arkade5_noark5_test"), "Arkade Noark 5")
        self.assertEqual(display_category("arkade5_noark5_test"), "Kontroll")
        self.assertEqual(short_name("arkade5_pronom_analysis"), "Arkade PRONOM")
        self.assertEqual(display_category("arkade5_pronom_analysis"), "Analyse")

    def test_default_sequences_are_unchanged_in_a272(self):
        catalog = load_workflow_sequences()
        standard = catalog.get("noark5_standard")
        self.assertEqual(
            standard.operation_ids,
            (
                "metadata_inventory",
                "validate_xml_schema",
                "analyse_arkivstruktur",
                "run_noark5_xpath_tests_2026",
                "import_arkade5_reports",
                "compose_noark5_views",
                "build_noark5_depot_report",
            ),
        )

    def test_predefined_sequences_have_exact_contents_and_order(self):
        catalog = load_workflow_sequences()
        self.assertEqual(
            catalog.get("noark5_standard_arkade").operation_ids,
            (
                "metadata_inventory",
                "validate_xml_schema",
                "analyse_arkivstruktur",
                "arkade5_noark5_test",
                "arkade5_pronom_analysis",
                "run_noark5_xpath_tests_2026",
                "import_arkade5_reports",
                "compose_noark5_views",
                "build_noark5_depot_report",
            ),
        )
        self.assertEqual(
            catalog.get("noark5_dwm_only").operation_ids,
            (
                "metadata_inventory",
                "validate_xml_schema",
                "analyse_arkivstruktur",
                "run_noark5_xpath_tests_2026",
                "compose_noark5_views",
                "build_noark5_depot_report",
            ),
        )
        self.assertEqual(
            catalog.get("noark5_arkade_only").operation_ids,
            ("arkade5_noark5_test", "arkade5_pronom_analysis"),
        )

    def test_new_sequences_can_be_applied_to_job_without_breaking_cursor_contract(self):
        catalog = load_workflow_sequences()
        for sequence_id in (
            "noark5_standard_arkade", "noark5_dwm_only", "noark5_arkade_only",
        ):
            sequence = catalog.get(sequence_id)
            job = Job(
                job_id="JOB-1",
                profile_id="noark5",
                workflow_ids=["legacy_operation"],
                status=JobStatus.WAITING,
                next_operation_index=3,
            )
            job.set_workflow(sequence.operation_ids)
            self.assertEqual(job.workflow_ids, list(sequence.operation_ids))
            self.assertEqual(job.status, JobStatus.READY)
            self.assertEqual(job.next_operation_index, 0)

    def test_operations_reuse_a26_arkade_runner_and_auto_import(self):
        source = (ROOT / "noark5_workflow" / "operations" / "run_arkade5_cli.py").read_text(encoding="utf-8")
        self.assertIn("build_arkade5_plan", source)
        self.assertIn("run_arkade5_plan", source)
        self.assertIn("import_arkade5_run_outputs", source)
        self.assertNotIn("subprocess", source)

    def test_workflow_auto_import_uses_a26_api_without_settings_keyword(self):
        source = (ROOT / "noark5_workflow" / "operations" / "run_arkade5_cli.py").read_text(encoding="utf-8")
        self.assertIn("import_arkade5_run_outputs(", source)
        self.assertIn("on_progress=ctx.log", source)
        self.assertNotIn("settings=ctx.settings", source)

    def test_operations_require_cli_source_and_work(self):
        source = (ROOT / "noark5_workflow" / "operations" / "run_arkade5_cli.py").read_text(encoding="utf-8")
        self.assertIn("Work - operations må være definert", source)
        self.assertIn("Source - extraction må være definert", source)
        self.assertIn("Arkade 5 CLI må være konfigurert", source)

    def test_runtime_is_a272_and_version_is_current_v016_alpha(self):
        main = (ROOT / "main.py").read_text(encoding="utf-8")
        runtime = (ROOT / "gui" / "persistent_app_a27_2.py").read_text(encoding="utf-8")
        version = (ROOT / "version.py").read_text(encoding="utf-8")
        self.assertIn("from gui.persistent_app_a27_2 import run_gui", main)
        self.assertIn("class WorkflowApp(A27_1WorkflowApp)", runtime)
        match = re.search(r'VERSION\s*=\s*"0\.1\.6-a(\d+)"', version)
        self.assertIsNotNone(match, version)
        self.assertGreaterEqual(int(match.group(1)), 27)


if __name__ == "__main__":
    unittest.main()
