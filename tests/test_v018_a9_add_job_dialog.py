"""Headless regression tests for readable paths in the a9 New Noark 5 Job dialog.

Run without PySide6; execute the actual _new_job method with lightweight fake widgets.
"""
from __future__ import annotations

import ast
import unittest
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / "gui_qt" / "main_window.py").read_text(encoding="utf-8")
TREE = ast.parse(SOURCE)
WINDOW = next(n for n in TREE.body if isinstance(n, ast.ClassDef) and n.name == "DwmMainWindow")
NEW_JOB = next(n for n in WINDOW.body if isinstance(n, ast.FunctionDef) and n.name == "_new_job")


class Signal:
    def __init__(self):
        self.callbacks = []

    def connect(self, fn):
        self.callbacks.append(fn)


class Dialog:
    DialogCode = SimpleNamespace(Accepted=1)
    current = None
    result = 1

    def __init__(self, parent):
        Dialog.current = self
        self.parent = parent
        self.width = self.height = self.minimum_width = 0
        self.has_grip = False

    def setWindowTitle(self, title):
        self.title = title

    def resize(self, width, height):
        self.width, self.height = width, height

    def setMinimumWidth(self, width):
        self.minimum_width = width

    def setSizeGripEnabled(self, enabled):
        self.has_grip = enabled

    def accept(self):
        pass

    def reject(self):
        pass

    def exec(self):
        return Dialog.result


class Form:
    RowWrapPolicy = SimpleNamespace(WrapAllRows="wrap-all-rows")
    FieldGrowthPolicy = SimpleNamespace(AllNonFixedFieldsGrow="expand")

    def __init__(self, dialog):
        self.dialog = dialog
        dialog.form = self
        self.rows = []

    def setRowWrapPolicy(self, policy):
        self.wrap_policy = policy

    def setFieldGrowthPolicy(self, policy):
        self.growth_policy = policy

    def setContentsMargins(self, *args):
        self.margins = args

    def setVerticalSpacing(self, spacing):
        self.spacing = spacing

    def addRow(self, *args):
        self.rows.append(args)


class LineEdit:
    initial_texts = []
    created = []

    def __init__(self):
        self.value = LineEdit.initial_texts.pop(0)
        self.textChanged = Signal()
        self.tooltip = None
        LineEdit.created.append(self)

    def text(self):
        return self.value

    def setToolTip(self, tip):
        self.tooltip = tip


class ButtonBox:
    StandardButton = SimpleNamespace(Ok=1, Cancel=2)

    def __init__(self, flags):
        self.accepted = Signal()
        self.rejected = Signal()


class FakeAPI:
    def __init__(self):
        self.calls = []

    def create_job(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(job_id="JOB-001")


class FakeMain:
    def __init__(self, screen_width):
        self._complexity = "Standard"
        self.width = screen_width
        self.api = FakeAPI()
        self._active_id = None
        self.refreshed = False

    def screen(self):
        return SimpleNamespace(availableGeometry=lambda: SimpleNamespace(width=lambda: self.width))

    def _path_form_row(self, form, label, editor):
        form.addRow(label, editor)

    def _refresh(self, **kwargs):
        self.refreshed = True

    def _error(self, exc):
        raise AssertionError(f"Unexpected error: {exc}")


namespace = {
    "QDialog": Dialog,
    "QFormLayout": Form,
    "QLineEdit": LineEdit,
    "QDialogButtonBox": ButtonBox,
    "_muted": lambda text: text,
}
exec(compile(ast.fix_missing_locations(ast.Module(body=[NEW_JOB], type_ignores=[])), "_new_job", "exec"), namespace)
FakeMain._new_job = namespace["_new_job"]


class NewJobDialogLayoutTests(unittest.TestCase):
    def setUp(self):
        Dialog.result = 1
        LineEdit.created = []
        LineEdit.initial_texts = [
            "1599_001 Documaster Test",
            r"C:\arkiv-test\sip_noark5_documaster\2016-09-27\content\uttrekk",
            r"C:\arkiv-test\sip_noark5_documaster\dwm-work-02\Test-01\1599_001_Documaster\repository_operations\dwm",
        ]

    def test_wide_path_fields_and_user_resizable_dialog(self):
        main = FakeMain(1366)
        main._new_job()
        dialog = Dialog.current
        self.assertEqual(dialog.width, 1100)
        self.assertTrue(dialog.has_grip)
        self.assertEqual(dialog.form.wrap_policy, Form.RowWrapPolicy.WrapAllRows)
        self.assertEqual(dialog.form.growth_policy, Form.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        self.assertEqual([r[0] for r in dialog.form.rows[:3]],
                         ["Jobbnavn (valgfritt)", "Source – uttrekk", "Work – operations"])
        self.assertTrue(all(editor.textChanged.callbacks for editor in LineEdit.created[1:]))

    def test_dialog_fits_laptop_and_keeps_full_paths(self):
        main = FakeMain(800)
        expected = list(LineEdit.initial_texts)
        main._new_job()
        dialog = Dialog.current
        self.assertEqual(dialog.width, 700)
        self.assertEqual(dialog.minimum_width, 700)
        self.assertEqual(main.api.calls, [{"source_extraction": expected[1],
                                           "work_operations": expected[2],
                                           "name": expected[0]}])
        self.assertEqual(main._active_id, "JOB-001")
        self.assertTrue(main.refreshed)
        # Tooltips update to the exact contents, without truncating the value.
        for editor in LineEdit.created[1:]:
            editor.textChanged.callbacks[0](editor.value)
            self.assertEqual(editor.tooltip, editor.value)

    def test_cancel_does_not_create_job(self):
        Dialog.result = 0
        main = FakeMain(1400)
        main._new_job()
        self.assertEqual(main.api.calls, [])
        self.assertIsNone(main._active_id)

    def test_existing_qt_docking_and_separate_log_window_preserved(self):
        self.assertIn("saveState(4)", SOURCE)
        self.assertIn("from .detached_log_window_v018_a9 import (", SOURCE)
        self.assertIn("DetachedJobLogWindow, DetachedRunWindow, DetachableDockTitleBar", SOURCE)
        self.assertIn("def _a8_float_job_log", SOURCE)
        self.assertIn("def _a8_dock_floating", SOURCE)


if __name__ == "__main__":
    unittest.main()
