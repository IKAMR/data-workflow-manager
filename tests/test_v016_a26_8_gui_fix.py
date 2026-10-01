from pathlib import Path
import unittest


class V016A268GuiFixTests(unittest.TestCase):
    def test_unavailable_storage_suggestion_uses_info_icon_not_disabled_checkbox(self):
        source = Path("gui/storage_suggestion_preview_dialog.py").read_text(encoding="utf-8")
        self.assertIn('text="ⓘ"', source)
        self.assertNotIn('state="normal" if selectable else "disabled"', source)

    def test_arkade_live_log_gets_more_vertical_space(self):
        source = Path("gui/arkade5_run_dialog.py").read_text(encoding="utf-8")
        self.assertIn("self.grid_rowconfigure(7, weight=1)", source)
        self.assertIn("height=300", source)
        self.assertIn('self._live_log.grid(row=7, column=0', source)
        self.assertIn('sticky="nsew"', source)


if __name__ == "__main__":
    unittest.main()
