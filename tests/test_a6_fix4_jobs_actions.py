from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class A6Fix4JobsActionsTests(unittest.TestCase):
    def test_action_order_is_open_mapper_standard_reset_delete(self):
        text = (
            ROOT / "gui" / "jobs_window_a24.py"
        ).read_text(encoding="utf-8")

        self.assertIn('view["open"].grid_configure(column=7', text)
        self.assertIn('view["mapper"].grid_configure(column=8', text)
        self.assertIn('view["standard"].grid_configure(column=9', text)
        self.assertIn('view["reset"].grid_configure(column=10', text)
        self.assertIn('view["delete"].grid_configure(column=11', text)

    def test_window_uses_current_app_name(self):
        text = (
            ROOT / "gui" / "jobs_window_a24.py"
        ).read_text(encoding="utf-8")
        self.assertIn("from version import APP_NAME", text)
        self.assertIn('self.title(f"Jobber - {APP_NAME}")', text)

    def test_a38_uses_a24_jobs_window(self):
        text = (
            ROOT / "gui" / "persistent_app_a38.py"
        ).read_text(encoding="utf-8")
        self.assertIn("from .jobs_window_a24 import A24JobsWindow", text)
        self.assertIn("self.jobs_window = A24JobsWindow(", text)


if __name__ == "__main__":
    unittest.main()
