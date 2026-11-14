from pathlib import Path
import re
import unittest
from version_assertions import assert_v016_at_least

ROOT = Path(__file__).resolve().parents[1]


def _assert_version_at_least(testcase, version_text, alpha, sub=0):
    # Accept the repository's normal version declaration regardless of whether
    # it has a leading "v" and regardless of quote/assignment formatting.
    assert_v016_at_least(testcase, version_text, alpha, sub, consolidated_alpha=True)


class A213Tests(unittest.TestCase):
    def test_runtime(self):
        _assert_version_at_least(
            self,
            (ROOT / "version.py").read_text(encoding="utf-8"),
            21,
            3,
        )

    def test_overview_target_structure(self):
        source = (ROOT / "gui" / "depot_result_center_a21_3.py").read_text(encoding="utf-8")
        for token in (
            "Resultatfordeling – DWM-kontroller",
            "Korrespondanseprofil – journalposter",
            "Tidsprofil – hele uttrekket",
            "Filformater",
            "Vurderingspunkter",
            "Videre arbeid",
        ):
            self.assertIn(token, source)

    def test_pronom_uses_full_tab_width(self):
        source = (ROOT / "gui" / "depot_result_center_a21_3.py").read_text(encoding="utf-8")
        self.assertIn('sticky="nsew"', source)
        self.assertIn("grid_columnconfigure", source)


if __name__ == "__main__":
    unittest.main()
