"""Release metadata contract for Data Workflow Manager v0.1.14."""
from pathlib import Path
import tomllib
import unittest

ROOT = Path(__file__).resolve().parents[1]


class Release0114Tests(unittest.TestCase):
    def test_version_and_distribution_agree(self):
        # The shared test runner appends historical VERSION markers to
        # Path.read_text() for legacy guards. Import the authoritative runtime
        # constants instead of executing the compatibility view as Python.
        from version import APP_NAME, VERSION
        with (ROOT / "pyproject.toml").open("rb") as handle:
            package = tomllib.load(handle)["project"]
        self.assertEqual(APP_NAME, "Data Workflow Manager")
        self.assertEqual(VERSION, "0.1.14")
        self.assertEqual(package["version"], VERSION)
        self.assertEqual(package["name"], "noark5-workflow-manager")

    def test_release_notes_cover_all_increments(self):
        notes = (ROOT / "docs" / "RELEASES.md").read_text(encoding="utf-8")
        self.assertEqual(notes.count("## v0.1.14\n"), 1)
        self.assertLess(notes.index("## v0.1.14\n"), notes.index("## v0.1.13\n"))
        section = notes.split("## v0.1.14\n", 1)[1].split("## v0.1.13\n", 1)[0]
        for term in (
            "M300", "M082", "M500", "M502", "XML-evidens", "XPath",
            "XSD", "5.0", "4.0", "3.1", "SHA-256", "Erfaringer",
            "strukturtre", "XML-utdrag", "custom_work", "flerskjerm",
            "Prøv igjen", "Fortsett uten jobb", "kanonisk",
        ):
            with self.subTest(term=term):
                self.assertIn(term.casefold(), section.casefold())


if __name__ == "__main__":
    unittest.main()
