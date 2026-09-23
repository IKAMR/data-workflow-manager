from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class V015A10ArkadeGapOverlapGuiTests(unittest.TestCase):
    def test_gui_exposes_static_gap_overlap(self):
        source = (ROOT / "gui" / "depot_result_views_a19.py").read_text(encoding="utf-8")
        self.assertIn("build_gap_overlap_analysis", source)
        self.assertIn("Gap og overlapp...", source)
        self.assertIn("Statisk kunnskapsmodell", source)

    def test_a10_routes_result_views_to_a19(self):
        source = (ROOT / "gui" / "direct_depot_assessment_dialog_a19.py").read_text(encoding="utf-8")
        self.assertIn("DepotResultViewsDialogA19", source)

    def test_main_activates_a51(self):
        source = (ROOT / "main.py").read_text(encoding="utf-8")
        self.assertIn("from gui.persistent_app_a51 import run_gui", source)

    def test_version_has_not_regressed_before_a10(self):
        version = (ROOT / "version.py").read_text(encoding="utf-8")
        match = re.search(r'VERSION\s*=\s*"0\.1\.5-a(\d+)(?:\.\d+)*"', version)
        self.assertIsNotNone(match)
        self.assertGreaterEqual(int(match.group(1)), 10)


if __name__ == "__main__":
    unittest.main()
