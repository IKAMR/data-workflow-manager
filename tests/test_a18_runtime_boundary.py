from pathlib import Path
import re
import unittest

from version import VERSION

ROOT = Path(__file__).resolve().parents[1]


class A18RuntimeBoundaryTests(unittest.TestCase):
    def test_current_runtime_preserves_a18(self):
        main = (ROOT / "main.py").read_text(encoding="utf-8")
        self.assertIn("persistent_app_a21", main)
        a21 = (ROOT / "gui" / "persistent_app_a21.py").read_text(encoding="utf-8")
        a20 = (ROOT / "gui" / "persistent_app_a20.py").read_text(encoding="utf-8")
        a19 = (ROOT / "gui" / "persistent_app_a19.py").read_text(encoding="utf-8")
        self.assertIn("A20WorkflowApp", a21)
        self.assertIn("A19WorkflowApp", a20)
        a18 = (ROOT / "gui" / "persistent_app_a18.py").read_text(encoding="utf-8")
        self.assertIn("from .persistent_app_a18 import WorkflowApp as A18WorkflowApp", a19)
        self.assertIn("class WorkflowApp(A18WorkflowApp)", a19)

    def test_a18_extends_a17_instead_of_replacing_it(self):
        a18 = (ROOT / "gui" / "persistent_app_a18.py").read_text(encoding="utf-8")
        self.assertIn("from .persistent_app_a17 import WorkflowApp as A17WorkflowApp", a18)
        self.assertIn("class WorkflowApp(A17WorkflowApp)", a18)

    def test_version_boundary_is_not_older_than_a18(self):
        alpha = re.fullmatch(
            r"(\d+)\.(\d+)\.(\d+)-a(\d+)(?:\.\d+)*",
            VERSION,
        )
        release = re.fullmatch(r"(\d+)\.(\d+)\.(\d+)", VERSION)

        self.assertTrue(
            alpha or release,
            f"Uventet versjonsformat: {VERSION}",
        )

        if release:
            major, minor, patch = map(int, release.groups())
            self.assertGreaterEqual((major, minor, patch), (0, 1, 2))
            return

        major, minor, patch, alpha_no = map(int, alpha.groups())
        self.assertGreaterEqual((major, minor, patch, alpha_no), (0, 1, 2, 18))


if __name__ == "__main__":
    unittest.main()
