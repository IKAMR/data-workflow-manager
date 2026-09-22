from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class A8MainRuntimeCompatibilityTests(unittest.TestCase):
    def test_old_runtime_boundary_imports_remain_literal(self):
        text = (ROOT / "main.py").read_text(encoding="utf-8")
        self.assertIn("from gui.persistent_app_a36 import run_gui", text)
        self.assertIn("from gui.persistent_app_a37 import run_gui", text)
        self.assertIn("from gui.persistent_app_a38 import run_gui", text)

    def test_a40_is_final_active_runtime(self):
        text = (ROOT / "main.py").read_text(encoding="utf-8")
        self.assertLess(
            text.index("from gui.persistent_app_a38 import run_gui"),
            text.index("from gui.persistent_app_a40 import run_gui"),
        )


if __name__ == "__main__":
    unittest.main()
