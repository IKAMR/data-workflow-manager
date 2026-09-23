
from __future__ import annotations

import json
import re
import tempfile
import unittest
import zipfile
from pathlib import Path

from noark5_workflow.external_evidence.arkade5_export import (
    write_arkade5_evidence_package,
)


ROOT = Path(__file__).resolve().parents[1]


class V015A8ArkadePortableExportTests(unittest.TestCase):
    def _make_import(self, root: Path) -> Path:
        work = root / "work"
        import_id = "20260923-abc123"
        base = work / "external_evidence" / "arkade5" / import_id
        source = base / "source" / "arkade.json"
        normalized = base / "normalized" / "arkade5_results.json"
        source.parent.mkdir(parents=True)
        normalized.parent.mkdir(parents=True)

        source.write_text('{"Summary":{},"TestsResults":[]}', encoding="utf-8")
        normalized.write_text(json.dumps({
            "format_version": 2,
            "source_version": "2.13.0",
            "summary": {"date_of_testing": "2026-09-23"},
            "tests": [{
                "test_id": "N5.30",
                "test_name": "Dokumentfilers sjekksummer",
                "source_status": "ok",
                "number_of_errors": 0,
                "results": [],
            }],
        }), encoding="utf-8")

        import hashlib
        digest = hashlib.sha256(source.read_bytes()).hexdigest()
        manifest = {
            "format_version": 2,
            "import_id": import_id,
            "source": {
                "original_name": "arkade.json",
                "sha256": digest,
                "preserved_file": str(source.relative_to(work)),
            },
            "normalized_file": str(normalized.relative_to(work)),
            "reconciliation_file": None,
        }
        (base / "manifest.json").write_text(
            json.dumps(manifest), encoding="utf-8"
        )
        return work

    def test_package_contains_raw_normalized_knowledge_and_coverage(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            work = self._make_import(root)
            depot = {
                "technical_validation": {
                    "tests": [{"test_id": "kdrs.c17"}]
                }
            }
            path = write_arkade5_evidence_package(
                work_operations=work,
                output_dir=root / "out",
                depot_model=depot,
            )
            self.assertTrue(path.is_file())

            with zipfile.ZipFile(path) as archive:
                names = set(archive.namelist())
                self.assertIn("manifest.json", names)
                self.assertIn("README.md", names)
                self.assertIn("knowledge/arkade5_test_catalog.json", names)
                self.assertIn("knowledge/dwm_arkade5_mapping.json", names)
                self.assertIn("knowledge/combined_coverage_model.json", names)
                self.assertIn(
                    "imports/20260923-abc123/source/arkade.json", names
                )
                self.assertIn(
                    "imports/20260923-abc123/normalized/arkade5_results.json",
                    names,
                )
                self.assertIn(
                    "imports/20260923-abc123/combined_coverage.json", names
                )
                manifest = json.loads(archive.read("manifest.json"))
                self.assertEqual(
                    manifest["package_type"],
                    "dwm.noark5.arkade5-portable-evidence",
                )
                self.assertTrue(
                    manifest["principles"]["arkade_does_not_become_dwm_master"]
                )
                self.assertTrue(manifest["files"])
                self.assertTrue(
                    all(row.get("sha256") for row in manifest["files"])
                )

    def test_gui_exposes_portable_export(self):
        text = (ROOT / "gui" / "depot_result_views_a18.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("Eksporter evidenspakke...", text)
        self.assertIn("write_arkade5_evidence_package", text)

    def test_runtime_routes_to_a18(self):
        main = (ROOT / "main.py").read_text(encoding="utf-8")
        self.assertIn("persistent_app_a50 import run_gui", main)

    def test_version_has_not_regressed_before_a8(self):
        version = (ROOT / "version.py").read_text(encoding="utf-8")
        match = re.search(
            r'VERSION\s*=\s*"0\.1\.5-a(\d+)(?:\.\d+)*"',
            version,
        )
        self.assertIsNotNone(match)
        self.assertGreaterEqual(int(match.group(1)), 8)


if __name__ == "__main__":
    unittest.main()
