"""Pure dynamic-layout regression tests; runnable without PySide6."""
import unittest

from gui_qt.canonical_layout_v0115_a9 import (
    content_split, button_columns, text_visual_lines,
)


class TestContentSplitter(unittest.TestCase):
    def test_long_report_gets_more_space(self):
        tree, report = content_split(700, 100, 1400)
        self.assertGreater(report, tree * 3)
        self.assertEqual(tree + report, 700)

    def test_many_sources_get_more_space(self):
        tree, report = content_split(700, 1300, 100)
        self.assertGreater(tree, report * 3)
        self.assertEqual(tree + report, 700)

    def test_similar_content_is_balanced(self):
        tree, report = content_split(700, 210, 220)
        self.assertLess(abs(tree - report), 20)

    def test_small_window_still_scrollable(self):
        tree, report = content_split(220, 3000, 3000)
        self.assertEqual(tree + report, 220)
        self.assertGreaterEqual(tree, 100)
        self.assertGreaterEqual(report, 100)

    def test_empty_content_no_division_by_zero(self):
        self.assertEqual(sum(content_split(500, 0, 0)), 500)

    def test_explicit_minima(self):
        tree, report = content_split(400, 10000, 10, tree_min=120, report_min=100)
        self.assertGreaterEqual(report, 100)
        self.assertEqual(tree + report, 400)


class TestButtonReflow(unittest.TestCase):
    def test_narrow_window_wraps(self):
        self.assertEqual(button_columns(420, [120, 160, 180, 140], spacing=8), 2)

    def test_wide_window_uses_one_row(self):
        self.assertEqual(button_columns(900, [120, 160, 180, 140], spacing=8), 4)

    def test_very_long_button_gets_own_column(self):
        self.assertEqual(button_columns(290, [300, 100], spacing=8), 1)

    def test_empty_buttons(self):
        self.assertEqual(button_columns(500, []), 1)

    def test_line_wrap_changes_with_width(self):
        lines = ['x' * 180, 'short', '']
        self.assertGreater(text_visual_lines(lines, 120, 8),
                           text_visual_lines(lines, 600, 8))


if __name__ == '__main__':
    unittest.main()
