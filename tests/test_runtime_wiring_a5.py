import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class A5RuntimeWiringTests(unittest.TestCase):
    def test_current_runtime_preserves_a5_chain(self):
        main = (ROOT / "main.py").read_text(encoding="utf-8")
        a21 = (ROOT / "gui" / "persistent_app_a21.py").read_text(encoding="utf-8")
        a20 = (ROOT / "gui" / "persistent_app_a20.py").read_text(encoding="utf-8")
        a19 = (ROOT / "gui" / "persistent_app_a19.py").read_text(encoding="utf-8")
        a18 = (ROOT / "gui" / "persistent_app_a18.py").read_text(encoding="utf-8")
        a17 = (ROOT / "gui" / "persistent_app_a17.py").read_text(encoding="utf-8")
        a13 = (ROOT / "gui" / "persistent_app_a13.py").read_text(encoding="utf-8")
        a6 = (ROOT / "gui" / "persistent_app_a6.py").read_text(encoding="utf-8")
        self.assertIn("persistent_app_a21", main)
        self.assertIn("A20WorkflowApp", a21)
        self.assertIn("A19WorkflowApp", a20)
        self.assertIn("A18WorkflowApp", a19)
        self.assertIn("A17WorkflowApp", a18)
        self.assertIn("A13WorkflowApp", a17)
        self.assertIn("persistent_app_a6", a13)
        self.assertIn("A5WorkflowApp", a6)

    def test_a5_inherits_a2155_and_wires_runners(self):
        text = (ROOT / "gui" / "persistent_app_a5.py").read_text(encoding="utf-8")
        self.assertIn("A2155WorkflowApp", text)
        self.assertIn("JobRunner", text)
        self.assertIn("BatchRunner", text)
        self.assertIn("self.job_runner.run", text)
        self.assertIn("self.batch_runner.run", text)

    def test_a5_preserves_startup_watchdog(self):
        text = (ROOT / "gui" / "persistent_app_a5.py").read_text(encoding="utf-8")
        self.assertIn("startup_watchdog", text)
        self.assertIn("first_job_registered", text)
        self.assertIn("worker_started", text)
        self.assertIn("BATCH STARTUP-FEIL", text)


if __name__ == "__main__":
    unittest.main()
