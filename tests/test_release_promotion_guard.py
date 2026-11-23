"""Permanent release rule: detect unfinished alpha -> final transitions."""
from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from importlib.util import module_from_spec, spec_from_file_location
import unittest

ROOT = Path(__file__).resolve().parents[1]
_spec = spec_from_file_location("_dwm_release_gate", ROOT / "tools" / "release_gate.py")
assert _spec is not None and _spec.loader is not None
_gate = module_from_spec(_spec)
_spec.loader.exec_module(_gate)
release_errors = _gate.release_errors


class ReleaseGateTests(unittest.TestCase):
    def test_current_version_is_consistent_already_during_alpha(self):
        from version import VERSION
        self.assertEqual(release_errors(ROOT, require_final='-a' not in VERSION), [])

    def _fixture(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        for subdir in ("docs", "tests"):
            (root / subdir).mkdir()
        (root / "version.py").write_text(
            'APP_NAME = "Data Workflow Manager"\nVERSION = "0.2.1"\n', encoding="utf-8"
        )
        (root / "pyproject.toml").write_text('[project]\nversion = "0.2.1"\n', encoding="utf-8")
        (root / "docs/RELEASE-v0.2.1.md").write_text("# Release\n", encoding="utf-8")
        (root / "docs/RELEASES.md").write_text("# Historikk\n\n## v0.2.1\n", encoding="utf-8")
        return root

    def test_legacy_alpha_regex_is_rejected(self):
        root = self._fixture()
        (root / "tests/test_v021_a10_old.py").write_text(
            '''from version import VERSION
import unittest
class Old(unittest.TestCase):
    def test_version(self):
        self.assertRegex(VERSION, r'^0\\.2\\.1-a[0-9]+$')
''', encoding="utf-8"
        )
        issues = release_errors(root)
        self.assertEqual(len(issues), 1)
        self.assertIn("assertRegex", issues[0])

    def test_hardcoded_alpha_file_checks_are_rejected(self):
        root = self._fixture()
        (root / "tests/test_v021_a16_old.py").write_text(
            '''import unittest
class Old(unittest.TestCase):
    def test_version(self):
        self.assertIn('VERSION = "0.2.1-a16"', (root / 'version.py').read_text())
        self.assertIn('version = "0.2.1a16"', (root / 'pyproject.toml').read_text())
''', encoding="utf-8"
        )
        issues = release_errors(root)
        self.assertEqual(len(issues), 2)
        self.assertTrue(all("hardkodet alpha" in issue for issue in issues))

    def test_missing_history_blocks_release(self):
        root = self._fixture()
        (root / "docs/RELEASES.md").write_text("# Historikk\n", encoding="utf-8")
        self.assertTrue(any("RELEASES.md" in issue for issue in release_errors(root)))

    def test_distribution_mismatch_blocks_release(self):
        root = self._fixture()
        (root / "pyproject.toml").write_text('[project]\nversion = "0.2.1a16"\n', encoding="utf-8")
        self.assertTrue(any("pyproject.toml" in issue for issue in release_errors(root)))

    def test_no_source_write_or_test_bypass(self):
        source = (ROOT / "tools/release_gate.py").read_text(encoding="utf-8")
        for forbidden in (".write_text(", ".write_bytes(", "skip_if", "skipTest(", "patch.dict(", "sys.modules["):
            self.assertNotIn(forbidden, source)
        rule = (ROOT / "docs/RELEASE-VERSION-TEST-RULE.md").read_text(encoding="utf-8")
        self.assertIn("Ingen", rule)
        self.assertIn("test.bat", rule)
        self.assertIn("release_prepare.py", rule)
        self.assertIn("alpha", rule.lower())


if __name__ == "__main__":
    unittest.main()
