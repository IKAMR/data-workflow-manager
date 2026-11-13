"""Regression tests: remembered DWM window positions on external displays."""
from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'gui_qt' / 'window_positions_v0114_a1.py'
spec = importlib.util.spec_from_file_location('a114_fix4_positions', SOURCE)
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)
Rect = module.Rect


class SecondMonitorTests(unittest.TestCase):
    def setUp(self):
        self.laptop = Rect(0, 0, 1440, 900)
        self.wide = Rect(1440, -120, 3440, 1440)
        self.screens = [self.laptop, self.wide]

    def test_position_far_right_of_widescreen_stays_there(self):
        saved = Rect(3650, 120, 1100, 850)
        self.assertEqual(module.restored_main_rect(
            saved, self.screens, saved_screen='Wide',
            screen_names=('Laptop', 'Wide')), saved)

    def test_saved_screen_wins_when_window_overlaps_both_monitors(self):
        saved = Rect(1100, 100, 900, 750)
        actual = module.restored_main_rect(
            saved, self.screens, saved_screen='Wide',
            screen_names=('Laptop', 'Wide'))
        # Keep a small margin for the native Windows frame/DPI rounding.
        self.assertEqual(actual.x, 1452)
        self.assertEqual(actual.width, 900)

    def test_widescreen_to_left_with_negative_virtual_coordinates(self):
        screens = [self.laptop, Rect(-3440, -90, 3440, 1440)]
        saved = Rect(-3100, 0, 1400, 900)
        self.assertEqual(module.restored_main_rect(
            saved, screens, saved_screen='Wide',
            screen_names=('Laptop', 'Wide')), saved)

    def test_remapped_display_preserves_relative_coordinates(self):
        old = Rect(3650, 120, 1100, 850)
        new_wide = Rect(-3440, -120, 3440, 1440)
        result = module.restored_main_rect(
            old, [self.laptop, new_wide], saved_screen='Wide',
            screen_names=('Laptop', 'Wide'), saved_relative=(2210, 240))
        self.assertEqual(result, Rect(-1230, 120, 1100, 850))

    def test_disconnected_widescreen_falls_back_to_laptop(self):
        saved = Rect(3650, 120, 1100, 850)
        restored = module.restored_main_rect(
            saved, [self.laptop], saved_screen='Wide',
            screen_names=('Laptop',), saved_relative=(2210, 240))
        self.assertGreaterEqual(restored.x, 0)
        self.assertLessEqual(restored.right, self.laptop.right)

    def test_persistence_is_independent_of_app_version(self):
        source = SOURCE.read_text('utf-8')
        for name in ('qt/a14_main_valid', 'qt/a14_main_screen',
                     'qt/a14_main_maximized', 'qt/a14_main_offset_x'):
            self.assertIn(name, source)
        self.assertIn("config.setValue('qt/window_geometry', main.saveGeometry())", source)
        self.assertIn('main.move(destination.x, destination.y)', source)
        self.assertIn('self._ready = True', source)


if __name__ == '__main__':
    unittest.main()
