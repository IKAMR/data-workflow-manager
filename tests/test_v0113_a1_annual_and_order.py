"""Annual coverage and new Basic ordering, read-only regression tests."""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
import unittest

from app.annual_v0113_a1 import annual_table_with_coverage
from app.basic_order_v0113_a1 import ordered_basic_operation_ids


class _Shot:
    def __init__(self, name, parts):
        self.job = SimpleNamespace(job_uid=name, job_id=name, name=name)
        self.depot = {"archive_parts": parts}


def _part(identity, series):
    return {"archive_part": {"system_id": identity, "title": identity},
            "yearly_volume": series}


class AnnualCoverageTests(unittest.TestCase):
    def test_partial_subtotals_never_claim_complete_coverage(self):
        one = _part("a", {"folder": {"2005": 1}, "registration": {"2005": 10}})
        two = _part("b", {"folder": {"2006": 2}, "registration": {"2005": 25}})
        report = annual_table_with_coverage([_Shot("job1", [one, two])])
        rows = {r["year"]: r for r in report.rows}
        self.assertEqual(rows[2005]["folder"], 1)
        self.assertEqual(rows[2005]["coverage"]["folder"], (1, 2))
        self.assertEqual(rows[2005]["registration"], 35)
        self.assertEqual(rows[2005]["coverage"]["registration"], (2, 2))
        self.assertIsNone(rows[2006]["registration"])
        self.assertTrue(any("delsum" in w for w in report.warnings))

    def test_zero_is_only_zero_when_explicitly_stored(self):
        report = annual_table_with_coverage([_Shot("job1", [
            _part("a", {"folder": {"2005": 0}}),
            _part("b", {})
        ])])
        self.assertEqual(report.rows[0]["folder"], 0)
        self.assertEqual(report.rows[0]["coverage"]["folder"], (1, 2))
        self.assertIsNone(report.rows[0]["registration"])

    def test_aggregate_and_single_part(self):
        report = annual_table_with_coverage([_Shot("job1", [
            _part("a", {"folder": {"2005": 7}}),
            _part("b", {"folder": {"2005": 2}}),
        ])])
        self.assertEqual(report.rows[0]["folder"], 9)
        self.assertEqual(report.rows[0]["coverage"]["folder"], (2, 2))
        key = "part:job1:a"
        one = annual_table_with_coverage([_Shot("job1", [
            _part("a", {"folder": {"2005": 7}}),
            _part("b", {"folder": {"2005": 2}}),
        ])], key)
        self.assertEqual(one.rows[0]["folder"], 7)


class BasicOrderTests(unittest.TestCase):
    def test_combined_controls_order(self):
        normal = ("metadata_inventory", "validate_xml_schema", "analyse_arkivstruktur",
                  "run_noark5_xpath_tests_2026", "compose_noark5_views",
                  "build_noark5_depot_report")
        arkade = ("metadata_inventory", "validate_xml_schema", "analyse_arkivstruktur",
                  "arkade5_noark5_test", "arkade5_pronom_analysis",
                  "run_noark5_xpath_tests_2026", "import_arkade5_reports",
                  "compose_noark5_views", "build_noark5_depot_report")
        profiles = {
            "noark5_dwm": SimpleNamespace(profile_id="noark5", operation_ids=normal),
            "noark5_standard_arkade": SimpleNamespace(profile_id="noark5", operation_ids=arkade),
        }
        operations = ordered_basic_operation_ids(
            ("dwm", "siegfried", "arkade_noark5", "arkade_pronom"),
            sequence_loader=profiles.get,
        )
        required = ("run_noark5_xpath_tests_2026", "arkade5_noark5_test",
                    "siegfried_pronom_identification", "arkade5_pronom_analysis",
                    "build_noark5_depot_report")
        self.assertEqual(tuple(op for op in operations if op in required), required)


if __name__ == "__main__":
    unittest.main()
