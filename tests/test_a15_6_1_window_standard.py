from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class A1561WindowStandardRuntimeContract(unittest.TestCase):
    def test_runtime_chain_preserved_and_current_runtime_is_a36(self):
        main = (ROOT / "main.py").read_text(encoding="utf-8")
        self.assertIn("from gui.persistent_app_a24 import WorkflowApp as _A24WorkflowApp", main)
        self.assertIn("from gui.persistent_app_a35 import WorkflowApp as _A35WorkflowApp", main)
        self.assertIn("from gui.persistent_app_a36 import run_gui", main)


if __name__ == "__main__":
    unittest.main()
