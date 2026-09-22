from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class A9RuntimeContractTests(unittest.TestCase):
    def test_main_activates_a41(self):
        text = (ROOT / "main.py").read_text(encoding="utf-8")
        self.assertIn("from gui.persistent_app_a41 import run_gui", text)

    def test_runtime_filters_overview_to_participating_jobs(self):
        text = (
            ROOT / "gui" / "persistent_app_a41.py"
        ).read_text(encoding="utf-8")
        self.assertIn("def _jobs_participating_in_run", text)
        self.assertIn("records", text)

    def test_jobs_window_uses_kjoremodus_not_scheduler(self):
        text = (
            ROOT / "gui" / "jobs_window_a27.py"
        ).read_text(encoding="utf-8")
        self.assertIn("Kjøremodus:", text)

    def test_overview_has_search_and_status_filter(self):
        text = (
            ROOT / "app" / "noark5_validation_overview.py"
        ).read_text(encoding="utf-8")
        self.assertIn('id="searchBox"', text)
        self.assertIn('id="statusFilter"', text)


if __name__ == "__main__":
    unittest.main()
