import unittest

from noark5_workflow.analysis.archive_parts_summary import build_all_archive_parts_summary


class TestAllArchivePartsSummary(unittest.TestCase):
    def test_sums_counts_years_and_declared_period(self):
        model = {
            "archive_parts": [
                {"folder_count": 2, "journalpost_count": 3, "yearly_volume": {"folder": {"2008": 2}, "journal": {"2009": 3}}},
                {"folder_count": 5, "journalpost_count": 7, "yearly_volume": {"folder": {"2010": 5}, "journal": {"2011": 7}}},
            ],
            "period_reconciliation": {"declared_period": {"start_date": "2007-01-01", "end_date": "2020-12-31", "start_year": "2007", "end_year": "2020"}},
        }
        summary = build_all_archive_parts_summary(model)
        self.assertEqual(2, summary["archive_part_count"])
        self.assertEqual(7, summary["folder_count"])
        self.assertEqual(10, summary["journalpost_count"])
        self.assertEqual("2008", summary["observed_period"]["first_year"])
        self.assertEqual("2011", summary["observed_period"]["last_year"])
        self.assertEqual("2007-01-01", summary["declared_period"]["start_date"])

    def test_main_activates_a16_12(self):
        text = open("main.py", encoding="utf-8").read()
        self.assertIn("from gui.persistent_app_a16_12 import run_gui", text)


if __name__ == "__main__":
    unittest.main()
