import unittest
from pathlib import Path

ROOT = Path(__file__).parents[1]

class A243RegressionOperationTests(unittest.TestCase):

    def test_operation_module_defines_separate_normal_and_regression_classes(self):
        text = (
            ROOT / "noark5_workflow/operations/run_noark5_xpath_tests.py"
        ).read_text(encoding="utf-8")
        self.assertIn("class RunNoark5XpathTestsOperation", text)
        self.assertIn("class RunNoark5XpathRegressionOperation", text)
        self.assertIn('execution_profile = "normal"', text)
        self.assertIn('execution_profile = "regression"', text)
        self.assertIn('output_subdir = "xpath_regression"', text)

    def test_regression_operation_is_explicit_qa_operation(self):
        text = (
            ROOT / "noark5_workflow/operations/run_noark5_xpath_tests.py"
        ).read_text(encoding="utf-8")
        self.assertIn('operation_id="run_noark5_xpath_regression_2026"', text)
        self.assertIn('name="Noark 5 XPath-regresjon 2026"', text)
        self.assertIn('category="Systemspesifikt"', text)
        self.assertIn("Utviklings-/QA-kjøring", text)

    def test_operations_init_exports_regression_operation(self):
        text = (
            ROOT / "noark5_workflow/operations/__init__.py"
        ).read_text(encoding="utf-8")
        self.assertIn("RunNoark5XpathRegressionOperation", text)

    def test_profile_registers_normal_then_regression_operation(self):
        text = (
            ROOT / "noark5_workflow/profile.py"
        ).read_text(encoding="utf-8")
        self.assertIn("RunNoark5XpathRegressionOperation", text)
        normal = text.index("        RunNoark5XpathTestsOperation,")
        regression = text.index("        RunNoark5XpathRegressionOperation,")
        self.assertLess(normal, regression)

if __name__ == "__main__":
    unittest.main()
