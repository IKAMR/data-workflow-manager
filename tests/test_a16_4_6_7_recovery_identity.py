from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class A16467RecoveryIdentityTests(unittest.TestCase):
    def setUp(self):
        self.runtime = (ROOT / "gui" / "persistent_app_a36.py").read_text(encoding="utf-8")

    def test_recovery_can_use_persisted_log_evidence(self):
        self.assertIn("GJENOPPRETTING: eldre lagringsfeil klassifisert som", self.runtime)
        self.assertIn("LAGRINGSFEIL: recovery avbrutt; kan forsøkes igjen", self.runtime)

    def test_confirm_rerun_does_not_call_broken_ancestor_dialog(self):
        method = self.runtime.split("def _confirm_rerun(self, jobs) -> bool:", 1)[1].split("def run_gui", 1)[0]
        self.assertNotIn("super()._confirm_rerun", method)
        self.assertIn("messagebox.askyesno(APP_NAME, message)", method)

    def test_current_runtime_is_a36(self):
        main = (ROOT / "main.py").read_text(encoding="utf-8")
        self.assertIn("from gui.persistent_app_a35 import WorkflowApp as _A35WorkflowApp", main)
        self.assertIn("from gui.persistent_app_a36 import run_gui", main)


if __name__ == "__main__":
    unittest.main()
