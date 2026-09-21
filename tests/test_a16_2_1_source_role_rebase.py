from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class A1621RuntimeContract(unittest.TestCase):
    def test_a28_integrity_layer_is_preserved_below_a34(self):
        main = (ROOT / "main.py").read_text(encoding="utf-8")
        self.assertIn(
            "from gui.persistent_app_a28 import WorkflowApp as _A28WorkflowApp",
            main,
        )
        self.assertIn(
            "from gui.persistent_app_a33 import WorkflowApp as _A33WorkflowApp",
            main,
        )
        self.assertIn(
            "from gui.persistent_app_a34 import run_gui",
            main,
        )

        runtime = (
            ROOT / "gui" / "persistent_app_a28.py"
        ).read_text(encoding="utf-8")
        self.assertNotIn(
            "_rebase_job_roles_for_source_change",
            runtime,
        )


if __name__ == "__main__":
    unittest.main()
