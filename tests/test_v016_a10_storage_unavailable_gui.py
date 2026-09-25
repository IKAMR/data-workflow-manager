from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class V016A10StorageUnavailableGuiTests(unittest.TestCase):

    def test_storage_unavailable_is_distinct_from_missing_report(self):
        runtime = (ROOT / "gui" / "persistent_app_a70.py").read_text(
            encoding="utf-8"
        )
        dialog = (ROOT / "gui" / "depot_assessment_dialog_a30.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("return None, expected, expected", runtime)
        self.assertIn(
            "Lagringsområdet for aktiv jobb er ikke tilgjengelig",
            dialog,
        )

    def test_missing_report_case_remains_possible_when_storage_is_online(self):
        runtime = (ROOT / "gui" / "persistent_app_a70.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("return None, expected, None", runtime)


if __name__ == "__main__":
    unittest.main()
