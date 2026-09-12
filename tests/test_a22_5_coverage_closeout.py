import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "config" / "noark5" / "tests" / "xpath_catalog_2026_05_26.json"
COVERAGE = ROOT / "config" / "noark5" / "analysis" / "u1_u2_coverage_2026_05_26.json"

class A225CoverageCloseoutTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalog=json.loads(CATALOG.read_text(encoding="utf-8"))
        cls.coverage=json.loads(COVERAGE.read_text(encoding="utf-8"))
        cls.tests={t["test_id"]:t for t in cls.catalog["tests"]}

    def test_raw_data_coverage_is_closed(self):
        self.assertTrue(self.coverage["summary"]["raw_data_coverage_complete_for_a22"])
        unresolved=[x for x in self.coverage["items"] if x["status"] in {"missing","partial"}]
        self.assertEqual(unresolved, [])

    def test_all_covered_test_references_exist(self):
        missing=[]
        for item in self.coverage["items"]:
            if item["status"] != "covered":
                continue
            for tid in item.get("tests",[]):
                if tid not in self.tests:
                    missing.append((item["id"],tid))
        self.assertEqual(missing, [])

    def test_deferred_items_have_future_phase(self):
        deferred=[x for x in self.coverage["items"] if x["status"]=="deferred"]
        self.assertTrue(deferred)
        for item in deferred:
            self.assertIn(item["phase"], {"a23","a24","a25","a26","later"})
            self.assertTrue(item.get("reason"))

    def test_u_jobs_are_marked_reference_without_disabling_them(self):
        for tid in ("kdrs.u01","kdrs.u02"):
            t=self.tests[tid]
            self.assertEqual(t["lifecycle"]["role"], "development_regression_reference")
            self.assertEqual(t["status"], "regression_reference")
            self.assertFalse(t["lifecycle"]["normal_execution"])
            self.assertTrue(t["lifecycle"]["regression_execution"])
            self.assertNotEqual(t["legacy"]["job_enabled"], 0)

if __name__ == "__main__":
    unittest.main()
