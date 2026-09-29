from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]


def _assert_version_at_least(testcase, version_text, alpha, sub=0):
    # Accept the repository's normal version declaration regardless of whether
    # it has a leading "v" and regardless of quote/assignment formatting.
    match = re.search(r'0\.1\.6-a(\d+)(?:\.(\d+))?', version_text)
    testcase.assertIsNotNone(
        match,
        msg=f"Could not parse v0.1.6 alpha version from version.py: {version_text!r}",
    )
    actual_alpha = int(match.group(1))
    actual_sub = None if match.group(2) is None else int(match.group(2))
    testcase.assertTrue(actual_alpha > alpha or (actual_alpha == alpha and (actual_sub is None or actual_sub >= sub)))


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
