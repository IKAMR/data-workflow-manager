"""A17 integration invariants; no Qt or large XML required."""
from __future__ import annotations

from pathlib import Path
import tomllib
import unittest

ROOT = Path(__file__).resolve().parents[1]


class A17Wiring(unittest.TestCase):
    def test_both_version_metadata_fields_match(self):
        from version import VERSION
        with (ROOT / 'pyproject.toml').open('rb') as handle:
            self.assertEqual(tomllib.load(handle)['project']['version'], VERSION.replace('-a', 'a'))

    def test_child_worker_installs_a17_after_a13(self):
        source = (ROOT / 'noark5_workflow/a13_xpath_worker.py').read_text(encoding='utf-8')
        self.assertLess(source.index('a13_large_xml.install()'),source.index('a17_xpath_stream.install()'))
        self.assertIn('DWM_A13_EVENT',source)
        self.assertIn('noark5_workflow.analysis.xpath_diagnostics',source)

    def test_source_is_not_modified(self):
        source = (ROOT / 'noark5_workflow/analysis/a17_xpath_stream.py').read_text(encoding='utf-8')
        self.assertIn("events=('start','end')",source)
        self.assertIn('resolve_entities=False',source)
        self.assertIn('no_network=True',source)
        self.assertIn("'status':'error'",source)


if __name__ == '__main__':
    unittest.main()
