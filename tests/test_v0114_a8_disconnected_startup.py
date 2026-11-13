"""Regression for reconnecting an encrypted drive after a disconnected startup."""
import tempfile
import unittest
from pathlib import Path

from app.workbench_recent_v018_a4 import recent_joblists, remember_joblist


class DisconnectedStartupTests(unittest.TestCase):
    def test_missing_last_never_falls_back_to_other_job(self):
        with tempfile.TemporaryDirectory() as tmp:
            other = Path(tmp) / "other.n5jobs"
            other.write_text("{}", encoding="utf-8")
            missing = Path(tmp) / "encrypted-drive" / "original.n5jobs"
            recent = recent_joblists(str(missing), [str(other)])
            self.assertEqual(recent[0], str(missing))
            self.assertEqual(recent[1], str(other))

    def test_legacy_last_is_protected_when_qt_last_not_set(self):
        with tempfile.TemporaryDirectory() as tmp:
            other = Path(tmp) / "other.n5jobs"
            other.touch()
            missing = Path(tmp) / "I-drive" / "original.n5jobs"
            recent = recent_joblists("", [str(other)], {
                "last_job_list_file": str(missing),
            })
            # The last selected job always wins over ordinary recent history.
            self.assertEqual(recent[0], str(missing))

    def test_existing_last_stays_first(self):
        with tempfile.TemporaryDirectory() as tmp:
            last = Path(tmp) / "last.n5jobs"
            other = Path(tmp) / "other.n5jobs"
            last.touch()
            other.touch()
            self.assertEqual(recent_joblists(str(last), [str(other)])[0], str(last))

    def test_unavailable_history_other_than_last_still_filtered(self):
        with tempfile.TemporaryDirectory() as tmp:
            last = Path(tmp) / "last.n5jobs"
            stale = Path(tmp) / "stale.n5jobs"
            last.touch()
            self.assertEqual(recent_joblists(str(last), [str(stale)]), (str(last),))

    def test_opening_original_again_retains_intent(self):
        with tempfile.TemporaryDirectory() as tmp:
            last = Path(tmp) / "I-drive" / "original.n5jobs"
            other = Path(tmp) / "other.n5jobs"
            other.touch()
            self.assertEqual(recent_joblists(str(last), [str(other)])[0], str(last))
            last.parent.mkdir()
            last.touch()
            self.assertEqual(recent_joblists(str(last), [str(other)])[0], str(last))
            self.assertEqual(remember_joblist(last, [str(other)])[0], str(last))

    def test_windows_letter_case_and_slashes_deduplicate(self):
        recent = recent_joblists(r"I:\Archive\original.n5jobs", [
            "i:/archive/original.n5jobs", "C:/other.n5jobs"
        ], existing_only=False)
        self.assertEqual(len(recent), 2)


if __name__ == "__main__":
    unittest.main()
