import json
import unittest
from pathlib import Path

from noark5_workflow.analysis.xpath_test_engine import _select_catalog_tests

ROOT = Path(__file__).parents[1]

def load(path):
    return json.loads((ROOT / path).read_text(encoding="utf-8"))

class A24ExecutionProfileTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.catalog = load("config/noark5/tests/xpath_catalog_2026_05_26.json")

    def test_execution_profiles_exist(self):
        self.assertIn("normal", self.catalog["execution_profiles"])
        self.assertIn("regression", self.catalog["execution_profiles"])

    def test_normal_excludes_regression_references(self):
        selected, excluded = _select_catalog_tests(
            self.catalog, execution_profile="normal", include_disabled=True
        )
        selected_ids = {t["test_id"] for t in selected}
        excluded_ids = {t["test_id"] for t in excluded}
        self.assertNotIn("kdrs.u01", selected_ids)
        self.assertNotIn("kdrs.u02", selected_ids)
        self.assertIn("kdrs.u01", excluded_ids)
        self.assertIn("kdrs.u02", excluded_ids)
        self.assertEqual(len(selected), len(self.catalog["tests"]) - 2)

    def test_regression_includes_legacy_references(self):
        selected, excluded = _select_catalog_tests(
            self.catalog, execution_profile="regression", include_disabled=True
        )
        selected_ids = {t["test_id"] for t in selected}
        self.assertIn("kdrs.u01", selected_ids)
        self.assertIn("kdrs.u02", selected_ids)
        self.assertEqual(excluded, [])

    def test_reference_status_and_lifecycle_are_explicit(self):
        refs = [
            t for t in self.catalog["tests"]
            if t.get("lifecycle", {}).get("role") == "development_regression_reference"
        ]
        self.assertEqual({t["test_id"] for t in refs}, {"kdrs.u01", "kdrs.u02"})
        for test in refs:
            self.assertEqual(test["status"], "regression_reference")
            self.assertFalse(test["lifecycle"]["normal_execution"])
            self.assertTrue(test["lifecycle"]["regression_execution"])

    def test_regression_contract_is_profile_discoverable(self):
        profile = load("config/noark5/profile.json")
        contract = "config/noark5/analysis/legacy_regression_contract.json"
        self.assertIn(contract, profile["definitions"]["analysis"])
        self.assertTrue((ROOT / contract).is_file())

    def test_engine_does_not_hardcode_u_test_ids_for_selection(self):
        engine = (ROOT / "noark5_workflow/analysis/xpath_test_engine.py").read_text(encoding="utf-8")
        helper = engine[engine.index("def _select_catalog_tests"):engine.index("def run_catalog")]
        self.assertNotIn("kdrs.u01", helper)
        self.assertNotIn("kdrs.u02", helper)

if __name__ == "__main__":
    unittest.main()
