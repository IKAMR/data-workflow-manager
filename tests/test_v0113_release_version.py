"""Version and release metadata for the final v0.1.13 release."""
from __future__ import annotations

from pathlib import Path
import tomllib
import unittest

from version import APP_NAME, VERSION

ROOT = Path(__file__).resolve().parents[1]


class V0113ReleaseVersionTests(unittest.TestCase):
    def test_final_version(self):
        self.assertEqual(APP_NAME, "Data Workflow Manager")
        self.assertEqual(VERSION, "0.1.13")

    def test_physical_version_file(self):
        with (ROOT / "version.py").open("r", encoding="utf-8") as stream:
            source = stream.read()
        self.assertEqual(source, 'APP_NAME = "Data Workflow Manager"\nVERSION = "0.1.13"\n')

    def test_package_version(self):
        with (ROOT / "pyproject.toml").open("rb") as stream:
            project = tomllib.load(stream)["project"]
        self.assertEqual(project["name"], "noark5-workflow-manager")
        self.assertEqual(project["version"], VERSION)

    def test_release_history(self):
        notes = (ROOT / "docs" / "RELEASES.md").read_text(encoding="utf-8")
        for section in ("## v0.1.13\n", "## v0.1.12\n", "## v0.1.11\n"):
            self.assertEqual(notes.count(section), 1)
        self.assertLess(notes.index("## v0.1.13\n"), notes.index("## v0.1.12\n"))
        self.assertLess(notes.index("## v0.1.12\n"), notes.index("## v0.1.11\n"))
        section = notes.split("## v0.1.13\n", 1)[1].split("## v0.1.12\n", 1)[0]
        for keyword in ("Enkel modus", "DIAS", "info.xml", "Work", "jobbliste", "Årsfordeling", "Siegfried", "Arkade 5"):
            with self.subTest(keyword=keyword):
                self.assertIn(keyword.casefold(), section.casefold())


if __name__ == "__main__":
    unittest.main()
