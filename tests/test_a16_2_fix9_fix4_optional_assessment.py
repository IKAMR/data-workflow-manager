import unittest
from types import SimpleNamespace
from unittest.mock import patch
from noark5_workflow.reporting import report_package_a16 as mod

class TestOptionalAssessment(unittest.TestCase):
    def test_no_saved_review_does_not_crash(self):
        job = SimpleNamespace(job_id="JOB-001", progress=1.0, status="Ferdig")
        candidate = {"declared_years": [2000, 2005], "observed_years": [2000, 2005], "proposed_years": [2000, 2005]}
        with patch.object(mod, "_extraction_label", return_value="Test"), patch.object(mod, "_archive_names", return_value="Arkiv"), patch.object(mod, "_review_status", return_value="Samsvar"), patch.object(mod, "review_candidate", return_value=candidate), patch.object(mod, "load_assessment", return_value=None), patch.object(mod, "reviewed_years", return_value=None):
            row = mod._overview_entry(job, {"summary": {}}, "")
        self.assertEqual(len(row), 8)
        self.assertEqual(row[4], "")

    def test_observed_different_without_saved_review(self):
        job = SimpleNamespace(job_id="JOB-022", progress=1.0, status="Ferdig")
        candidate = {"declared_years": [1999, 2005], "observed_years": [1997, 2005], "proposed_years": [1997, 2005]}
        with patch.object(mod, "_extraction_label", return_value="Test"), patch.object(mod, "_archive_names", return_value="Arkiv"), patch.object(mod, "_review_status", return_value="Under undersokelse"), patch.object(mod, "review_candidate", return_value=candidate), patch.object(mod, "load_assessment", return_value=None), patch.object(mod, "reviewed_years", return_value=None):
            row = mod._overview_entry(job, {"summary": {}}, "")
        self.assertIn("1997", row[4])
