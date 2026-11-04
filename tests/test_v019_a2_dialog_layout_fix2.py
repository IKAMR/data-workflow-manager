"""Headless layout regression for DWM v0.1.9-a2 (Windows Qt check still required)."""
from __future__ import annotations

import ast
from pathlib import Path
from types import SimpleNamespace
import unittest

ROOT = Path(__file__).resolve().parents[1]
UI = ROOT / "gui_qt" / "depot_review_v019_a2.py"


class A2LayoutFix2Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = UI.read_text(encoding="utf-8")
        cls.module = ast.parse(cls.source)

    def _method_source(self, klass: str, method: str) -> str:
        found = next(node for node in self.module.body
                     if isinstance(node, ast.ClassDef) and node.name == klass)
        target = next(node for node in found.body
                      if isinstance(node, ast.FunctionDef) and node.name == method)
        return ast.get_source_segment(self.source, target) or ""

    def test_actual_screen_size_is_respected(self):
        """Size policy executes headlessly: no PySide6 runtime required."""
        method = next(node for node in self.module.body
                      if isinstance(node, ast.FunctionDef) and node.name == "_dialog_size")
        class Screen:
            def __init__(self, width, height):
                self._area = SimpleNamespace(width=lambda: width, height=lambda: height)
            def availableGeometry(self):
                return self._area
        namespace = {"QApplication": SimpleNamespace(primaryScreen=lambda: Screen(1366, 700))}
        exec(compile(ast.Module(body=[method], type_ignores=[]), str(UI), "exec"), namespace)
        fn = namespace["_dialog_size"]
        parent = SimpleNamespace(screen=lambda: Screen(1920, 1080))
        self.assertEqual(fn(parent, 1180, 900), (1180, 900))
        parent = SimpleNamespace(screen=lambda: Screen(1366, 700))
        self.assertEqual(fn(parent, 1180, 900), (1180, 616))
        self.assertEqual(fn(None, 1180, 900), (1180, 616))

    def test_review_table_gets_majority_of_visible_tab(self):
        init = self._method_source("DepotReviewPanel", "__init__")
        self.assertIn("setChildrenCollapsible(False)", init)
        self.assertIn("self.tree.setMinimumHeight(230)", init)
        self.assertIn("self.detail.setMinimumHeight(130)", init)
        self.assertIn("splitter.setStretchFactor(0, 6)", init)
        self.assertIn("splitter.setStretchFactor(1, 4)", init)
        self.assertIn("splitter.setSizes([630, 370])", init)
        show = self._method_source("DepotReviewPanel", "showEvent")
        allocate = self._method_source("DepotReviewPanel", "_allocate_initial_space")
        self.assertIn("QTimer.singleShot(0, self._allocate_initial_space)", show)
        self.assertIn("self._initial_split_applied", show)
        self.assertIn("available * 0.62", allocate)
        self.assertIn("available * 0.38", allocate)
        self.assertNotIn("QTimer.singleShot", self._method_source("DepotReviewPanel", "set_snapshots"))

    def test_full_evidence_window_is_selectable_and_maximizable(self):
        init = self._method_source("ReviewEvidenceDialog", "__init__")
        self.assertIn('self.setWindowFlag(Qt.WindowType.WindowMaximizeButtonHint, True)', init)
        self.assertIn("self.resize(*_dialog_size(parent, 1180, 900))", init)
        self.assertIn('self.evidence.setReadOnly(True)', init)
        self.assertIn("_review_payload(row)", init)
        panel = self._method_source("DepotReviewPanel", "__init__")
        self.assertIn("self.detail_button.clicked.connect(self._open_large_details)", panel)
        self.assertIn("self.detail_button.setEnabled(bool(row))",
                      self._method_source("DepotReviewPanel", "_selection_changed"))
        self.assertIn("ReviewEvidenceDialog(row, self).exec()",
                      self._method_source("DepotReviewPanel", "_open_large_details"))

    def test_decision_dialog_keeps_reason_visible_without_changing_save_logic(self):
        init = self._method_source("DepotDecisionDialog", "__init__")
        save = self._method_source("DepotDecisionDialog", "_save")
        self.assertIn('self.setWindowFlag(Qt.WindowType.WindowMaximizeButtonHint, True)', init)
        self.assertIn("self.resize(*_dialog_size(parent, 1180, 900))", init)
        self.assertIn("evidence.setMinimumHeight(170)", init)
        self.assertIn("self.reason.setMinimumHeight(100)", init)
        self.assertIn("self.reason.setMaximumHeight(180)", init)
        self.assertNotIn("body = QSplitter", init)
        for marker in ("record_depot_review", "STATUS_LABELS", "self.reason.toPlainText().strip()",
                       "QMessageBox.question"):
            self.assertIn(marker, save)
        self.assertNotIn("import customtkinter", self.source)
        self.assertNotIn("import tkinter", self.source)


if __name__ == "__main__":
    unittest.main()
