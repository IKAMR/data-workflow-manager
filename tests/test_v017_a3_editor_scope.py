"""Contract: DIAS metadata editor exposes only 47 fields, preserving separate depot metadata."""
import ast
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]

class A36MetadataLayoutTests(unittest.TestCase):
    def test_only_47_dias_fields_are_editable(self):
        tree = ast.parse((ROOT / "gui" / "depot_metadata_editor_v017_a1.py").read_text(encoding="utf-8"))
        values = {node.targets[0].id: ast.literal_eval(node.value)
                  for node in tree.body if isinstance(node, ast.Assign)
                  and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name)
                  and node.targets[0].id in {"_FIELDS", "_DEPOT_ADDITIONAL_FIELDS"}}
        self.assertEqual(len(values["_FIELDS"]), 47)
        self.assertEqual(len(values["_DEPOT_ADDITIONAL_FIELDS"]), 4)
        self.assertFalse({key for key, *_ in values["_FIELDS"]} &
                         {key for key, *_ in values["_DEPOT_ADDITIONAL_FIELDS"]})

    def test_conflicts_use_unambiguous_labels(self):
        source = (ROOT / "gui" / "depot_metadata_editor_v017_a1.py").read_text(encoding="utf-8")
        self.assertIn('text=f"Gammel: {old}"', source)
        self.assertIn('text=f"Ny: {new}"', source)
        self.assertNotIn('text=f"Fra: {old}"', source)
        self.assertNotIn('text=f"Til:  {new}"', source)

    def test_existing_additional_data_not_written_by_editor(self):
        source = (ROOT / "gui" / "depot_metadata_editor_v017_a1.py").read_text(encoding="utf-8")
        self.assertIn('return {key: self._field_value(key) for key, _, _ in _FIELDS}', source)
        self.assertIn('update_current_metadata(self.job, self._values())', source)

if __name__ == "__main__":
    unittest.main()
