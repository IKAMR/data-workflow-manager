"""Regression: reports open without external command processes."""
from pathlib import Path
import unittest


class ReportOpenRegressionTests(unittest.TestCase):
    def test_no_external_process_invocation_in_dialog(self):
        source = (Path(__file__).resolve().parents[1] / "gui" / "kdrs_query_results_a4.py").read_text(encoding="utf-8")
        self.assertNotIn("subprocess", source)
        self.assertIn("webbrowser.open", source)
        self.assertIn("os.startfile", source)


if __name__ == "__main__":
    unittest.main()
