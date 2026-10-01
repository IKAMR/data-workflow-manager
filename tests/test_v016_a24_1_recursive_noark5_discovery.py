from __future__ import annotations

from pathlib import Path
import re
import tempfile
import unittest

from noark5_workflow.noark5_discovery import discover_noark5_extractions


ROOT = Path(__file__).resolve().parents[1]


class A241RecursiveNoark5DiscoveryTests(unittest.TestCase):
    def test_discovers_nested_extraction_case_insensitively(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            extraction = base / "client" / "package" / "content"
            extraction.mkdir(parents=True)
            (extraction / "ArKiVsTrUkTuR.Xml").write_text("<x/>", encoding="utf-8")
            (extraction / "DoKuMeNtEr").mkdir()

            result = discover_noark5_extractions(base)

            self.assertEqual(result.roots, (extraction,))
            self.assertEqual(result.candidates[0].document_dir.name, "DoKuMeNtEr")

    def test_requires_both_arkivstruktur_and_document_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            only_xml = base / "only-xml"
            only_xml.mkdir()
            (only_xml / "arkivstruktur.xml").write_text("<x/>", encoding="utf-8")

            only_docs = base / "only-docs"
            only_docs.mkdir()
            (only_docs / "DOKUMENT").mkdir()

            result = discover_noark5_extractions(base)
            self.assertEqual(result.roots, ())

    def test_document_payload_is_pruned_from_recursive_search(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            outer = base / "valid"
            outer.mkdir()
            (outer / "arkivstruktur.xml").write_text("<x/>", encoding="utf-8")
            documents = outer / "DOKUMENT"
            documents.mkdir()

            fake_nested = documents / "not-an-independent-extraction"
            fake_nested.mkdir()
            (fake_nested / "arkivstruktur.xml").write_text("<x/>", encoding="utf-8")
            (fake_nested / "dokumenter").mkdir()

            result = discover_noark5_extractions(base)
            self.assertEqual(result.roots, (outer,))

    def test_runtime_activates_a241(self):
        source = (ROOT / "main.py").read_text(encoding="utf-8")
        self.assertIn("from gui.persistent_app_a24_1 import run_gui", source)

    def test_version_is_a241(self):
        source = (ROOT / "version.py").read_text(encoding="utf-8")
        match = re.search(r'VERSION\s*=\s*"0\.1\.6-a(\d+)(?:\.(\d+))?"', source)
        self.assertIsNotNone(match)
        self.assertGreaterEqual(int(match.group(1)), 24)

    def test_jobs_window_exposes_recursive_discovery_action(self):
        source = (ROOT / "gui" / "jobs_window_a29.py").read_text(encoding="utf-8")
        self.assertIn('text="Finn Noark 5..."', source)
        self.assertIn("discover_noark5_extractions", source)
        self.assertIn("threading.Thread", source)

    def test_discovery_is_separate_from_robocopy_import(self):
        source = (ROOT / "gui" / "persistent_app_a24_1.py").read_text(encoding="utf-8")
        self.assertNotIn("robocopy", source.lower())
        self.assertIn("_a241_apply_noark5_discovery", source)


if __name__ == "__main__":
    unittest.main()
