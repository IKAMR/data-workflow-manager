"""Qt-free structural regression for the a5 standard-values dialogue."""
from pathlib import Path
import ast
import unittest

FILE = Path(__file__).resolve().parents[1] / 'gui_qt/standard_values_v0114_a2.py'

class A5GuiContract(unittest.TestCase):
    def test_version_dialog_is_wired_to_selected_finding(self):
        text = FILE.read_text(encoding='utf-8')
        ast.parse(text)
        for piece in (
            'class NoarkVersionEvidenceDialog',
            "self.version_button = QPushButton('XSD / Noark-versjon…')",
            'self.version_button.clicked.connect(self._show_version_evidence)',
            'inspect_report_version(finding.report_path)',
            'comparison_label(evidence, item.version)',
            "add('Uttrekkets Noark-versjon (XSD)', evidence.display)",
            'QFileDialog.getExistingDirectory(',
        ):
            self.assertIn(piece, text)

if __name__ == '__main__': unittest.main()
