import unittest

from app.noark5_control_worklist import filter_rows, sort_rows


class A10ControlWorklistTests(unittest.TestCase):
    def test_attention_statuses_sort_before_ok(self):
        rows = [
            {"job_id": "3", "control_status": "OK", "name": "C"},
            {"job_id": "2", "control_status": "VURDER", "name": "B"},
            {"job_id": "1", "control_status": "FEIL", "name": "A"},
        ]
        result = sort_rows(rows)
        self.assertEqual(
            [row["control_status"] for row in result],
            ["FEIL", "VURDER", "OK"],
        )

    def test_filter_supports_status_and_free_text(self):
        rows = [
            {
                "job_id": "JOB-001",
                "name": "1525_004",
                "control_status": "VURDER",
                "source_extraction": r"H:\arkiv-noark5\1525\1525_004",
            },
            {
                "job_id": "JOB-002",
                "name": "1525_005",
                "control_status": "OK",
                "source_extraction": r"H:\arkiv-noark5\1525\1525_005",
            },
        ]
        result = filter_rows(rows, status="VURDER", search="1525_004")
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["job_id"], "JOB-001")


if __name__ == "__main__":
    unittest.main()
