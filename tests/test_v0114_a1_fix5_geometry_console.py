"""Fix 5: Qt-free geometry and Qt message severity regression checks."""
import ast
import unittest
from pathlib import Path

from gui_qt.window_positions_v0114_a1 import Rect, restored_main_rect
from gui_qt.console_alert_v0114_a1 import should_flag_qt_message

ROOT = Path(__file__).resolve().parents[1]

class Fix5Tests(unittest.TestCase):
    def test_second_screen_frame_padding(self):
        monitor = Rect(3840, 0, 3840, 1080)
        restored = restored_main_rect(Rect(6900, 5, 1100, 1050), [Rect(0,0,1920,1080), monitor],
                                      saved_screen='PHL', screen_names=('Laptop','PHL'))
        self.assertGreaterEqual(restored.x, monitor.x)
        self.assertLessEqual(restored.right, monitor.right - 12)
        self.assertLessEqual(restored.bottom, monitor.bottom - 36)

    def test_negative_virtual_coordinates(self):
        monitor = Rect(-3440, -100, 3440, 1440)
        restored = restored_main_rect(Rect(-3300, 20, 1500, 1200), [monitor, Rect(0,0,1920,1080)],
                                      saved_screen='PHL', screen_names=('PHL','Laptop'))
        self.assertGreaterEqual(restored.x, monitor.x)
        self.assertLessEqual(restored.bottom, monitor.bottom - 36)

    def test_move_is_persisted(self):
        source = (ROOT/'gui_qt/window_positions_v0114_a1.py').read_text('utf-8')
        self.assertIn('QEvent.Type.Move, QEvent.Type.Resize', source)
        self.assertIn("('x', 'y', 'width', 'height')", source)

    def test_console_severity(self):
        for value in (1,2,3): self.assertTrue(should_flag_qt_message(value))
        for value in (0,4): self.assertFalse(should_flag_qt_message(value))

    def test_qt_enum_severity(self):
        class QtMsg:
            value = 1
        self.assertTrue(should_flag_qt_message(QtMsg()))

    def test_alert_integrated_in_basic(self):
        source = (ROOT/'gui_qt/basic_main_v0113_a2.py').read_text('utf-8')
        ast.parse(source)
        self.assertIn('install_console_alert(self, self._a2_navigation)', source)

if __name__=='__main__': unittest.main()

class HtmlLabelTests(unittest.TestCase):
    def test_label_width_bounded_in_readable_evidence(self):
        from gui_qt.result_label_width_v0114_a1 import constrain_detail_label_width
        original = '<table><tr><td width="39%">category</td><td>value</td></tr></table>'
        adjusted = constrain_detail_label_width(original)
        self.assertIn('width="280"', adjusted)
        self.assertNotIn('39%', adjusted)
        self.assertIn('<td>value</td>', adjusted)
