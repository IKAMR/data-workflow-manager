from pathlib import Path
import re
import tomllib
import unittest

from version import APP_NAME, VERSION

ROOT = Path(__file__).resolve().parents[1]


class V014A1IdentityTests(unittest.TestCase):
    def test_app_branding_and_alpha_development_line(self):
        self.assertEqual(APP_NAME, "Data Workflow Manager")
        self.assertRegex(
            VERSION,
            r"^\d+\.\d+\.\d+(?:-a\d+(?:\.\d+)*)?$",
        )

    def test_repository_identity_is_documented(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("# Data Workflow Manager", readme)
        self.assertIn("IKAMR/data-workflow-manager", readme)
        self.assertIn("v0.1.3", readme)
        self.assertIn("Noark 5 er den første", readme)

    def test_legacy_technical_identifiers_are_intentionally_preserved(self):
        migration = (ROOT / "docs" / "IDENTITY-MIGRATION.md").read_text(
            encoding="utf-8"
        )
        for value in (
            "noark5_workflow",
            "n5wf",
            ".n5jobs",
            "noark5-workflow-manager",
        ):
            self.assertIn(value, migration)

        pyproject = tomllib.loads(
            (ROOT / "pyproject.toml").read_text(encoding="utf-8")
        )
        self.assertEqual(pyproject["project"]["name"], "noark5-workflow-manager")
        # The packaging version may advance beyond the historic v0.1.4a1
        # milestone. Preserve the technical name, not a frozen alpha version.
        package_version = pyproject["project"]["version"]
        self.assertRegex(package_version, r"^\d+\.\d+\.\d+(?:a\d+)?$")
        release = tuple(int(part) for part in re.match(
            r"^(\d+)\.(\d+)\.(\d+)", package_version
        ).groups())
        self.assertGreaterEqual(release, (0, 1, 4))
        self.assertEqual(pyproject["project"]["description"], "Data Workflow Manager")

    def test_old_repository_name_is_not_to_be_reused_immediately(self):
        migration = (ROOT / "docs" / "IDENTITY-MIGRATION.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("skal **ikke opprettes på nytt", migration)
        self.assertIn("redirect", migration)


if __name__ == "__main__":
    unittest.main()
