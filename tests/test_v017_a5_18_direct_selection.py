import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

class TestA518(unittest.TestCase):
    def test_direct_archive_evidence_choice(self):
        src = (ROOT / "gui/depot_result_center_v017_a1.py").read_text(encoding="utf-8")
        self.assertIn("def _choose_a5_part_evidence", src)
        self.assertIn("initial_part=part_index", src)
        self.assertIn("on_evidence_saved=self._refresh_a5_evidence", src)

    def test_dialog_honors_initial_scope_and_metric(self):
        src = (ROOT / "gui/kdrs_query_results_a4.py").read_text(encoding="utf-8")
        self.assertIn("initial_metric=None, initial_part=None", src)
        self.assertIn("metric_menu.set(metrics[initial_metric])", src)
        self.assertIn("scope_menu.set(f'Arkivdel {initial_part}')", src)
        self.assertIn("self._on_evidence_saved()", src)
