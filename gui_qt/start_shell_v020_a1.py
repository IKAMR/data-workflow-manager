"""v0.2.0-a1: navigation layer over the existing DWM Qt control window.

No new job, runner, Source/Work or DIAS implementation is introduced here.
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QFrame, QGridLayout, QGroupBox, QHBoxLayout,
    QLabel, QMessageBox, QPushButton, QRadioButton, QVBoxLayout, QWidget,
)

PROFILE_KEY = 'ui_work_profile'
STARTUP_KEY = 'ui_startup_mode'
FEATURES_KEY = 'ui_visible_sections'
PROFILES = ('control', 'depot', 'custom')
STARTUP_MODES = ('last', 'basic', 'advanced')
PROFILE_NAMES = {
    'control': 'Kontroll',
    'depot': 'Depot – produksjonslinje',
    'custom': 'Egendefinert',
}
SECTIONS = (
    ('ingest', 'Ingest', 'Registrering og mottak'),
    ('antivirus', 'Antiviruskontroll', 'Karantene og sikkerhetskontroll'),
    ('workspace', 'Til arbeidsområde', 'Klargjør uttrekk og Work'),
    ('control', 'Kontroll', 'Enkel og Avansert kontroll'),
    ('report', 'Rapportering', 'Kontrollresultater og rapporter'),
    ('preserve', 'Bevaring', 'Eksisterende DIAS AIP-pakking'),
    ('crm', 'Mot intern CRM', 'Oversikt og oppfølging'),
    ('access', 'Innsyn', 'Tilgjengeliggjøring og gjenfinning'),
)


def normalize_profile(value):
    return value if value in PROFILES else 'control'


def normalize_startup(value):
    return value if value in STARTUP_MODES else 'basic'


def normalize_sections(items):
    if not isinstance(items, (list, tuple)):
        return ['control']
    permitted = {item[0] for item in SECTIONS}
    return list(dict.fromkeys(item for item in items if isinstance(item, str) and item in permitted))


def visible_sections(settings):
    profile = normalize_profile(settings.get(PROFILE_KEY, 'control'))
    if profile == 'depot':
        return [item[0] for item in SECTIONS]
    if profile == 'custom':
        return normalize_sections(settings.get(FEATURES_KEY, ['control']))
    return ['control']


def startup_target(settings, last_mode):
    choice = normalize_startup(settings.get(STARTUP_KEY, 'basic'))
    return last_mode if choice == 'last' and last_mode in ('basic', 'advanced') else ('basic' if choice == 'last' else choice)


def navigation_labels(settings, is_basic):
    """Text for the always-visible navigation bar, in either control mode."""
    profile = PROFILE_NAMES[normalize_profile(settings.get(PROFILE_KEY, 'control'))]
    mode = 'Enkel' if is_basic else 'Avansert'
    switch = 'Avansert modus' if is_basic else 'Enkel modus'
    return 'Arbeidsprofil: ' + profile, 'Kontroll · ' + mode + ' modus', switch


class StartupSetupPage(QWidget):
    """Setup tab; values are persisted only by the existing Setup save action."""

    def __init__(self, settings, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        profile_group = QGroupBox('Arbeidsprofil')
        profile_layout = QVBoxLayout(profile_group)
        self.profile = QComboBox()
        self.profile.addItem('Kontroll (standard)', 'control')
        self.profile.addItem('Depot – produksjonslinje', 'depot')
        self.profile.addItem('Egendefinert', 'custom')
        self.profile.setCurrentIndex(max(0, self.profile.findData(normalize_profile(settings.get(PROFILE_KEY)))))
        profile_layout.addWidget(self.profile)
        self.checks = {}
        grid = QGridLayout()
        for i, (key, title, _) in enumerate(SECTIONS):
            check = QCheckBox(title)
            check.setChecked(key in normalize_sections(settings.get(FEATURES_KEY, ['control'])))
            grid.addWidget(check, i // 2, i % 2)
            self.checks[key] = check
        profile_layout.addLayout(grid)
        layout.addWidget(profile_group)
        mode_group = QGroupBox('Oppstartsmodus for Kontroll')
        mode_layout = QVBoxLayout(mode_group)
        self.modes = {}
        options = [('last', 'Sist brukte modus'), ('basic', 'Alltid Enkel modus'), ('advanced', 'Alltid Avansert modus')]
        current = normalize_startup(settings.get(STARTUP_KEY, 'basic'))
        for key, label in options:
            button = QRadioButton(label)
            button.setChecked(key == current)
            mode_layout.addWidget(button)
            self.modes[key] = button
        layout.addWidget(mode_group)
        hint = QLabel('Modus kan alltid byttes manuelt. Fast oppstartsmodus gjelder først ved neste oppstart.\nEksisterende jobber, DIAS og Work endres ikke.')
        hint.setWordWrap(True)
        layout.addWidget(hint)
        layout.addStretch()
        self.profile.currentIndexChanged.connect(self._sync)
        self._sync()

    def _sync(self):
        enabled = self.profile.currentData() == 'custom'
        for control in self.checks.values():
            control.setEnabled(enabled)

    def updates(self):
        return {
            PROFILE_KEY: self.profile.currentData(),
            STARTUP_KEY: next(key for key, control in self.modes.items() if control.isChecked()),
            FEATURES_KEY: [key for key, control in self.checks.items() if control.isChecked()],
        }


def install_setup_tab():
    # The existing Basic Setup imports this class dynamically at click time.
    # Decorating the existing class preserves all its storage/DIAS/external tabs.
    from gui_qt import setup_format_v0111_a2 as module
    base = module.DwmSetupDialog
    if getattr(base, '_v020_has_startup', False):
        return

    class SetupWithStartup(base):
        _v020_has_startup = True

        def __init__(self, api, parent=None):
            super().__init__(api, parent)
            self.startup_page = StartupSetupPage(self.settings, self)
            self.tabs.insertTab(0, self.startup_page, 'Oppstart og profil')
            # Every Setup entry point (including the advanced menu) updates the
            # global navigation after a successful save, not on Cancel.
            self.accepted.connect(self._refresh_navigation)

        def _refresh_navigation(self):
            parent = self.parentWidget()
            if parent is not None and hasattr(parent, 'v020_sync_navigation'):
                parent.v020_sync_navigation()

        def _updates(self):
            values = super()._updates()
            values.update(self.startup_page.updates())
            return values

    module.DwmSetupDialog = SetupWithStartup


class StartPage(QDialog):
    """Rounded navigation choices; unavailable integrations are not misrepresented."""

    def __init__(self, window):
        super().__init__(window)
        self.window = window
        self.setWindowTitle('Data Workflow Manager – Startside')
        self.setMinimumSize(630, 470)
        self.resize(750, 650)
        self.setStyleSheet('QFrame#startCard {border: 1px solid palette(mid); border-radius: 16px; padding: 12px;} QPushButton#cardButton {text-align:left; padding:12px; border-radius:10px;}')
        layout = QVBoxLayout(self)
        top = QHBoxLayout()
        heading = QLabel('Hva vil du gjøre?')
        heading.setStyleSheet('font-size: 21px; font-weight: 600;')
        top.addWidget(heading)
        top.addStretch()
        setup = QPushButton('Oppstart og profil…')
        setup.clicked.connect(self._open_setup)
        top.addWidget(setup)
        layout.addLayout(top)
        profile_row = QHBoxLayout()
        profile_row.addWidget(QLabel('Arbeidsprofil:'))
        self.profile_choice = QComboBox(self)
        self.profile_choice.addItem('Kontroll', 'control')
        self.profile_choice.addItem('Depot – produksjonslinje', 'depot')
        self.profile_choice.addItem('Egendefinert', 'custom')
        self.profile_choice.setCurrentIndex(max(0, self.profile_choice.findData(normalize_profile(window.api.settings.get(PROFILE_KEY)))))
        self.profile_choice.currentIndexChanged.connect(self._change_profile)
        profile_row.addWidget(self.profile_choice, 1)
        layout.addLayout(profile_row)
        self.subtitle = QLabel('Velg arbeidsområde. Enkel og Avansert bruker samme jobb- og resultatgrunnlag.')
        self.subtitle.setWordWrap(True)
        layout.addWidget(self.subtitle)
        self.cards = QGridLayout()
        self.cards.setSpacing(12)
        layout.addLayout(self.cards)
        layout.addStretch()
        self.refresh()

    def refresh(self):
        while self.cards.count():
            item = self.cards.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        settings = self.window.api.settings
        keys = set(visible_sections(settings))
        choices = [s for s in SECTIONS if s[0] in keys]
        self.subtitle.setText(('Depot – produksjonslinje' if normalize_profile(settings.get(PROFILE_KEY)) == 'depot' else 'Arbeidsprofil: Kontroll / Egendefinert') + '  •  Velg arbeidsområde')
        for i, (key, name, desc) in enumerate(choices):
            card = QFrame(self)
            card.setObjectName('startCard')
            inner = QVBoxLayout(card)
            action = QPushButton(name + ('  →' if key == 'control' else ''), card)
            action.setObjectName('cardButton')
            action.setMinimumHeight(46)
            action.clicked.connect(lambda _checked=False, k=key: self._open_section(k))
            inner.addWidget(action)
            label = QLabel(desc, card)
            label.setWordWrap(True)
            inner.addWidget(label)
            self.cards.addWidget(card, i // 2, i % 2)

    def _open_section(self, key):
        if key == 'control':
            self.accept()
            return
        QMessageBox.information(self, 'Arbeidsområde',
            'Boksen er foreløpig navigasjon i v0.2.0-a1. Eksisterende funksjoner endres ikke.\n'
            'Integrasjon for dette arbeidsområdet kommer i senere utviklingstrinn.')

    def _change_profile(self):
        key = self.profile_choice.currentData()
        if key == normalize_profile(self.window.api.settings.get(PROFILE_KEY)):
            return
        try:
            self.window.api.save_setup({PROFILE_KEY: key})
        except Exception as exc:
            QMessageBox.warning(self, 'Kunne ikke lagre arbeidsprofil', str(exc))
            saved = normalize_profile(self.window.api.settings.get(PROFILE_KEY))
            self.profile_choice.blockSignals(True)
            self.profile_choice.setCurrentIndex(self.profile_choice.findData(saved))
            self.profile_choice.blockSignals(False)
            return
        self.window.v020_sync_navigation()
        self.refresh()

    def _open_setup(self):
        self.window._open_setup()
        self.window.v020_sync_navigation()
        current = normalize_profile(self.window.api.settings.get(PROFILE_KEY))
        self.profile_choice.blockSignals(True)
        self.profile_choice.setCurrentIndex(self.profile_choice.findData(current))
        self.profile_choice.blockSignals(False)
        self.refresh()


def install_start_navigation(window):
    """A fixed, shared top bar outside Basic's scrolling area and Advanced docks.

    Moving the existing mode button (rather than adding a duplicate) preserves
    its identity and the actual Basic/Advanced state transitions.  The bar is
    a separate QMainWindow toolbar: the inherited _toolbar is hidden in Basic.
    """
    from PySide6.QtCore import QTimer
    from PySide6.QtGui import QAction
    from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QSizePolicy, QToolBar, QWidget

    def home():
        page = StartPage(window)
        try:
            page.exec()
        finally:
            window.v020_sync_navigation()
        # Navigation does not open or modify a job, Work or DIAS package.

    def open_setup():
        window._open_setup()
        window.v020_sync_navigation()

    window.v020_home = home
    action = QAction('Startside', window)
    action.setShortcut('Alt+Home')
    action.triggered.connect(home)
    window.addAction(action)

    toolbar = QToolBar('Navigasjon', window)
    toolbar.setObjectName('v020_navigation_toolbar')
    toolbar.setMovable(False)
    toolbar.setFloatable(False)
    toolbar.setAllowedAreas(Qt.ToolBarArea.TopToolBarArea)
    toolbar.setContextMenuPolicy(Qt.ContextMenuPolicy.PreventContextMenu)
    toolbar.setMinimumHeight(45)
    nav = QWidget(toolbar)
    nav.setObjectName('v020_navigation_content')
    nav.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
    header = QHBoxLayout(nav)
    header.setContentsMargins(12, 4, 12, 4)
    header.setSpacing(12)

    home_button = QPushButton('Startside', nav)
    home_button.setObjectName('v020_home_button')
    home_button.clicked.connect(home)
    header.addWidget(home_button)

    profile_label = QLabel(nav)
    profile_label.setObjectName('v020_profile_label')
    header.addWidget(profile_label)
    section_label = QLabel(nav)
    section_label.setObjectName('v020_section_label')
    header.addWidget(section_label)
    header.addStretch(1)

    setup_button = QPushButton('Setup…', nav)
    setup_button.setObjectName('v020_setup_button')
    setup_button.clicked.connect(open_setup)
    header.addWidget(setup_button)

    # IMPORTANT: The Basic title/header is in a scroll area.  Its parent
    # content.layout() is a QVBoxLayout, *not* the horizontal header layout.
    # Reparent the original mode button into the fixed toolbar, never insert a
    # button into the content QVBoxLayout (that put Startside at the bottom).
    mode_button = window.basic_advanced_button
    content = mode_button.parentWidget()
    content_layout = content.layout()
    original_header = content_layout.itemAt(0).layout()
    if original_header is None or original_header.indexOf(mode_button) < 0:
        raise RuntimeError('Fant ikke overskriftsraden for Enkel/Avansert-knappen.')
    original_header.removeWidget(mode_button)
    mode_button.setParent(nav)
    # This is the existing button; only its location and click route change.
    mode_button.clicked.disconnect()

    def switch_control_mode():
        if window._basic_active:
            window._leave_basic()
        else:
            window._enter_basic()
        QTimer.singleShot(0, sync_navigation)

    mode_button.clicked.connect(switch_control_mode)
    mode_button.setObjectName('v020_mode_button')
    header.addWidget(mode_button)
    toolbar.addWidget(nav)
    # Above the existing Advanced toolbar, with its own full-width row.
    window.insertToolBar(window._toolbar, toolbar)
    window.insertToolBarBreak(window._toolbar)

    def sync_navigation(*_unused):
        profile, section, switch = navigation_labels(window.api.settings, window._basic_active)
        profile_label.setText(profile)
        section_label.setText(section)
        mode_button.setText(switch)
        # Native layout restore during Basic/Advanced switching must not hide
        # the shared bar.  The inherited _toolbar is controlled separately.
        toolbar.show()

    window.v020_home_action = action
    window.v020_home_button = home_button
    window.v020_mode_button = mode_button
    window.v020_nav_toolbar = toolbar
    window.v020_profile_label = profile_label
    window.v020_section_label = section_label
    window.v020_sync_navigation = sync_navigation
    window.pages.currentChanged.connect(sync_navigation)

    last = str(window.config.value('qt/v0111_interface_mode', 'basic'))
    target = startup_target(window.api.settings, last)
    if target == 'advanced':
        window._leave_basic()
    else:
        window._enter_basic()
    sync_navigation()
    if normalize_profile(window.api.settings.get(PROFILE_KEY)) != 'control':
        QTimer.singleShot(0, home)
