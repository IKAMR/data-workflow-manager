"""Prevent the classic GUI launcher from silently pointing at the a2 layout."""
from __future__ import annotations

import ast
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class ClassicGuiEntryTests(unittest.TestCase):
    def test_legacy_bat_starts_classic_runtime(self):
        source = (ROOT / "start-legacy.bat").read_text(encoding="utf-8")
        self.assertIn('set "PYTHON_GIL=1"', source)
        self.assertIn('py -m gui.legacy_runtime_v018_a4', source)
        self.assertLess(source.index('set "PYTHON_GIL=1"'), source.index('py -m'))
        self.assertNotIn('py main.py', source)

    def test_classic_runtime_inherits_pre_a2_gui(self):
        source = (ROOT / "gui" / "legacy_runtime_v018_a4.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        classes = [node for node in tree.body if isinstance(node, ast.ClassDef)]
        self.assertEqual(len(classes), 1)
        self.assertEqual(classes[0].name, "WorkflowApp")
        self.assertEqual([base.id for base in classes[0].bases], ["A46WorkflowApp"])
        self.assertIn("from .persistent_app_a4_6_runtime import WorkflowApp as A46WorkflowApp", source)
        self.assertNotIn("from .embedded_jobs_v018_a2 import", source)

    def test_original_receiving_folder_action_is_available(self):
        source = (ROOT / "gui" / "legacy_runtime_v018_a4.py").read_text(encoding="utf-8")
        self.assertIn('text="Mottak / Ingest"', source)
        self.assertIn("def _open_receiving_folder_dialog", source)
        self.assertIn("def run_gui()", source)


if __name__ == "__main__":
    unittest.main()
