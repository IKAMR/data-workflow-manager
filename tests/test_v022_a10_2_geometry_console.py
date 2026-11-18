"""a10.2 headless regressions: real Windows warning size and diagnostic UI.

Native Qt/Windows behavior still requires a Windows smoke test.
"""
from __future__ import annotations

import ast
from pathlib import Path
import unittest

from app.window_geometry_v022_a10_2 import (
    ScreenArea, WindowRect, bounded_window_rect, bounded_dialog_size,
)
from gui_qt.console_alert_v0114_a1 import (
    is_minor_windows_geometry_adjustment, should_flag_qt_message,
)

ROOT = Path(__file__).resolve().parents[1]

WARN = (
    'QWindowsWindow::setGeometry: Unable to set geometry '
    '2459x2040+1956+45 (frame: 2475x2096+1948-3) '
    'on QWidgetWindow/"DwmMainWindowWindow" on "\\\\.\\DISPLAY1". '
    'Resulting geometry: 2465x1770+1953+48 '
    '(frame: 2481x1826+1945+0) margins: 8, 48, 8, 8'
)


class TestWindowGeometry(unittest.TestCase):
    def test_observed_main_window_geometry_bounded_to_monitor(self):
        screen = ScreenArea(1920, 0, 2560, 1800, 'DISPLAY1')
        safe = bounded_window_rect(WindowRect(1956, 45, 2459, 2040), (screen,),
                                   preferred_screen='DISPLAY1')
        self.assertGreaterEqual(safe.x, screen.x + 20)
        self.assertGreaterEqual(safe.y, screen.y + 64)
        self.assertLessEqual(safe.x + safe.width, screen.right - 28)
        self.assertLessEqual(safe.y + safe.height, screen.bottom - 36)
        self.assertLess(safe.height, 2040)

    def test_second_screen_and_negative_coordinates(self):
        laptop = ScreenArea(0, 0, 1920, 1080, 'Laptop')
        phl = ScreenArea(5750, 0, 2560, 1200, 'PHL 499P9')
        a = bounded_window_rect(WindowRect(6347, 61, 1643, 1180),
                                [laptop, phl], preferred_screen='PHL 499P9')
        self.assertGreaterEqual(a.x, phl.x + 20)
        self.assertLessEqual(a.y + a.height, phl.bottom - 36)
        self.assertGreater(a.x, laptop.right)
        neg = ScreenArea(-3200, -150, 3200, 1900, 'Left')
        b = bounded_window_rect(WindowRect(-3180, -100, 2000, 1850), [laptop, neg],
                                preferred_screen='Left')
        self.assertGreaterEqual(b.x, neg.x + 20)
        self.assertLessEqual(b.y + b.height, neg.bottom - 36)

    def test_unplugged_preferred_monitor_recovers_on_surviving_screen(self):
        only = ScreenArea(0, 0, 1920, 1080, 'Laptop')
        safe = bounded_window_rect(WindowRect(6330, 300, 2900, 1600),
                                   [only], preferred_screen='Disconnected')
        self.assertGreaterEqual(safe.x, only.x)
        self.assertLessEqual(safe.x + safe.width, only.right)
        self.assertLessEqual(safe.y + safe.height, only.bottom)

    def test_same_safe_geometry_is_idempotent(self):
        screen = ScreenArea(100, 50, 2400, 1400, 'Monitor')
        initial = WindowRect(280, 230, 1100, 800)
        safe = bounded_window_rect(initial, [screen], preferred_screen='Monitor')
        self.assertEqual(safe, initial)
        self.assertEqual(bounded_window_rect(safe, [screen], preferred_screen='Monitor'), safe)

    def test_dialog_dimensions_respect_screen_and_saved_size(self):
        self.assertEqual(bounded_dialog_size(900, 540, 2560, 1800), (900, 540))
        self.assertEqual(bounded_dialog_size(1900, 1200, 1440, 900), (1360, 790))
        self.assertEqual(bounded_dialog_size(700, 400, 1000, 700), (700, 400))

    def test_substantial_qt_warning_is_not_silenced(self):
        self.assertFalse(is_minor_windows_geometry_adjustment(WARN))
        self.assertTrue(should_flag_qt_message(1, WARN))
        self.assertTrue(should_flag_qt_message(2, WARN))
        self.assertFalse(should_flag_qt_message(0, WARN))


class TestDialogIntegration(unittest.TestCase):
    def test_main_skips_only_unsafe_native_restore_not_other_state(self):
        code = (ROOT / 'gui_qt/main_v022_a10.py').read_text(encoding='utf-8')
        ast.parse(code)
        for required in ('def _restore_settings(self):',
                         "self._a102_suppress_legacy_restore = True",
                         'super()._restore_settings()',
                         'self._a102_restore_bounded_geometry()',
                         'def _a102_sync_position_controller(self):',
                         'bounded_window_rect(saved, screens',
                         'controller._startup_rect = Rect(',
                         'return super().restoreGeometry(geometry)'):
            self.assertIn(required, code)
        self.assertNotIn('DWM_ENABLE_QT_POPUP_FILTER', code)

    def test_console_has_resizable_dialog_and_full_copy(self):
        code = (ROOT / 'gui_qt/console_alert_v0114_a1.py').read_text(encoding='utf-8')
        ast.parse(code)
        for required in ('QDialog(main)', 'QPlainTextEdit(dialog)',
                         "viewer.setPlainText(details)",
                         'dialog.setSizeGripEnabled(True)',
                         'Kopier alle detaljer',
                         'QApplication.clipboard().setText(details)',
                         'Skjul detaljer', 'Vis detaljer',
                         "'qt/a102_console_width'", "'qt/a102_console_height'",
                         'qInstallMessageHandler(handler)',
                         'sys.__stderr__.write',
                         'should_flag_qt_message(kind, message)'):
            self.assertIn(required, code)
        self.assertNotIn('QMessageBox(main)', code)


if __name__ == '__main__':
    unittest.main()
