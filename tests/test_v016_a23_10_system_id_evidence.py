from pathlib import Path
import re
import unittest
from version_assertions import assert_v016_at_least

ROOT = Path(__file__).resolve().parents[1]
CENTER = ROOT / "gui" / "depot_result_center_a23_10.py"


class A2310SystemIdEvidenceTests(unittest.TestCase):
    def test_runtime_activates_a2310_or_newer(self):
        source = (ROOT / "main.py").read_text(encoding="utf-8")
        imports = [
            int(v)
            for v in re.findall(
                r"from gui\.persistent_app_a23_(\d+) import run_gui",
                source,
            )
        ]
        self.assertTrue(imports)
        self.assertGreaterEqual(max(imports), 10)

    def test_version_is_a2310_or_newer(self):
        source = (ROOT / "version.py").read_text(encoding="utf-8")
        assert_v016_at_least(self, source, 23, 10)

    def test_system_id_has_structured_evidence(self):
        source = CENTER.read_text(encoding="utf-8")
        self.assertIn('label == "systemID"', source)
        self.assertIn("_a2310_render_system_id", source)
        self.assertIn('"Identifikasjon"', source)
        self.assertIn('"Kontekst"', source)
        self.assertIn('"Vurderingsstøtte"', source)

    def test_materialized_only(self):
        source = CENTER.read_text(encoding="utf-8")
        self.assertNotIn("subprocess", source)
        self.assertNotIn("lxml", source)
        self.assertNotIn("etree", source)


if __name__ == "__main__":
    unittest.main()
