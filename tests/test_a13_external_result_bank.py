from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from noark5_workflow.external_evidence.arkade5 import import_arkade5_report
from noark5_workflow.external_evidence.result_bank import (
    build_external_result_bank,
    write_external_result_bank,
)


def sample(date: str, test_id: str = "N5.04") -> dict:
    return {
        "Summary": {
            "DateOfTesting": date,
            "NumberOfTestsRun": 1,
            "NumberOfErrors": 0,
            "NumberOfWarnings": 0,
        },
        "TestsResults": [{
            "TestId": test_id,
            "TestName": "Test " + test_id,
            "TestType": "ContentAnalysis",
            "ResultSet": {
                "Results": [{
                    "ResultType": "Success",
                    "Message": "Totalt: 1",
                    "Location": {},
                }],
                "ResultSets": [],
            },
            "HasResults": True,
            "NumberOfErrors": "0",
        }],
    }


class A13ExternalResultBankTests(unittest.TestCase):
    def test_two_external_reports_remain_two_groups(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            work = root / "work"
            depot = root / "depot.json"
            depot.write_text(
                json.dumps({"summary": {"archive_count": 1}}),
                encoding="utf-8",
            )

            first = root / "arkade-old.json"
            second = root / "arkade-new.json"
            first.write_text(json.dumps(sample("2025-12-23")), encoding="utf-8")
            second.write_text(json.dumps(sample("2026-02-26")), encoding="utf-8")

            import_arkade5_report(
                first,
                work_operations=work,
                depot_report_path=depot,
            )
            import_arkade5_report(
                second,
                work_operations=work,
                depot_report_path=depot,
            )

            bank = build_external_result_bank(work)

            self.assertEqual(bank["format_version"], 2)
            self.assertEqual(len(bank["groups"]), 2)
            self.assertEqual(bank["summary"]["resources"], 2)

            dates = {
                group["source_test_date"]
                for group in bank["groups"]
            }
            self.assertEqual(dates, {"2025-12-23", "2026-02-26"})

            for group in bank["groups"]:
                self.assertEqual(len(group["resources"]), 1)
                self.assertEqual(
                    group["resources"][0]["source_import_id"],
                    group["source_import_id"],
                )

    def test_flat_resources_are_still_kept_for_machine_use(self):
        with tempfile.TemporaryDirectory() as td:
            path = write_external_result_bank(td)
            data = json.loads(path.read_text(encoding="utf-8"))
            self.assertIn("groups", data)
            self.assertIn("resources", data)

    def test_gui_states_each_external_report_is_separate(self):
        root = Path(__file__).resolve().parents[1]
        text = (
            root / "gui" / "depot_result_views_a13.py"
        ).read_text(encoding="utf-8")
        self.assertIn("Eksterne rapporter/kjøringer", text)
        self.assertIn("Import-ID:", text)
        self.assertIn("SHA-256:", text)
        self.assertIn("Hver ekstern rapport/kjøring beholdes separat", text)


if __name__ == "__main__":
    unittest.main()
