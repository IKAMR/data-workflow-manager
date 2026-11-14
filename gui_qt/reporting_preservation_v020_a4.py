"""v0.2.0-a4: Reporting and Preservation stages in the main Qt window.

Only read-only Work status is projected here. All professional decisions use
DWM's existing Depotvurdering tab and its signed, report-bound audit trail.
Generating reports, staging evidence, or launching the legacy DIAS packer are
separate, explicitly initiated operations; visiting a page never does them.
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame, QGridLayout, QHBoxLayout, QLabel, QMessageBox, QPushButton,
    QScrollArea, QVBoxLayout, QWidget,
)

from app.production_review_v020_a4 import inspect_production_evidence


class _ProductionEvidencePage(QWidget):
    """Shared current-job context, with actions delegated to established UI."""

    def __init__(self, window, *, preserve: bool):
        super().__init__(window)
        self.window = window
        self.preserve = preserve
        self.setObjectName('v020_a4_preservation_page' if preserve else 'v020_a4_reporting_page')
        self._snapshot = None
        self._buttons = {}

        outer = QVBoxLayout(self)
        outer.setContentsMargins(5, 5, 5, 5)
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        outer.addWidget(scroll)
        content = QWidget(scroll)
        scroll.setWidget(content)
        layout = QVBoxLayout(content)
        layout.setContentsMargins(25, 17, 25, 22)
        layout.setSpacing(13)
        header = QHBoxLayout()
        title = QLabel('Bevaring – forberedelse og DIAS' if preserve
                       else 'Rapportering – resultater og faglig vurdering', content)
        title.setStyleSheet('font-size: 22px; font-weight: 600;')
        header.addWidget(title, 1)
        back = QPushButton('Til Startside', content)
        back.clicked.connect(lambda: window.v020_integrated_home())
        header.addWidget(back)
        layout.addLayout(header)
        introductory = QLabel(
            ('Bevaring er en egen beslutning og prosess etter kontroll og faglig vurdering. '
             'En evidenskandidat er ikke en DIAS AIP, og en depotvurdering utfører ikke pakking.'
             if preserve else
             'Les eksisterende kontrollresultater fra Work. Faglige beslutninger for hele uttrekket '
             'og hver arkivdel registreres eksplisitt med bruker, begrunnelse og historikk i '
             'den eksisterende Depotvurdering-fanen.'), content,
        )
        introductory.setWordWrap(True)
        layout.addWidget(introductory)

        summary = QFrame(content)
        summary.setObjectName('v020_a4_work_summary')
        box = QVBoxLayout(summary)
        box.setContentsMargins(13, 12, 13, 12)
        box.setSpacing(9)
        box.addWidget(QLabel('Aktiv jobb og lagret Work-evidens', summary))
        grid = QGridLayout()
        grid.setHorizontalSpacing(18)
        grid.setVerticalSpacing(11)
        fields = (
            ('job', 'Jobb:'), ('work', 'Work operations:'),
            ('report', 'Depotrapport:'), ('technical', 'Teknisk status:'),
            ('professional', 'Faglig depotstatus:'), ('parts', 'Arkivdeler:'),
            ('results', 'Resultatfiler (indeks):'),
        )
        if preserve:
            fields += (('candidate', 'Evidenskandidat:'),)
        self._values = {}
        for i, (key, label) in enumerate(fields):
            grid.addWidget(QLabel(label, summary), i, 0, Qt.AlignmentFlag.AlignTop)
            value = QLabel('Ikke undersøkt', summary)
            value.setObjectName('v020_a4_' + key)
            value.setWordWrap(True)
            value.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            grid.addWidget(value, i, 1)
            self._values[key] = value
        grid.setColumnStretch(1, 1)
        box.addLayout(grid)
        layout.addWidget(summary)

        caution = QLabel(
            'Teknisk fullført ≠ faglig akseptert ≠ beslutning om bevaring ≠ ferdig AIP. '
            'Vurderingshistorikk gjelder kun den uendrede rapportversjonen.', content,
        )
        caution.setWordWrap(True)
        caution.setObjectName('v020_a4_non_approval_note')
        layout.addWidget(caution)
        self.warnings = QLabel(content)
        self.warnings.setWordWrap(True)
        self.warnings.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.warnings.setObjectName('v020_a4_warnings')
        layout.addWidget(self.warnings)

        layout.addWidget(QLabel('Handlinger', content))
        actions = QGridLayout()
        actions.setHorizontalSpacing(12)
        actions.setVerticalSpacing(10)
        if preserve:
            definitions = (
                ('dias_link', 'Kanoniske resultatdata / DIAS-koblingskontroll…',
                 'Eksisterende Qt-dialog. Kontrollen og eventuell evidenskandidat er ikke AIP.'),
                ('review', 'Faglig depotvurdering…',
                 'Åpner eksisterende depotbeslutninger for uttrekk og arkivdeler.'),
                ('legacy', 'DIAS AIP-pakking i eldre GUI…',
                 'Åpner eldre GUI etter bekreftelse. Ingen pakking startes automatisk.'),
                ('reporting', 'Til Rapportering',
                 'Tilbake til rapporter og faglig vurdering.'),
            )
        else:
            definitions = (
                ('results', 'Resultatvisninger…',
                 'Kjente resultater og kilder fra Work.'),
                ('review', 'Faglig depotvurdering – uttrekk / arkivdeler…',
                 'Åpner den etablerte depotvurderingen med brukeridentifisert beslutningshistorikk.'),
                ('generate', 'Lag rapport / samlerapport…',
                 'Eksisterende eksportdialog; ingen ny kontroll utføres.'),
                ('canonical', 'Kanoniske resultatdata / KS-utkast…',
                 'Åpner eksisterende arbeidsdialog, uten automatisk godkjenning.'),
                ('preservation', 'Til Bevaring',
                 'Les status og undersøk DIAS-kobling uten å starte pakking.'),
            )
        for i, (key, text, hint) in enumerate(definitions):
            button = QPushButton(text, content)
            button.setToolTip(hint)
            button.setMinimumHeight(43)
            button.clicked.connect(lambda _checked=False, action=key: self._run_action(action))
            actions.addWidget(button, i // 2, i % 2)
            self._buttons[key] = button
        actions.setColumnStretch(0, 1)
        actions.setColumnStretch(1, 1)
        layout.addLayout(actions)

        footer = QHBoxLayout()
        update = QPushButton('Oppdater status', content)
        update.clicked.connect(self.refresh)
        footer.addWidget(update)
        control = QPushButton('Til Kontroll', content)
        control.clicked.connect(lambda: window.v020_show_control_page())
        footer.addWidget(control)
        footer.addStretch()
        layout.addLayout(footer)
        layout.addStretch(1)
        # Do not scan Work until the page becomes visible or the user refreshes.

    def refresh(self):
        active_id = getattr(self.window, '_active_id', None)
        job = None
        error = ''
        if active_id:
            try:
                job = self.window.api.job_details(active_id).job
            except (AttributeError, KeyError, ValueError, RuntimeError) as exc:
                error = 'Aktiv jobb kan ikke leses: ' + str(exc)
        try:
            snapshot = inspect_production_evidence(job)
        except (OSError, ValueError, RuntimeError) as exc:
            # No exception in read-only status may cause an automatic retry or
            # write; preserve the problem for the human operator.
            snapshot = inspect_production_evidence(None)
            error = 'Kunne ikke lese Work-status: ' + str(exc)
        self._snapshot = snapshot
        self._values['job'].setText(
            (snapshot.job_id + ' – ' + snapshot.job_name) if snapshot.has_job
            else 'Ingen aktiv jobb valgt'
        )
        self._values['work'].setText(str(snapshot.work) if snapshot.work else 'Ikke angitt')
        self._values['report'].setText(str(snapshot.depot_report) if snapshot.depot_report
                                       else 'Ingen gyldig depotrapport funnet')
        self._values['technical'].setText(snapshot.technical_status)
        self._values['professional'].setText(
            snapshot.professional_status +
            (f' ({snapshot.professional_history} historiske vurderinger)'
             if snapshot.professional_history else '')
        )
        self._values['parts'].setText(
            ('Ukjent' if snapshot.archive_parts is None else
             f'{snapshot.reviewed_parts} av {snapshot.archive_parts} med lagret vurdering')
        )
        self._values['results'].setText(str(snapshot.result_files))
        if self.preserve:
            self._values['candidate'].setText(snapshot.candidate_status)
        notes = ([error] if error else []) + list(snapshot.warnings)
        self.warnings.setText('Merknader: ' + ' | '.join(notes) if notes else
                              'Ingen nye merknader. Dette innebærer ikke faglig godkjenning.')
        for key, button in self._buttons.items():
            button.setEnabled(snapshot.has_job if key not in ('reporting', 'preservation')
                              else True)

    def _run_action(self, action: str):
        if action == 'reporting':
            self.window.v020_show_reporting_page()
            return
        if action == 'preservation':
            self.window.v020_show_preservation_page()
            return
        if not self._snapshot or not self._snapshot.has_job:
            QMessageBox.information(self, 'Velg jobb', 'Velg en aktiv jobb i Kontroll først.')
            return
        # Prevent concurrent report/decision/preservation actions while a job
        # may still be modifying Work. All actual writes stay in mature dialogs.
        if getattr(self.window, '_worker', None) is not None or self.window.api.running:
            QMessageBox.warning(self, 'Pågående kjøring',
                                'Avslutt pågående kjøring før vurdering eller rapportering.')
            return
        if action == 'results':
            self.window._a12_open_result_center()
        elif action == 'review':
            self.window._a12_open_result_center(depot=True)
        elif action == 'generate':
            self.window._a12_open_selected_report()
        elif action in ('canonical', 'dias_link'):
            link = getattr(self.window, '_a15_canonical_action', None)
            if link is None:
                QMessageBox.warning(self, 'Kanoniske resultatdata',
                                    'Eksisterende Qt-koblingskontroll er ikke tilgjengelig.')
                return
            link.trigger()
        elif action == 'legacy':
            reply = QMessageBox.question(
                self, 'DIAS AIP-pakking i eldre GUI',
                'DIAS AIP-pakking ligger fortsatt i eldre DWM-grensesnitt. '
                'Det åpnes som et separat program; ingen AIP opprettes ved å åpne det.\n\n'
                'Start eldre GUI?',
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if reply == QMessageBox.StandardButton.Yes:
                self.window._open_legacy()
        self.refresh()


class ReportingPage(_ProductionEvidencePage):
    def __init__(self, window):
        super().__init__(window, preserve=False)


class PreservationPage(_ProductionEvidencePage):
    def __init__(self, window):
        super().__init__(window, preserve=True)
