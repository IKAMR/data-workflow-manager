import unittest
from pathlib import Path

ROOT = Path(__file__).parents[1]


class A145TooltipDialogStabilityTests(unittest.TestCase):
    def test_tooltip_has_no_time_based_auto_hide(self):
        text = (ROOT / "gui/workflow_panel.py").read_text(encoding="utf-8")
        self.assertNotIn("AUTO_HIDE_MS", text)
        self.assertNotIn("after(self.AUTO_HIDE_MS, self._hide)", text)
        self.assertIn('"<Leave>"', text)
        self.assertIn("_hide_if_owner", text)

    def test_tooltip_uses_stable_semantic_font_role(self):
        panel = (ROOT / "gui/workflow_panel.py").read_text(encoding="utf-8")
        theme = (ROOT / "gui/theme.py").read_text(encoding="utf-8")
        self.assertIn("TOOLTIP_SIZE", theme)
        self.assertIn("tooltip_font", panel)
        self.assertIn("FontRegistry.effective_size(theme.TOOLTIP_SIZE)", panel)

    def test_result_versions_dialog_is_hidden_until_layout_is_final(self):
        text = (ROOT / "gui/result_versions_dialog.py").read_text(encoding="utf-8")
        self.assertIn("self.withdraw()", text)
        self.assertIn("self.update_idletasks()", text)
        self.assertIn("self.deiconify()", text)
        self.assertLess(text.index("self.withdraw()"), text.index("self.deiconify()"))

    def test_dialog_grab_happens_after_deiconify(self):
        text = (ROOT / "gui/result_versions_dialog.py").read_text(encoding="utf-8")
        self.assertLess(text.rindex("self.deiconify()"), text.rindex("self.grab_set()"))


if __name__ == "__main__":
    unittest.main()
