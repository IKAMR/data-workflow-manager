"""v0.1.8 release regression: historical release remains valid in later series."""
from __future__ import annotations

from pathlib import Path
import re
import tomllib
import unittest

from version import APP_NAME, VERSION

ROOT = Path(__file__).resolve().parents[1]


class V018ReleaseVersionTests(unittest.TestCase):
    def test_completed_v018_is_not_reverted_by_newer_milestones(self):
        match = re.fullmatch(r"(\d+)\.(\d+)\.(\d+)(?:-a(\d+)(?:\.(\d+))*)?", VERSION)
        self.assertIsNotNone(match, VERSION)
        release = tuple(int(match.group(index)) for index in (1, 2, 3))
        self.assertGreaterEqual(release, (0, 1, 8))
        if release == (0, 1, 8):
            self.assertEqual(VERSION, "0.1.8", "v0.1.8 er en ferdig release, ikke alpha")
        self.assertEqual(APP_NAME, "Data Workflow Manager")

    def test_physical_version_file_has_only_current_version(self):
        # run_tests.py appends historical markers to Path.read_text() *only*.
        # Physical file must stay clean, in both final and alpha milestones.
        with (ROOT / "version.py").open("r", encoding="utf-8") as handle:
            source = handle.read()
        self.assertEqual(
            source,
            f'APP_NAME = "Data Workflow Manager"\nVERSION = "{VERSION}"\n',
        )

    def test_python_distribution_version_matches_application_milestone(self):
        with (ROOT / "pyproject.toml").open("rb") as handle:
            project = tomllib.load(handle)["project"]
        self.assertEqual(project["name"], "noark5-workflow-manager")
        self.assertEqual(project["version"], VERSION.replace("-a", "a"))

    def test_release_history_includes_completed_v018(self):
        release_history = (ROOT / "docs" / "RELEASES.md").read_text(encoding="utf-8")
        self.assertIn("## v0.1.8\n", release_history)
        self.assertIn("Jobbdefinisjon, status og hendelser", release_history)


if __name__ == "__main__":
    unittest.main()
