from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from noark5_workflow.extraction_discovery import discover_in_folders, extraction_definition


class A244SourceRootContractTests(unittest.TestCase):
    def test_noark5_extraction_and_source_root_are_distinct(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td) / "1502_003_AIC-1"
            extraction = base / "content" / "sip" / "content" / "part-001" / "avleveringspakke"
            extraction.mkdir(parents=True)
            (extraction / "arkivstruktur.xml").write_text("<x/>", encoding="utf-8")
            (extraction / "dokument").mkdir()
            result = discover_in_folders(base, extraction_definition("noark5"))
            self.assertEqual(len(result.candidates), 1)
            candidate = result.candidates[0]
            self.assertEqual(candidate.path, extraction)
            self.assertEqual(candidate.source_root_hint, base)

    def test_noark5_source_root_rule_is_external_data(self):
        payload = json.loads((Path(__file__).resolve().parents[1] / "config" / "extraction_types.json").read_text(encoding="utf-8"))
        noark = next(x for x in payload["extraction_types"] if x["id"] == "noark5")
        self.assertEqual(noark["source_root"]["strategy"], "ancestor_before_sequence")
        self.assertEqual(noark["source_root"]["sequence"], ["content", "sip", "content"])

    def test_siard_source_root_is_parent_folder(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            siard = base / "db.siard"
            siard.write_bytes(b"")
            result = discover_in_folders(base, extraction_definition("siard"))
            self.assertEqual(result.candidates[0].source_root_hint, base)

    def test_runtime_activates_a244(self):
        source = (Path(__file__).resolve().parents[1] / "main.py").read_text(encoding="utf-8")
        self.assertIn("persistent_app_a24_4", source)


if __name__ == "__main__":
    unittest.main()
