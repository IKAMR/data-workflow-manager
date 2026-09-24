
from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class V015A25ActivationFixTests(unittest.TestCase):
    def test_runtime_uses_explicit_a25_layers(self):
        text = (ROOT / "gui" / "persistent_app_a60.py").read_text(encoding="utf-8")
        self.assertIn("DepotAssessmentDialogA20", text)
        self.assertIn("DirectDepotAssessmentDialogA20", text)
        self.assertIn("Noark5ControlOverviewDialogA20", text)

    def test_runtime_no_longer_depends_on_monkeypatch(self):
        text = (ROOT / "gui" / "persistent_app_a60.py").read_text(encoding="utf-8")
        self.assertNotIn(
            "depot_assessment_dialog.DepotResultViewsDialog = DepotResultViewsDialogA20",
            text,
        )
        self.assertNotIn("_activate_a25_result_views", text)

    def test_active_runtime_is_a60(self):
        text = (ROOT / "main.py").read_text(encoding="utf-8")
        self.assertIn("from gui.persistent_app_a60 import run_gui", text)


if __name__ == "__main__":
    unittest.main()
