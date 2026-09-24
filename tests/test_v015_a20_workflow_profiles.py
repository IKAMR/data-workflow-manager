
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.workflow_sequences import (
    load_builtin_workflow_sequences,
    workflow_sequence_by_id,
)


class V015A20WorkflowProfilesTests(unittest.TestCase):
    def test_builtin_sequences_include_standard_dwm_and_analysis(self):
        ids = [sequence.sequence_id for sequence in load_builtin_workflow_sequences()]
        self.assertIn("noark5_standard", ids)
        self.assertIn("noark5_dwm", ids)
        self.assertIn("noark5_analyse", ids)

    def test_dwm_sequence_has_no_arkade_import(self):
        sequence = workflow_sequence_by_id("noark5_dwm")
        self.assertIsNotNone(sequence)
        self.assertNotIn("import_arkade5_reports", sequence.operation_ids)
        self.assertIn("compose_noark5_views", sequence.operation_ids)
        self.assertIn("build_noark5_depot_report", sequence.operation_ids)

    def test_standard_sequence_keeps_arkade_import(self):
        sequence = workflow_sequence_by_id("noark5_standard")
        self.assertIsNotNone(sequence)
        self.assertIn("import_arkade5_reports", sequence.operation_ids)

    def test_a55_enables_save_and_choose_profile_controls(self):
        root = Path(__file__).resolve().parents[1]
        text = (root / "gui" / "persistent_app_a55.py").read_text(encoding="utf-8")
        self.assertIn('text="Lagre profil..."', text)
        self.assertIn('text="Velg profil..."', text)
        self.assertIn("save_custom_workflow_sequence", text)
        self.assertIn("WorkflowProfilesDialog", text)

    def test_main_activates_a55_runtime(self):
        root = Path(__file__).resolve().parents[1]
        text = (root / "main.py").read_text(encoding="utf-8")
        self.assertIn("from gui.persistent_app_a55 import run_gui", text)


if __name__ == "__main__":
    unittest.main()
