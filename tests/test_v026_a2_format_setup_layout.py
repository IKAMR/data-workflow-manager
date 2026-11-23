"""Qt-free regression for the v0.2.6-a2 Setup format assessment layout."""
from __future__ import annotations

import ast
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'gui_qt' / 'format_assessment_layout_v026_a2.py'
ENTRY = ROOT / 'gui_qt' / '__main__.py'


class Signal:
    def __init__(self):
        self.callbacks = []

    def connect(self, cb):
        self.callbacks.append(cb)

    def emit(self, *args):
        for cb in self.callbacks:
            cb(*args)


class Widget:
    def __init__(self, text='', parent=None):
        if isinstance(text, Widget):
            parent = text
            text = ''
        self.text_value = text
        self.parent = parent
        self.layout = None
        self.minimum_width = None

    def setMinimumWidth(self, width):
        self.minimum_width = width


class Group(Widget):
    pass


class Label(Widget):
    def setTextFormat(self, fmt):
        self.text_format = fmt

    def setWordWrap(self, enabled):
        self.word_wrap = enabled

    def setTextInteractionFlags(self, flags):
        self.interaction_flags = flags

    def setSizePolicy(self, *policy):
        self.size_policy = policy

    def setText(self, value):
        self.text_value = value


class Layout:
    def __init__(self, owner):
        self.owner = owner
        self.entries = []
        owner.layout = self

    def setContentsMargins(self, *margins):
        self.margins = margins

    def setSpacing(self, value):
        self.spacing = value

    def addWidget(self, item):
        self.entries.append(item)

    def addStretch(self, count):
        self.entries.append(('stretch', count))


class Combo(Widget):
    def __init__(self, parent):
        super().__init__(parent)
        self.options = []
        self.index = 0
        self.currentIndexChanged = Signal()

    def addItem(self, caption, key):
        self.options.append((caption, key))

    def findData(self, data):
        return next((i for i, (_, key) in enumerate(self.options) if key == data), -1)

    def setCurrentIndex(self, i):
        self.index = i
        self.currentIndexChanged.emit(i)

    def currentData(self):
        return self.options[self.index][1]


class Form:
    def __init__(self):
        self.rows = []

    def addRow(self, *row):
        self.rows.append(row)


class StubDialog:
    def __init__(self, settings):
        self.settings = settings
        self.forms = {}

    def _tab(self, name):
        form = Form()
        self.forms[name] = form
        return Widget(), form

    def _update_format_description(self, index=None):
        data = self.format_source.currentData()
        self.format_explanation.setText(next(
            (d for key, _, d in SOURCES if key == data), ''
        ))


SOURCES = (
    ('nasjonalarkivet_2026_11_10', 'Nasjonalarkivet - datert formatliste (2026-11-10)',
     'Vurder identifiserte PUID-er mot den daterte JSON-kopien.'),
    ('arkade_raf220301', 'Arkade 5 - RAF-220301 (historisk)',
     'Vis den historiske klassifiseringen fra Arkade 5.'),
)


def funcs():
    nodes = ast.parse(SOURCE.read_text(encoding='utf-8')).body
    selected = [n for n in nodes if isinstance(n, ast.FunctionDef)
                and n.name in {'_build_format_assessment_tab',
                               'install_format_assessment_layout'}]
    ns = {}
    exec(compile(ast.fix_missing_locations(ast.Module(body=selected, type_ignores=[])),
                 str(SOURCE), 'exec'), ns)
    return ns


def fakes():
    qt = types.ModuleType('PySide6.QtCore')
    qt.Qt = types.SimpleNamespace(
        TextFormat=types.SimpleNamespace(PlainText=1),
        TextInteractionFlag=types.SimpleNamespace(TextSelectableByMouse=2),
    )
    widgets = types.ModuleType('PySide6.QtWidgets')
    widgets.QComboBox = Combo
    widgets.QGroupBox = Group
    widgets.QLabel = Label
    widgets.QSizePolicy = types.SimpleNamespace(
        Policy=types.SimpleNamespace(Expanding=1, Preferred=2)
    )
    widgets.QVBoxLayout = Layout
    widgets.QWidget = Widget
    formats = types.ModuleType('app.format_assessment_v0111_a2')
    formats.FORMAT_SOURCES = SOURCES
    formats.DEFAULT_FORMAT_SOURCE = SOURCES[0][0]
    def chosen_source(settings):
        value = settings.get('format_assessment_source', SOURCES[0][0])
        if value not in {item[0] for item in SOURCES}:
            raise ValueError('unknown')
        return value

    formats.chosen_format_source = chosen_source
    return {
        'PySide6': types.ModuleType('PySide6'),
        'PySide6.QtCore': qt,
        'PySide6.QtWidgets': widgets,
        'app.format_assessment_v0111_a2': formats,
    }


