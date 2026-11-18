"""a12.1: regression for the two exact Windows/PySide6 geometry warnings.

No Qt installation is needed. The original native warnings are retained in
stderr, but the red alert is reserved for materially larger corrections.
"""
from __future__ import annotations

import unittest
from gui_qt.console_alert_v0114_a1 import (
    is_minor_windows_geometry_adjustment, should_flag_qt_message,
)


# Literal, unmodified logs supplied for v0.2.2-a12 on 18 November 2026.
FIRST = (
    'QWindowsWindow::setGeometry: Unable to set geometry '
    '1979x1796+2129+102 (frame: 1995x1852+2121+54) '
    'on QWidgetWindow/"DwmMainWindowWindow" on "\\\\.\\DISPLAY1". '
    'Resulting geometry: 1985x1770+2126+105 '
    '(frame: 2001x1826+2118+57) margins: 8, 48, 8, 8 '
    'minimum size: 720x480'
)
SECOND = (
    'QWindowsWindow::setGeometry: Unable to set geometry '
    '1323x1180+6653+107 (frame: 1339x1219+6645+76) '
    'on QWidgetWindow/"DwmMainWindowWindow" on "PHL 499P9". '
    'Resulting geometry: 1323x1197+6653+90 '
    '(frame: 1339x1236+6645+59) margins: 8, 31, 8, 8 '
    'minimum size: 720x480'
)
LARGE = (
    'QWindowsWindow::setGeometry: Unable to set geometry '
    '2459x2040+1956+45 (frame: 2475x2096+1948-3) '
    'on QWidgetWindow/"DwmMainWindowWindow" on "\\\\.\\DISPLAY1". '
    'Resulting geometry: 2465x1770+1953+48 '
    '(frame: 2481x1826+1945+0) margins: 8, 48, 8, 8'
)


class TestMainWindowDpiCorrection(unittest.TestCase):
    def test_exact_display1_26_pixel_height_change_is_not_red(self):
        self.assertTrue(is_minor_windows_geometry_adjustment(FIRST))
        self.assertFalse(should_flag_qt_message(1, FIRST))

    def test_exact_phl_17_pixel_height_change_is_not_red(self):
        self.assertTrue(is_minor_windows_geometry_adjustment(SECOND))
        self.assertFalse(should_flag_qt_message(1, SECOND))

    def test_old_270_pixel_clipping_stays_red(self):
        self.assertFalse(is_minor_windows_geometry_adjustment(LARGE))
        self.assertTrue(should_flag_qt_message(1, LARGE))

    def test_large_position_shift_stays_red_even_if_size_is_small(self):
        moved = FIRST.replace('1985x1770+2126+105', '1985x1770+1800+105')
        self.assertTrue(should_flag_qt_message(1, moved))

    def test_only_main_window_uses_small_percent_allowance(self):
        other = FIRST.replace('DwmMainWindowWindow', 'DifferentDialogWindow')
        self.assertFalse(is_minor_windows_geometry_adjustment(other))
        self.assertTrue(should_flag_qt_message(1, other))

    def test_fatal_or_critical_geometry_messages_always_red(self):
        self.assertTrue(should_flag_qt_message(2, FIRST))
        self.assertTrue(should_flag_qt_message(3, SECOND))

    def test_non_geometry_warnings_still_red(self):
        self.assertTrue(should_flag_qt_message(1, 'QWidget: paint device destroyed'))
        self.assertTrue(should_flag_qt_message(1, 'QWindowsWindow::setGeometry: invalid result'))

    def test_debug_and_info_not_red(self):
        self.assertFalse(should_flag_qt_message(0, FIRST))
        self.assertFalse(should_flag_qt_message(4, LARGE))

    def test_fraction_cap_at_48_pixels(self):
        text = FIRST.replace('1979x1796', '4000x3000').replace('1985x1770', '4006x2950')
        self.assertTrue(should_flag_qt_message(1, text))

    def test_non_main_still_obeys_explicit_tolerance(self):
        other = FIRST.replace('DwmMainWindowWindow', 'DifferentDialogWindow')
        self.assertTrue(is_minor_windows_geometry_adjustment(other, tolerance=26))


if __name__ == '__main__':
    unittest.main()
