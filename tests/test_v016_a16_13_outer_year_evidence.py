import unittest

from noark5_workflow.analysis.archive_parts_summary import build_all_archive_parts_summary


class TestOuterYearEvidence(unittest.TestCase):
    def test_materializes_series_periods_and_document_only_year(self):
        model = {
            "archive_parts": [
                {
                    "yearly_volume": {
                        "folder": {"2008": 2},
                        "journal": {"2008": 4},
                        "document_description": {"2008": 5, "2099": 11},
                        "document_object": {"2008": 9, "2099": 24},
                    }
                }
            ],
            "period_reconciliation": {
                "declared_period": {"start_date": "2007-01-01", "end_date": "2099-12-31"}
            },
        }
        summary = build_all_archive_parts_summary(model)
        self.assertEqual(2, summary["all_archive_parts_summary_format_version"])
        self.assertEqual("2008", summary["observed_period_by_series"]["folder"]["last_year"])
        self.assertEqual("2099", summary["observed_period_by_series"]["document_object"]["last_year"])
        self.assertEqual(1, summary["review_finding_count"])
        self.assertEqual("2099", summary["cross_source_year_findings"][0]["year"])

    def test_main_activates_a16_13(self):
        text = open("main.py", encoding="utf-8").read()
        self.assertIn("from gui.persistent_app_a16_13 import run_gui", text)


if __name__ == "__main__":
    unittest.main()
