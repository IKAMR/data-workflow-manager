"""Dedicated a1 version and packaging boundary tests."""
from __future__ import annotations

from pathlib import Path
import re
import tomllib
import unittest

from version import APP_NAME, VERSION

ROOT = Path(__file__).resolve().parents[1]


class V019A1VersionTests(unittest.TestCase):
    def test_a1_milestone_and_identity(self):
        self.assertEqual(APP_NAME, "Data Workflow Manager")
        match = re.fullmatch(r"(\d+)\.(\d+)\.(\d+)(?:-a(\d+)(?:\.(\d+))*)?", VERSION)
        self.assertIsNotNone(match, VERSION)
        release = tuple(int(match.group(i)) for i in (1, 2, 3))
        self.assertGreaterEqual(release, (0, 1, 9))
        if release == (0, 1, 9) and match.group(4) is not None:
            self.assertGreaterEqual(int(match.group(4)), 1)

    def test_distribution_version_matches_pep440_alpha(self):
        with (ROOT / "pyproject.toml").open("rb") as file:
            project = tomllib.load(file)["project"]
        self.assertEqual(project["version"], VERSION.replace("-a", "a"))
        self.assertEqual(project["name"], "noark5-workflow-manager")

    def test_v018_release_version_not_overwritten(self):
        with (ROOT / "version.py").open("r", encoding="utf-8") as file:
            source = file.read()
        self.assertEqual(source, f'APP_NAME = "Data Workflow Manager"\nVERSION = "{VERSION}"\n')


if __name__ == "__main__":
    unittest.main()
