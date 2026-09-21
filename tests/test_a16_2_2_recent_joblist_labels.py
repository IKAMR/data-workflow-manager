from pathlib import Path
import unittest

from gui.job_list_location_dialog import JobListLocationDialog


class A1622RecentJobListLabelsTests(unittest.TestCase):
    def test_only_first_recent_item_is_called_last_used(self):
        self.assertEqual("Sist brukt", JobListLocationDialog._recent_label(0))
        self.assertEqual("", JobListLocationDialog._recent_label(1))
        self.assertEqual("", JobListLocationDialog._recent_label(7))

    def test_open_dialog_uses_indexed_recent_label(self):
        text = (
            Path(__file__).resolve().parents[1]
            / "gui"
            / "job_list_location_dialog.py"
        ).read_text(encoding="utf-8")
        open_block = text.split("def _build_open_rows", 1)[1].split(
            "def _build_save_rows", 1
        )[0]
        self.assertIn("recent_index = 0", open_block)
        self.assertIn("self._recent_label(recent_index)", open_block)
        self.assertIn("recent_index += 1", open_block)


if __name__ == "__main__":
    unittest.main()
