import unittest
from pathlib import Path

ROOT = Path(__file__).parents[1]


class A146SharedTooltipTests(unittest.TestCase):
    def test_workflow_panel_uses_one_shared_tooltip_manager(self):
        text = (ROOT / "gui/workflow_panel.py").read_text(encoding="utf-8")
        self.assertIn("self._tooltip = _Tooltip(self)", text)
        self.assertIn("self._tooltips = [self._tooltip]", text)
        self.assertIn("self._tooltip.bind(widget, text)", text)
        self.assertNotIn("self._tooltips.append(_Tooltip", text)

    def test_tooltip_follows_pointer_and_is_not_centered_in_main_view(self):
        text = (ROOT / "gui/workflow_panel.py").read_text(encoding="utf-8")
        self.assertIn("event.x_root", text)
        self.assertIn("event.y_root", text)
        self.assertIn("OFFSET_X", text)
        self.assertIn("OFFSET_Y", text)
        self.assertNotIn("winfo_rootx() + self.widget.winfo_width() // 2", text)

    def test_tooltip_is_hidden_by_owner_leave_without_time_based_hide(self):
        text = (ROOT / "gui/workflow_panel.py").read_text(encoding="utf-8")
        self.assertIn("_hide_if_owner", text)
        self.assertIn('"<Leave>"', text)
        self.assertIn("self.window.withdraw()", text)
        self.assertNotIn("AUTO_HIDE_MS", text)

    def test_tooltip_has_dark_and_light_contrast_palettes(self):
        text = (ROOT / "gui/theme.py").read_text(encoding="utf-8")
        self.assertIn("TOOLTIP_DARK_BG", text)
        self.assertIn("TOOLTIP_LIGHT_BG", text)
        self.assertIn("def tooltip_colors()", text)
        self.assertIn("ctk.get_appearance_mode()", text)

    def test_tooltip_font_still_follows_global_font_offset(self):
        text = (ROOT / "gui/workflow_panel.py").read_text(encoding="utf-8")
        self.assertIn("FontRegistry.effective_size(theme.TOOLTIP_SIZE)", text)


if __name__ == "__main__":
    unittest.main()
