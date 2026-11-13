"""Disconnected encrypted drive: retain selected list and offer manual retry."""
from pathlib import Path
import tempfile
import unittest

from app.workbench_recent_v018_a4 import (
    disconnected_joblist_message, recent_joblists,
)


class ReleaseRestoreTests(unittest.TestCase):
    def test_missing_last_is_not_replaced_by_available_older_job(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            other = root / "other.n5jobs"
            other.write_text("{}", encoding="utf-8")
            selected = root / "encrypted" / "original.n5jobs"
            self.assertEqual(recent_joblists(selected, [other])[0], str(selected))
            self.assertFalse(selected.is_file())
            selected.parent.mkdir()
            selected.write_text("{}", encoding="utf-8")
            self.assertTrue(selected.is_file())
            self.assertEqual(recent_joblists(selected, [other])[0], str(selected))

    def test_explanation_identifies_saved_path_and_retry(self):
        path = r"I:\archive\joblists\original.n5jobs"
        title, detail = disconnected_joblist_message(path)
        self.assertIn("ikke tilgjengelig", title)
        self.assertIn("Prøv igjen", detail)
        self.assertIn(path, detail)
        self.assertIn("beholdes", detail)

    def test_gui_has_explicit_retry_and_no_automatic_fallback(self):
        src = (Path(__file__).resolve().parents[1] / "gui_qt" / "main_window.py")
        if not src.exists():
            self.skipTest("main_window.py absent from isolated fix test folder")
        text = src.read_text(encoding="utf-8")
        self.assertIn("def _retry_unavailable_startup_joblist(", text)
        self.assertIn("disconnected_joblist_message(", text)
        self.assertIn('"Prøv igjen"', text)
        self.assertIn('"Fortsett uten jobb"', text)
        self.assertIn('self.config.value("qt/last_job_list"', text)
        self.assertIn('self._retry_unavailable_startup_joblist(last)', text)
        self.assertIn('if Path(last).is_file():', text)


if __name__ == "__main__":
    unittest.main()
