from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class AdaptiveParallelBatchGuiA5Tests(unittest.TestCase):
    def test_main_uses_a37_runtime(self):
        text = (ROOT / "main.py").read_text(encoding="utf-8")
        self.assertIn("from gui.persistent_app_a37 import run_gui", text)

    def test_job_window_exposes_batch_controls(self):
        text = (ROOT / "gui" / "jobs_window_a21.py").read_text(encoding="utf-8")
        self.assertIn('text="Batchkjøring"', text)
        self.assertIn('"Auto"', text)
        self.assertIn('"Sekvensiell"', text)
        self.assertIn('"Parallell"', text)
        self.assertIn('text="Maks workers"', text)

    def test_gui_uses_parallel_core_without_reordering_workflow(self):
        text = (ROOT / "gui" / "persistent_app_a37.py").read_text(encoding="utf-8")
        self.assertIn("self.batch_runner.run_parallel(", text)
        self.assertIn("recommend_batch_execution(", text)
        self.assertIn("self.after(", text)


if __name__ == "__main__":
    unittest.main()
