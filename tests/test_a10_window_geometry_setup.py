from __future__ import annotations

import unittest
from pathlib import Path

from gui.window_geometry import startup_geometry

ROOT = Path(__file__).resolve().parents[1]


class _FakeWindow:
    def __init__(self, width=1500, height=900, screen_width=1920, screen_height=1080):
        self._width = width
        self._height = height
        self._screen_width = screen_width
        self._screen_height = screen_height

    def update_idletasks(self):
        pass

    def winfo_width(self):
        return self._width

    def winfo_height(self):
        return self._height

    def winfo_screenwidth(self):
        return self._screen_width

    def winfo_screenheight(self):
        return self._screen_height


class A10WindowGeometrySetupTests(unittest.TestCase):
    def test_setup_exposes_independent_position_and_size_checkboxes(self):
        text = (ROOT / "gui" / "settings_dialog_a10.py").read_text(encoding="utf-8")
        self.assertIn("Start med samme vindusposisjon", text)
        self.assertIn("Start med samme vindusstørrelse", text)
        self.assertIn("restore_main_window_position", text)
        self.assertIn("restore_main_window_size", text)

    def test_window_choices_are_part_of_scrollable_setup_body(self):
        text = (ROOT / "gui" / "settings_dialog_a10.py").read_text(encoding="utf-8")
        self.assertIn("CTkScrollableFrame", text)
        self.assertIn('text="Vindu"', text)
        self.assertIn("Start med samme vindusposisjon", text)
        self.assertIn("Start med samme vindusstørrelse", text)
        self.assertNotIn("window_frame =", text)
        self.assertNotIn("tools.grid_configure", text)
        self.assertNotIn("buttons.grid_configure", text)

    def test_defaults_enable_both_independent_choices(self):
        text = (ROOT / "settings.py").read_text(encoding="utf-8")
        self.assertIn('"restore_main_window_position": True', text)
        self.assertIn('"restore_main_window_size": True', text)

    def test_position_can_be_disabled_while_size_is_restored(self):
        window = _FakeWindow()
        settings = {
            "restore_main_window_position": False,
            "restore_main_window_size": True,
            "main_window_width": 1400,
            "main_window_height": 800,
            "main_window_x": 3000,
            "main_window_y": 0,
        }
        self.assertEqual(startup_geometry(settings, window), "1400x800")

    def test_both_restore_choices_can_be_disabled(self):
        window = _FakeWindow()
        settings = {
            "restore_main_window_position": False,
            "restore_main_window_size": False,
        }
        self.assertIsNone(startup_geometry(settings, window))

    def test_runtime_persists_last_normal_geometry_without_overriding_close_protocol(self):
        text = (ROOT / "gui" / "persistent_app_a20.py").read_text(encoding="utf-8")
        self.assertIn('self.bind("<Configure>"', text)
        self.assertIn('self.bind("<Destroy>"', text)
        self.assertNotIn('protocol("WM_DELETE_WINDOW"', text)
        self.assertIn("main_window_width", text)
        self.assertIn("main_window_height", text)

    def test_main_preserves_a19_runtime_boundary_and_uses_a20(self):
        text = (ROOT / "main.py").read_text(encoding="utf-8")
        self.assertIn("persistent_app_a19", text)
        self.assertIn("persistent_app_a20", text)


if __name__ == "__main__":
    unittest.main()
