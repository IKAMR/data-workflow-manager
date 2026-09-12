import unittest
from pathlib import Path
import json

ROOT = Path(__file__).parents[1]

class A24CloseoutTests(unittest.TestCase):
    def test_regression_operation_disables_checkpoint(self):
        text=(ROOT/"noark5_workflow/operations/run_noark5_xpath_tests.py").read_text(encoding="utf-8")
        self.assertIn("class RunNoark5XpathRegressionOperation", text)
        self.assertIn("allow_checkpoint = False", text)

    def test_job_runner_preserves_default_checkpoint_behavior(self):
        text=(ROOT/"noark5_workflow/core/job_runner.py").read_text(encoding="utf-8")
        self.assertIn('getattr(operation, "allow_checkpoint", True)', text)

    def test_closeout_evidence_records_verified_regression(self):
        data=json.loads((ROOT/"config/noark5/analysis/legacy_regression_contract.json").read_text(encoding="utf-8"))
        evidence=data["validation_evidence"]
        self.assertEqual(evidence["machine_regression_checks"],113)
        self.assertEqual(evidence["matches"],113)
        self.assertEqual(evidence["mismatches"],0)
        self.assertEqual(evidence["not_comparable"],0)
        self.assertEqual(data["legacy_status"],"reference_only_regression")

if __name__=="__main__":
    unittest.main()
