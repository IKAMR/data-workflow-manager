
from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class V015A25ResultRoutingFix3Tests(unittest.TestCase):
    def test_historical_a19_contract_is_preserved(self):
        source = (ROOT / "gui" / "direct_depot_assessment_dialog_a19.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("DepotResultViewsDialogA19", source)

    def test_new_direct_layer_routes_to_a20(self):
        source = (ROOT / "gui" / "direct_depot_assessment_dialog_a20.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("DepotResultViewsDialogA20", source)
        self.assertIn("class DirectDepotAssessmentDialogA20", source)

    def test_control_overview_routes_to_new_direct_layer(self):
        source = (ROOT / "gui" / "noark5_control_overview_dialog_a20.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("DirectDepotAssessmentDialogA20", source)

    def test_active_a25_runtime_overrides_both_entry_points(self):
        source = (ROOT / "gui" / "persistent_app_a60.py").read_text(encoding="utf-8")
        self.assertIn("Noark5ControlOverviewDialogA20", source)
        self.assertIn("DirectDepotAssessmentDialogA20", source)
        self.assertIn("DepotAssessmentDialogA20", source)
        self.assertIn("def _open_validation_overview", source)
        self.assertIn("def _open_depot_assessment", source)


if __name__ == "__main__":
    unittest.main()
