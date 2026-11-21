"""Release notes must be reusable without named client extractions.

Only public release notes are inspected; internal test data and technical
reports retain their own provenance and source identifiers.
"""
from __future__ import annotations

from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
EXTRACTION_ID = re.compile(r"(?<![0-9])[0-9]{4}[_-][0-9]{3,5}\b")
NAMED_MUNICIPALITY = re.compile(
    r"\b[A-Z\u00c5\u00c6\u00d8][a-z\u00e5\u00e6\u00f8]+"
    r"(?:[ -][A-Z\u00c5\u00c6\u00d8][a-z\u00e5\u00e6\u00f8]+){0,2}"
    r"[ ]kommune\b"
)


class ReleaseDescriptionPrivacyTests(unittest.TestCase):
    def test_release_notes_do_not_name_specific_extractions_or_municipalities(self):
        docs = ROOT / 'docs'
        files = sorted(docs.glob('RELEASE-v*.md')) + [docs / 'RELEASES.md']
        self.assertGreaterEqual(len(files), 5)
        for path in files:
            with self.subTest(path=path.name):
                text = path.read_text(encoding='utf-8')
                self.assertIsNone(EXTRACTION_ID.search(text), path.name)
                self.assertIsNone(NAMED_MUNICIPALITY.search(text), path.name)


if __name__ == '__main__':
    unittest.main()
