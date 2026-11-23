"""Permanent alpha/final workflow tests, without alpha-locked assertions."""
from __future__ import annotations

from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import tomllib
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))
import release_gate  # noqa: E402
import release_prepare  # noqa: E402


class ReleasePrepareTests(unittest.TestCase):
    def _fixture(self, *, alpha: str = "7", notes: bool = True) -> Path:
        temp = TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        (root / "docs").mkdir()
        (root / "tests").mkdir()
        (root / "version.py").write_text(
            f'APP_NAME = "Data Workflow Manager"\nVERSION = "0.2.6-a{alpha}"\n',
            encoding="utf-8",
        )
        (root / "pyproject.toml").write_text(
            f'[project]\nname = "noark5-workflow-manager"\nversion = "0.2.6a{alpha}"\n',
            encoding="utf-8",
        )
        (root / "docs" / "RELEASES.md").write_text(
            '# Versjonshistorikk\n\n## v0.2.6\n\nReelle endringer\n\n## v0.2.5\n\nHistorikk\n',
            encoding="utf-8",
        )
        if notes:
            (root / "docs" / "RELEASE-v0.2.6.md").write_text(
                '# v0.2.6\n\nDetaljer\n', encoding="utf-8",
            )
        return root

    def test_current_alpha_is_ready_for_eventual_release(self):
        from version import VERSION
        from tests.version_assertions import assert_release_at_least
        assert_release_at_least(self, f'VERSION = "{VERSION}"', '0.2.6', 1)
        base, alpha = release_prepare.current_identity(ROOT)
        self.assertGreaterEqual(tuple(map(int, base.split('.'))), (0, 2, 6))
        if base == '0.2.6' and alpha is not None:
            self.assertGreaterEqual(int(alpha), 1)
        with (ROOT / "pyproject.toml").open('rb') as stream:
            self.assertEqual(tomllib.load(stream)['project']['version'], VERSION.replace('-a', 'a'))
        self.assertEqual(release_gate.release_errors(ROOT, require_final=False), [])

    def test_promotion_only_changes_two_version_files(self):
        root = self._fixture()
        notes = (root / "docs" / "RELEASE-v0.2.6.md").read_bytes()
        history = (root / "docs" / "RELEASES.md").read_bytes()
        ok, issues = release_prepare.promote(root)
        self.assertTrue(ok, issues)
        self.assertEqual((root / "version.py").read_text(encoding='utf-8'),
                         'APP_NAME = "Data Workflow Manager"\nVERSION = "0.2.6"\n')
        with (root / "pyproject.toml").open('rb') as stream:
            self.assertEqual(tomllib.load(stream)['project']['version'], '0.2.6')
        self.assertEqual((root / "docs" / "RELEASE-v0.2.6.md").read_bytes(), notes)
        self.assertEqual((root / "docs" / "RELEASES.md").read_bytes(), history)
        self.assertEqual(release_gate.release_errors(root), [])

    def test_missing_final_notes_prevents_any_writes(self):
        root = self._fixture(notes=False)
        before = ((root / "version.py").read_bytes(), (root / "pyproject.toml").read_bytes())
        ok, issues = release_prepare.promote(root)
        self.assertFalse(ok)
        self.assertTrue(any('RELEASE-v0.2.6' in msg for msg in issues))
        self.assertEqual((root / "version.py").read_bytes(), before[0])
        self.assertEqual((root / "pyproject.toml").read_bytes(), before[1])

    def test_exact_alpha_lock_is_detected_during_alpha_development(self):
        root = self._fixture()
        (root / "tests" / "test_v026_a7_bad.py").write_text(
            'import unittest\nfrom version import VERSION\n'
            'class TestBad(unittest.TestCase):\n'
            '  def test_version(self):\n'
            '    self.assertEqual(VERSION, "0.2.6-a7")\n', encoding="utf-8",
        )
        issues = release_gate.release_errors(root, require_final=False)
        self.assertTrue(any('hardkodet VERSION' in issue for issue in issues), issues)
        original = (root / "version.py").read_bytes()
        self.assertFalse(release_prepare.promote(root)[0])
        self.assertEqual((root / "version.py").read_bytes(), original)

    def test_generic_named_test_is_also_checked(self):
        root = self._fixture()
        (root / "tests" / "test_current_version.py").write_text(
            'import unittest\nfrom version import VERSION\n'
            'class TestBad(unittest.TestCase):\n'
            '  def test_version(self):\n'
            '    self.assertRegex(VERSION, r"^0\\.2\\.6-a\\d+$")\n', encoding="utf-8",
        )
        issues = release_gate.release_errors(root, require_final=False)
        self.assertTrue(any('assertRegex' in issue for issue in issues), issues)

    def test_mismatched_distribution_rejected_in_alpha(self):
        root = self._fixture()
        (root / "pyproject.toml").write_text('[project]\nversion = "0.2.5"\n', encoding="utf-8")
        self.assertTrue(any('pyproject.toml' in e for e in
                            release_gate.release_errors(root, require_final=False)))
        self.assertFalse(release_prepare.promote(root)[0])

    def test_final_promotion_is_not_repeated(self):
        root = self._fixture()
        self.assertTrue(release_prepare.promote(root)[0])
        self.assertFalse(release_prepare.promote(root)[0])

    def test_notes_are_not_synthesized_when_missing(self):
        root = self._fixture(notes=False)
        ok, problems = release_prepare.promote(root)
        self.assertFalse(ok, problems)
        self.assertFalse((root / "docs" / "RELEASE-v0.2.6.md").exists())


if __name__ == '__main__':
    unittest.main()
