"""v0.2.2-a1.10: Qt Save As arrow contrast without changing save paths."""
from __future__ import annotations

import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch

from gui_qt.file_dialog_contrast_v022_a1_10 import (
    button_stylesheet, contrast_ratio, install_file_dialog_navigation_contrast,
    navigation_colors,
)


class PaletteTests(unittest.TestCase):
    def test_forest_green_qt_button_has_readable_up_arrow(self):
        # Green/Dark save dialog from the reported Windows screenshot.
        bg = (37, 68, 54)
        colors = navigation_colors(bg)
        self.assertEqual(colors.ink, '#ffffff')
        self.assertGreater(contrast_ratio(bg, (255, 255, 255)), 7.0)
        self.assertIn('border: 2px solid', button_stylesheet(colors))

    def test_light_and_native_palettes_select_dark_ink(self):
        for bg in ((232, 239, 231), (255, 255, 255), (209, 222, 232)):
            with self.subTest(bg=bg):
                colors = navigation_colors(bg)
                self.assertEqual(colors.ink, '#000000')
                self.assertGreaterEqual(contrast_ratio(bg, (0, 0, 0)), 7.0)

    def test_true_black_white_and_boundary_values_have_sufficient_contrast(self):
        for bg in ((0, 0, 0), (255, 255, 255), (128, 128, 128), (70, 130, 90)):
            with self.subTest(bg=bg):
                fg = navigation_colors(bg).ink
                rgb = tuple(int(fg[i:i + 2], 16) for i in (1, 3, 5))
                self.assertGreaterEqual(contrast_ratio(bg, rgb), 4.5)

    def test_styles_only_target_parent_button(self):
        style = button_stylesheet(navigation_colors((37, 68, 54)))
        self.assertIn('QToolButton#toParentButton:focus', style)
        self.assertNotIn('QFileDialog {', style)
        self.assertNotIn('QPushButton {', style)


class FakeButton:
    def __init__(self):
        self.icon = None
        self.icon_size = None
        self.css = ''
        self.tooltip = ''
        self.accessible = ''

    def palette(self):
        return types.SimpleNamespace(color=lambda role: types.SimpleNamespace(
            red=lambda: 37, green=lambda: 68, blue=lambda: 54))

    def setIcon(self, value):
        self.icon = value

    def setIconSize(self, size):
        self.icon_size = size

    def setStyleSheet(self, value):
        self.css = value

    def setToolTip(self, value):
        self.tooltip = value

    def setAccessibleName(self, value):
        self.accessible = value


class FakeFileDialog:
    def __init__(self, button=None):
        self.button = button
        self.requested = []

    def findChild(self, kind, name):
        self.requested.append(name)
        return self.button if name == 'toParentButton' else None


class FakeQPainter:
    class RenderHint:
        Antialiasing = 'antialias'

    def __init__(self, pixmap):
        self.pixmap = pixmap

    def setRenderHint(self, *_args):
        pass

    def setPen(self, *_args):
        pass

    def drawPath(self, *_args):
        pass

    def end(self):
        pass


class FakePainterPath:
    def moveTo(self, *_args):
        pass

    def lineTo(self, *_args):
        pass


class FakeIcon:
    def __init__(self, pixmap):
        self.pixmap = pixmap


class FakePixmap:
    def __init__(self, width, height):
        self.size = (width, height)

    def fill(self, *_args):
        pass


class FakeQObject:
    def __init__(self, parent):
        self.parent = parent


class FakeApp:
    def __init__(self):
        self.filters = []

    def installEventFilter(self, item):
        self.filters.append(item)


class FilterTests(unittest.TestCase):
    def test_installer_updates_only_qt_up_button_and_preserves_events(self):
        scheduled = []
        core = types.ModuleType('PySide6.QtCore')
        core.QObject = FakeQObject
        core.QEvent = types.SimpleNamespace(Type=types.SimpleNamespace(Show='show'))
        core.QSize = lambda w, h: (w, h)
        core.QTimer = types.SimpleNamespace(singleShot=lambda delay, action:
                                            scheduled.append(action))
        core.Qt = types.SimpleNamespace(
            GlobalColor=types.SimpleNamespace(transparent='transparent'),
            PenStyle=types.SimpleNamespace(SolidLine='line'),
            PenCapStyle=types.SimpleNamespace(RoundCap='cap'),
            PenJoinStyle=types.SimpleNamespace(RoundJoin='join'),
        )
        gui = types.ModuleType('PySide6.QtGui')
        gui.QColor = lambda color: color
        gui.QIcon = FakeIcon
        gui.QPainter = FakeQPainter
        gui.QPainterPath = FakePainterPath
        gui.QPalette = types.SimpleNamespace(ColorRole=types.SimpleNamespace(Button='button'))
        gui.QPen = lambda *args: args
        gui.QPixmap = FakePixmap
        widgets = types.ModuleType('PySide6.QtWidgets')
        widgets.QFileDialog = FakeFileDialog
        widgets.QToolButton = FakeButton
        app = FakeApp()
        button = FakeButton()
        dialog = FakeFileDialog(button)
        event = types.SimpleNamespace(type=lambda: 'show')
        with patch.dict(sys.modules, {'PySide6.QtCore': core,
                                      'PySide6.QtGui': gui,
                                      'PySide6.QtWidgets': widgets}):
            filter_obj = install_file_dialog_navigation_contrast(app)
            self.assertEqual(len(app.filters), 1)
            self.assertIs(filter_obj, install_file_dialog_navigation_contrast(app))
            self.assertEqual(len(app.filters), 1, 'Must not install duplicate global filters')
            self.assertFalse(filter_obj.eventFilter(dialog, event))
            self.assertEqual(len(scheduled), 1)
            self.assertIsNone(button.icon, 'Deferred until after dialog is shown')
            scheduled.pop()()
            self.assertEqual(dialog.requested, ['toParentButton'])
            self.assertIsInstance(button.icon, FakeIcon)
            self.assertEqual(button.icon.pixmap.size, (64, 64))
            self.assertEqual(button.icon_size, (22, 22))
            self.assertIn('#ffffff', button.css)
            self.assertIn('Opp ett mappenivå', button.tooltip)
            self.assertFalse(filter_obj.eventFilter(dialog,
                types.SimpleNamespace(type=lambda: 'other')))
            self.assertEqual(len(scheduled), 0)
            self.assertFalse(filter_obj.fix_dialog(FakeFileDialog()),
                             'Native dialogs must be left untouched')

    def test_entrypoint_installs_filter_after_appearance(self):
        entry = (Path(__file__).resolve().parents[1] / 'gui_qt' / '__main__.py')
        source = entry.read_text(encoding='utf-8')
        self.assertIn('install_file_dialog_navigation_contrast(application)', source)
        self.assertLess(source.index('apply_appearance(application, api.settings)'),
                        source.index('install_file_dialog_navigation_contrast(application)'))


if __name__ == '__main__':
    unittest.main()
