"""a3-fix2: headless contracts for full-card theme selection and staged Save."""
from __future__ import annotations

import ast
from pathlib import Path
from types import SimpleNamespace
import unittest

from gui_qt.appearance_v0110_a3 import THEME_CHOICES, theme_mode, accent_mode

ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / 'gui_qt' / 'setup_v0110_a3.py').read_text(encoding='utf-8')
MODULE = ast.parse(SOURCE)
CARD = next(node for node in MODULE.body
            if isinstance(node, ast.ClassDef) and node.name == '_AppearanceCard')
DIALOG = next(node for node in MODULE.body
              if isinstance(node, ast.ClassDef) and node.name == 'DwmSetupDialog')
REFRESH = next(node for node in DIALOG.body
               if isinstance(node, ast.FunctionDef) and node.name == '_refresh_appearance_explanation')


class Frame:
    class Shape:
        StyledPanel = 'frame'

    def __init__(self):
        self.radio = None
        self.style_string = ''
        self.props = {}
        self.updated = False

    def setObjectName(self, name):
        self.name = name

    def setFrameShape(self, _value):
        pass

    def setCursor(self, _cursor):
        pass

    def setAccessibleDescription(self, text):
        self.description = text

    def setProperty(self, key, value):
        self.props[key] = value

    def setStyleSheet(self, value):
        self.style_string = value

    def update(self):
        self.updated = True

    def mousePressEvent(self, event):
        event.fell_through = True


class Radio:
    def __init__(self, checked=False):
        self.checked = checked

    def setChecked(self, selected):
        self.checked = bool(selected)

    def isChecked(self):
        return self.checked


class Event:
    def __init__(self, button):
        self.button_value = button
        self.accepted = False
        self.fell_through = False

    def button(self):
        return self.button_value

    def accept(self):
        self.accepted = True


qt = SimpleNamespace(
    MouseButton=SimpleNamespace(LeftButton='left'),
    CursorShape=SimpleNamespace(PointingHandCursor='pointer'),
)
card_ns = {'QFrame': Frame, 'Qt': qt}
exec(compile(ast.fix_missing_locations(ast.Module(body=[CARD], type_ignores=[])),
             '<setup_theme_card>', 'exec'), card_ns)
AppearanceCard = card_ns['_AppearanceCard']


class Label:
    def __init__(self):
        self.value = ''

    def setText(self, text):
        self.value = text


class Combo:
    def __init__(self, value):
        self.value = value

    def setEnabled(self, flag):
        self.enabled = flag

    def currentData(self):
        return self.value


refresh_ns = {
    'THEME_CHOICES': THEME_CHOICES,
    'theme_mode': theme_mode,
    'accent_mode': accent_mode,
    'QPalette': SimpleNamespace(ColorRole=SimpleNamespace(Window='window')),
}
exec(compile(ast.fix_missing_locations(ast.Module(body=[REFRESH], type_ignores=[])),
             '<setup_theme_selection>', 'exec'), refresh_ns)


class ThemeDialogStub:
    _refresh_appearance_explanation = refresh_ns['_refresh_appearance_explanation']

    def __init__(self, selected='dark', saved='dark', accent='purple', saved_accent='purple', light=False):
        self.settings = {'appearance_mode': saved, 'qt_accent_color': saved_accent}
        self.appearance_buttons = {key: Radio(key == selected) for key in THEME_CHOICES}
        self.appearance_cards = {key: AppearanceCard() for key in THEME_CHOICES}
        self.accent_combo = Combo(accent)
        self.accent_note = Label()
        self.appearance_state = Label()
        self.light = light

    def palette(self):
        brightness = 245 if self.light else 15
        return SimpleNamespace(color=lambda _role: SimpleNamespace(lightness=lambda: brightness))

    def _chosen_theme(self):
        return next(k for k,v in self.appearance_buttons.items() if v.isChecked())


class AppearanceCardInteractionTests(unittest.TestCase):
    def test_full_card_left_click_selects_radio(self):
        card = AppearanceCard()
        card.radio = Radio()
        event = Event('left')
        card.mousePressEvent(event)
        self.assertTrue(card.radio.checked)
        self.assertTrue(event.accepted)
        self.assertFalse(event.fell_through)

    def test_other_mouse_button_is_not_selection(self):
        card = AppearanceCard()
        card.radio = Radio()
        event = Event('right')
        card.mousePressEvent(event)
        self.assertFalse(card.radio.checked)
        self.assertTrue(event.fell_through)

    def test_selected_card_has_visible_border_and_pending_message(self):
        dialog = ThemeDialogStub(selected='light', saved='dark')
        dialog._refresh_appearance_explanation()
        self.assertEqual([key for key, card in dialog.appearance_cards.items()
                          if card.props.get('chosen')], ['light'])
        self.assertIn('border: 2px solid #7b5ab3', dialog.appearance_cards['light'].style_string)
        self.assertIn('border: 1px solid', dialog.appearance_cards['dark'].style_string)
        self.assertIn('ikke lagret', dialog.appearance_state.value)
        self.assertIn('Lagre', dialog.appearance_state.value)

    def test_native_windows_choice_still_has_obvious_outline(self):
        dialog = ThemeDialogStub(selected='system', saved='dark', light=True)
        dialog._refresh_appearance_explanation()
        self.assertIn('border: 2px solid #317bc0', dialog.appearance_cards['system'].style_string)
        self.assertFalse(dialog.accent_combo.enabled)
        self.assertIn('ikke lagret', dialog.appearance_state.value)

    def test_existing_theme_is_identified_as_current(self):
        dialog = ThemeDialogStub(selected='dark', saved='dark')
        dialog._refresh_appearance_explanation()
        self.assertIn('Gjeldende tema', dialog.appearance_state.value)
        self.assertNotIn('ikke lagret', dialog.appearance_state.value)

    def test_unsaved_accent_change_is_identified_too(self):
        dialog = ThemeDialogStub(selected='dark', saved='dark', accent='green', saved_accent='purple')
        dialog._refresh_appearance_explanation()
        self.assertIn('ikke lagret', dialog.appearance_state.value)
        self.assertIn('border: 2px solid #328766', dialog.appearance_cards['dark'].style_string)

    def test_selection_does_not_save_configuration(self):
        self.assertNotIn('save_config(', SOURCE)
        self.assertIn("result['appearance_mode'] = self._chosen_theme()", SOURCE)
        self.assertIn('self.appearance_buttons[theme_mode(self.settings)].setChecked(True)', SOURCE)
        self.assertIn('WA_TransparentForMouseEvents', SOURCE)
        self.assertIn('self.appearance_cards[key] = card', SOURCE)
        self.assertIn('self.appearance_state.setText(', SOURCE)


if __name__ == '__main__':
    unittest.main()
