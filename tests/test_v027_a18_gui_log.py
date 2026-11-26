"""a18 static wiring tests that also run without PySide6 on CI."""
from pathlib import Path
import ast
import unittest

ROOT = Path(__file__).resolve().parents[1]

class TestA18LogWiring(unittest.TestCase):
    def test_startup_installs_log_selection_fix(self):
        main = (ROOT / 'gui_qt' / '__main__.py').read_text(encoding='utf-8')
        self.assertIn('install_active_run_log(window)', main)
        self.assertIn('from gui_qt.active_log_v027_a18 import install_active_run_log', main)

    def test_log_prefers_live_run_and_preserves_historical_selection(self):
        text = (ROOT / 'gui_qt' / 'active_log_v027_a18.py').read_text(encoding='utf-8')
        ast.parse(text)
        self.assertIn("combo.setCurrentIndex(0)",text)
        self.assertIn('previous_selected == previous_head',text)
        self.assertIn('current == previous_head',text)
        self.assertIn('return original_history_log(key)',text)

if __name__=='__main__':
    unittest.main()
