from __future__ import annotations

import json
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class A243SelectionAndJobInitTests(unittest.TestCase):
    def test_selection_dialog_defaults_all_candidates_selected(self):
        source = (ROOT / "gui" / "extraction_candidate_selection_dialog.py").read_text(encoding="utf-8")
        self.assertIn("ctk.BooleanVar(value=True)", source)
        self.assertIn('text="Velg alle"', source)
        self.assertIn('text="Tøm"', source)
        self.assertIn('text="Legg til valgte"', source)
        self.assertIn("CTkCheckBox", source)

    def test_generic_discovery_routes_through_selection_dialog(self):
        source = (ROOT / "gui" / "persistent_app_a24_3.py").read_text(encoding="utf-8")
        self.assertIn("ExtractionCandidateSelectionDialog(", source)
        self.assertIn("on_confirm=lambda selected:", source)

    def test_every_selected_job_gets_both_source_fields_and_profile(self):
        source = (ROOT / "gui" / "persistent_app_a24_3.py").read_text(encoding="utf-8")
        self.assertRegex(source, r"job\.source_root\s*=\s*path")
        self.assertRegex(source, r"job\.source_extraction\s*=\s*path")
        self.assertRegex(source, r"job\.profile_id\s*=\s*candidate\.profile_id")
        self.assertNotRegex(source, r"else:\s*\n\s*job = self\._create_job\(path\)\s*\n\s*job\.source_extraction")

    def test_noark5_job_name_uses_extraction_parent_not_generic_avleveringspakke(self):
        payload = json.loads((ROOT / "config" / "extraction_types.json").read_text(encoding="utf-8"))
        noark = next(item for item in payload["extraction_types"] if item["id"] == "noark5")
        self.assertEqual(noark["job_name"], "parent_name")
        source = (ROOT / "noark5_workflow" / "extraction_discovery.py").read_text(encoding="utf-8")
        self.assertIn('definition.job_name == "parent_name"', source)

    def test_runtime_and_version_are_a243(self):
        main = (ROOT / "main.py").read_text(encoding="utf-8")
        version = (ROOT / "version.py").read_text(encoding="utf-8")
        self.assertIn("from gui.persistent_app_a24_3 import run_gui", main)
        match = re.search(r'VERSION\s*=\s*"0\.1\.6-a(\d+)(?:\.(\d+))?"', version)
        self.assertIsNotNone(match)
        self.assertGreaterEqual(int(match.group(1)), 24)


if __name__ == "__main__":
    unittest.main()
