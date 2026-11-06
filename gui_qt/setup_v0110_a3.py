"""v0.1.10-a3: explicit, saved Windows/dark/light and window placement setup.

A3 adds a fifth Setup tab without replacing a2's storage-profile and general
pages. Appearance changes are staged until the existing Save button is used.
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QPalette, QColor
from PySide6.QtWidgets import (
    QButtonGroup, QComboBox, QColorDialog, QDialog, QDialogButtonBox,
    QFrame, QGridLayout, QHBoxLayout, QLabel, QMessageBox, QPushButton,
    QRadioButton, QVBoxLayout, QWidget,
)

from gui_qt.appearance_v0110_a3 import (
    THEME_CHOICES, ACCENT_CHOICES, theme_mode, accent_mode,
)
from app.palette_presets_v0110_a3 import (
    PALETTE_CHOICES, CUSTOM_KEYS, palette_mode, palette_colors,
    custom_defaults, normalize_custom_colors, contrast, selected_text,
)
from gui_qt.window_placement_v0110_a3 import (
    PLACEMENT_CHOICES,
)
from gui_qt.setup_v0110_a2 import (
    DwmSetupDialog as _A2SetupDialog, _information, _wrap,
)


class _AppearanceCard(QFrame):
    """Select its radio when any part of the large theme preview is clicked."""

    def __init__(self):
        super().__init__()
        self.radio = None
        self.setObjectName('dwmAppearanceCard')
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setAccessibleDescription(
            'Klikk hvor som helst i dette kortet for å velge tema. '
            'Valget brukes når Setup lagres.'
        )

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.radio is not None:
            self.radio.setChecked(True)
            event.accept()
            return
        super().mousePressEvent(event)

    def set_chosen(self, chosen: bool, *, highlight: str, light: bool,
                   surface: str | None = None, selected_surface: str | None = None,
                   edge: str | None = None):
        """Make the pending selection visible, including in native Windows mode."""
        self.setProperty('chosen', bool(chosen))
        background = ('#e3eefb' if chosen else '#f6f8fc') if light else (
            '#25374f' if chosen else '#151c28'
        )
        if surface is not None:
            background = (selected_surface or surface) if chosen else surface
        outline = (f'2px solid {highlight}' if chosen else
                   f'1px solid {edge}' if edge else
                   ('1px solid #a6b5c9' if light else '1px solid #33485f'))
        self.setStyleSheet(
            'QFrame#dwmAppearanceCard {'
            f'background-color: {background}; border: {outline}; border-radius: 7px;'
            '} '
            'QFrame#dwmAppearanceCard QLabel, '
            'QFrame#dwmAppearanceCard QRadioButton { background-color: transparent; }'
        )
        self.update()


class _CustomPaletteDialog(QDialog):
    """Edit five validated colours with a live *local* preview; nothing is saved."""

    def __init__(self, initial: dict[str, str], mode: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle('Egendefinerte farger – Data Workflow Manager')
        self.setMinimumSize(640, 460)
        self.resize(690, 535)
        self.colors = dict(initial)
        self.mode = mode if mode in ('light', 'dark') else 'light'
        root = QVBoxLayout(self)
        root.addWidget(_wrap(
            'Velg fargene for hele DWM. Forhåndsvisningen under oppdateres ' 
            'mens du redigerer. Ingenting endres før du lagrer Setup.'
        ))
        grid = QGridLayout()
        self.color_buttons = {}
        for row, (key, title) in enumerate(CUSTOM_KEYS.items()):
            grid.addWidget(QLabel(title + ':'), row, 0)
            choose = QPushButton()
            choose.setMinimumHeight(33)
            choose.setAccessibleName('Velg farge: ' + title)
            choose.clicked.connect(lambda _checked=False, role=key: self._choose_color(role))
            self.color_buttons[key] = choose
            grid.addWidget(choose, row, 1)
        root.addLayout(grid)
        root.addWidget(_wrap('Forhåndsvisning', strong=True))
        self.sample = QFrame()
        self.sample.setMinimumHeight(115)
        sample_layout = QVBoxLayout(self.sample)
        self.sample_title = QLabel('DWM – eksempel på panel, tekst og bakgrunn')
        sample_layout.addWidget(self.sample_title)
        self.sample_selection = QLabel('Valgt jobb / aktiv fane')
        self.sample_selection.setMinimumHeight(33)
        sample_layout.addWidget(self.sample_selection)
        self.sample_button = QLabel('  Kjør valgt jobb  ')
        sample_layout.addWidget(self.sample_button)
        root.addWidget(self.sample)
        self.contrast_note = _wrap('')
        root.addWidget(self.contrast_note)
        actions = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        actions.button(QDialogButtonBox.StandardButton.Ok).setText('Bruk fargene')
        actions.accepted.connect(self._validate_and_accept)
        actions.rejected.connect(self.reject)
        root.addWidget(actions)
        self._refresh_preview()

    def _choose_color(self, role: str):
        chosen = QColorDialog.getColor(
            QColor(self.colors[role]), self, 'Velg ' + CUSTOM_KEYS[role].lower()
        )
        if chosen.isValid():
            self.colors[role] = chosen.name().lower()
            self._refresh_preview()

    def _refresh_preview(self):
        for role, button in self.color_buttons.items():
            hex_color = self.colors[role]
            button.setText(hex_color.upper())
            fg = selected_text(hex_color)
            button.setStyleSheet(
                f'QPushButton {{ background-color: {hex_color}; color: {fg}; '
                'padding: 5px; border: 1px solid #777; border-radius: 4px; }'
            )
        c = self.colors
        self.sample.setStyleSheet(
            f'QFrame {{background-color: {c["window"]}; border: 1px solid {c["accent"]}; border-radius: 6px; }}'
        )
        self.sample_title.setStyleSheet(
            f'QLabel {{background-color: {c["surface"]}; color: {c["text"]}; padding: 7px; }}'
        )
        self.sample_selection.setStyleSheet(
            f'QLabel {{background-color: {c["accent"]}; '
            f'color: {selected_text(c["accent"])}; padding: 7px; }}'
        )
        self.sample_button.setStyleSheet(
            f'QLabel {{background-color: {c["button"]}; color: {c["text"]}; '
            'padding: 7px; border: 1px solid #888; }}'
        )
        try:
            normalize_custom_colors(self.colors, mode=self.mode)
        except ValueError as error:
            self.contrast_note.setText('Kontrast må forbedres: ' + str(error))
        else:
            self.contrast_note.setText('Tekstkontrasten er godkjent (minimum 4,5:1).')

    def _validate_and_accept(self):
        try:
            self.colors = normalize_custom_colors(self.colors, mode=self.mode)
        except ValueError as error:
            QMessageBox.warning(self, 'For liten tekstkontrast', str(error))
            return
        self.accept()


class DwmSetupDialog(_A2SetupDialog):
    """Appearance, accents, and screen-safe popup placement for the Qt GUI."""

    def __init__(self, api, parent=None):
        super().__init__(api, parent)
        self._build_appearance_tab()

    def _build_appearance_tab(self):
        _content, form = self._tab('Utseende og vinduer')
        body = QWidget()
        layout = QVBoxLayout(body)
        layout.setContentsMargins(10, 9, 10, 14)
        layout.setSpacing(14)
        layout.addWidget(_wrap('Farger i Data Workflow Manager', strong=True))
        layout.addWidget(_information(
            'Velg hvordan vinduene skal se ut',
            'Windows / systemfarger følger operativsystemets vanlige farger. '
            'Mørk bruker dagens DWM-farger, mens Lys gir en lys arbeidsflate. '
            'Valget trer i kraft når du lagrer Setup, uten å endre jobber eller filer.'
        ))
        self.appearance_group = QButtonGroup(self)
        self.appearance_group.setExclusive(True)
        self.appearance_buttons = {}
        self.appearance_cards = {}
        choice_row = QHBoxLayout()
        choice_row.setSpacing(9)
        themes = (
            ('system', 'Windows / systemfarger', 'Følg Windows/Qt', '#f2f4f8', '#26384e'),
            ('dark', 'Mørk (dagens)', 'Dagens DWM', '#141b26', '#dce5f2'),
            ('light', 'Lys', 'Dempet lyst arbeidsområde', '#e8edf3', '#243247'),
        )
        for key, label, caption, bg, fg in themes:
            card = _AppearanceCard()
            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(10, 10, 10, 10)
            card_layout.setSpacing(7)
            radio = QRadioButton(label)
            card.radio = radio
            card_layout.addWidget(radio)
            self.appearance_group.addButton(radio)
            self.appearance_buttons[key] = radio
            self.appearance_cards[key] = card
            sample = QLabel('Aa  •  ▤  ☷')
            sample.setAlignment(Qt.AlignmentFlag.AlignCenter)
            sample.setMinimumHeight(45)
            sample.setStyleSheet(
                f'background: {bg}; color: {fg}; border: 1px solid #8395aa; border-radius: 5px;'
            )
            sample.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
            card_layout.addWidget(sample)
            explanation = _wrap(caption)
            explanation.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
            card_layout.addWidget(explanation)
            choice_row.addWidget(card, 1)
        layout.addLayout(choice_row)
        self.appearance_buttons[theme_mode(self.settings)].setChecked(True)
        self.appearance_state = _wrap('', strong=True)
        self.appearance_state.setObjectName('dwmAppearanceSelection')
        layout.addWidget(self.appearance_state)

        layout.addWidget(_wrap('Helhetlig fargekombinasjon – Mørk og Lys', strong=True))
        self.palette_combo = QComboBox()
        for key, label in PALETTE_CHOICES.items():
            self.palette_combo.addItem(label, key)
        self.palette_combo.setCurrentIndex(
            max(0, self.palette_combo.findData(palette_mode(self.settings)))
        )
        self._custom_colors = dict(self.settings.get('qt_custom_colors') or {})
        self._previous_palette = str(self.palette_combo.currentData() or 'standard')
        self.palette_combo.currentIndexChanged.connect(self._palette_changed)
        layout.addWidget(self.palette_combo)
        self.palette_preview = QWidget()
        preview_layout = QHBoxLayout(self.palette_preview)
        preview_layout.setContentsMargins(0, 3, 0, 3)
        preview_layout.setSpacing(5)
        self.palette_swatches = {}
        for role, label in (
            ('window', 'Bakgrunn'), ('surface', 'Panel'),
            ('button', 'Knapper'), ('accent', 'Valg'), ('text', 'Tekst')
        ):
            swatch = QLabel(' ' + label)
            swatch.setMinimumHeight(32)
            swatch.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.palette_swatches[role] = swatch
            preview_layout.addWidget(swatch, 1)
        layout.addWidget(self.palette_preview)
        self.palette_note = _wrap('')
        layout.addWidget(self.palette_note)
        self.custom_button = QPushButton('Tilpass farger …')
        self.custom_button.clicked.connect(self._open_custom_palette)
        layout.addWidget(self.custom_button)

        self.accent_title = _wrap('Aksentfarge – bare Standard-paletten', strong=True)
        layout.addWidget(self.accent_title)
        self.accent_combo = QComboBox()
        for key, label in ACCENT_CHOICES.items():
            self.accent_combo.addItem(label, key)
        self.accent_combo.setCurrentIndex(max(0, self.accent_combo.findData(accent_mode(self.settings))))
        layout.addWidget(self.accent_combo)
        self.accent_note = _wrap('')
        layout.addWidget(self.accent_note)
        for radio in self.appearance_buttons.values():
            radio.toggled.connect(self._refresh_appearance_explanation)
        self.accent_combo.currentIndexChanged.connect(
            lambda _index: self._refresh_appearance_explanation()
        )
        self._refresh_appearance_explanation()

        layout.addWidget(_wrap('Plassering av popup-vinduer', strong=True))
        self.popup_combo = QComboBox()
        for key, label in PLACEMENT_CHOICES.items():
            self.popup_combo.addItem(label, key)
        selected = str(self.settings.get('qt_popup_placement') or 'auto')
        self.popup_combo.setCurrentIndex(max(0, self.popup_combo.findData(selected)))
        layout.addWidget(self.popup_combo)
        layout.addWidget(_information(
            'Automatisk er anbefalt',
            'Setup og redigeringsvinduer åpnes over hovedvinduet. '
            'Rapportgenerering og resultatvisninger forsøkes åpnet ved siden '
            'av hovedvinduet eller på en ekstra skjerm. Hvis det ikke er '
            'plass, åpnes de synlig over hovedvinduet. '
            'Hovedvinduet flyttes ikke.'
        ))
        form.addRow(body)

    def _refresh_appearance_explanation(self):
        selected = self._chosen_theme()
        native = selected == 'system'
        preset = (str(self.palette_combo.currentData() or 'standard')
                  if hasattr(self, 'palette_combo') else 'standard')
        self.accent_combo.setEnabled(not native and preset == 'standard')
        if hasattr(self, 'accent_title'):
            show_accent = not native and preset == 'standard'
            self.accent_title.setVisible(show_accent)
            self.accent_combo.setVisible(show_accent)
            self.accent_note.setVisible(show_accent)
        self.accent_note.setText(
            'Windows styrer aksentfargen når systemtema er valgt.' if native else
            'Farger og aksent følger den valgte helhetlige paletten.' if preset != 'standard' else
            'Aksentfargen brukes på aktive faner, markeringer og valgte profilkort.'
        )
        if hasattr(self, 'palette_combo'):
            self.palette_combo.setEnabled(not native)
            self.custom_button.setEnabled(not native)
            self._refresh_palette_preview(selected, preset)
        # The whole card is a selector, not just the small radio indicator.
        # Paint selection locally so Windows / systemfarger has a visible
        # border even though its application-wide Qt stylesheet is empty.
        light_ui = self.palette().color(QPalette.ColorRole.Window).lightness() > 145
        accent = str(self.accent_combo.currentData() or 'system')
        accent_colors = {
            'system': '#317bc0', 'blue': '#317bc0', 'green': '#328766',
            'purple': '#7b5ab3', 'pink': '#b3447c', 'slate': '#596d83',
        }
        highlight = '#317bc0' if native else accent_colors.get(accent, '#317bc0')
        card_colors = None
        if not native and preset != 'standard' and hasattr(self, 'palette_combo'):
            mode = 'dark' if selected == 'dark' else 'light'
            try:
                card_colors = palette_colors(
                    mode, preset, self._custom_colors or custom_defaults(mode)
                )
            except ValueError:
                card_colors = palette_colors(mode, 'standard')
            highlight = card_colors['accent']
        for key, card in self.appearance_cards.items():
            kw = ({'surface': card_colors['surface'],
                   'selected_surface': card_colors['chosen'],
                   'edge': card_colors['border']} if card_colors else {})
            card.set_chosen(key == selected, highlight=highlight, light=light_ui, **kw)
        label = THEME_CHOICES[selected]
        if hasattr(self, 'palette_combo') and not native:
            label += ' · ' + PALETTE_CHOICES.get(preset, 'Standard')
        changed_palette = (
            hasattr(self, 'palette_combo') and
            (preset != palette_mode(self.settings) or
             (preset == 'custom' and self._custom_colors !=
              dict(self.settings.get('qt_custom_colors') or {})))
        )
        if (selected != theme_mode(self.settings) or changed_palette or
                (not native and preset == 'standard' and accent != accent_mode(self.settings))):
            self.appearance_state.setText(
                f'Valgt: {label} – ikke lagret. Trykk «Lagre» nederst til høyre '
                'for å bruke temaet.'
            )
        else:
            self.appearance_state.setText(
                f'Gjeldende tema: {label}. Du kan klikke hvor som helst i et '
                'annet kort og deretter «Lagre».'
            )

    def _refresh_palette_preview(self, selected: str, preset: str):
        base_mode = 'dark' if selected == 'dark' else 'light'
        if preset == 'custom':
            initial = self._custom_colors or custom_defaults(base_mode)
            try:
                colors = palette_colors(base_mode, preset, initial)
            except ValueError:
                colors = palette_colors(base_mode, 'standard')
        else:
            colors = palette_colors(base_mode, preset)
            if preset == 'standard':
                accent = str(self.accent_combo.currentData() or 'system')
                from gui_qt.appearance_v0110_a3 import _accent_colors
                colors['accent'] = _accent_colors(base_mode, accent)[0]
        for role, label in (
            ('window', 'Bakgrunn'), ('surface', 'Panel'),
            ('button', 'Knapper'), ('accent', 'Valg'), ('text', 'Tekst')
        ):
            swatch = self.palette_swatches[role]
            bg = colors[role]
            fg = selected_text(bg)
            swatch.setStyleSheet(
                f'QLabel {{ background-color: {bg}; color: {fg}; '
                'border: 1px solid #888; border-radius: 4px; padding: 5px; }'
            )
            swatch.setToolTip(f'{label}: {bg}')
        self.palette_note.setText(
            'Windows bruker systemets egne farger.' if selected == 'system' else
            'Hele DWM bruker denne paletten: bakgrunn, paneler, knapper, '
            'faner, tabeller og markeringer.' if preset != 'standard' else
            'Standard beholder den nøytrale DWM-paletten. '
            'Du kan endre aksentfargen nedenfor.'
        )

    def _palette_changed(self, _index):
        chosen = str(self.palette_combo.currentData() or 'standard')
        if chosen == 'custom' and not self._custom_colors:
            if not self._open_custom_palette():
                self.palette_combo.blockSignals(True)
                old = self.palette_combo.findData(self._previous_palette)
                self.palette_combo.setCurrentIndex(max(0, old))
                self.palette_combo.blockSignals(False)
                self._refresh_appearance_explanation()
                return
        self._previous_palette = chosen
        self._refresh_appearance_explanation()

    def _open_custom_palette(self):
        base = self._chosen_theme()
        initial = self._custom_colors or custom_defaults(
            'dark' if base == 'dark' else 'light'
        )
        dialog = _CustomPaletteDialog(initial, base, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return False
        self._custom_colors = dict(dialog.colors)
        self.palette_combo.blockSignals(True)
        self.palette_combo.setCurrentIndex(
            max(0, self.palette_combo.findData('custom'))
        )
        self.palette_combo.blockSignals(False)
        self._previous_palette = 'custom'
        self._refresh_appearance_explanation()
        return True

    def _chosen_theme(self) -> str:
        for key, radio in self.appearance_buttons.items():
            if radio.isChecked():
                return key
        return 'system'

    def _updates(self) -> dict:
        result = super()._updates()
        result['appearance_mode'] = self._chosen_theme()
        result['qt_accent_color'] = str(self.accent_combo.currentData() or 'system')
        result['qt_palette_preset'] = str(self.palette_combo.currentData() or 'standard')
        if self._custom_colors:
            result['qt_custom_colors'] = dict(self._custom_colors)
        result['qt_popup_placement'] = str(self.popup_combo.currentData() or 'auto')
        return result
