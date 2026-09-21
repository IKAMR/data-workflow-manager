from pathlib import Path
import importlib.util
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "tools" / "delta_preflight.py"

spec = importlib.util.spec_from_file_location("delta_preflight", TOOL)
delta_preflight = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(delta_preflight)


class DeltaPreflightTests(unittest.TestCase):
    def test_documented_preflight_exists(self):
        doc = (ROOT / "docs" / "DELTA-PREFLIGHT.md").read_text(encoding="utf-8")
        self.assertIn("ikke leveringsklart", doc)
        self.assertIn("runtime-kjede", doc)
        self.assertIn("eksakte", doc)
        self.assertIn("berørte tester", doc)

    def test_active_runtime_uses_last_unaliased_import(self):
        text = (
            "from gui.persistent_app_a33 import WorkflowApp as _A33WorkflowApp\n"
            "from gui.persistent_app_a34 import run_gui\n"
        )
        self.assertEqual(
            delta_preflight.active_runtime_module(text),
            "persistent_app_a34",
        )

    def test_stale_runtime_expectation_is_blocker(self):
        with tempfile.TemporaryDirectory() as td:
            test = Path(td) / "test_runtime.py"
            test.write_text(
                'self.assertIn("from gui.persistent_app_a33 import run_gui", main)\n',
                encoding="utf-8",
            )
            problems = delta_preflight.stale_runtime_expectations(
                "from gui.persistent_app_a34 import run_gui\n",
                [test],
            )
        self.assertEqual(len(problems), 1)
        self.assertIn("a33", problems[0])
        self.assertIn("a34", problems[0])

    def test_current_runtime_expectation_is_not_blocker(self):
        with tempfile.TemporaryDirectory() as td:
            test = Path(td) / "test_runtime.py"
            test.write_text(
                'self.assertIn("from gui.persistent_app_a34 import run_gui", main)\n',
                encoding="utf-8",
            )
            problems = delta_preflight.stale_runtime_expectations(
                "from gui.persistent_app_a34 import run_gui\n",
                [test],
            )
        self.assertEqual(problems, [])

    def test_assertin_literal_extraction(self):
        literals = delta_preflight._assertin_literals(
            'self.assertIn("for tooltip in self._tooltips: tooltip._hide()", text)\n'
        )
        self.assertEqual(
            literals,
            ["for tooltip in self._tooltips: tooltip._hide()"],
        )


if __name__ == "__main__":
    unittest.main()
