from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class A193OpenOverlayTests(unittest.TestCase):
    def test_runtime_activates_a19_3(self):
        main = (ROOT / "main.py").read_text(encoding="utf-8")
        version = (ROOT / "version.py").read_text(encoding="utf-8")
        self.assertIn("from gui.persistent_app_a19_3 import run_gui", main)
        self.assertRegex(version, r'VERSION = \"0\.1\.6-a19(?:\.(?:[3-9]|[1-9][0-9]+))?\"')

    def test_main_window_has_real_indeterminate_loading_overlay(self):
        source = (ROOT / "gui/persistent_app_a19_3.py").read_text(encoding="utf-8")
        self.assertIn('text="Åpner Resultatvisninger …"', source)
        self.assertIn('mode="indeterminate"', source)
        self.assertIn("progress.start()", source)
        self.assertIn("panel.place(", source)
        self.assertIn("self.update_idletasks()", source)

    def test_depot_button_is_temporarily_disabled_and_restored(self):
        source = (ROOT / "gui/persistent_app_a19_3.py").read_text(encoding="utf-8")
        self.assertIn('button.configure(state="disabled")', source)
        self.assertIn("button.configure(state=previous_state)", source)


if __name__ == "__main__":
    unittest.main()
