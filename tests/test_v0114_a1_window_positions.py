"""v0.1.14-a1: placement on multi-monitor layouts and persistence contract."""
from __future__ import annotations

import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / 'gui_qt' / 'window_positions_v0114_a1.py'
GUI = ROOT / 'gui_qt' / 'basic_main_v0113_a2.py'

spec = importlib.util.spec_from_file_location('dwm_window_positions_test', MODULE)
mod = importlib.util.module_from_spec(spec)
import sys
sys.modules[spec.name] = mod
spec.loader.exec_module(mod)
Rect = mod.Rect


class WindowPositionTests(unittest.TestCase):
    def setUp(self):
        self.laptop = Rect(0, 0, 1440, 900)
        self.ultrawide = Rect(1440, -120, 3440, 1440)
        self.main = Rect(3400, 120, 1300, 900)

    def test_main_screen_is_ultrawide_even_when_laptop_is_first(self):
        self.assertEqual(mod.screen_for_main(self.main, [self.laptop, self.ultrawide]),
                         self.ultrawide)

    def test_dialog_centered_on_same_monitor(self):
        r = mod.popup_on_main_screen(self.main, (850, 650), (500, 400),
                                     [self.laptop, self.ultrawide])
        self.assertGreaterEqual(r.x, self.ultrawide.x)
        self.assertLessEqual(r.right, self.ultrawide.right)
        self.assertLessEqual(r.bottom, self.ultrawide.bottom)
        self.assertGreater(r.x, self.laptop.right)

    def test_beside_fallback_overlaps_main_instead_of_using_laptop(self):
        main = Rect(1490, 0, 3330, 1300)
        r = mod.popup_on_main_screen(main, (1400, 900), (800, 500),
                                     [self.laptop, self.ultrawide], beside=True)
        self.assertGreaterEqual(r.x, self.ultrawide.x)
        self.assertLessEqual(r.right, self.ultrawide.right)
        self.assertTrue(r.x < main.right and r.right > main.x)

    def test_beside_on_same_monitor_when_there_is_room(self):
        main = Rect(1600, 0, 850, 600)
        r = mod.popup_on_main_screen(main, (650, 500), (400, 300),
                                     [self.laptop, self.ultrawide], beside=True)
        self.assertGreaterEqual(r.x, main.right)
        self.assertLessEqual(r.right, self.ultrawide.right)

    def test_large_dialog_is_clamped_to_main_monitor(self):
        r = mod.popup_on_main_screen(self.main, (9999, 9999), (850, 600),
                                     [self.laptop, self.ultrawide])
        self.assertEqual(r.width, self.ultrawide.width)
        self.assertEqual(r.height, self.ultrawide.height)
        self.assertEqual(r.x, self.ultrawide.x)

    def test_disconnected_screen_visibility(self):
        self.assertFalse(mod.visible_on_any(self.main, [self.laptop]))
        self.assertTrue(mod.visible_on_any(self.main, [self.laptop, self.ultrawide]))

    def test_main_and_popup_are_wired_without_changing_settings_identity(self):
        source = GUI.read_text(encoding='utf-8')
        controller = MODULE.read_text(encoding='utf-8')
        self.assertIn('install_window_positions(self)', source)
        self.assertIn("qt/window_geometry", controller)
        self.assertIn('main.saveGeometry()', controller)
        self.assertIn('QApplication.instance().installEventFilter(self)', controller)
        self.assertIn('QEvent.Type.WindowStateChange', controller)
        self.assertNotIn('QtApp-v0.1.14', controller)


if __name__ == '__main__':
    unittest.main()
