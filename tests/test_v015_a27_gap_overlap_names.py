
from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class V015A27GapOverlapNamesTests(unittest.TestCase):
    def test_gap_overlap_shows_arkade_and_dwm_names(self):
        text = (ROOT / "gui" / "depot_result_views_a21.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("arkade_test_name", text)
        self.assertIn('item.get("name")', text)
        self.assertIn("DWM: {self._dwm_text(area)}", text)

    def test_gap_overlap_has_dwm_only_section(self):
        text = (ROOT / "gui" / "depot_result_views_a21.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("Kontroller kun i DWM", text)
        self.assertIn('model.get("dwm_only")', text)

    def test_a27_runtime_uses_new_result_view_layer(self):
        text = (ROOT / "gui" / "persistent_app_a61.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("Noark5ControlOverviewDialogA21", text)
        self.assertIn("DirectDepotAssessmentDialogA21", text)
        self.assertIn("DepotAssessmentDialogA21", text)


if __name__ == "__main__":
    unittest.main()
