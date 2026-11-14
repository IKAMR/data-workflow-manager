"""Regression: historical version checks remain strict after the v0.2 transition."""
from __future__ import annotations

import unittest
from version_assertions import assert_release_at_least, assert_v016_at_least


class HistoricalVersionBoundaryTests(unittest.TestCase):
    def test_newer_minor_satisfies_old_milestone(self):
        assert_v016_at_least(self, 'VERSION = "0.2.0-a1"', 39)
        assert_release_at_least(self, 'VERSION = "0.2.0-a1"', '0.1.9', 2)

    def test_completed_historical_release_satisfies_alpha(self):
        assert_v016_at_least(self, 'VERSION = "0.1.6"', 39)
        assert_v016_at_least(self, 'VERSION = "0.1.15"', 39)

    def test_same_release_below_alpha_is_rejected(self):
        with self.assertRaises(AssertionError):
            assert_v016_at_least(self, 'VERSION = "0.1.6-a8"', 9)

    def test_same_alpha_below_subincrement_is_rejected(self):
        with self.assertRaises(AssertionError):
            assert_v016_at_least(self, 'VERSION = "0.1.6-a23.9"', 23, 10)
        assert_v016_at_least(self, 'VERSION = "0.1.6-a23.10"', 23, 10)
        assert_v016_at_least(self, 'VERSION = "0.1.6-a14.3.1"', 14, 3)

    def test_consolidated_historical_alpha_preserves_legacy_meaning(self):
        with self.assertRaises(AssertionError):
            assert_v016_at_least(self, 'VERSION = "0.1.6-a21"', 21, 14)
        assert_v016_at_least(self, 'VERSION = "0.1.6-a21"', 21, 14, consolidated_alpha=True)

    def test_older_release_is_rejected_even_with_large_alpha(self):
        with self.assertRaises(AssertionError):
            assert_v016_at_least(self, 'VERSION = "0.1.5-a999"', 1)

    def test_invalid_and_duplicate_versions_are_rejected(self):
        for text in ('VERSION = "not-a-version"', 'VERSION = "0.2.0-a1"\nVERSION = "0.1.6-a39"'):
            with self.subTest(text=text), self.assertRaises(AssertionError):
                assert_v016_at_least(self, text, 39)

    def test_same_019_release_follows_alpha_floor(self):
        with self.assertRaises(AssertionError):
            assert_release_at_least(self, 'VERSION = "0.1.9-a1"', '0.1.9', 2)
        assert_release_at_least(self, 'VERSION = "0.1.9-a2"', '0.1.9', 2)
        assert_release_at_least(self, 'VERSION = "0.1.10-a1"', '0.1.9', 2)


if __name__ == '__main__':
    unittest.main()
