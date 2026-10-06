from __future__ import annotations

from pathlib import Path
import unittest

from version import VERSION
from tests.version_assertions import assert_v016_at_least

ROOT = Path(__file__).resolve().parents[1]


class ReleaseVersionCompatibilityTests(unittest.TestCase):
    def test_final_v016_is_newer_than_last_alpha(self):
        assert_v016_at_least(self, f'VERSION = "{VERSION}"', 39)

    def test_version_file_is_clean_final_release(self):
        # open() deliberately bypasses the historical compatibility view used
        # by test.bat for old alpha milestone guards.
        with open(ROOT / "version.py", "r", encoding="utf-8") as handle:
            source = handle.read()
        self.assertEqual(
            source,
            'APP_NAME = "Data Workflow Manager"\nVERSION = "0.1.6"\n',
        )
        self.assertNotIn("LAST_DEVELOPMENT_VERSION", source)
        self.assertNotIn("-a39", source)


if __name__ == "__main__":
    unittest.main()
