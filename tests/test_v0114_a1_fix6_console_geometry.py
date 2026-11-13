"""Fix 6: Qt console warnings and monitor geometry are non-destructive."""
from __future__ import annotations

import ast
from pathlib import Path
import unittest

from gui_qt.console_alert_v0114_a1 import (
    is_minor_windows_geometry_adjustment, should_flag_qt_message,
)

ROOT = Path(__file__).resolve().parents[1]
WINDOWS_WARNING = (
    'QWindowsWindow::setGeometry: Unable to set geometry '
    '1080x784+6908+66 (frame: 1096x823+6900+35) on '
    'QWidgetWindow/"DwmMainWindowWindow" on "PHL 499P9". '
    'Resulting geometry: 1086x801+6905+52 '
    '(frame: 1102x840+6897+21) margins: 8, 31, 8, 8 '
    'minimum size: 720x480'
)

class GeometryAndConsoleTests(unittest.TestCase):
    def test_observed_windows_rounding_is_not_red_alert(self):
        self.assertTrue(is_minor_windows_geometry_adjustment(WINDOWS_WARNING))
        self.assertFalse(should_flag_qt_message(1, WINDOWS_WARNING))

    def test_significant_geometry_failure_is_red_alert(self):
        shifted = WINDOWS_WARNING.replace('1086x801+6905+52', '1086x801+100+52')
        self.assertFalse(is_minor_windows_geometry_adjustment(shifted))
        self.assertTrue(should_flag_qt_message(1, shifted))

    def test_all_real_warnings_and_errors_still_flagged(self):
        self.assertTrue(should_flag_qt_message(1, 'QWidget: invalid paint device'))
        self.assertTrue(should_flag_qt_message(2, WINDOWS_WARNING))
        self.assertTrue(should_flag_qt_message(3, WINDOWS_WARNING))
        self.assertFalse(should_flag_qt_message(0, 'debug'))
        self.assertFalse(should_flag_qt_message(4, 'info'))

    def test_suspicious_or_unparseable_geometry_is_not_suppressed(self):
        message = 'QWindowsWindow::setGeometry: Unable to set geometry unknown'
        self.assertTrue(should_flag_qt_message(1, message))
        self.assertFalse(is_minor_windows_geometry_adjustment(message))

    def test_global_handler_preserves_original_diagnostics(self):
        code = (ROOT/'gui_qt/console_alert_v0114_a1.py').read_text('utf-8')
        self.assertIn('qInstallMessageHandler(handler)', code)
        self.assertIn('sys.__stderr__.write', code)
        self.assertIn('should_flag_qt_message(kind, message)', code)

    def test_avoid_reapplying_near_identical_main_geometry(self):
        code = (ROOT/'gui_qt/window_positions_v0114_a1.py').read_text('utf-8')
        ast.parse(code)
        self.assertIn('abs(current.x - destination.x) > tolerance', code)
        self.assertIn('abs(current.width - destination.width) > tolerance', code)
        self.assertIn('main.move(destination.x, destination.y)', code)
        self.assertIn('QEvent.Type.Move, QEvent.Type.Resize', code)

if __name__ == '__main__':
    unittest.main()
