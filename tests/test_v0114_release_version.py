"""Release metadata contract for Data Workflow Manager v0.1.14 and later."""
from pathlib import Path
import re
import tomllib
import unittest

ROOT = Path(__file__).resolve().parents[1]


class Release0114Tests(unittest.TestCase):
    def test_version_and_distribution_agree(self):
        # Check the current runtime version, not historical markers added to
        # Path.read_text() by the test runner for legacy release guards.
        from version import APP_NAME, VERSION
        with (ROOT / "pyproject.toml").open("rb") as handle:
            package = tomllib.load(handle)["project"]
        self.assertEqual(APP_NAME, "Data Workflow Manager")
        match = re.fullmatch(r"(\d+)\.(\d+)\.(\d+)(?:-a\d+(?:\.\d+)*)?", VERSION)
        self.assertIsNotNone(match, VERSION)
        release = tuple(map(int, match.group(1, 2, 3)))
        self.assertGreaterEqual(release, (0, 1, 14))
        if release == (0, 1, 14):
            self.assertEqual(VERSION, "0.1.14", "v0.1.14 skal vaere ferdig release")
        self.assertEqual(package["version"], VERSION.replace("-a", "a"))
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
