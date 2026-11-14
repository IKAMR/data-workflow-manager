"""v0.2.0-a1: navigation layer over the existing DWM Qt control window.

No new job, runner, Source/Work or DIAS implementation is introduced here.
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QFrame, QGridLayout, QGroupBox, QHBoxLayout,
    QLabel, QMessageBox, QPushButton, QRadioButton, QScrollArea, QVBoxLayout, QWidget,
)

PROFILE_KEY = 'ui_work_profile'
STARTUP_KEY = 'ui_startup_mode'
FEATURES_KEY = 'ui_visible_sections'
PAGE_KEY = 'ui_startup_page'
AREA_VISIBILITY_KEY = 'ui_area_visibility'
PROFILES = ('control', 'depot', 'custom')
STARTUP_MODES = ('last', 'basic', 'advanced')
START_PAGES = ('profile', 'last', 'home', 'control')
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


def normalize_startpage(value):
    return value if value in START_PAGES else 'profile'


def startup_page_target(settings, last_page):
    """Choose Startside or Kontroll; independent of Enkel/Avansert startup mode."""
    choice = normalize_startpage(settings.get(PAGE_KEY, 'profile'))
    if choice == 'last':
        if last_page in ('home', 'control'):
            return last_page
        choice = 'profile'
    if choice == 'profile':
        return 'control' if normalize_profile(settings.get(PROFILE_KEY, 'control')) == 'control' else 'home'
    return choice


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
        outer = QVBoxLayout(self)
        outer.setContentsMargins(4, 4, 4, 4)
        scroll = QScrollArea(self)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setWidgetResizable(True)
        outer.addWidget(scroll)
        body = QWidget(scroll)
        scroll.setWidget(body)
        layout = QVBoxLayout(body)
        layout.setSpacing(12)
        profile_group = QGroupBox('Arbeidsprofil')
        profile_layout = QVBoxLayout(profile_group)
        self.profile = QComboBox()
        self.profile.addItem('Kontroll (standard)', 'control')
        self.profile.addItem('Depot – produksjonslinje', 'depot')
        self.profile.addItem('Egendefinert', 'custom')
        self.profile.setCurrentIndex(max(0, self.profile.findData(normalize_profile(settings.get(PROFILE_KEY)))))
        profile_layout.addWidget(self.profile)
        # ui_visible_sections belongs only to Egendefinert.  Fixed profiles
        # display their actual sections without overwriting the saved custom
        # selection when the user changes profiles before clicking Lagre.
        self._custom_sections = normalize_sections(settings.get(FEATURES_KEY, ['control']))
        self._shown_profile = None
        self.checks = {}
        grid = QGridLayout()
        for i, (key, title, _) in enumerate(SECTIONS):
            check = QCheckBox(title)
            grid.addWidget(check, i // 2, i % 2)
            self.checks[key] = check
        profile_layout.addLayout(grid)
        profile_note = QLabel(
            'Kontroll og Depot viser faste, låste valg. Velg Egendefinert for '
            'å endre hvilke arbeidsområder som vises på Startsiden.', profile_group
        )
        profile_note.setWordWrap(True)
        profile_layout.addWidget(profile_note)
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
        page_group = QGroupBox('Oppstartsside')
        page_layout = QVBoxLayout(page_group)
        self.pages = {}
        page_options = (
            ('profile', 'Følg arbeidsprofil (standard)'),
            ('last', 'Sist brukte side (Startside eller Kontroll)'),
            ('home', 'Alltid Startside'),
            ('control', 'Alltid Kontroll'),
        )
        page_current = normalize_startpage(settings.get(PAGE_KEY, 'profile'))
        for key, label in page_options:
            button = QRadioButton(label, page_group)
            button.setChecked(key == page_current)
            page_layout.addWidget(button)
            self.pages[key] = button
        layout.addWidget(page_group)
        # Startup choices appear first; profile checkboxes follow below.
        layout.addWidget(profile_group)

        maturity_group = QGroupBox('Synlige arbeidsområder etter modenhet')
        maturity_layout = QVBoxLayout(maturity_group)
        from app.ui_start_preferences_v020_a2 import WORK_AREA_VISIBILITY_LABELS
        from app.ui_work_areas_v020_a2 import normalize_area_visibility
        self.area_visibility = QComboBox(maturity_group)
        for level, label in WORK_AREA_VISIBILITY_LABELS.items():
            self.area_visibility.addItem(label, level)
        selected = normalize_area_visibility(settings.get(AREA_VISIBILITY_KEY))
        self.area_visibility.setCurrentIndex(self.area_visibility.findData(selected))
        maturity_layout.addWidget(self.area_visibility)
        maturity_note = QLabel(
            'Gjelder funksjonsboksene på Startsiden. Modenhet 0=Alpha, 1=Beta, 2=Stabil. '
            'Eksisterende «Vis operasjoner» under Arbeidsflyt endres ikke.', maturity_group
        )
        maturity_note.setWordWrap(True)
        maturity_layout.addWidget(maturity_note)
        layout.addWidget(maturity_group)

        hint = QLabel('Modus og side kan alltid byttes manuelt. Faste valg gjelder fra neste oppstart.\nEksisterende jobber, DIAS og Work endres ikke.')
        hint.setWordWrap(True)
        layout.addWidget(hint)
        layout.addStretch()
        self.profile.currentIndexChanged.connect(self._sync)
        self._sync()

    def _sync(self):
        """Show effective selections for the chosen profile, not custom data."""
        # The old profile is still visible in the checkboxes when Qt emits
        # currentIndexChanged.  Capture any unsaved custom edits first.
        if self._shown_profile == 'custom':
            self._custom_sections = [
                key for key, control in self.checks.items() if control.isChecked()
            ]
        profile = normalize_profile(self.profile.currentData())
        selected = set(visible_sections({
            PROFILE_KEY: profile, FEATURES_KEY: self._custom_sections,
        }))
        for key, control in self.checks.items():
            control.setChecked(key in selected)
            control.setEnabled(profile == 'custom')
        self._shown_profile = profile

    def updates(self):
        # Saving a fixed profile must not replace the remembered custom areas
        # with the fixed profile's displayed checkmarks.
        custom_sections = ([
            key for key, control in self.checks.items() if control.isChecked()
        ] if self.profile.currentData() == 'custom' else list(self._custom_sections))
        return {
            PROFILE_KEY: self.profile.currentData(),
            STARTUP_KEY: next(key for key, control in self.modes.items() if control.isChecked()),
            PAGE_KEY: next(key for key, control in self.pages.items() if control.isChecked()),
            AREA_VISIBILITY_KEY: self.area_visibility.currentData(),
            FEATURES_KEY: custom_sections,
        }



def preferred_setup_height(current_height, content_height, chrome_height, screen_height):
    """Grow Setup to fit the selected tab, never beyond the usable screen.

    The tab's existing QScrollArea handles the remainder on short screens.
    All dimensions are Qt logical pixels (respect Windows display scaling).
    """
    ceiling = max(320, int(screen_height) - 40)
    requested = max(int(current_height), int(content_height) + int(chrome_height) + 28)
    return max(1, min(requested, ceiling))


def open_startup_setup(window):
    """Open shared Setup with the startup/profile tab selected for this shortcut.

    The ordinary Setup action keeps its existing default tab.  The marker is
    temporary, so cancelling Setup or an exception cannot affect later opens.
    """
    marker = '_v020_setup_target'
    previous = getattr(window, marker, None)
    setattr(window, marker, 'startup')
    try:
        return window._open_setup()
    finally:
        if previous is None:
            delattr(window, marker)
        else:
            setattr(window, marker, previous)


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
            if getattr(parent, '_v020_setup_target', None) == 'startup':
                self.tabs.setCurrentWidget(self.startup_page)
            # Earlier Setup uses a fixed 880x640 window.  Expand to the height
            # of the selected tab when the screen permits; keep scrollbars on
            # shorter screens.  Recalculate when switching any Setup tab.
            self.tabs.currentChanged.connect(self._v020_fit_active_setup_tab)
            self._v020_fit_active_setup_tab()
            # Every Setup entry point (including the advanced menu) updates the
            # global navigation after a successful save, not on Cancel.
            self.accepted.connect(self._refresh_navigation)

        def showEvent(self, event):
            super().showEvent(event)
            # Account for final platform font metrics and DPI after first show.
            from PySide6.QtCore import QTimer
            QTimer.singleShot(0, self._v020_fit_active_setup_tab)

        def _v020_fit_active_setup_tab(self, _index=None):
            if self.isMaximized() or self.isFullScreen():
                return  # Do not override a user-maximized Setup window.
            from PySide6.QtWidgets import QApplication
            self.layout().activate()
            page = self.tabs.currentWidget()
            if page is None:
                return
            scroller = page.findChild(QScrollArea)
            if scroller is None or scroller.widget() is None:
                return
            content = scroller.widget()
            if content.layout() is not None:
                content.layout().activate()
            page_content_height = content.sizeHint().height()
            # Measure all non-tab controls rather than guessing a constant
            # title/button height: this supports varying fonts and DPI.
            outer = self.layout()
            margins = outer.contentsMargins()
            chrome = margins.top() + margins.bottom()
            chrome += max(0, outer.count() - 1) * outer.spacing()
            for i in range(outer.count()):
                item = outer.itemAt(i)
                if item.widget() is self.tabs:
                    chrome += self.tabs.tabBar().sizeHint().height() + 14
                else:
                    chrome += item.sizeHint().height()
            screen = (self.parentWidget().screen() if self.parentWidget() is not None
                      else self.screen())
            if screen is None:
                screen = QApplication.primaryScreen()
            if screen is None:
                return
            bounds = screen.availableGeometry()
            frame_extra = max(0, self.frameGeometry().height() - self.height())
            usable = max(320, bounds.height() - frame_extra)
            target_height = preferred_setup_height(
                self.height(), page_content_height, chrome, usable
            )
            # The original dialog has a 490px minimum.  Respect smaller displays
            # by relaxing that minimum only if they cannot fit it.
            if target_height < self.minimumHeight():
                self.setMinimumHeight(target_height)
            if target_height != self.height():
                self.resize(self.width(), target_height)
            # Expanding after a tab switch must not place Save/Cancel offscreen.
            # The caller's existing window placement still controls the default.
            if self.isVisible():
                left = max(bounds.left(), min(self.x(), bounds.right() - self.width() + 1))
                top = max(bounds.top(), min(self.y(), bounds.bottom() -
                                           self.frameGeometry().height() + 1))
                if (left, top) != (self.x(), self.y()):
                    self.move(left, top)

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
        open_startup_setup(self.window)
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
        # a2 uses the same QMainWindow and swaps its central view.  Keep the
        # a1 popup only as a backwards-compatible fallback for older clients.
        integrated = getattr(window, 'v020_integrated_home', None)
        if integrated is not None:
            integrated()
            return
        factory = getattr(window, 'v020_start_page_factory', StartPage)
        page = factory(window)
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
    # v0.2.0-a2: selection of the initial Startside/Kontroll page is handled
    # by install_integrated_home, after the QStackedWidget has been installed.
    # Retain a1 standalone fallback for clients without the a2 page factory.
    if (not hasattr(window, 'v020_start_page_factory') and
            normalize_profile(window.api.settings.get(PROFILE_KEY)) != 'control'):
        QTimer.singleShot(0, home)
