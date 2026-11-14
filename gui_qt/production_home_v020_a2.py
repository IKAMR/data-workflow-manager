"""v0.2.0-a4: depot production navigation integrated in the main Qt window.

Home is a QWidget in the original QMainWindow, NOT a modal popup. Existing
Noark 5 jobs, runner, result windows and DIAS implementation are reused.
"""
from __future__ import annotations

from PySide6.QtCore import QEvent, QObject, Qt, QTimer
from PySide6.QtWidgets import (
    QComboBox, QFrame, QGridLayout, QHBoxLayout, QLabel, QMessageBox,
    QPushButton, QScrollArea, QStackedWidget, QVBoxLayout, QWidget,
)

from app.ui_work_areas_v020_a2 import cards_for, destination, normalize_area_visibility
from gui_qt.start_shell_v020_a1 import (
    PROFILE_KEY, PROFILE_NAMES, SECTIONS, AREA_VISIBILITY_KEY,
    normalize_profile, startup_page_target, visible_sections, open_startup_setup,
)
from version import VERSION
from gui_qt.production_progress_v020_a5 import active_job_context, saved_section_for_window


class ProductionStartPage(QWidget):
    """One production landing page; no independent window or duplicated jobs."""

    def __init__(self, window):
        super().__init__(window)
        self.window = window
        self.setObjectName('v020_home_page')
        self.setStyleSheet(
            'QFrame#startCard { border: 1px solid palette(mid); '
            'border-radius: 14px; padding: 7px; } '
            'QPushButton#cardButton { text-align: left; padding: 10px; '
            'border-radius: 9px; }'
        )
        outer = QVBoxLayout(self)
        outer.setContentsMargins(8, 5, 8, 5)
        scroll = QScrollArea(self)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setWidgetResizable(True)
        outer.addWidget(scroll)
        content = QWidget(scroll)
        scroll.setWidget(content)
        layout = QVBoxLayout(content)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(14)

        header = QHBoxLayout()
        heading = QLabel('Hva vil du gjøre?', content)
        heading.setStyleSheet('font-size: 22px; font-weight: 600;')
        header.addWidget(heading)
        header.addStretch()
        setup = QPushButton('Oppstart og profil…', content)
        setup.clicked.connect(self._open_setup)
        header.addWidget(setup)
        layout.addLayout(header)

        profile_row = QHBoxLayout()
        profile_row.addWidget(QLabel('Arbeidsprofil:', content))
        self.profile_choice = QComboBox(content)
        for profile, label in PROFILE_NAMES.items():
            self.profile_choice.addItem(label, profile)
        self.profile_choice.currentIndexChanged.connect(self._change_profile)
        profile_row.addWidget(self.profile_choice, 1)
        layout.addLayout(profile_row)

        self.subtitle = QLabel(content)
        self.subtitle.setWordWrap(True)
        layout.addWidget(self.subtitle)
        self.context_label = QLabel(content)
        self.context_label.setObjectName('v020_a2_context')
        self.context_label.setWordWrap(True)
        layout.addWidget(self.context_label)
        self.production_status = QLabel(content)
        self.production_status.setObjectName('v020_a5_quick_status')
        self.production_status.setWordWrap(True)
        layout.addWidget(self.production_status)
        status_actions = QHBoxLayout()
        progress_button = QPushButton('Jobbstatus og historikk', content)
        progress_button.setObjectName('v020_a5_status_button')
        progress_button.clicked.connect(lambda: self.window.v020_show_progress_page())
        status_actions.addWidget(progress_button)
        self.resume_button = QPushButton('Fortsett sist', content)
        self.resume_button.setObjectName('v020_a5_resume_button')
        self.resume_button.clicked.connect(lambda: self.window.v020_resume_area())
        status_actions.addWidget(self.resume_button)
        status_actions.addStretch(1)
        layout.addLayout(status_actions)

        self.cards = QGridLayout()
        self.cards.setSpacing(12)
        layout.addLayout(self.cards)
        self.status_explanation = QLabel(
            'Status gjelder GUI-integrasjon, ikke om arkivuttrekket er kontrollert, '
            'godkjent eller bevart.', content,
        )
        self.status_explanation.setObjectName('v020_a2_status_explanation')
        self.status_explanation.setWordWrap(True)
        layout.addWidget(self.status_explanation)
        layout.addStretch(1)
        self.refresh()

    def refresh(self):
        settings = self.window.api.settings
        profile = normalize_profile(settings.get(PROFILE_KEY, 'control'))
        self.profile_choice.blockSignals(True)
        self.profile_choice.setCurrentIndex(self.profile_choice.findData(profile))
        self.profile_choice.blockSignals(False)
        while self.cards.count():
            item = self.cards.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        threshold = normalize_area_visibility(settings.get(AREA_VISIBILITY_KEY))
        cards = cards_for(visible_sections(settings), SECTIONS, threshold)
        self.subtitle.setText(
            PROFILE_NAMES[profile] + ' · ' + str(len(cards)) +
            (' arbeidsområde' if len(cards) == 1 else ' arbeidsområder')
        )
        active = getattr(self.window, '_active_id', None)
        self.context_label.setText(
            ('Aktiv jobb: ' + str(active)) if active else
            'Ingen aktiv jobb valgt. Valg på Startsiden oppretter ikke jobber.'
        )
        job, _key = active_job_context(self.window)
        if job is None:
            self.production_status.setText('Ingen jobbstatus å vise. Velg en jobb i Kontroll.')
        else:
            from app.production_progress_v020_a5 import _progress_percent
            self.production_status.setText(
                'Lagret kontrollstatus: ' + str(job.status) +
                f' | {_progress_percent(job.progress)} % av kontrolloperasjonene. '
                'Faglig depotvurdering og bevaring er separate trinn.'
            )
        self.resume_button.setEnabled(bool(saved_section_for_window(self.window)))
        for index, (key, title, capability) in enumerate(cards):
            frame = QFrame(self)
            frame.setObjectName('startCard')
            inner = QVBoxLayout(frame)
            header = QHBoxLayout()
            action = QPushButton(f'{index + 1}. {title}' +
                                 ('  →' if capability.route else ''), frame)
            action.setObjectName('cardButton')
            action.setMinimumHeight(44)
            action.setEnabled(capability.route is not None)
            if capability.route is not None:
                action.clicked.connect(
                    lambda _checked=False, section=key: self._open_section(section)
                )
            else:
                action.setToolTip('Dette arbeidsområdet er ikke integrert ennå.')
            header.addWidget(action, 1)
            status = QLabel(capability.state_label + ' · ' + capability.maturity_label, frame)
            status.setObjectName('v020_a2_status_' + key)
            status.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            header.addWidget(status)
            inner.addLayout(header)
            detail = QLabel(capability.detail, frame)
            detail.setObjectName('v020_a2_detail_' + key)
            detail.setWordWrap(True)
            inner.addWidget(detail)
            self.cards.addWidget(frame, index // 2, index % 2)
        self.cards.setColumnStretch(0, 1)
        self.cards.setColumnStretch(1, 1)
        self.status_explanation.setText(
            'Modenhetsfilter: ' + str(threshold) + ' (0=alle, 1=Beta+Stabil, 2=kun Stabil). '
            'Status gjelder GUI-integrasjon, ikke om uttrekket er kontrollert, godkjent eller bevart.'
        )
        if not cards:
            empty = QLabel(
                'Ingen arbeidsområder vises for denne profilen og modenhetsgrensen. '
                'Endre «Synlige arbeidsområder» i Oppstart og profil.', self
            )
            empty.setWordWrap(True)
            self.cards.addWidget(empty, 0, 0, 1, 2)

    def _change_profile(self, _index=None):
        key = self.profile_choice.currentData()
        if key == normalize_profile(self.window.api.settings.get(PROFILE_KEY)):
            return
        try:
            self.window.api.save_setup({PROFILE_KEY: key})
        except Exception as exc:
            QMessageBox.warning(self, 'Kunne ikke lagre arbeidsprofil', str(exc))
            self.refresh()
            return
        self.window.v020_sync_navigation()
        self.refresh()

    def _open_setup(self):
        open_startup_setup(self.window)
        self.window.v020_sync_navigation()
        self.refresh()

    def accept(self):
        """Compatibility with the a2 navigation contract: show Control in-place."""
        self.window.v020_show_control_page()

    def _close_and_run(self, callback):
        """Return to the workbench before opening an existing Qt dialog."""
        self.accept()
        QTimer.singleShot(0, callback)

    def _open_section(self, key):
        route = destination(key)
        if route is None:
            return
        if route == 'control':
            self.accept()
        elif route == 'basic_work':
            self._close_and_run(self._open_existing_work_step)
        elif route == 'report':
            self._report_actions()
        elif route == 'preservation':
            self._preservation_actions()
        elif route == 'qt_ingest':
            self.window.v020_show_ingest_page()
        elif route == 'antivirus_info':
            self.window.v020_show_antivirus_page()
        elif route == 'legacy_ingest':
            self._legacy_launch('Ingest / mottak')

    def _open_existing_work_step(self):
        window = self.window
        if hasattr(window, 'v020_show_control_page'):
            window.v020_show_control_page()
        window._enter_basic()
        window._a2_set_step('work')
        window.v020_sync_navigation()
        if hasattr(window, 'v020_remember_area'):
            window.v020_remember_area('workspace')

    def _report_actions(self):
        """Use the a4 page in this QMainWindow, not a floating choice dialog."""
        self.window.v020_show_reporting_page()

    def _preservation_actions(self):
        """Expose status/actions; visiting Bevaring never generates a package."""
        self.window.v020_show_preservation_page()

    def _legacy_launch(self, purpose):
        if getattr(self.window, '_worker', None) is not None or self.window.api.running:
            QMessageBox.warning(self, purpose, 'Avslutt pågående kjøring før du åpner eldre GUI.')
            return
        choice = QMessageBox.question(
            self, purpose,
            purpose + ' er foreløpig tilgjengelig i DWM sitt eldre GUI, '
            'som åpnes separat.\n\n'
            'Start eldre GUI? Velg aktuell funksjon der. '
            'Ingen mottak, kontroll eller pakking startes automatisk.',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if choice == QMessageBox.StandardButton.Yes:
            self._close_and_run(self.window._open_legacy)


def install_integrated_home(window):
    """Place Startside beside the workbench in ONE QMainWindow.

    A stacked central widget preserves the exact existing widget, job state,
    controller and mode switches. No new application/runner is created.
    """
    from gui_qt.main_window import DOCK_NAMES
    from gui_qt.ingest_v020_a3 import IngestPage
    from gui_qt.antivirus_v020_a3 import AntivirusPage
    from gui_qt.reporting_preservation_v020_a4 import ReportingPage, PreservationPage
    from gui_qt.production_progress_v020_a5 import ProductionProgressPage

    original = window.takeCentralWidget()
    if original is None:
        raise RuntimeError('Hovedvinduet har ikke noen sentral kontrollflate.')
    stack = QStackedWidget(window)
    stack.setObjectName('v020_main_stack')
    stack.addWidget(original)
    home = ProductionStartPage(window)
    stack.addWidget(home)
    ingest = IngestPage(window)
    antivirus = AntivirusPage(window)
    stack.addWidget(ingest)
    stack.addWidget(antivirus)
    reporting = ReportingPage(window)
    preservation = PreservationPage(window)
    stack.addWidget(reporting)
    stack.addWidget(preservation)
    progress = ProductionProgressPage(window)
    stack.addWidget(progress)
    window.setCentralWidget(stack)
    saved_advanced = None
    original_sync = window.v020_sync_navigation

    def sync_navigation(*_args):
        original_sync()
        active = stack.currentWidget()
        if active is home:
            window.v020_section_label.setText('Startside · ' +
                PROFILE_NAMES[normalize_profile(window.api.settings.get(PROFILE_KEY))])
        elif active is ingest:
            window.v020_section_label.setText('Ingest · Mottak / Uttrekk')
        elif active is antivirus:
            window.v020_section_label.setText('Antiviruskontroll · Ikke skannet')
        elif active is reporting:
            window.v020_section_label.setText('Rapportering · Work og depotvurdering')
        elif active is preservation:
            window.v020_section_label.setText('Bevaring · Forberedelse og DIAS')
        elif active is progress:
            window.v020_section_label.setText('Produksjonsstatus · Aktiv jobb')

    def remember_area(area):
        if area not in ('ingest', 'antivirus', 'workspace', 'control', 'report', 'preserve'):
            return
        _job, job_key = active_job_context(window)
        if job_key:
            window.config.setValue('qt/v020_last_area_job_key', job_key)
            window.config.setValue('qt/v020_last_area', area)

    def show_home(*, record=True):
        nonlocal saved_advanced
        if record:
            window.config.setValue('qt/v020_last_page', 'home')
        if stack.currentWidget() is home:
            home.refresh()
            sync_navigation()
            return
        # Visiting Home -> Ingest -> Home must NOT snapshot already-hidden
        # Advanced docks a second time; only the first departure may save.
        if not window._basic_active and saved_advanced is None:
            saved_advanced = {
                'docks': {name: getattr(window, 'dock_' + name).isVisible()
                          for name in DOCK_NAMES},
                'toolbar': window._toolbar.isVisible(),
                'menu': window.menuBar().isVisible(),
                'status': window.statusBar().isVisible(),
            }
            for name in DOCK_NAMES:
                getattr(window, 'dock_' + name).hide()
            window._toolbar.hide()
            window.menuBar().hide()
            window.statusBar().hide()
        stack.setCurrentWidget(home)
        home.refresh()
        sync_navigation()

    def show_control(*, record=True):
        nonlocal saved_advanced
        if record:
            window.config.setValue('qt/v020_last_page', 'control')
            remember_area('control')
        if stack.currentWidget() is original:
            sync_navigation()
            return
        stack.setCurrentWidget(original)
        if saved_advanced is not None and not window._basic_active:
            for name, visible in saved_advanced['docks'].items():
                getattr(window, 'dock_' + name).setVisible(visible)
            window._toolbar.setVisible(saved_advanced['toolbar'])
            window.menuBar().setVisible(saved_advanced['menu'])
            window.statusBar().setVisible(saved_advanced['status'])
        saved_advanced = None
        sync_navigation()

    def show_ingest():
        # Reuse the proven a2 home transition to hide Advanced docks without
        # changing their saved visibility, then show the integrated form.
        show_home(record=True)
        stack.setCurrentWidget(ingest)
        remember_area('ingest')
        sync_navigation()

    def show_antivirus():
        show_home(record=True)
        stack.setCurrentWidget(antivirus)
        remember_area('antivirus')
        sync_navigation()

    def show_reporting():
        show_home(record=True)
        stack.setCurrentWidget(reporting)
        remember_area('report')
        reporting.refresh()
        sync_navigation()

    def show_preservation():
        show_home(record=True)
        stack.setCurrentWidget(preservation)
        remember_area('preserve')
        preservation.refresh()
        sync_navigation()

    def go_to_work():
        # No implicit job association or relocation of Source/Work.
        show_control()
        window._enter_basic()
        window._a2_set_step('work')
        remember_area('workspace')
        sync_navigation()

    def show_progress():
        show_home(record=True)
        stack.setCurrentWidget(progress)
        progress.refresh()
        sync_navigation()

    def open_area(area):
        routes = {
            'ingest': show_ingest,
            'antivirus': show_antivirus,
            'workspace': go_to_work,
            'control': show_control,
            'report': show_reporting,
            'preserve': show_preservation,
        }
        action = routes.get(area)
        if action is not None:
            action()

    def resume_area():
        area = saved_section_for_window(window)
        if area:
            open_area(area)

    window.v020_remember_area = remember_area
    window.v020_show_progress_page = show_progress
    window.v020_open_area = open_area
    window.v020_resume_area = resume_area
    window.v020_integrated_home = show_home
    window.v020_show_control_page = show_control
    window.v020_show_ingest_page = show_ingest
    window.v020_show_antivirus_page = show_antivirus
    window.v020_show_reporting_page = show_reporting
    window.v020_show_preservation_page = show_preservation
    window.v020_go_to_work = go_to_work
    window.v020_sync_navigation = sync_navigation
    # The fixed toolbar's existing mode button is reused. Switching from
    # Startside must reveal Control before changing Basic/Advanced state.
    previous_switch = window.v020_mode_button
    previous_switch.clicked.disconnect()

    def switch_mode():
        show_control()
        if window._basic_active:
            window._leave_basic()
        else:
            window._enter_basic()
        sync_navigation()

    previous_switch.clicked.connect(switch_mode)

    class RestoreControlBeforeClose(QObject):
        """Do not persist hidden advanced docks when closing from Startside."""

        def eventFilter(self, obj, event):
            if obj is window and event.type() == QEvent.Type.Close:
                show_control(record=False)
            return super().eventFilter(obj, event)

    # Keep the filter alive for the entire native window lifetime.
    window._v020_close_guard = RestoreControlBeforeClose(window)
    window.installEventFilter(window._v020_close_guard)
    initial_page = startup_page_target(
        window.api.settings,
        str(window.config.value('qt/v020_last_page', '')),
    )
    if initial_page == 'home':
        # Delay until window.show(): isVisible() is false for child docks,
        # menu and toolbar while QMainWindow itself is still hidden. Taking
        # that snapshot now would erase the user's Advanced layout on return.
        QTimer.singleShot(0, lambda: show_home(record=False))
    # No separate QDialog.exec() is used for the start navigation.
    return home
