from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class A16465RecoveryRunButtonTests(unittest.TestCase):
    def setUp(self):
        self.runtime = (ROOT / "gui" / "persistent_app_a35.py").read_text(encoding="utf-8")

    def test_recoverable_failure_bypasses_terminal_rerun_confirmation(self):
        self.assertIn("_recoverable_storage_failure", self.runtime)
        self.assertIn("ordinary_reruns", self.runtime)

    def test_ordinary_reruns_keep_existing_confirmation(self):
        self.assertIn("super()._confirm_rerun(ordinary_reruns)", self.runtime)

    def test_current_runtime_is_a36(self):
        main = (ROOT / "main.py").read_text(encoding="utf-8")
        self.assertIn("from gui.persistent_app_a35 import WorkflowApp as _A35WorkflowApp", main)
        self.assertIn("from gui.persistent_app_a36 import run_gui", main)


if __name__ == "__main__":
    unittest.main()
