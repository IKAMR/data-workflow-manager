"""Guard the a3 entrypoint, version and multi-job stop contract."""
from __future__ import annotations

from pathlib import Path
import tomllib
import unittest

from version import VERSION

ROOT = Path(__file__).resolve().parents[1]


class V025A3WiringTests(unittest.TestCase):
    def test_version_consistency(self):
        self.assertEqual(VERSION, '0.2.5-a3')
        with (ROOT / 'pyproject.toml').open('rb') as f:
            self.assertEqual(tomllib.load(f)['project']['version'], '0.2.5a3')

    def test_startup_retains_legacy_tool_health_and_uses_a3(self):
        source = (ROOT / 'gui_qt/__main__.py').read_text(encoding='utf-8')
        self.assertIn('DwmMainWindow = _V025A3Window', source)
        self.assertIn('DwmMainWindow = _V025A1Window', source)
        self.assertIn('install_tool_health_setup()', source)
        self.assertIn('schedule_tool_check(window, api)', source)
        self.assertIn('DwmWorkbenchAPI = _A3WorkbenchAPI', source)

    def test_existing_worker_stops_on_checkpoint_without_running_next_job(self):
        source = (ROOT / 'gui_qt/main_v025_a3.py').read_text(encoding='utf-8')
        self.assertIn('from app.batch_continue_v025_a3 import batch_can_advance', source)
        self.assertIn('if not batch_can_advance(ok, state.status if state else None):', source)
        self.assertIn('if not ok:', source)


if __name__ == '__main__':
    unittest.main()
