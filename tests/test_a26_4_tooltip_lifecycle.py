import unittest
from pathlib import Path

ROOT = Path(__file__).parents[1]


class TooltipLifecycleTests(unittest.TestCase):
    def test_tooltip_has_pointer_lifecycle_guards_without_auto_hide(self):
        text = (ROOT / "gui/workflow_panel.py").read_text(encoding="utf-8")
        self.assertIn('"<Destroy>"', text)
        self.assertIn('"<ButtonRelease>"', text)
        self.assertIn('"<Leave>"', text)
        self.assertIn("_hide_if_owner", text)
        self.assertNotIn("AUTO_HIDE_MS", text)

    def test_refresh_still_hides_tooltips_before_rebuild(self):
        text = (ROOT / "gui/workflow_panel.py").read_text(encoding="utf-8")
        self.assertIn("for tooltip in self._tooltips: tooltip._hide()", text)


if __name__ == "__main__":
    unittest.main()
