from __future__ import annotations

from pathlib import Path
import re
import unittest

from version import APP_NAME, VERSION

ROOT = Path(__file__).resolve().parents[1]


class V018ReleaseVersionTests(unittest.TestCase):
    def test_final_version_has_no_alpha_suffix(self):
        self.assertEqual(VERSION, "0.1.8")
        self.assertNotIn("-a", VERSION)
        self.assertEqual(APP_NAME, "Data Workflow Manager")

    def test_physical_version_file_is_clean_release(self):
        # run_tests.py adds historical markers to Path.read_text() only.
        # Read the physical release file directly, as required by the release rule.
        with (ROOT / "version.py").open("r", encoding="utf-8") as handle:
            source = handle.read()
        self.assertEqual(
            source,
            'APP_NAME = "Data Workflow Manager"\nVERSION = "0.1.8"\n',
        )

    def test_python_distribution_version_matches_release(self):
        source = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
        self.assertRegex(source, r'(?m)^name = "noark5-workflow-manager"$')
        versions = re.findall(r'(?m)^version = "([^"]+)"$', source)
        self.assertEqual(versions, [VERSION])

    def test_release_history_includes_v018(self):
        release_history = (ROOT / "docs" / "RELEASES.md").read_text(encoding="utf-8")
        self.assertIn("## v0.1.8\n", release_history)
        self.assertIn("Jobbdefinisjon, status og hendelser", release_history)


if __name__ == "__main__":
    unittest.main()
