
from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class V015A25UiCleanupFix5Tests(unittest.TestCase):
    def setUp(self):
        self.source = (
            ROOT / "gui" / "depot_result_views_a20.py"
        ).read_text(encoding="utf-8")

    def test_arkade_only_uses_neutral_short_label(self):
        self.assertIn('"arkade_only": "Kun Arkade"', self.source)
        self.assertNotIn("Kun Arkade / DWM-gap", self.source)

    def test_gap_summary_does_not_present_dwm_gap_wording(self):
        self.assertIn('f"Kun Arkade: {summary[', self.source)
        self.assertIn('"Kontroller kun i Arkade 5"', self.source)
        self.assertNotIn("Dokumenterte DWM-gap som Arkade 5 dekker", self.source)

    def test_combined_rows_place_detail_button_before_text(self):
        button_pos = self.source.index('text="Detaljer..."')
        compact_class = self.source.index("class Arkade5CombinedCoverageDialogA25")
        label_pos = self.source.index("Arkade-status:", compact_class)
        self.assertLess(button_pos, label_pos)
        self.assertIn("card.grid_columnconfigure(1, weight=1)", self.source)
        self.assertIn("pady=2", self.source)

    def test_duplicate_analysis_action_removed_from_advanced(self):
        advanced = self.source[self.source.index("def _open_arkade5_advanced"):]
        self.assertNotIn('("Analyser Arkade 5..."', advanced)
        self.assertIn('("Generer Arkade-analyser..."', advanced)

    def test_gap_dialog_paints_loading_state_before_analysis(self):
        gap = self.source[self.source.index("class ArkadeGapOverlapDialogA25"):]
        self.assertIn("Laster gap- og overlappoversikt", gap)
        self.assertIn("self.after(75, self._build_content)", gap)
        self.assertIn("build_gap_overlap_analysis()", gap)
        self.assertIn("self.focus_force()", gap)

    def test_advanced_closes_before_opening_child_action(self):
        self.assertIn("self.grab_release()", self.source)
        self.assertIn("self.destroy()", self.source)
        self.assertIn("parent.after_idle(callback)", self.source)


if __name__ == "__main__":
    unittest.main()
