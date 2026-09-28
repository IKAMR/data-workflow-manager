from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class A1614ResultSurfaceTests(unittest.TestCase):
    def test_main_uses_a16_14_before_main_guard(self):
        text = (ROOT / "main.py").read_text(encoding="utf-8")
        import_pos = text.rfind("from gui.persistent_app_a16_14 import run_gui")
        guard_pos = text.rfind('if __name__ == "__main__":')
        self.assertGreater(import_pos, -1)
        self.assertLess(import_pos, guard_pos)

    def test_legacy_controls_sink_prevents_destroyed_textbox_write(self):
        text = (ROOT / "gui" / "depot_result_center_a16_14.py").read_text(encoding="utf-8")
        self.assertIn("_ensure_legacy_controls_sink", text)
        self.assertIn("self._a10_controls = sink", text)

    def test_per_year_has_context_panel(self):
        text = (ROOT / "gui" / "depot_result_center_a16_14.py").read_text(encoding="utf-8")
        self.assertIn('text="Ytterår og kilder"', text)
        self.assertIn("Arkivdeler med egne oppgitte ytterår", text)
        self.assertIn("År som krever vurdering", text)


if __name__ == "__main__":
    unittest.main()
