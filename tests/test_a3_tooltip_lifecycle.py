from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class A3TooltipLifecycleTests(unittest.TestCase):
    def test_workflow_tooltip_is_not_global_topmost(self):
        text = (ROOT / "gui" / "workflow_panel.py").read_text(encoding="utf-8")
        self.assertNotIn('attributes("-topmost", True)', text)
        self.assertNotIn("attributes('-topmost', True)", text)

    def test_workflow_tooltip_is_transient_to_app_window(self):
        text = (ROOT / "gui" / "workflow_panel.py").read_text(encoding="utf-8")
        self.assertIn("tip.transient(parent)", text)
        self.assertIn("tip.lift(parent)", text)

    def test_runtime_hides_tooltips_when_app_loses_focus_or_is_unmapped(self):
        text = (ROOT / "gui" / "persistent_app_a19.py").read_text(encoding="utf-8")
        self.assertIn('bind_all("<FocusOut>", self._hide_workflow_tooltips', text)
        self.assertIn('bind("<Unmap>", self._hide_workflow_tooltips', text)

    def test_depot_dialog_hides_tooltips_before_opening(self):
        text = (ROOT / "gui" / "persistent_app_a19.py").read_text(encoding="utf-8")
        method = text.split("def _open_depot_assessment", 1)[1].split("def _depot_assessment_closed", 1)[0]
        self.assertIn("self._hide_workflow_tooltips()", method)
        self.assertLess(
            method.index("self._hide_workflow_tooltips()"),
            method.index("DepotAssessmentDialog("),
        )


if __name__ == "__main__":
    unittest.main()
