"""Release boundary for v0.2.1 and compatibility with its alpha milestones."""
from __future__ import annotations

from pathlib import Path
import re
import tomllib
import unittest

from version import APP_NAME, VERSION
from tests.version_assertions import assert_release_at_least

ROOT = Path(__file__).resolve().parents[1]


class V021ReleaseTests(unittest.TestCase):
    def test_final_release_identity_and_distribution(self):
        self.assertEqual(APP_NAME, "Data Workflow Manager")
        self.assertRegex(VERSION, r"^\d+\.\d+\.\d+(?:-a\d+)?$")
        base = tuple(map(int, VERSION.split("-", 1)[0].split(".")))
        self.assertGreaterEqual(base, (0, 2, 1))
        if base == (0, 2, 1):
            self.assertEqual(VERSION, "0.2.1")
        with (ROOT / "pyproject.toml").open("rb") as stream:
            project = tomllib.load(stream)["project"]
        self.assertEqual(project["name"], "noark5-workflow-manager")
        self.assertEqual(project["version"], VERSION.replace("-a", "a"))

    def test_physical_version_file_is_clean(self):
        self.assertEqual(
            (ROOT / "version.py").read_text(encoding="utf-8"),
            f'APP_NAME = "Data Workflow Manager"\nVERSION = "{VERSION}"\n',
        )

    def test_every_a16_milestone_satisfied_by_final_release(self):
        declaration = f'VERSION = "{VERSION}"'
        for alpha in range(1, 17):
            with self.subTest(alpha=alpha):
                assert_release_at_least(self, declaration, "0.2.1", alpha)
        with self.assertRaises(AssertionError):
            assert_release_at_least(self, 'VERSION = "0.2.1-a15"', "0.2.1", 16)

    def test_release_notes_cover_scope_and_unresolved_work(self):
        text = (ROOT / "docs" / "RELEASE-v0.2.1.md").read_text(encoding="utf-8")
        for term in (
            "3.1", "4.0", "5.0", "KDRS", "Saxon/lxml", "Arkade 5",
            "M053", "N5.22", "XML", "SHA-256", "Work", "49",
            "47", "info.xml", "dias-mets.xml", "Periodevurdering",
            "Depotvurdering", "Test Depot", "test.bat", "ikke",
        ):
            with self.subTest(term=term):
                self.assertIn(term.casefold(), text.casefold())
        self.assertIn("c8aedccb331213fcf5faaceadff7ad7ce4f8d8c9", text)
        history = (ROOT / "docs" / "RELEASES.md").read_text(encoding="utf-8")
        self.assertIn("## v0.2.1\n", history)

    def test_required_release_features_are_preserved_in_tree(self):
        for relpath in (
            "gui_qt/result_navigation_v020_a6.py",
            "gui_qt/dias_metadata_v021_a16.py",
            "gui_qt/checklist_v021_a15.py",
            "noark5_workflow/reporting/dias_metadata_v021_a16.py",
            "noark5_workflow/reporting/dias_metadata_views_v021_a16_1.py",
            "noark5_workflow/reporting/qa_decision_v021_a12.py",
        ):
            with self.subTest(path=relpath):
                self.assertTrue((ROOT / relpath).is_file(), relpath)


if __name__ == "__main__":
    unittest.main()
