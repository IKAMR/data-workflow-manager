from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]

LEGACY_VERSION_GUARD_TESTS = (
    "test_v015_a6_arkade_combined_gui.py",
    "test_v015_a8_arkade_portable_export.py",
    "test_v015_a9_arkade_gap_overlap.py",
    "test_v015_a10_arkade_gap_overlap_gui.py",
    "test_v015_a11_arkade_coverage_policy.py",
    "test_v015_a12_arkade_integration_health.py",
    "test_v015_a13_arkade_practical_acceptance.py",
    "test_v015_a14_arkade_release_readiness.py",
    "test_v015_a15_arkade_2131.py",
)


class V016A1VersionTransitionTests(unittest.TestCase):
    def test_legacy_v015_guards_accept_newer_release_series(self):
        for name in LEGACY_VERSION_GUARD_TESTS:
            source = (ROOT / "tests" / name).read_text(encoding="utf-8")
            self.assertIn('(\\d+)\\.(\\d+)\\.(\\d+)', source, name)
            self.assertIn('self.assertGreaterEqual(release, (0, 1, 5))', source, name)


if __name__ == "__main__":
    unittest.main()
