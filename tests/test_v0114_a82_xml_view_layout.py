"""a8.2 GUI integration contracts; executable without PySide6 on CI."""
import ast
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VIEW = ROOT / 'gui_qt' / 'standard_values_v0114_a2.py'
PREFS = ROOT / 'gui_qt' / 'view_display_preferences.py'


class LayoutContracts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.view = VIEW.read_text(encoding='utf-8')
        cls.prefs = PREFS.read_text(encoding='utf-8')
        cls.tree = ast.parse(cls.view)

    def test_auto_button_reuses_same_layout_as_search_completion(self):
        self.assertIn("QPushButton('Autojuster visning')", self.view)
        self.assertIn('self.auto_layout_button.clicked.connect(self._auto_layout)', self.view)
        self.assertIn('QTimer.singleShot(0, self._auto_layout)', self.view)
        self.assertIn('self.lower_splitter.setSizes(', self.view)
        self.assertIn('self.vertical_splitter.setSizes(', self.view)

    def test_auto_size_uses_available_screen_not_fixed_resolution(self):
        methods = [n for n in ast.walk(self.tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == '_auto_layout']
        self.assertEqual(len(methods), 1)
        body = ast.get_source_segment(self.view, methods[0])
        self.assertIn('screen.availableGeometry()', body)
        self.assertIn('QTimer.singleShot(0, self._fit_panes)', body)
        self.assertIn('self.results.setColumnWidth(', self.view)
        self.assertIn('self.structure.setColumnWidth(', self.view)
        self.assertNotIn('self.xml_path.write', body)

    def test_shared_wrap_default_on_and_persistent(self):
        self.assertIn("_WORD_WRAP_KEY = 'result_views/word_wrap'", self.prefs)
        self.assertIn('.value(_WORD_WRAP_KEY, True)', self.prefs)
        self.assertIn('QSettings(_ORGANIZATION, _APPLICATION).setValue(', self.prefs)
        self.assertIn('QPlainTextEdit.LineWrapMode.WidgetWidth', self.prefs)
        self.assertIn('QPlainTextEdit.LineWrapMode.NoWrap', self.prefs)

    def test_local_toggle_applies_to_all_three_panes(self):
        self.assertIn("QCheckBox('Bryt tekst')", self.view)
        self.assertIn('self.wrap_text.setChecked(word_wrap_enabled())', self.view)
        self.assertIn('self.wrap_text.toggled.connect(self._set_wrap_text)', self.view)
        self.assertIn('apply_word_wrap(enabled, self.results, self.structure, self.xml_text)', self.view)
        self.assertIn('save_word_wrap_enabled(enabled)', self.view)

    def test_does_not_change_context_source_or_sort(self):
        self.assertIn('cell.data(Qt.ItemDataRole.UserRole)', self.view)
        self.assertIn('save_xml_extract(', self.view)
        self.assertIn('inspect_xml_context, self.xml_path, xpath', self.view)
        self.assertIn('self.results.horizontalHeader().sectionClicked.connect(self._click_sort)', self.view)


if __name__ == '__main__':
    unittest.main()
