import unittest

from noark5_workflow.external_evidence.arkade5 import normalize_arkade5_report
from noark5_workflow.external_evidence.arkade5_coverage import build_arkade5_coverage


class V015A3ArkadeImportTests(unittest.TestCase):
    def test_unknown_source_fields_are_preserved_at_all_levels(self):
        report = {
            "Summary": {"Uuid": "u", "FutureSummaryField": {"x": 1}},
            "FutureRootField": [1, 2],
            "TestsResults": [{
                "TestId": "N5.32",
                "TestName": "test",
                "TestType": "ContentControl",
                "TestDescription": None,
                "HasResults": True,
                "NumberOfErrors": 0,
                "FutureTestField": "keep",
                "ResultSet": {
                    "Name": "Arkivdel A",
                    "ResultSets": [],
                    "Results": [{
                        "ResultType": "Success",
                        "Message": "ok",
                        "FutureResultField": 17,
                        "Location": {
                            "String": "x",
                            "FileName": "arkivstruktur.xml",
                            "LineNumbers": [2],
                            "FutureLocationField": "loc"
                        }
                    }]
                }
            }]
        }
        normalized = normalize_arkade5_report(report)
        self.assertEqual(normalized["source_extra"]["FutureRootField"], [1, 2])
        self.assertEqual(normalized["summary"]["source_extra"]["FutureSummaryField"], {"x": 1})
        test = normalized["tests"][0]
        self.assertEqual(test["source_extra"]["FutureTestField"], "keep")
        result = test["results"][0]
        self.assertEqual(result["source_extra"]["FutureResultField"], 17)
        self.assertEqual(result["location"]["source_extra"]["FutureLocationField"], "loc")

    def test_a2_mapping_drives_import_coverage(self):
        normalized = {"tests": [
            {"test_id": "N5.19", "test_name": "eq", "source_status": "ok"},
            {"test_id": "N5.24", "test_name": "partial", "source_status": "ok"},
            {"test_id": "N5.35", "test_name": "comp", "source_status": "ok"},
            {"test_id": "N5.47", "test_name": "arkade", "source_status": "ok"},
        ]}
        by_id = {row["arkade_test_id"]: row for row in build_arkade5_coverage(normalized)["items"]}
        self.assertEqual(by_id["N5.19"]["classification"], "equivalent")
        self.assertEqual(by_id["N5.24"]["classification"], "partial")
        self.assertEqual(by_id["N5.35"]["classification"], "complementary")
        self.assertEqual(by_id["N5.47"]["classification"], "arkade_only")


if __name__ == "__main__":
    unittest.main()
