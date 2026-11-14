"""Headless wiring and version contracts for Qt depot assessment in a2."""
from __future__ import annotations

import ast
from pathlib import Path
import re
import tomllib
import unittest

from version import APP_NAME, VERSION
from version_assertions import assert_release_at_least

ROOT = Path(__file__).resolve().parents[1]


class A2DepotQtContractTests(unittest.TestCase):
    def test_a2_version_is_clean_and_distribution_matches(self):
        self.assertEqual(APP_NAME, "Data Workflow Manager")
        assert_release_at_least(self, f'VERSION = "{VERSION}"', "0.1.9", 2)
        with (ROOT / "pyproject.toml").open("rb") as handle:
            project = tomllib.load(handle)["project"]
        self.assertEqual(project["name"], "noark5-workflow-manager")
        self.assertEqual(project["version"], VERSION.replace("-a", "a"))
        with (ROOT / "version.py").open("r", encoding="utf-8") as handle:
            source = handle.read()
        self.assertEqual(source, f'APP_NAME = "Data Workflow Manager"\nVERSION = "{VERSION}"\n')

    def test_existing_result_center_and_a1_tabs_still_used(self):
        main = (ROOT / "gui_qt/main_window.py").read_text(encoding="utf-8")
        a1 = (ROOT / "gui_qt/result_center_v019_a1.py").read_text(encoding="utf-8")
        ast.parse(main)
        ast.parse(a1)
        self.assertIn('dialog = EvidenceResultCenter(', main)
        self.assertIn('.result_center_v019_a1 import ResultCenterWindow', main)
        self.assertIn('self._a2_panel.set_snapshots(self._snapshots, sources=self._a1_sources)', a1)
        self.assertIn('self.tabs.addTab(self._a2_panel, "Depotvurdering")', a1)
        self.assertIn('self._a2_open_depot_review', main)
        self.assertIn('dialog.show_depot_review()', main)
        for old in ('Kildeoversikt', 'Arkade-dekning', 'KDRS Query', 'source_inventory',
                    'arkade_coverage', 'export_inventory'):
            self.assertIn(old, a1)

    def test_qt_panel_uses_common_period_review_and_user_identity(self):
        ui = (ROOT / "gui_qt/depot_review_v019_a2.py").read_text(encoding="utf-8")
        ast.parse(ui)
        for marker in ('DepotReviewPanel', 'DepotDecisionDialog', 'ReviewUserProfileDialog',
                       'LocalUserProfileIdentityProvider', 'save_user_profile',
                       'record_depot_review', '_open_period_review', 'QSplitter',
                       'system-ID', 'Faglig depotvurdering'):
            self.assertIn(marker, ui)
        self.assertNotIn('import tkinter', ui)
        self.assertNotIn('customtkinter', ui)

    def test_headless_service_reuses_mature_whole_engine_and_preserves_report(self):
        core = (ROOT / "app/depot_review_v019_a2.py").read_text(encoding="utf-8")
        ast.parse(core)
        for marker in ('load_depot_assessment', 'record_depot_assessment',
                       'load_part_decisions', 'record_part_decision', 'PART_FILE',
                       'report_sha256', 'report_type', 'UserIdentity', 'os.replace'):
            # report SHA may be written with a Norwegian property label.
            if marker == 'report_sha256':
                self.assertIn('rapport_sha256', core)
            else:
                self.assertIn(marker, core)
        self.assertNotIn('app.user_profile', core)
        self.assertNotIn('import customtkinter', core)


if __name__ == "__main__":
    unittest.main()
