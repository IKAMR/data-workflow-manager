
from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class V015A25DirectResultRouteTests(unittest.TestCase):
    def test_historical_a19_route_is_preserved(self):
        text = (
            ROOT / "gui" / "direct_depot_assessment_dialog_a19.py"
        ).read_text(encoding="utf-8")
        self.assertIn("DepotResultViewsDialogA19", text)

    def test_new_a20_route_opens_a25_result_view(self):
        text = (
            ROOT / "gui" / "direct_depot_assessment_dialog_a20.py"
        ).read_text(encoding="utf-8")
        self.assertIn(
            "from .depot_result_views_a20 import DepotResultViewsDialogA20",
            text,
        )
        self.assertIn("dialog = DepotResultViewsDialogA20(", text)

    def test_control_overview_uses_new_direct_route(self):
        text = (
            ROOT / "gui" / "noark5_control_overview_dialog_a20.py"
        ).read_text(encoding="utf-8")
        self.assertIn("DirectDepotAssessmentDialogA20", text)


if __name__ == "__main__":
    unittest.main()
