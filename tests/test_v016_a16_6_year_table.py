from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]

class A166YearTableTests(unittest.TestCase):
    def test_runtime_is_wired(self):
        main = (ROOT / "main.py").read_text(encoding="utf-8")
        self.assertIn("from gui.persistent_app_a16_6 import run_gui", main)

    def test_readable_year_table(self):
        text = (ROOT / "gui" / "depot_result_center_a16_6.py").read_text(encoding="utf-8")
        for label in ("År", "Mapper/saker", "Registrering/JP", "Dok.beskrivelser", "Dok.objekter", "Sum"):
            self.assertIn(label, text)

    def test_document_analysis_scope_is_recorded(self):
        text = (ROOT / "gui" / "depot_result_center_a16_6.py").read_text(encoding="utf-8")
        for label in ("dokumentbeskrivelse", "dokumentobjekt", "hoveddokument", "vedlegg", "produksjonsformat", "arkivformat", "dokumentnummer", "versjonsnummer"):
            self.assertIn(label, text.lower())

if __name__ == "__main__":
    unittest.main()
