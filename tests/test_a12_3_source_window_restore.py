from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class A123SourceAndWindowRestoreTests(unittest.TestCase):
    def test_unavailable_source_is_described_as_unavailable_storage(self):
        text = (ROOT / "gui" / "source_panel.py").read_text(encoding="utf-8")
        self.assertIn("Uttrekksmappen er ikke tilgjengelig", text)
        self.assertIn("ekstern disk, nettverksstasjon eller annen lagring", text)
        self.assertIn("if not root_path.is_dir()", text)

    def test_setup_exposes_maximized_restore_option(self):
        text = (ROOT / "gui" / "settings_dialog_a10.py").read_text(encoding="utf-8")
        self.assertIn("restore_main_window_maximized", text)
        self.assertIn("Start maksimert hvis vinduet ble avsluttet maksimert", text)

    def test_maximized_state_is_persisted_and_restored(self):
        text = (ROOT / "gui" / "persistent_app_a20.py").read_text(encoding="utf-8")
        self.assertIn('"main_window_maximized"', text)
        self.assertIn('self.state("zoomed")', text)
        self.assertIn("should_restore_maximized", text)

    def test_maximized_restore_is_resolution_independent(self):
        text = (ROOT / "gui" / "window_geometry.py").read_text(encoding="utf-8")
        self.assertIn("def should_restore_maximized", text)
        self.assertIn("restore_main_window_maximized", text)
        self.assertIn("main_window_maximized", text)


if __name__ == "__main__":
    unittest.main()
