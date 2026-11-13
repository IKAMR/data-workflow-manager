"""Static GUI wiring checks (PySide6 runtime verified separately on Windows)."""
from pathlib import Path
import ast
import unittest

ROOT=Path(__file__).resolve().parents[1]

class A7GuiContract(unittest.TestCase):
    def test_dialog_action_is_wired_and_no_autosave(self):
        source=(ROOT/'gui_qt/standard_values_v0114_a2.py').read_text(encoding='utf8')
        ui=(ROOT/'gui_qt/experience_assessment_v0114_a7.py').read_text(encoding='utf8')
        ast.parse(source);ast.parse(ui)
        self.assertIn("self.experience_button.clicked.connect(self._show_experience)",source)
        self.assertIn('version_evidence.status == \'confirmed\'',ui)
        self.assertIn('save_assessment(self.work,',ui)
        self.assertIn('self.reuse.isChecked()',ui)
        self.assertIn('QMessageBox.information',ui)
    def test_docs_link_and_future_data_strategy(self):
        readme=(ROOT/'README.md').read_text(encoding='utf8')
        roadmap=(ROOT/'docs/NOARK5-CANONICAL-RESULTS-AND-KNOWLEDGE-ROADMAP.md').read_text(encoding='utf8')
        self.assertIn('docs/NOARK5-LOCAL-EXPERIENCE.md',readme)
        self.assertIn('samlet, versjonert resultatmodell',roadmap)
        self.assertIn('v0.1.14-a7',roadmap)
if __name__=='__main__': unittest.main()
