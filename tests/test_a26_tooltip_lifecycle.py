import unittest
from pathlib import Path

ROOT = Path(__file__).parents[1]

class A26TooltipLifecycleTests(unittest.TestCase):

    def test_tooltip_has_destroy_release_and_auto_hide_guards(self):
        text = (ROOT / "gui/workflow_panel.py").read_text(encoding="utf-8")
        self.assertIn('widget.bind("<Destroy>", self._hide', text)
        self.assertIn('widget.bind("<ButtonRelease>", self._hide', text)
        self.assertIn("AUTO_HIDE_MS", text)
        self.assertIn("after(self.AUTO_HIDE_MS, self._hide)", text)

    def test_refresh_still_hides_tooltips_before_rebuild(self):
        text = (ROOT / "gui/workflow_panel.py").read_text(encoding="utf-8")
        self.assertIn("for tooltip in self._tooltips: tooltip._hide()", text)

if __name__ == "__main__":
    unittest.main()
