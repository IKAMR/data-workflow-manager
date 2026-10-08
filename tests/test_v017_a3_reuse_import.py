"""a3.5: non-evidence import must be a separate operator action."""
import ast
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
FILE = ROOT / 'gui' / 'depot_metadata_editor_v017_a1.py'

class ReuseImportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = FILE.read_text(encoding='utf-8')
        cls.tree = ast.parse(cls.text)
        cls.editor = next(n for n in cls.tree.body if isinstance(n, ast.ClassDef) and n.name == 'DepotMetadataEditor')

    def method(self, name):
        return next(n for n in self.editor.body if isinstance(n, ast.FunctionDef) and n.name == name)

    def test_explicit_two_import_modes(self):
        method = ast.get_source_segment(self.text, self.method('_choose_import_mode'))
        self.assertIn('Importer som evidens', method)
        self.assertIn('Importer for gjenbruk', method)
        self.assertIn('select(None)', method)

    def test_reuse_branch_never_registers_evidence(self):
        method = self.method('_choose_info_xml')
        branch = next(n for n in ast.walk(method) if isinstance(n, ast.If) and isinstance(n.test, ast.Compare)
                      and isinstance(n.test.left, ast.Name) and n.test.left.id == 'mode'
                      and any(isinstance(c, ast.Constant) and c.value == 'reuse' for c in n.test.comparators))
        block = ast.get_source_segment(self.text, branch)
        self.assertIn('read_meta_from_mets(Path(filename))', block)
        self.assertIn('self._reuse_source =', block)
        calls = [n.func.id if isinstance(n.func, ast.Name) else n.func.attr if isinstance(n.func, ast.Attribute) else ''
                 for statement in branch.body for n in ast.walk(statement) if isinstance(n, ast.Call)]
        for forbidden in ('import_selected_info_xml', 'update_current_metadata', 'save_depot_metadata', 'save_template'):
            self.assertNotIn(forbidden, calls)
        self.assertIn('import_selected_info_xml(self.job, Path(filename))', ast.get_source_segment(self.text, method))

    def test_reuse_is_not_written_to_source_imports(self):
        render = ast.get_source_segment(self.text, self.method('_render'))
        self.assertIn('self._imports.extend(load_templates())', render)
        self.assertIn('self._imports.append(self._reuse_source)', render)
        self.assertNotIn('payload["source_imports"].append(self._reuse_source)', render)
        self.assertIn('self._source_menu.set(_source_choices(self._imports)[self._selected_source])', self.text)

    def test_reuse_follows_existing_transfer_and_template_flow(self):
        self.assertIn('def _copy_field(', self.text)
        self.assertIn('def _review_replacements(', self.text)
        self.assertIn('def _fill_missing(', self.text)
        self.assertIn('def _fill_all(', self.text)
        self.assertIn('save_template(name.strip(), self._values())', self.text)
        self.assertIn('source_values(payload, key)', self.text)

if __name__ == '__main__':
    unittest.main()
