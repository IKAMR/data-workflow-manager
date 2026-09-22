import unittest
from noark5_workflow.external_evidence.arkade5_coverage import build_arkade5_coverage

class A12ArkadeCoverageTests(unittest.TestCase):
    def test_all_present_arkade_tests_are_classified(self):
        normalized = {"tests": [
            {"test_id":"N5.04","test_name":"Arkiv","source_status":"ok"},
            {"test_id":"N5.09","test_name":"Tom klasse","source_status":"ok"},
            {"test_id":"N5.10","test_name":"Mapper","source_status":"ok"},
            {"test_id":"N5.999","test_name":"Ukjent","source_status":"ok"},
        ]}
        coverage = build_arkade5_coverage(normalized)
        self.assertEqual(coverage["arkade_tests_present"], 4)
        by_id = {x["arkade_test_id"]: x for x in coverage["items"]}
        self.assertEqual(by_id["N5.04"]["classification"], "equivalent")
        self.assertEqual(by_id["N5.09"]["classification"], "known_non_equivalent")
        self.assertEqual(by_id["N5.10"]["classification"], "equivalent")
        self.assertEqual(by_id["N5.999"]["classification"], "unmapped")
        self.assertEqual(sum(coverage["summary"].values()), 4)

    def test_candidate_never_counts_as_equivalent(self):
        normalized = {"tests": [
            {"test_id":"N5.15","test_name":"Status","source_status":"ok"},
        ]}
        coverage = build_arkade5_coverage(normalized)
        row = coverage["items"][0]
        self.assertIn(row["classification"], {"candidate", "unmapped"})
        self.assertNotEqual(row["classification"], "equivalent")

if __name__ == "__main__":
    unittest.main()
