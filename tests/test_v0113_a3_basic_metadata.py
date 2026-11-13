"""Qt-free checks for a3 New control, clean LABEL and DIAS status."""
from __future__ import annotations

import ast
from pathlib import Path
from types import SimpleNamespace
import unittest
from app.dias_status_v0113_a3 import describe_info_xml_status
from app.dias_info_v0113_a2 import linked_values

ROOT = Path(__file__).resolve().parents[1]
GUI = ROOT / 'gui_qt/basic_main_v0113_a2.py'


class InfoXmlStatusTests(unittest.TestCase):
    def test_missing(self):
        self.assertEqual(describe_info_xml_status({}), 'Ikke funnet')

    def test_created_without_original(self):
        self.assertEqual(describe_info_xml_status({'label': 'Arkiv'}), 'Opprettet i DWM')
        self.assertEqual(describe_info_xml_status({'label': 'Arkiv'}, dirty=True),
                         'Opprettet i DWM (ikke lagret)')

    def test_imported_unchanged_and_edited(self):
        source = [{'fields': {'label': 'A', 'archive_description': 'A'}}]
        self.assertEqual(describe_info_xml_status({'label': 'A', 'archive_description': 'A'}, source),
                         'Original importert')
        self.assertEqual(describe_info_xml_status({'label': 'B', 'archive_description': 'B'}, source),
                         'Redigert')
        self.assertEqual(describe_info_xml_status({'label': 'B', 'archive_description': 'B'}, source,
                                                  dirty=True), 'Redigert (ikke lagret)')

    def test_discovered_but_not_imported(self):
        from tempfile import TemporaryDirectory
        with TemporaryDirectory() as tmp:
            original = Path(tmp) / 'info.xml'
            original.write_text('placeholder', encoding='utf-8')
            self.assertEqual(describe_info_xml_status({'label': 'A'}, original=original,
                                                      original_fields={'label': 'A'}, dirty=True),
                             'Funnet – ikke importert')
            self.assertEqual(describe_info_xml_status({'label': 'B'}, original=original,
                                                      original_fields={'label': 'A'}, dirty=True),
                             'Redigert (ikke lagret)')

    def test_explicit_empty_label_clears_linked_field(self):
        result = linked_values({'label': '', 'archive_description': 'Old'})
        self.assertEqual((result['label'], result['archive_description']), ('', ''))
        self.assertEqual(linked_values({'archive_description': 'Original'})['label'], 'Original')


