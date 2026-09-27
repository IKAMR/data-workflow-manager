from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from noark5_workflow.external_evidence.arkade5_pronom import (
    attach_arkade5_pronom_evidence,
)


class V016A13PronomStatisticsTests(unittest.TestCase):
    def test_imports_statistics_but_only_documents_detailed_inventory(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            work = root / "repository_operations" / "dwm" / "b09"
            import_id = "20250226-deadbeefcafe"
            manifest_dir = work / "external_evidence" / "arkade5" / import_id
            manifest_dir.mkdir(parents=True)
            (manifest_dir / "manifest.json").write_text(
                json.dumps({
                    "import_id": import_id,
                    "source": {"sha256": "abc"},
                }),
                encoding="utf-8",
            )

            arkade = root / "repository_operations" / "arkade5_v2.12.3" / "folder"
            arkade.mkdir(parents=True)
            report = arkade / "1543_010_testrapport.json"
            report.write_text("{}", encoding="utf-8")

            stats = arkade / "1543_010_noark5_filformatinfo-statistikk.csv"
            stats.write_text(
                "PUID;Format;Antall\nfmt/18;PDF;10\nfmt/111;XML;3\n",
                encoding="utf-8",
            )
            detail = arkade / "1543_010_noark5_filformatinfo.csv"
            detail.write_text(
                "Fil;PUID\nDOKUMENT/1.pdf;fmt/18\n",
                encoding="utf-8",
            )

            result = attach_arkade5_pronom_evidence(
                report,
                work_operations=work,
                import_id=import_id,
            )

            self.assertEqual(result["status"], "ok")
            self.assertTrue(result["statistics_found"])
            self.assertTrue(result["statistics_imported"])
            self.assertEqual(result["statistics_row_count"], 2)
            self.assertTrue(result["detailed_inventory_found"])
            self.assertFalse(result["detailed_inventory_imported"])

            manifest = json.loads(
                (manifest_dir / "manifest.json").read_text(encoding="utf-8")
            )
            pronom = manifest["pronom_evidence"]
            self.assertTrue(pronom["statistics"]["imported"])
            self.assertEqual(pronom["statistics"]["row_count"], 2)
            self.assertTrue(pronom["detailed_file_inventory"]["found"])
            self.assertFalse(pronom["detailed_file_inventory"]["imported"])
            self.assertEqual(
                pronom["detailed_file_inventory"]["original_name"],
                detail.name,
            )

            preserved_stats = work / pronom["statistics"]["preserved_file"]
            normalized = work / pronom["statistics"]["normalized_file"]
            self.assertTrue(preserved_stats.is_file())
            self.assertTrue(normalized.is_file())

            # The large one-row-per-file inventory must not be copied.
            copied_detail = manifest_dir / "source" / detail.name
            self.assertFalse(copied_detail.exists())

            normalized_data = json.loads(normalized.read_text(encoding="utf-8"))
            self.assertEqual(normalized_data["csv"]["row_count"], 2)
            self.assertEqual(
                normalized_data["csv"]["rows"][0]["PUID"],
                "fmt/18",
            )

    def test_missing_pronom_files_is_valid_and_recorded(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            work = root / "work"
            import_id = "x"
            manifest_dir = work / "external_evidence" / "arkade5" / import_id
            manifest_dir.mkdir(parents=True)
            (manifest_dir / "manifest.json").write_text(
                json.dumps({"import_id": import_id}),
                encoding="utf-8",
            )
            report = root / "arkade5_v2.12.3" / "folder" / "report.json"
            report.parent.mkdir(parents=True)
            report.write_text("{}", encoding="utf-8")

            result = attach_arkade5_pronom_evidence(
                report,
                work_operations=work,
                import_id=import_id,
            )
            self.assertEqual(result["status"], "ok")
            self.assertFalse(result["statistics_found"])
            self.assertFalse(result["detailed_inventory_found"])


if __name__ == "__main__":
    unittest.main()
