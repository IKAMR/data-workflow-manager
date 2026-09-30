from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]

class A223ControlWorkspaceTests(unittest.TestCase):
    def test_runtime_activates_a223(self):
        source=(ROOT/'main.py').read_text(encoding='utf-8')
        self.assertIn('from gui.persistent_app_a22_3 import run_gui', source)
    def test_workspace_is_maximized_standard_window(self):
        source=(ROOT/'gui'/'depot_result_center_a22_3.py').read_text(encoding='utf-8')
        self.assertIn('win.state("zoomed")', source)
        self.assertIn('win.resizable(True, True)', source)
        self.assertNotIn('win.transient(self)', source)
    def test_workspace_shows_evidence_and_navigation(self):
        source=(ROOT/'gui'/'depot_result_center_a22_3.py').read_text(encoding='utf-8')
        for token in ('Resultat og evidens','Faglig vurdering','← Forrige kontroll','Neste kontroll →','Lagre og neste →'):
            self.assertIn(token, source)

if __name__ == '__main__':
    unittest.main()
