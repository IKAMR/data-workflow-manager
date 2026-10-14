"""a18-fix6: one active job and selected jobs use the same read-only report flow."""
from __future__ import annotations

import ast
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest import TestCase
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / 'gui/persistent_app_a4_6_runtime.py'
DIALOG = ROOT / 'gui/report_selected_dialog_a16.py'


class FakeBase:
    def _refresh_active_job_label(self):
        self.refresh_calls = getattr(self, 'refresh_calls', 0) + 1


class FakeWidget:
    def __init__(self, master, column):
        self.master = master
        self.column = column
        master.children.append(self)

    def grid_info(self):
        return {'column': self.column}

    def grid_configure(self, *, column):
        self.column = column


class FakeHeader:
    def __init__(self):
        self.children = []

    def winfo_children(self):
        return list(self.children)


class FakeButton(FakeWidget):
    def __init__(self, master, **kwargs):
        super().__init__(master, -1)
        self.options = kwargs

    def grid(self, **kwargs):
        self.column = kwargs['column']

    def configure(self, **kwargs):
        self.options.update(kwargs)


def runtime_class():
    """Load the actual production methods while replacing Tk and app dependencies."""
    tree = ast.parse(RUNTIME.read_text(encoding='utf-8'))
    definition = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'WorkflowApp')
    definition.bases = [ast.Name(id='FakeBase', ctx=ast.Load())]
    program = ast.fix_missing_locations(ast.Module(body=[definition], type_ignores=[]))
    theme = SimpleNamespace(SMALL_SIZE=11, BUTTON_BG='#223344', BUTTON_HOVER='#334455', font=lambda size: size)
    scope = {'__name__': 'gui.mock_runtime', '__package__': 'gui', 'FakeBase': FakeBase,
             'ctk': SimpleNamespace(CTkButton=FakeButton), 'theme': theme}
    exec(compile(program, str(RUNTIME), 'exec'), scope)
    return scope['WorkflowApp']


class SingleJobReportTests(TestCase):
    def test_selected_and_active_job_use_same_dialog(self):
        Runtime = runtime_class()
        app = Runtime.__new__(Runtime)
        app.jobs_window = object()
        a, b = object(), object()
        app.current_job = a
        calls = []
        report_dialog = ModuleType('gui.report_selected_dialog_a16')
        report_dialog.open_selected_report_dialog = lambda parent, jobs: calls.append((parent, jobs))
        with patch.dict(sys.modules, {'gui.report_selected_dialog_a16': report_dialog}):
            app._open_active_job_report()
            app._v017_a1_report_selected((a, b))
        self.assertIs(calls[0][0], app)
        self.assertEqual(calls[0][1], (a,))
        self.assertIs(calls[1][0], app.jobs_window)
        self.assertEqual(calls[1][1], (a, b))

    def test_no_active_job_never_opens_report(self):
        Runtime = runtime_class()
        app = Runtime.__new__(Runtime)
        app.current_job = None
        app.jobs_window = None
        with patch.dict(sys.modules, {'gui.report_selected_dialog_a16': ModuleType('gui.report_selected_dialog_a16')}):
            app._open_active_job_report()

    def test_button_is_placed_after_kdrs_without_removing_existing_controls(self):
        Runtime = runtime_class()
        app = Runtime.__new__(Runtime)
        header = FakeHeader()
        app.kdrs_query_button = FakeWidget(header, 6)
        trailing = FakeWidget(header, 7)
        job = object()
        app.current_job = job
        app._install_active_report_button()
        button = app.active_report_button
        self.assertEqual(button.column, 7)
        self.assertEqual(trailing.column, 8)
        self.assertEqual(button.options['text'], 'Rapport')
        self.assertEqual(button.options['state'], 'normal')
        self.assertEqual(len(header.children), 3)
        app._install_active_report_button()
        self.assertEqual(len(header.children), 3)
        self.assertEqual(trailing.column, 8)

    def test_button_follows_active_job_state(self):
        Runtime = runtime_class()
        app = Runtime.__new__(Runtime)
        app.kdrs_query_button = FakeWidget(FakeHeader(), 6)
        app.current_job = None
        app._install_active_report_button()
        self.assertEqual(app.active_report_button.options['state'], 'disabled')
        app.current_job = object()
        app._refresh_active_job_label()
        self.assertEqual(app.active_report_button.options['state'], 'normal')
        app.current_job = None
        app._refresh_active_job_label()
        self.assertEqual(app.active_report_button.options['state'], 'disabled')
        self.assertEqual(app.refresh_calls, 2)

    def test_same_report_options_writer_for_one_and_many(self):
        source = DIALOG.read_text(encoding='utf-8')
        self.assertIn('write_report_package(Path(target), jobs, opts,', source)
        self.assertIn("dialog.title('Rapport for ett uttrekk' if single", source)
        self.assertIn('job_display_name(jobs[0])', source)
        self.assertIn('formats=formats', source)
        self.assertIn("'HTML','PDF','JSON'", source)

    def test_current_entrypoint_installs_button(self):
        source = RUNTIME.read_text(encoding='utf-8')
        self.assertIn('self._install_active_report_button()', source)
        self.assertIn('command=self._open_active_job_report', source)
        self.assertIn('self._v017_a1_report_selected((job,), parent=self)', source)


if __name__ == '__main__':
    import unittest
    unittest.main()
