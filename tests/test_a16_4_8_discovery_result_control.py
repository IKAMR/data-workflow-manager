from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from noark5_workflow.core.result_inventory import scan_result_inventory


class A1648DiscoveryResultControlTests(unittest.TestCase):
    def test_manifest_results_are_filtered_by_source(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            wanted = root / "source-a"
            other = root / "source-b"

            a = root / "001" / "noark5_tests" / "schema" / "JOB-001__RUN-A"
            b = root / "002" / "noark5_tests" / "xpath" / "JOB-002__RUN-B"
            a.mkdir(parents=True)
            b.mkdir(parents=True)

            (a / "artifact_manifest.json").write_text(
                json.dumps({
                    "job_id": "JOB-001",
                    "run_id": "RUN-A",
                    "operation_id": "validate_xml_schema",
                    "source_extraction": str(wanted),
                }),
                encoding="utf-8",
            )
            (b / "artifact_manifest.json").write_text(
                json.dumps({
                    "job_id": "JOB-002",
                    "run_id": "RUN-B",
                    "operation_id": "run_noark5_xpath_tests_2026",
                    "source_extraction": str(other),
                }),
                encoding="utf-8",
            )

            inventory = scan_result_inventory(root, source_extraction=wanted)
            self.assertEqual(inventory.manifests, 1)
            self.assertEqual(inventory.schema_runs, 1)
            self.assertEqual(inventory.xpath_runs, 0)
            self.assertTrue(inventory.has_results)

    def test_legacy_results_are_reported_without_claiming_identity(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            legacy = root / "noark5_tests" / "schema"
            legacy.mkdir(parents=True)
            (legacy / "xml-validation-arkivstruktur.json").write_text(
                "{}",
                encoding="utf-8",
            )

            inventory = scan_result_inventory(
                root,
                source_extraction=root / "source-a",
            )
            self.assertEqual(inventory.manifests, 0)
            self.assertEqual(inventory.legacy_artifacts, 1)
            self.assertIn("Legacy/ukjent 1", inventory.summary)

    def test_discovery_dialog_exposes_check_and_reset_options(self):
        root = Path(__file__).resolve().parents[1]
        source = (root / "gui" / "discovered_sources_dialog.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("Kontroller eksisterende resultater", source)
        self.assertIn("Nullstill kjørestatus/cursor", source)
        self.assertIn("Kontroller nå", source)

    def test_jobs_discovery_uses_inventory_and_non_destructive_reset(self):
        root = Path(__file__).resolve().parents[1]
        source = (root / "gui" / "jobs_window_a20.py").read_text(encoding="utf-8")
        self.assertIn("scan_result_inventory(", source)
        self.assertIn("dialog.reset_execution_state", source)
        self.assertIn("job.reset_execution(", source)
        self.assertIn("Resultatfiler og logger på disk", source)
        self.assertNotIn(".unlink(", source)
        self.assertNotIn("rmtree(", source)


if __name__ == "__main__":
    unittest.main()
