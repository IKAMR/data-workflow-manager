from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class Noark5OutputLayoutA15Tests(unittest.TestCase):
    def test_schema_validation_uses_common_noark5_tests_root(self):
        source = (
            ROOT / "noark5_workflow" / "operations" / "validate_xml_schema.py"
        ).read_text(encoding="utf-8")
        self.assertIn('"noark5_tests",', source)
        self.assertIn('"schema",', source)
        self.assertIn("artifact_run_dir(", source)
        self.assertNotIn('/ "xml-validation" /', source)

    def test_new_analysis_operation_is_in_noark5_profile(self):
        source = (
            ROOT / "noark5_workflow" / "profile.py"
        ).read_text(encoding="utf-8")
        self.assertIn("AnalyseNoark5CoreOperation", source)
        self.assertIn("AnalyseNoark5CoreOperation,", source)


if __name__ == "__main__":
    unittest.main()
