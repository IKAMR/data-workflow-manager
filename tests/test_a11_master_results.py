from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from noark5_workflow.analysis.master_results import (
    MasterResultError,
    build_master_result_set,
    iter_master_entries,
    load_master_result_set,
    load_master_values,
)

ROOT = Path(__file__).resolve().parents[1]


class A11MasterResultTests(unittest.TestCase):
    def _run_dir(self, profile: str = "normal"):
        temp = tempfile.TemporaryDirectory()
        run_dir = Path(temp.name)
        (run_dir / "results").mkdir()
        index = {
            "result_set_format_version": 2,
            "catalog_id": "test-catalog",
            "execution_profile": profile,
            "tests": [
                {
                    "test_id": "kdrs.c01",
                    "status": "ok",
                    "file": "results/kdrs_c01.json",
                    "test_point": "N5.04",
                    "normalized_test_point": "N5.04",
                },
                {
                    "test_id": "kdrs.c02",
                    "status": "error",
                    "file": "results/kdrs_c02.json",
                    "test_point": "N5.05/06",
                    "normalized_test_point": None,
                },
            ],
        }
        (run_dir / "index.json").write_text(json.dumps(index), encoding="utf-8")
        (run_dir / "results" / "kdrs_c01.json").write_text(
            json.dumps({
                "result_format_version": 2,
                "test_id": "kdrs.c01",
                "status": "ok",
                "source_xml": "arkivstruktur.xml",
                "definition": {
                    "name": "Arkiv i arkivstrukturen",
                    "tags": ["archive", "archive_creator"],
                },
                "values": {"archive_count": 1, "archive_creator_count": 1},
            }),
            encoding="utf-8",
        )
        (run_dir / "results" / "kdrs_c02.json").write_text(
            json.dumps({
                "result_format_version": 2,
                "test_id": "kdrs.c02",
                "status": "error",
                "source_xml": "arkivstruktur.xml",
                "definition": {
                    "name": "Arkivdeler",
                    "tags": ["archive_part", "summary"],
                },
                "error": "syntetisk feil",
            }),
            encoding="utf-8",
        )
        return temp, run_dir

    def test_model_declares_individual_results_as_master(self):
        model = json.loads(
            (ROOT / "config" / "noark5" / "master_result_model.json").read_text(encoding="utf-8")
        )
        self.assertEqual(model["principles"]["master_values"], "individual_normal_test_results")
        self.assertTrue(model["principles"]["reference_sources_are_not_master"])
        roles = {row["source_id"]: row["role"] for row in model["reference_sources"]}
        self.assertEqual(roles["legacy_u1"], "comparison_only")
        self.assertEqual(roles["legacy_u2"], "comparison_only")
        self.assertEqual(roles["arkade5"], "external_evidence_comparison")

    def test_normal_run_materializes_master_index_without_copying_values(self):
        temp, run_dir = self._run_dir()
        self.addCleanup(temp.cleanup)
        master_path = build_master_result_set(run_dir)
        master = load_master_result_set(master_path)
        entry = master["tests"][0]
        self.assertEqual(entry["role"], "master")
        self.assertEqual(entry["result_file"], "results/kdrs_c01.json")
        self.assertNotIn("values", entry)
        self.assertEqual(master["summary"]["available_master_results"], 1)

    def test_master_values_are_loaded_from_individual_result_file(self):
        temp, run_dir = self._run_dir()
        self.addCleanup(temp.cleanup)
        master_path = build_master_result_set(run_dir)
        self.assertEqual(load_master_values(master_path, "kdrs.c01")["archive_count"], 1)

    def test_entity_projection_uses_test_tags(self):
        temp, run_dir = self._run_dir()
        self.addCleanup(temp.cleanup)
        master_path = build_master_result_set(run_dir)
        entries = list(iter_master_entries(master_path, entity="archive"))
        self.assertEqual([entry["test_id"] for entry in entries], ["kdrs.c01"])
        master = load_master_result_set(master_path)
        entities = {row["entity"]: row["test_ids"] for row in master["entities"]}
        self.assertIn("kdrs.c01", entities["archive_creator"])

    def test_failed_individual_test_is_preserved_but_not_available_master_value(self):
        temp, run_dir = self._run_dir()
        self.addCleanup(temp.cleanup)
        master_path = build_master_result_set(run_dir)
        master = load_master_result_set(master_path)
        failed = next(row for row in master["tests"] if row["test_id"] == "kdrs.c02")
        self.assertEqual(failed["role"], "master_test_unavailable")
        self.assertEqual(master["summary"]["unavailable_master_results"], 1)
        self.assertEqual(list(iter_master_entries(master_path, entity="archive_part")), [])

    def test_regression_profile_cannot_be_promoted_to_master(self):
        temp, run_dir = self._run_dir(profile="regression")
        self.addCleanup(temp.cleanup)
        with self.assertRaises(MasterResultError):
            build_master_result_set(run_dir)

    def test_standard_sequences_no_longer_depend_on_u1_u2_transition_operations(self):
        data = json.loads((ROOT / "config" / "workflow_sequences.json").read_text(encoding="utf-8"))
        standard = next(row for row in data["sequences"] if row["sequence_id"] == "noark5_standard")
        self.assertIn("run_noark5_xpath_tests_2026", standard["operation_ids"])
        self.assertNotIn("analyse_noark5_u1", standard["operation_ids"])
        self.assertNotIn("analyse_noark5_core", standard["operation_ids"])
        self.assertNotIn("run_noark5_xpath_regression_2026", standard["operation_ids"])

    def test_documentation_locks_reference_source_role(self):
        text = (ROOT / "docs" / "NOARK5-MASTER-RESULTS.md").read_text(encoding="utf-8")
        self.assertIn("individuelle Noark 5-testpunktene er master", text)
        self.assertIn("U1", text)
        self.assertIn("U2", text)
        self.assertIn("Arkade 5", text)
        self.assertIn("CLI", text)

    def test_normal_operation_materializes_master_but_regression_does_not(self):
        text = (ROOT / "noark5_workflow" / "operations" / "run_noark5_xpath_tests.py").read_text(encoding="utf-8")
        self.assertIn("if self.execution_profile == \"normal\"", text)
        self.assertIn("build_master_result_set(out)", text)
        self.assertIn('index["master_result_set"]', text)
        self.assertIn('execution_profile = "regression"', text)


if __name__ == "__main__":
    unittest.main()
