import unittest
from noark5_workflow.external_evidence.arkade5_coverage import build_arkade5_coverage


class A12ArkadeCoverageTests(unittest.TestCase):
    def test_all_present_arkade_tests_use_verified_a2_classification(self):
        normalized = {"tests": [
            {"test_id": "N5.04", "test_name": "Arkiv", "source_status": "ok"},
            {"test_id": "N5.09", "test_name": "Tom klasse", "source_status": "ok"},
            {"test_id": "N5.19", "test_name": "Klasse/registrering", "source_status": "ok"},
            {"test_id": "N5.32", "test_name": "Dokumentfiler", "source_status": "ok"},
            {"test_id": "N5.999", "test_name": "Ukjent", "source_status": "ok"},
        ]}
        coverage = build_arkade5_coverage(normalized)
        by_id = {x["arkade_test_id"]: x for x in coverage["items"]}
        self.assertEqual(by_id["N5.04"]["classification"], "partial")
        self.assertEqual(by_id["N5.09"]["classification"], "partial")
        self.assertEqual(by_id["N5.19"]["classification"], "equivalent")
        self.assertEqual(by_id["N5.32"]["classification"], "arkade_only")
        self.assertEqual(by_id["N5.999"]["classification"], "unmapped")
        self.assertEqual(sum(coverage["summary"].values()), 5)

    def test_same_number_never_creates_implicit_equivalence(self):
        normalized = {"tests": [{"test_id": "N5.15", "test_name": "Status", "source_status": "ok"}]}
        row = build_arkade5_coverage(normalized)["items"][0]
        self.assertEqual(row["classification"], "complementary")
        self.assertNotEqual(row["classification"], "equivalent")


if __name__ == "__main__":
    unittest.main()
