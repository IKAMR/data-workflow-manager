import unittest
from gui.depot_result_views_a17 import _find_normalized_test

class V015A7ArkadeCoverageDrilldownTests(unittest.TestCase):
    def test_finds_test_case_insensitively(self):
        normalized = {"tests": [{"test_id": "N5.30", "results": [{"message": "x"}]}]}
        self.assertEqual(_find_normalized_test(normalized, "n5.30")["test_id"], "N5.30")

    def test_missing_test_returns_none(self):
        self.assertIsNone(_find_normalized_test({"tests": []}, "N5.30"))

if __name__ == "__main__":
    unittest.main()
