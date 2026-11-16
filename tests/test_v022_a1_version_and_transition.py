"""v0.2.2-a1 version transition and historical regression safeguards."""
from __future__ import annotations

import importlib.util
from pathlib import Path
import re
import tomllib
import unittest

from version import APP_NAME, VERSION
from tests.version_assertions import assert_release_at_least

ROOT = Path(__file__).resolve().parents[1]
UPGRADER = ROOT / 'tools' / 'upgrade_v021_test_guards_v022_a1.py'


class V022A1VersionTests(unittest.TestCase):
    def test_runtime_and_distribution_version_are_real(self):
        self.assertEqual(APP_NAME, 'Data Workflow Manager')
        assert_release_at_least(self, f'VERSION = "{VERSION}"', '0.2.2', 1)
        self.assertEqual((ROOT / 'version.py').read_text(encoding='utf8'),
                         f'APP_NAME = "Data Workflow Manager"\nVERSION = "{VERSION}"\n')
        with (ROOT / 'pyproject.toml').open('rb') as stream:
            info = tomllib.load(stream)['project']
        self.assertEqual(info['version'], VERSION.replace('-a', 'a'))
        self.assertEqual(info['name'], 'noark5-workflow-manager')

    def test_earlier_release_milestones_still_satisfied(self):
        actual = f'VERSION = "{VERSION}"'
        for n in (1, 4, 7, 8, 9, 10, 12, 16):
            with self.subTest(alpha=n):
                assert_release_at_least(self, actual, '0.2.1', n)
        assert_release_at_least(self, actual, '0.2.2', 1)
        # Test the lower-bound behavior on a fixed synthetic declaration, not
        # against the current version (which will advance beyond a1).
        with self.assertRaises(AssertionError):
            assert_release_at_least(self, 'VERSION = "0.2.2-a1"', '0.2.2', 2)

    def test_obsolete_version_guards_were_migrated_not_bypassed(self):
        for relative, n in (
            ('tests/test_v021_a1_xpath_audit.py', 1),
            ('tests/test_v021_a2_xpath_regression.py', 2),
            ('tests/test_v021_a3_xpath_version_qa.py', 3),
            ('tests/test_v021_a4_xpath_metadata_qa.py', 4),
            ('tests/test_v021_a7_requirement_matrix.py', 7),
        ):
            with self.subTest(file=relative):
                original = (ROOT / relative).read_text(encoding='utf8')
                self.assertIn(
                    f'assert_release_at_least(self, f\'VERSION = "{{VERSION}}"\', "0.2.1", {n})',
                    original,
                )
                self.assertNotRegex(original, r"self\.assertRegex\(VERSION,\s*r['\"]\^0\\\.2\\\.1")


class V022A1MigrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        spec = importlib.util.spec_from_file_location('v022_upgrade_guards', UPGRADER)
        if spec is None or spec.loader is None:
            raise RuntimeError('Finner ikke historisk versjonsmigrering')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        cls.upgrade = staticmethod(module.upgrade)

    def test_upgrade_keeps_original_functional_assertions(self):
        old = ("        self.assertEqual(result, 27)\n"
               "        self.assertRegex(VERSION, r'^0\\.2\\.1(?:-a[1-9][0-9]*)?$')\n"
               "        self.assertEqual(status, 'PASS')\n")
        new = self.upgrade(old, 1)
        self.assertIn('self.assertEqual(result, 27)', new)
        self.assertIn("self.assertEqual(status, 'PASS')", new)
        self.assertIn('assert_release_at_least(self,', new)
        self.assertEqual(self.upgrade(new, 1), new)

    def test_mismatch_is_rejected_without_silent_loss_of_test(self):
        with self.assertRaises(ValueError):
            self.upgrade("        self.assertEqual(VERSION, 'fake')\n", 4)
        with self.assertRaises(ValueError):
            self.upgrade("        self.assertRegex(VERSION, r'^0\\.2\\.1-a[1-9]+$')\n"
                         "        self.assertRegex(VERSION, r'^0\\.2\\.1-a[2-9]+$')\n", 1)


if __name__ == '__main__':
    unittest.main()
