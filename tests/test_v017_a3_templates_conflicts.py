import ast
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]

class MetadataTemplatesAndConflictsTests(unittest.TestCase):
    def test_gui_contract_has_scrollable_conflict_selection(self):
        src = (ROOT / 'gui/depot_metadata_editor_v017_a1.py').read_text(encoding='utf-8')
        self.assertIn('def _review_replacements(', src)
        self.assertIn('ctk.CTkScrollableFrame(dialog)', src)
        self.assertIn('ctk.CTkCheckBox(frame,', src)
        self.assertIn('Overfør valgte', src)
        self.assertIn('save_template(name.strip(), self._values())', src)
        ast.parse(src)

    def test_source_choices_distinguish_template_from_evidence(self):
        src = (ROOT / 'gui/depot_metadata_editor_v017_a1.py').read_text(encoding='utf-8')
        node = next(n for n in ast.parse(src).body if isinstance(n, ast.FunctionDef) and n.name == '_source_choices')
        ns = {'Path': Path}
        exec(compile(ast.Module(body=[node], type_ignores=[]), '<choice>', 'exec'), ns)
        labels = ns['_source_choices']([{'path': 'C:/info.xml'}, {'kind': 'template', 'name': 'Arkivskaper'}])
        self.assertIn('Kilde:', labels[0])
        self.assertIn('Mal: Arkivskaper', labels[1])

    def test_templates_persist_without_evidence_records(self):
        import sys
        sys.path.insert(0, str(ROOT))
        from noark5_workflow.reporting import metadata_templates as m
        with tempfile.TemporaryDirectory() as root:
            with patch.dict('os.environ', {'APPDATA': root}):
                m.save_template('Kommunen', {'archivist_org': 'Test kommune', 'recipient': ''})
                entries = m.load_templates()
                self.assertEqual(entries[0]['fields'], {'archivist_org': 'Test kommune'})
                self.assertEqual(entries[0]['kind'], 'template')
                with self.assertRaises(ValueError):
                    m.save_template('kommunen', {'archivist_org': 'Annen'})
                self.assertEqual(len(m.load_templates()), 1)

if __name__ == '__main__':
    unittest.main()
