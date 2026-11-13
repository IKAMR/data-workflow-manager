"""Qt-free a3 fix2 regressions for metadata-first and local drop routing."""
from __future__ import annotations

import ast
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from app.basic_drop_v0113_a3 import classify_basic_drop

ROOT = Path(__file__).resolve().parents[1]
GUI = ROOT / "gui_qt" / "basic_main_v0113_a2.py"


class BasicDropsTests(unittest.TestCase):
    def test_directory_targets(self):
        with TemporaryDirectory() as tmp:
            folder = Path(tmp)
            self.assertEqual(classify_basic_drop(folder, "source"), ("source", folder))
            self.assertEqual(classify_basic_drop(folder, "work"), ("work", folder))
            with self.assertRaises(ValueError):
                classify_basic_drop(folder, "info")

    def test_xml_and_joblist(self):
        with TemporaryDirectory() as tmp:
            base = Path(tmp)
            xml = base / "info.xml"
            xml.write_text("<root/>", encoding="utf-8")
            joblist = base / "jobs.n5jobs"
            joblist.write_text("{}", encoding="utf-8")
            self.assertEqual(classify_basic_drop(xml, "source"), ("info", xml))
            self.assertEqual(classify_basic_drop(xml, "info"), ("info", xml))
            self.assertEqual(classify_basic_drop(joblist, "joblist"), ("joblist", joblist))
            with self.assertRaises(ValueError):
                classify_basic_drop(xml, "work")
            with self.assertRaises(ValueError):
                classify_basic_drop(joblist, "source")

    def test_invalid_paths_and_roles(self):
        with TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                classify_basic_drop(Path(tmp) / "missing.xml", "info")
            with self.assertRaises(ValueError):
                classify_basic_drop(tmp, "invalid")

    def test_gui_file_chooser_no_longer_requires_source(self):
        tree = ast.parse(GUI.read_text(encoding="utf-8"))
        gui = next(node for node in tree.body if isinstance(node, ast.ClassDef)
                   and node.name == "DwmMainWindow")
        method = next(node for node in gui.body if isinstance(node, ast.FunctionDef)
                      and node.name == "_a2_edit_info")
        body = ast.get_source_segment(GUI.read_text(encoding="utf-8"), method)
        self.assertNotIn("Velg Source eller les info.xml først", body)
        for method_name in ("_a3_enable_drops", "_a3_import_info_path",
                            "_a3_accept_source", "_a3_accept_work", "eventFilter"):
            self.assertTrue(any(isinstance(m, ast.FunctionDef) and m.name == method_name
                                for m in gui.body), method_name)
        self.assertIn("self._a3_enable_drops()", GUI.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
