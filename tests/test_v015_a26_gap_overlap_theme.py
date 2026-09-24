from __future__ import annotations

import unittest

from gui import theme


class V015A26GapOverlapThemeTests(unittest.TestCase):
    def test_gap_overlap_font_roles_exist(self):
        self.assertTrue(hasattr(theme, "HEADER_SIZE"))
        self.assertTrue(hasattr(theme, "BODY_SIZE"))

    def test_font_role_aliases_use_established_theme_sizes(self):
        self.assertEqual(theme.HEADER_SIZE, theme.TITLE_SIZE)
        self.assertEqual(theme.BODY_SIZE, theme.NORMAL_SIZE)

    def test_font_role_aliases_are_valid_sizes(self):
        self.assertGreater(theme.HEADER_SIZE, 0)
        self.assertGreater(theme.BODY_SIZE, 0)


if __name__ == "__main__":
    unittest.main()
