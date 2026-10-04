import unittest
from pathlib import Path


class ActiveJobRegressionTests(unittest.TestCase):
    def test_new_job_does_not_inherit_current_workflow_implicitly(self):
        source = (Path(__file__).resolve().parents[1] / "gui" / "app.py").read_text(encoding="utf-8")
        self.assertIn("self.jobs.new_job(source_root)", source)
        self.assertIn("_apply_default_noark5_workflow(job)", source)
        self.assertNotIn("workflow_ids=self.workflow.operation_ids()", source)

    def test_active_job_is_visible_in_main_header(self):
        source = (Path(__file__).resolve().parents[1] / "gui" / "app.py").read_text(encoding="utf-8")
        self.assertIn("AKTIV JOBB:", source)
        self.assertIn("Workflow: 0 operasjoner - legg til operasjoner", source)


if __name__ == "__main__":
    unittest.main()
