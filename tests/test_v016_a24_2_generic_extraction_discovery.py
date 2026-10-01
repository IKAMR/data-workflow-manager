from pathlib import Path
import json
import re
import tempfile
import unittest

from noark5_workflow.extraction_discovery import (
    discover_in_folders,
    extraction_definition,
    load_extraction_definitions,
)

ROOT = Path(__file__).resolve().parents[1]


class A242GenericExtractionDiscoveryTests(unittest.TestCase):
    def test_definitions_are_external_and_include_noark5_and_siard(self):
        path = ROOT / "config" / "extraction_types.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        ids = {item["id"] for item in payload["extraction_types"]}
        self.assertEqual({"noark5", "siard"}, ids)
        source = (ROOT / "noark5_workflow" / "extraction_discovery.py").read_text(encoding="utf-8")
        self.assertNotIn('_DOCUMENT_DIR_NAMES', source)
        self.assertNotIn('".siard"', source)

    def test_noark5_rule_is_data_driven(self):
        defs = load_extraction_definitions(ROOT / "config" / "extraction_types.json")
        definition = extraction_definition("noark5", defs)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "system" / "extract"
            root.mkdir(parents=True)
            (root / "ArKiVsTrUkTuR.XmL").write_text("<x/>", encoding="utf-8")
            (root / "DoKuMeNtEr").mkdir()
            result = discover_in_folders(Path(tmp), definition)
            self.assertEqual((root,), tuple(item.path for item in result.candidates))

    def test_siard_rule_is_data_driven(self):
        defs = load_extraction_definitions(ROOT / "config" / "extraction_types.json")
        definition = extraction_definition("siard", defs)
        with tempfile.TemporaryDirectory() as tmp:
            expected = Path(tmp) / "nested" / "base.SIARD"
            expected.parent.mkdir()
            expected.write_bytes(b"dummy")
            (expected.parent / "ignore.zip").write_bytes(b"dummy")
            result = discover_in_folders(Path(tmp), definition)
            self.assertEqual((expected,), tuple(item.path for item in result.candidates))

    def test_gui_has_one_generic_entry_and_two_source_choices(self):
        jobs = (ROOT / "gui" / "jobs_window_a30.py").read_text(encoding="utf-8")
        dialog = (ROOT / "gui" / "extraction_discovery_dialog.py").read_text(encoding="utf-8")
        self.assertIn('text="Finn uttrekk..."', jobs)
        self.assertIn('text="Søk i mapper..."', dialog)
        self.assertIn('text="Søk fra liste..."', dialog)
        self.assertIn('widget.pack_forget()', jobs)

    def test_robocopy_is_adapter_not_main_gui_concept(self):
        engine = (ROOT / "noark5_workflow" / "extraction_discovery.py").read_text(encoding="utf-8")
        jobs = (ROOT / "gui" / "jobs_window_a30.py").read_text(encoding="utf-8")
        self.assertIn('definition.list_reader == "robocopy_noark5"', engine)
        self.assertNotIn("Robocopy", jobs)

    def test_runtime_and_version_are_a242(self):
        main = (ROOT / "main.py").read_text(encoding="utf-8")
        version = (ROOT / "version.py").read_text(encoding="utf-8")
        self.assertIn("from gui.persistent_app_a24_2 import run_gui", main)
        match = re.search(r'VERSION\s*=\s*"0\.1\.6-a(\d+)(?:\.(\d+))?"', version)
        self.assertIsNotNone(match)
        self.assertGreaterEqual(int(match.group(1)), 24)


if __name__ == "__main__":
    unittest.main()
