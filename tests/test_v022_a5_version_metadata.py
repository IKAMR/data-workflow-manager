"""a5 regression: actual runtime and distribution identities must stay aligned.

The a5 Siegfried parallel tests remain in test_v022_a5_siegfried_parallel.py.
This file does not rewrite any historical test or modify the test runner.
"""
from __future__ import annotations

from pathlib import Path
import tomllib
import unittest

from version import APP_NAME, VERSION

ROOT = Path(__file__).resolve().parents[1]


class A5VersionMetadataTests(unittest.TestCase):
    def test_runtime_and_physical_version_are_a5(self):
        self.assertEqual(APP_NAME, "Data Workflow Manager")
        self.assertEqual(VERSION, "0.2.2-a5")
        self.assertEqual(
            (ROOT / "version.py").read_text(encoding="utf-8"),
            'APP_NAME = "Data Workflow Manager"\nVERSION = "0.2.2-a5"\n',
        )

    def test_distribution_version_matches_runtime(self):
        with (ROOT / "pyproject.toml").open("rb") as stream:
            project = tomllib.load(stream)["project"]
        self.assertEqual(project["name"], "noark5-workflow-manager")
        self.assertEqual(project["version"], "0.2.2a5")
        self.assertEqual(project["version"], VERSION.replace("-a", "a"))


if __name__ == "__main__":
    unittest.main()
