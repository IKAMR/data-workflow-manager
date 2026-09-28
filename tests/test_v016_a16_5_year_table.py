from pathlib import Path
import unittest
ROOT = Path(__file__).resolve().parents[1]
class A165YearTableTests(unittest.TestCase):
    def test_readable_year_table_is_in_a164_runtime_layer(self):
        view = (ROOT / "gui" / "depot_result_center_a16_4.py").read_text(encoding="utf-8")
        self.assertIn("CTkScrollableFrame", view)
        self.assertIn('"År", "Mapper/saker", "Registrering/JP", "Dok.beskrivelser", "Dok.objekter"', view)
        self.assertIn("_render_a165_year_table", view)
if __name__ == "__main__": unittest.main()
