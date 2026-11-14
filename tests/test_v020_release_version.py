"""v0.2.0 release boundary: actual runtime version and historical milestones."""
from __future__ import annotations

from pathlib import Path
import re
import tomllib
import unittest

from version import APP_NAME, VERSION
from tests.version_assertions import assert_release_at_least

ROOT = Path(__file__).resolve().parents[1]


class V020ReleaseTests(unittest.TestCase):
    def test_completed_release_or_later_series(self):
        self.assertRegex(VERSION, r"^\d+\.\d+\.\d+(?:-a\d+)?$")
        base = tuple(map(int, VERSION.split("-", 1)[0].split(".")))
        self.assertGreaterEqual(base, (0, 2, 0))
        if base == (0, 2, 0):
            self.assertEqual(VERSION, "0.2.0")
        self.assertEqual(APP_NAME, "Data Workflow Manager")

    def test_physical_version_is_unmodified_release(self):
        self.assertEqual(
            (ROOT / "version.py").read_text(encoding="utf-8"),
            f'APP_NAME = "Data Workflow Manager"\nVERSION = "{VERSION}"\n',
        )

    def test_distribution_version_agrees(self):
        with (ROOT / "pyproject.toml").open("rb") as f:
            info = tomllib.load(f)["project"]
        self.assertEqual(info["name"], "noark5-workflow-manager")
        self.assertEqual(info["version"], VERSION.replace("-a", "a"))

    def test_old_alpha_milestones_are_satisfied(self):
        declaration = f'VERSION = "{VERSION}"'
        for alpha in range(1, 7):
            with self.subTest(alpha=alpha):
                assert_release_at_least(self, declaration, "0.2.0", alpha)
        with self.assertRaises(AssertionError):
            assert_release_at_least(self, 'VERSION = "0.2.0-a5"', "0.2.0", 6)

    def test_release_scope_and_deferred_plan_are_documented(self):
        notes = (ROOT / "docs/RELEASE-v0.2.0.md").read_text(encoding="utf-8")
        plan = (ROOT / "docs/ROADMAP-ETTER-v0.2.0.md").read_text(encoding="utf-8")
        for label in ("Ingest", "antivirus", "Kontroll", "Rapportering",
                      "Bevaring", "CRM", "Innsyn", "Noark 5"):
            self.assertIn(label, notes)
        for name in ("a7", "a8", "a9", "a10", "a11", "a12", "Beta"):
            self.assertIn(name, plan)


if __name__ == "__main__":
    unittest.main()
