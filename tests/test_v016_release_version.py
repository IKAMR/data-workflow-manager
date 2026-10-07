from __future__ import annotations

from pathlib import Path
import re
import unittest

from version import VERSION
from tests.version_assertions import assert_v016_at_least

ROOT = Path(__file__).resolve().parents[1]


class ReleaseVersionCompatibilityTests(unittest.TestCase):
    def test_final_v016_is_newer_than_last_alpha(self):
        assert_v016_at_least(self, f'VERSION = "{VERSION}"', 39)

    def test_version_file_is_clean_final_release_or_newer_series(self):
        # The exact v0.1.6 release file was locked at release time.  Later
        # development series are valid successors and must not be forced back
        # to the old release string by this historical regression test.
        with open(ROOT / "version.py", "r", encoding="utf-8") as handle:
            source = handle.read()
        match = re.fullmatch(
            r'APP_NAME = "Data Workflow Manager"\nVERSION = "(\d+)\.(\d+)\.(\d+)(?:-a\d+(?:\.\d+)*)?"\n',
            source,
        )
        self.assertIsNotNone(match, source)
        release = tuple(int(match.group(index)) for index in (1, 2, 3))
        self.assertGreaterEqual(release, (0, 1, 6))
        if release == (0, 1, 6):
            self.assertEqual(
                source,
                'APP_NAME = "Data Workflow Manager"\nVERSION = "0.1.6"\n',
            )


if __name__ == "__main__":
    unittest.main()
