"""Headless regression: full-width tool setup without Qt installation.

The real Windows/PySide6 GUI must still be inspected before commit. These
stand-ins execute the actual GUI methods, not merely inspect their source.
"""
from __future__ import annotations

import ast
from pathlib import Path
from queue import Queue
import unittest

from app.siegfried_tool_v0111_a3 import SiegfriedCheck

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'gui_qt' / 'setup_format_v0111_a2.py'


class Signal:
    def __init__(self):
        self.slots = []

    def connect(self, slot):
        self.slots.append(slot)

    def emit(self, *args):
        for slot in self.slots:
            slot(*args)


class Widget:
    def __init__(self, *args):
        self.text_value = args[0] if args and isinstance(args[0], str) else ''
        self.parent = args[-1] if args and isinstance(args[-1], Widget) else None
        self._layout = None

    def setObjectName(self, name):
        self.object_name = name


class Label(Widget):
    def setWordWrap(self, v):
        self.wrapped = v

    def setTextInteractionFlags(self, flag):
        self.selectable = flag

    def setText(self, value):
        self.text_value = value

    def text(self):
        return self.text_value


class LineEdit(Widget):
    def __init__(self, text=''):
        super().__init__(text)
        self.textChanged = Signal()

    def text(self):
        return self.text_value

    def setText(self, text):
        self.text_value = text
        self.textChanged.emit(text)

    def setPlaceholderText(self, text):
        self.placeholder = text

    def setToolTip(self, text):
        self.tooltip = text


class Button(Widget):
    def __init__(self, name):
        super().__init__(name)
        self.clicked = Signal()

    def setEnabled(self, enabled):
        self.enabled = enabled


class Layout:
    def __init__(self, owner=None):
        self.owner = owner
        self.entries = []
        if isinstance(owner, Widget):
            owner._layout = self

    def setContentsMargins(self, *v):
        self.margins = v

    def setSpacing(self, v):
        self.spacing = v

    def addWidget(self, item, *args):
        self.entries.append(item)

    def addLayout(self, layout):
        self.entries.append(layout)

    def addStretch(self, *args):
        self.entries.append('stretch')


class Form:
    def __init__(self):
        self.rows = []

    def addRow(self, *args):
        self.rows.append(args)


class Timer:
    def __init__(self, *args):
        self.timeout = Signal()
        self.running = False

    def setInterval(self, _ms):
        pass

    def start(self):
        self.running = True

    def stop(self):
        self.running = False


class QtStub:
    class TextInteractionFlag:
        TextSelectableByMouse = 1


def load_methods():
    tree = ast.parse(SOURCE.read_text(encoding='utf-8'))
    cls = next(x for x in tree.body if isinstance(x, ast.ClassDef) and x.name == 'DwmSetupDialog')
    free = [x for x in tree.body if isinstance(x, ast.FunctionDef)
            and x.name in {'_full_width_note', '_tool_section', '_toolbar'}]
    methods = [x for x in cls.body if isinstance(x, ast.FunctionDef)
               and x.name in {'_build_external_tab', '_build_siegfried_tools',
                              '_clear_siegfried_status', '_find_siegfried',
                              '_read_siegfried_check'}]
    ns = {
        'QLabel': Label, 'QWidget': Widget, 'QGroupBox': Widget,
        'QLineEdit': LineEdit, 'QPushButton': Button, 'QHBoxLayout': Layout,
        'QVBoxLayout': Layout, 'QTimer': Timer, 'Qt': QtStub,
        'Queue': Queue, 'SiegfriedCheck': SiegfriedCheck,
        'find_siegfried_executable': lambda: Path('/shared/siegfried/sf.exe'),
    }
    mod = ast.fix_missing_locations(ast.Module(body=free + methods, type_ignores=[]))
    exec(compile(mod, str(SOURCE), 'exec'), ns)
    return ns


NS = load_methods()


