from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class A215RuntimeWiringTests(unittest.TestCase):
    def test_a215_runtime_import_precedes_run(self):
        source = (ROOT / "main.py").read_text(encoding="utf-8")
        import_pos = source.rfind("from gui.persistent_app_a21_5 import run_gui")
        run_pos = source.find('if __name__ == "__main__":')
        self.assertGreaterEqual(import_pos, 0)
        self.assertGreater(run_pos, import_pos)


if __name__ == "__main__":
    unittest.main()
