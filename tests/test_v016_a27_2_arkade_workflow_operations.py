from __future__ import annotations

import json
import unittest
from pathlib import Path

from noark5_workflow.app import build_registry
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
        for sequence in catalog.for_profile("noark5"):
            self.assertNotIn("arkade5_noark5_test", sequence.operation_ids)
            self.assertNotIn("arkade5_pronom_analysis", sequence.operation_ids)

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

    def test_runtime_is_a272_and_version_is_final_a27(self):
        main = (ROOT / "main.py").read_text(encoding="utf-8")
        runtime = (ROOT / "gui" / "persistent_app_a27_2.py").read_text(encoding="utf-8")
        version = (ROOT / "version.py").read_text(encoding="utf-8")
        self.assertIn("from gui.persistent_app_a27_2 import run_gui", main)
        self.assertIn("class WorkflowApp(A27_1WorkflowApp)", runtime)
        self.assertIn('VERSION = "0.1.6-a27"', version)


if __name__ == "__main__":
    unittest.main()
