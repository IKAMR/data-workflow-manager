from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
CENTER = ROOT / "gui" / "depot_result_center_a22_2.py"


class A222ControlTreatmentTests(unittest.TestCase):
    def test_runtime_activates_a222(self):
        source = (ROOT / "main.py").read_text(encoding="utf-8")
        self.assertIn("from gui.persistent_app_a22_2 import run_gui", source)

    def test_version(self):
        text = (ROOT / "version.py").read_text(encoding="utf-8")
        self.assertRegex(
            text,
            r'VERSION\s*=\s*"0\.1\.6-a22(?:\.(?:[2-9]|[1-9][0-9]+)(?:\.[0-9]+)?)?"'
        )

    def test_control_treatment_is_separate_sidecar(self):
        source = CENTER.read_text(encoding="utf-8")
        self.assertIn(".control_review.json", source)
        self.assertIn('"schema": "dwm.control-review.v1"', source)
        self.assertNotIn("self.model[\"reviews\"] =", source)

    def test_controls_have_open_treatment_window_and_treatment_column(self):
        source = CENTER.read_text(encoding="utf-8")
        self.assertIn("Åpne behandlingsvindu", source)
        self.assertIn('"Behandling"', source)
        self.assertIn("_a222_open_control_window", source)

    def test_review_points_are_structured_collection(self):
        source = CENTER.read_text(encoding="utf-8")
        self.assertIn("Vurderingspunkter – samlet behandling", source)
        self.assertIn("_a222_render_review_points", source)
        self.assertIn("review_status", source)
        self.assertIn("comment", source)

    def test_technical_view_is_responsive_columns(self):
        source = CENTER.read_text(encoding="utf-8")
        self.assertIn("_a222_reflow_technical", source)
        self.assertIn("columns = 3 if width >= 1350 else (2 if width >= 900 else 1)", source)


if __name__ == "__main__":
    unittest.main()
