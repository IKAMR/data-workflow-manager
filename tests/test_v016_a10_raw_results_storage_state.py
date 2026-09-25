from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class V016A10RawResultsStorageStateTests(unittest.TestCase):

    def test_raw_results_distinguish_unavailable_storage_from_zero_results(self):
        source = (ROOT / "gui" / "result_history_dialog.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("def raw_results_storage_unavailable", source)
        self.assertIn("if raw_results_storage_unavailable(self.job):", source)
        self.assertIn("Dette betyr ikke at jobben har 0 råresultater.", source)

    def test_unavailable_storage_message_matches_depot_semantics(self):
        source = (ROOT / "gui" / "result_history_dialog.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("LAGRING UTILGJENGELIG", source)
        self.assertIn("Koble til / lås opp lagringen og trykk Oppdater.", source)
        self.assertIn("Forventet Work-bane:", source)

    def test_expected_raw_result_file_is_shown(self):
        source = (ROOT / "gui" / "result_history_dialog.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("Forventet råresultatfil:", source)
        self.assertIn('"raw-results.jsonl"', source)

    def test_zero_results_text_is_only_after_storage_availability_check(self):
        source = (ROOT / "gui" / "result_history_dialog.py").read_text(
            encoding="utf-8"
        )
        unavailable_pos = source.index(
            "if raw_results_storage_unavailable(self.job):"
        )
        zero_pos = source.index(
            "Ingen råresultater er lagret for denne jobben ennå."
        )
        self.assertLess(unavailable_pos, zero_pos)


if __name__ == "__main__":
    unittest.main()