class FormatSetupLayoutTests(unittest.TestCase):
    def test_one_spanning_row_avoids_narrow_multiline_form_labels(self):
        view = StubDialog({'format_assessment_source': SOURCES[1][0]})
        with patch.dict(sys.modules, fakes()):
            funcs()['_build_format_assessment_tab'](view)
        rows = view.forms['Filformatvurdering'].rows
        self.assertEqual(len(rows), 1)
        self.assertEqual(len(rows[0]), 1)
        host = rows[0][0]
        self.assertEqual(host.minimum_width, 0)
        groups = [w for w in host.layout.entries if isinstance(w, Group)]
        self.assertEqual([g.text_value for g in groups], [
            'Grunnlag for vurdering', 'Vurdering og evidens', 'Siegfried / PRONOM'
        ])

    def test_wrapped_labels_and_source_selection_are_preserved(self):
        view = StubDialog({'format_assessment_source': SOURCES[1][0]})
        with patch.dict(sys.modules, fakes()):
            funcs()['_build_format_assessment_tab'](view)
        self.assertEqual(view.format_source.currentData(), SOURCES[1][0])
        self.assertIn('historiske', view.format_explanation.text_value)
        root = view.forms['Filformatvurdering'].rows[0][0]
        labels = [w for g in root.layout.entries if isinstance(g, Group)
                  for w in g.layout.entries if isinstance(w, Label)]
        self.assertTrue(all(l.word_wrap and l.minimum_width == 0 for l in labels))
        self.assertTrue(all(l.interaction_flags == 2 for l in labels))
        view.format_source.setCurrentIndex(0)
        self.assertEqual(view.format_source.currentData(), SOURCES[0][0])
        self.assertIn('PUID-er', view.format_explanation.text_value)

    def test_invalid_saved_authority_falls_back_without_modifying_settings(self):
        settings = {'format_assessment_source': 'unknown'}
        view = StubDialog(settings)
        with patch.dict(sys.modules, fakes()):
            funcs()['_build_format_assessment_tab'](view)
        self.assertEqual(view.format_source.currentData(), SOURCES[0][0])
        self.assertEqual(settings['format_assessment_source'], 'unknown')

    def test_hook_is_idempotent_and_preserves_existing_dialog(self):
        pkg = types.ModuleType('gui_qt')
        pkg.__path__ = []
        module = types.ModuleType('gui_qt.setup_format_v0111_a2')
        class BaseDialog:
            untouched = 123
        module.DwmSetupDialog = BaseDialog
        pkg.setup_format_v0111_a2 = module
        with patch.dict(sys.modules, {
            'gui_qt': pkg, 'gui_qt.setup_format_v0111_a2': module,
        }):
            namespace = funcs()
            install = namespace['install_format_assessment_layout']
            install()
            first = module.DwmSetupDialog
            install()
            self.assertIs(first, module.DwmSetupDialog)
            self.assertTrue(issubclass(first, BaseDialog))
            self.assertEqual(first.untouched, 123)
            self.assertIs(first._build_format_assessment_tab,
                          namespace['_build_format_assessment_tab'])

    def test_main_installs_layout_after_setup_without_loading_qt_in_fake_startup(self):
        source = ENTRY.read_text(encoding='utf-8')
        self.assertLess(source.index('    install_setup_tab()'),
                        source.index('    install_format_assessment_layout()'))
        self.assertIn('DwmMainWindow = _V025A3Window', source)
        self.assertIn('raise SystemExit(main())', source)

    def test_headless_startup_does_not_import_real_setup_or_pyside_qtcore(self):
        # Mocked Qt startup installs only a fake Setup hook.  A missing Setup
        # module must be left untouched; no real Qt imports are attempted.
        install = funcs()['install_format_assessment_layout']
        name = 'gui_qt.setup_format_v0111_a2'
        with patch.dict(sys.modules, {name: None}):
            install()
            self.assertIsNone(sys.modules[name])



if __name__ == '__main__':
    unittest.main()
