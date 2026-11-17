"""a5 regression: actual runtime and distribution identities must stay aligned.

The a5 Siegfried parallel tests remain in test_v022_a5_siegfried_parallel.py.
This file does not rewrite any historical test or modify the test runner.
"""
from __future__ import annotations

from pathlib import Path
import tomllib
import unittest

from version import APP_NAME, VERSION
from tests.version_assertions import assert_release_at_least

ROOT = Path(__file__).resolve().parents[1]


class A5VersionMetadataTests(unittest.TestCase):
    def test_runtime_and_physical_version_meet_a5_milestone(self):
        self.assertEqual(APP_NAME, "Data Workflow Manager")
        assert_release_at_least(self, f'VERSION = "{VERSION}"', "0.2.2", 5)
        self.assertEqual(
            (ROOT / "version.py").read_text(encoding="utf-8"),
            f'APP_NAME = "Data Workflow Manager"\nVERSION = "{VERSION}"\n',
        )

    def test_distribution_version_matches_runtime(self):
        with (ROOT / "pyproject.toml").open("rb") as stream:
            project = tomllib.load(stream)["project"]
        self.assertEqual(project["name"], "noark5-workflow-manager")
        self.assertEqual(project["version"], VERSION.replace("-a", "a"))


if __name__ == "__main__":
    unittest.main()
