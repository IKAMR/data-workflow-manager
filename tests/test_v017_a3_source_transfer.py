"""Regressions for metadata source selection and explicit transfer."""
import ast
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
EDITOR = ROOT / "gui" / "depot_metadata_editor_v017_a1.py"


def _methods():
    tree = ast.parse(EDITOR.read_text(encoding="utf-8"))
    wanted = {"_source_field", "_source_choices"}
    nodes = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name in wanted]
    namespace = {"Path": Path, "LEGACY_TO_CANONICAL": {"preserver": "recipient"}}
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(EDITOR), "exec"), namespace)
    return namespace


class MetadataSourceTransferTests(unittest.TestCase):
    def test_source_selection_disambiguates_same_filename_by_index_hash_and_date(self):
        f = _methods()["_source_choices"]
        choices = f([{"path": "C:/one/info.xml", "imported_at": "2026-01-01", "sha256": "a" * 64},
                     {"path": "D:/two/info.xml", "imported_at": "2026-01-02", "sha256": "b" * 64}])
        self.assertEqual(len(set(choices)), 2)
        self.assertTrue(choices[0].startswith("1:"))
        self.assertTrue(choices[1].startswith("2:"))

    def test_source_values_keep_provenance_separate(self):
        field = _methods()["_source_field"]
        one = {"fields": {"recipient": "Depot A"}}
        two = {"fields": {"recipient": "Depot B"}}
        self.assertEqual(field(one, "recipient"), "Depot A")
        self.assertEqual(field(two, "recipient"), "Depot B")
        self.assertEqual(field(one, "unknown"), "")

    def test_old_metadata_key_is_readable(self):
        field = _methods()["_source_field"]
        self.assertEqual(field({"fields": {"preserver": "Depot"}}, "recipient"), "Depot")

    def test_editor_has_source_selector_and_explicit_transfer_controls(self):
        source = EDITOR.read_text(encoding="utf-8")
        for name in ("_select_source", "_copy_field", "_fill_missing", "_fill_all", "_transfer"):
            self.assertIn("def " + name, source)
        self.assertIn("self._review_replacements(conflicts)", source)
        self.assertIn("ctk.CTkScrollableFrame(dialog)", source)
        self.assertIn("update_current_metadata(self.job, self._values())", source)


if __name__ == "__main__":
    unittest.main()