class SetupStub:
    _build_external_tab = NS['_build_external_tab']
    _build_siegfried_tools = NS['_build_siegfried_tools']
    _clear_siegfried_status = NS['_clear_siegfried_status']
    _find_siegfried = NS['_find_siegfried']
    _read_siegfried_check = NS['_read_siegfried_check']

    def __init__(self):
        self.settings = {'arkade5_cli_path': 'C:/tools/Arkade.exe',
                         'arkade5_output_subfolder': 'arkade5_<ver>',
                         'sf_executable': ''}
        self.forms = {}
        self._build_external_tab()
        self._build_siegfried_tools()

    def _tab(self, name):
        form = Form()
        self.forms[name] = form
        return Widget(), form

    def _clear_test_status(self, _text=''):
        self.cli_status.setText('Ikke testet i denne dialogen')

    def _browse_cli(self):
        pass

    def _find_cli(self):
        pass

    def _test_cli(self):
        pass

    def _browse_siegfried(self):
        pass

    def _test_siegfried(self):
        pass


class LayoutTests(unittest.TestCase):
    def setUp(self):
        self.ui = SetupStub()

    def test_one_spanning_row_no_narrow_form_labels(self):
        rows = self.ui.forms['Eksterne verktøy'].rows
        self.assertEqual(len(rows), 1)
        self.assertEqual(len(rows[0]), 1)  # QWidget spans all form columns
        self.assertIsInstance(rows[0][0], Widget)

    def test_independent_arkade_and_siegfried_sections(self):
        stack = self.ui._external_sections
        groups = [node for node in stack.entries if isinstance(node, Widget)
                  and getattr(node, 'object_name', None) == 'dwm-external-tool-section']
        self.assertEqual(len(groups), 2)
        self.assertEqual([g.text_value.split(' – ')[0] for g in groups], ['Arkade 5', 'Siegfried'])
        self.assertEqual(len(self.ui.cli_path.text()), len('C:/tools/Arkade.exe'))
        self.assertEqual(self.ui.arkade_output.text(), 'arkade5_<ver>')

    def test_path_fields_and_actions_are_separate_rows(self):
        for widget in (self.ui.cli_path, self.ui.sf_path):
            section = next(w for w in self.ui._external_sections.entries
                           if isinstance(w, Widget) and w._layout is not None
                           and widget in w._layout.entries)
            children = section._layout.entries
            position = children.index(widget)
            self.assertIsInstance(children[position+1], Layout)
            toolbar = children[position+1]
            self.assertEqual(len([b for b in toolbar.entries if isinstance(b, Button)]), 3)

    def test_all_status_and_help_labels_can_wrap(self):
        groups = [e for e in self.ui._external_sections.entries if isinstance(e, Widget)
                  and getattr(e, 'object_name', '') == 'dwm-external-tool-section']
        for group in groups:
            for child in group._layout.entries:
                if isinstance(child, Label):
                    self.assertTrue(child.wrapped)
                    self.assertTrue(child.selectable)
        self.assertIn('Delt installasjon:', self.ui.sf_discovery_status.text())

    def test_new_siegfried_path_invalidates_old_signature_display(self):
        self.ui.sf_signature_status.setText('PRONOM-signatur: OLD')
        self.ui.sf_path.setText('C:/other/sf.exe')
        self.assertEqual(self.ui.sf_signature_status.text(), 'PRONOM-signatur: ikke kontrollert')

    def test_siegfried_result_is_separated_into_version_path_signature(self):
        self.ui._sf_results.put(('', SiegfriedCheck(
            True, '/shared/siegfried/sf.exe', version='siegfried 1.11.9',
            signature='PRONOM DROID V125')))
        self.ui._sf_testing = True
        self.ui._read_siegfried_check()
        self.assertEqual(self.ui.sf_test_button.enabled, True)
        self.assertIn('siegfried 1.11.9', self.ui.sf_test_status.text())
        self.assertIn('/shared/siegfried/sf.exe', self.ui.sf_test_status.text())
        self.assertIn('PRONOM DROID V125', self.ui.sf_signature_status.text())

    def test_stale_result_does_not_overwrite_changed_executable(self):
        self.ui.sf_path.setText('C:/other/sf.exe')
        self.ui._sf_results.put(('', SiegfriedCheck(True, '/shared/sf.exe', version='old')))
        self.ui._sf_testing = True
        self.ui._read_siegfried_check()
        self.assertIn('endret', self.ui.sf_test_status.text())

    def test_code_does_not_install_or_copy_binary(self):
        source = SOURCE.read_text(encoding='utf-8')
        self.assertNotIn('install_siegfried(', source)
        self.assertNotIn('shutil.copy', source)
        self.assertIn("updates['sf_executable']", source)
        self.assertIn("updates['format_assessment_source']", source)


if __name__ == '__main__':
    unittest.main()
