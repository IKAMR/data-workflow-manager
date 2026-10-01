from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from noark5_workflow.external_tools.arkade5_auto_import import (
    _arkade_testing_date,
    _record_detailed_pronom_inventory,
)


class V016A26ArkadeMetadataDetailTests(unittest.TestCase):
    def test_time_of_testing_is_accepted_for_arkade_2131(self):
        with tempfile.TemporaryDirectory() as temp:
            report = Path(temp) / "report.json"
            report.write_text(
                json.dumps({"Summary": {"TimeOfTesting": "01. oktober 2026 21:13"}}),
                encoding="utf-8",
            )
            self.assertEqual(_arkade_testing_date(report), "20261001")

    def test_detailed_filformatinfo_is_recorded_found_but_not_imported(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            dwm = root / "dwm"
            import_id = "20261001-abc123"
            manifest_path = dwm / "external_evidence" / "arkade5" / import_id / "manifest.json"
            manifest_path.parent.mkdir(parents=True)
            manifest_path.write_text(
                json.dumps({"import_id": import_id, "pronom_evidence": {"detailed_file_inventory": {"found": False, "imported": False}}}),
                encoding="utf-8",
            )
            output = root / "arkade5_v2.13.1" / "pronom"
            output.mkdir(parents=True)
            (output / "filformatinfo").write_text("detail inventory", encoding="utf-8")

            _record_detailed_pronom_inventory(dwm_work=dwm, import_id=import_id, output_dir=output)

            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            detailed = manifest["pronom_evidence"]["detailed_file_inventory"]
            self.assertTrue(detailed["found"])
            self.assertFalse(detailed["imported"])
            self.assertEqual(detailed["original_name"], "filformatinfo")
            self.assertTrue(detailed["sha256"])


if __name__ == "__main__":
    unittest.main()
