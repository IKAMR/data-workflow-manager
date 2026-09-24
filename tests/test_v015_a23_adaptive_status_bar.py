
from __future__ import annotations

import unittest
from pathlib import Path

from gui.status_bar import StatusBar


class V015A23AdaptiveStatusBarTests(unittest.TestCase):
    def test_width_modes(self):
        self.assertEqual(StatusBar._mode_for_width(None, 1920), "wide")
        self.assertEqual(StatusBar._mode_for_width(None, 1600), "standard")
        self.assertEqual(StatusBar._mode_for_width(None, 1366), "compact")
        self.assertEqual(StatusBar._mode_for_width(None, 1200), "narrow")

    def test_left_side_is_the_flexible_grid_column(self):
        root = Path(__file__).resolve().parents[1]
        text = (root / "gui" / "status_bar.py").read_text(encoding="utf-8")
        self.assertIn("self.grid_columnconfigure(0, weight=1", text)
        self.assertIn("self.grid_columnconfigure(2, weight=0)", text)

    def test_work_context_is_kept(self):
        root = Path(__file__).resolve().parents[1]
        text = (root / "gui" / "status_bar.py").read_text(encoding="utf-8")
        self.assertIn('f"Arbeid: {self._work_text}"', text)

    def test_runtime_categories_exist_even_in_narrow_mode(self):
        root = Path(__file__).resolve().parents[1]
        text = (root / "gui" / "status_bar.py").read_text(encoding="utf-8")
        self.assertIn("short_detection", text)
        self.assertIn("short_backend", text)
        self.assertIn("self._threads", text)
        self.assertIn("free.replace", text)

    def test_backward_compatibility_contracts_are_kept(self):
        root = Path(__file__).resolve().parents[1]
        text = (root / "gui" / "status_bar.py").read_text(encoding="utf-8")
        self.assertIn('value="Jobbliste: [ikke lagret]"', text)
        self.assertIn('self.left_var.set(f"Jobbliste: {Path(path)}")', text)
        self.assertIn("Backward-compatible no-op", text)


if __name__ == "__main__":
    unittest.main()