class BasicA3GuiTests(unittest.TestCase):
    def test_new_control_resets_joblist_without_deleting_old_file(self):
        tree = ast.parse(GUI.read_text(encoding='utf-8'))
        cls = next(node for node in tree.body if isinstance(node, ast.ClassDef)
                   and node.name == 'DwmMainWindow')
        method = next(node for node in cls.body if isinstance(node, ast.FunctionDef)
                      and node.name == '_a3_new_control')
        module = ast.fix_missing_locations(ast.Module(body=[ast.ClassDef(
            name='Isolated', bases=[], keywords=[], body=[method], decorator_list=[],
        )], type_ignores=[]))
        scope = {'QMessageBox': SimpleNamespace(information=lambda *a: None)}
        exec(compile(module, str(GUI), 'exec'), scope)
        class Field:
            def __init__(self): self.value = 'X'
            def clear(self): self.value = ''
        class Note:
            def setText(self, value): self.value = value
        class Config:
            def __init__(self): self.values = {}
            def setValue(self, name, value): self.values[name] = value
        class API:
            running = False
            def __init__(self): self.joblist = 'C:/existing/project.n5jobs'; self.calls = 0
            def workspace(self): return SimpleNamespace(job_list_path=self.joblist)
            def new_job_list(self): self.joblist = None; self.calls += 1
        obj = scope['Isolated']()
        obj.api = API()
        obj._worker = None
        obj._maybe_save = lambda: True
        obj._active_id = 'JOB-001'
        obj._a2_pending_values = {'label': 'Old'}
        obj._a2_pending_dirty = True
        obj._a2_original = Path('C:/original/info.xml')
        obj.basic_dias_label = Field()
        obj.basic_dias_note = Note()
        obj.config = Config()
        obj._reset_basic_selection = lambda: None
        obj._refresh_recent_menu = lambda: None
        obj._refresh = lambda **kwargs: None
        obj._a2_set_step = lambda step: setattr(obj, 'step', step)
        obj._a3_new_control()
        self.assertEqual(obj.api.calls, 1)
        self.assertIsNone(obj.api.workspace().job_list_path)
        self.assertIsNone(obj._active_id)
        self.assertEqual(obj._a2_pending_values, {})
        self.assertEqual(obj.basic_dias_label.value, '')
        self.assertEqual(obj.config.values['qt/last_job_list'], '')
        self.assertEqual(obj.step, 'overview')

        # Cancel from the existing unsaved-changes prompt must leave everything.
        obj.api.joblist = 'C:/existing/project.n5jobs'
        obj._active_id = 'JOB-002'
        obj._maybe_save = lambda: False
        obj._a3_new_control()
        self.assertEqual(obj.api.calls, 1)
        self.assertEqual(obj.api.workspace().job_list_path, 'C:/existing/project.n5jobs')
        self.assertEqual(obj._active_id, 'JOB-002')

    def test_overview_starts_with_source_and_joblist_last(self):
        source = GUI.read_text(encoding='utf-8')
        ordered = (
            "('source', '1. Source og DIAS-metadata', 'source')",
            "('work', '2. Work', 'work')",
            "('run', '3. Kontroller og kjøring', 'run')",
            "('joblist', 'Jobbliste (valgfritt)', None)",
        )
        positions = [source.index(item) for item in ordered]
        self.assertEqual(positions, sorted(positions))
        self.assertIn("self.basic_info_xml_button = QPushButton('Info.xml – Les / endre'", source)
        self.assertNotIn("self.basic_load_info_button = QPushButton", source)
        self.assertIn("self.api.new_job_list()", source)
        self.assertIn("self.config.setValue('qt/skip_auto_reopen', True)", source)

    def test_manually_imported_info_survives_source_selection(self):
        tree = ast.parse(GUI.read_text(encoding='utf-8'))
        cls = next(node for node in tree.body if isinstance(node, ast.ClassDef)
                   and node.name == 'DwmMainWindow')
        method = next(node for node in cls.body if isinstance(node, ast.FunctionDef)
                      and node.name == '_a2_source_changed')
        module = ast.fix_missing_locations(ast.Module(body=[ast.ClassDef(
            name='Isolated', bases=[], keywords=[], body=[method], decorator_list=[],
        )], type_ignores=[]))
        scope = {}
        exec(compile(module, str(GUI), 'exec'), scope)
        class Field:
            def __init__(self): self.value = ''
            def setText(self, value): self.value = value
        obj = scope['Isolated']()
        obj._a2_preserve_draft = False
        obj._a3_manually_loaded_info = True
        obj._a2_original = Path('C:/info.xml')
        obj._a2_pending_values = {'label': 'Fra original'}
        obj._a2_pending_dirty = True
        obj.basic_dias_label = Field()
        obj.basic_dias_note = Field()
        obj._a2_matching_job = lambda: None
        obj._a2_source_changed('D:/source/new')
        self.assertEqual(obj._a2_pending_values['label'], 'Fra original')
        self.assertEqual(obj._a2_original, Path('C:/info.xml'))
        self.assertTrue(obj._a2_pending_dirty)

    def test_no_default_content_and_no_working_copy_path_in_overview(self):
        source = GUI.read_text(encoding='utf-8')
        self.assertIn("label = self._a2_pending_values.get('label') or ''", source)
        self.assertIn("label = values.get('label') or ''", source)
        self.assertNotIn("('info.xml (arbeidskopi)', 'Arbeidskopi')", source)
        self.assertIn("('info.xml', 'InfoStatus')", source)
        self.assertIn("QPushButton('Ny kontroll'", source)
        self.assertIn('describe_info_xml_status(', source)
        self.assertIn('self._a2_set_step(\'overview\')', source)


if __name__ == '__main__':
    unittest.main()
