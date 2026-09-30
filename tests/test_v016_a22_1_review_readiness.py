from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class A221ReviewReadinessTests(unittest.TestCase):
    def test_runtime_activates_a221(self):
        source = (ROOT / "main.py").read_text(encoding="utf-8")
        self.assertIn("from gui.persistent_app_a22_1 import run_gui", source)

    def test_a221_uses_existing_materialized_evidence(self):
        source = (ROOT / "gui" / "depot_result_center_a22_1.py").read_text(encoding="utf-8")
        self.assertIn("_missing_archive_fields", source)
        self.assertIn("_a2111_observed_period", source)
        self.assertIn("Klar for faglig vurdering", source)
        self.assertIn("Krever gjennomgang", source)

    def test_a221_does_not_start_new_analysis(self):
        source = (ROOT / "gui" / "depot_result_center_a22_1.py").read_text(encoding="utf-8")
        self.assertNotIn("subprocess", source)
        self.assertNotIn("Popen", source)
