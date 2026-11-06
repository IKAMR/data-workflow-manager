"""v0.1.9 release boundary; allow later series without reopening this release."""
from __future__ import annotations

from pathlib import Path
import re
import tomllib
import unittest

from version import APP_NAME, VERSION

ROOT = Path(__file__).resolve().parents[1]


class V019ReleaseVersionTests(unittest.TestCase):
    def test_v019_is_completed_release_or_newer_series(self):
        match = re.fullmatch(r"(\d+)\.(\d+)\.(\d+)(?:-a(\d+)(?:\.(\d+))*)?", VERSION)
        self.assertIsNotNone(match, VERSION)
        release = tuple(int(match.group(index)) for index in (1, 2, 3))
        self.assertGreaterEqual(release, (0, 1, 9))
        if release == (0, 1, 9):
            self.assertEqual(VERSION, "0.1.9", "v0.1.9 skal ikke ha alpha-suffiks")
        self.assertEqual(APP_NAME, "Data Workflow Manager")

    def test_physical_version_file_is_clean(self):
        # Read the physical file, not the test-runner's historical alpha view.
        with (ROOT / "version.py").open("r", encoding="utf-8") as handle:
            source = handle.read()
        self.assertEqual(
            source, f'APP_NAME = "Data Workflow Manager"\nVERSION = "{VERSION}"\n',
        )

    def test_distribution_version_matches_application(self):
        with (ROOT / "pyproject.toml").open("rb") as handle:
            project = tomllib.load(handle)["project"]
        self.assertEqual(project["name"], "noark5-workflow-manager")
        self.assertEqual(project["version"], VERSION.replace("-a", "a"))

    def test_release_history_documents_a1_through_a4(self):
        notes = (ROOT / "docs" / "RELEASES.md").read_text(encoding="utf-8")
        self.assertIn("## v0.1.9\n", notes)
        self.assertIn("## v0.1.8\n", notes)
        section = notes.split("## v0.1.9\n", 1)[1].split("## v0.1.8\n", 1)[0]
        for item in ("Kildeoversikt", "Arkade-dekning", "KDRS Query",
                     "Depotvurdering", "jobb-UUID", "lagringsmodell", "storage-roots.json"):
            self.assertIn(item, section)


if __name__ == "__main__":
    unittest.main()
