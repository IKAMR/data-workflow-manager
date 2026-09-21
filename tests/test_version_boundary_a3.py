from pathlib import Path
import re
import unittest

from version import VERSION

ROOT = Path(__file__).resolve().parents[1]


class VersionBoundaryA3Tests(unittest.TestCase):
    def test_internal_version_uses_supported_release_or_alpha_format(self):
        self.assertRegex(
            VERSION,
            r"^\d+\.\d+\.\d+(?:-a\d+(?:\.\d+)*)?$",
        )

    def test_release_version_has_no_alpha_suffix(self):
        if "-a" not in VERSION:
            self.assertRegex(VERSION, r"^\d+\.\d+\.\d+$")

    def test_alpha_state_documents_are_not_permanent(self):
        docs = ROOT / "docs"
        permanent_alpha_docs = [
            path.name
            for path in docs.glob("*a*.md")
            if path.name.lower().startswith(("a1", "a2", "a3"))
        ]
        self.assertEqual(permanent_alpha_docs, [])


if __name__ == "__main__":
    unittest.main()
