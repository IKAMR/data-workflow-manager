"""Opt-in canonical Work projection dialog for the existing DWM Qt frontend.

No changes to the runner, saved job, raw evidence or Source. Users explicitly
choose each evidence file and confirm before a canonical snapshot is replaced.
"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QObject, QThread, Signal
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QTreeWidget, QTreeWidgetItem,
    QHeaderView, QPushButton, QMessageBox, QPlainTextEdit, QFileDialog,
)

from noark5_workflow.analysis.canonical_work_adapter import (
    discover_work_sources, canonical_report,
)
from noark5_workflow.analysis.canonical_results import build_canonical_results

from app.canonical_selection_v0115_a3 import ALLOWED, selected_sources
from noark5_workflow.analysis.canonical_context_v0115_a4 import build_context
from noark5_workflow.analysis.canonical_external_v0115_a5 import discover_external_candidates


class _Task(QObject):
    finished = Signal(object, object)

    def __init__(self, work: Path, selection: dict | None):
        super().__init__()
        self.work = work
        self.selection = selection

    def run(self):
        try:
            if self.selection is None:
                result = discover_work_sources(self.work)
            elif '__a5_discover_external' in self.selection:
                result = {'a5_candidates': discover_external_candidates(self.work)}
            elif '__a4_context' in self.selection:
                context = build_context(self.work, **self.selection['__a4_context'])
                result = {'a4_context': context['summary']}
            else:
                document = build_canonical_results(self.work, **self.selection,
                                                   write=True)
                result = canonical_report(document)
            self.finished.emit(result, None)
        except Exception as exc:
            self.finished.emit(None, str(exc))


class CanonicalResultsDialog(QDialog):
    def __init__(self, work: str | Path, parent=None):
        super().__init__(parent)
        self.work = Path(work)
        self.setWindowTitle('Kanoniske resultatdata - Work')
        self.resize(940, 680)
        self.setMinimumSize(660, 440)
        self._thread = None
        self._task = None
        layout = QVBoxLayout(self)
        heading = QLabel('Resultatkilder i valgt Work')
        layout.addWidget(heading)
        work_label = QLabel(str(self.work))
        work_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        work_label.setWordWrap(True)
        layout.addWidget(work_label)
        self.tree = QTreeWidget(self)
        self.tree.setHeaderLabels(['Bruk', 'Kilde', 'Status', 'Tester / bytes'])
        self.tree.setRootIsDecorated(False)
        self.tree.setSortingEnabled(True)
        self.tree.header().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.tree.header().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        layout.addWidget(self.tree, 2)
        note = QLabel('Kilder velges manuelt. Eldre og ikke-stottede kilder tas ikke med. '
                      'Dette er en indeks over evidens, ikke en depotgodkjenning.')
        note.setWordWrap(True)
        layout.addWidget(note)
        self.report = QPlainTextEdit(self)
        self.report.setReadOnly(True)
        self.report.setPlaceholderText('Resultatdekning vises etter lagring.')
        layout.addWidget(self.report, 1)
        buttons = QHBoxLayout()
        self.refresh_button = QPushButton('Finn resultatkilder')
        self.refresh_button.clicked.connect(self.refresh)
        self.external_discover_button = QPushButton('Finn ekstern evidens')
        self.external_discover_button.clicked.connect(lambda: self._start({'__a5_discover_external': True}))
        self.build_button = QPushButton('Opprett resultatindeks...')
        self.build_button.clicked.connect(self.create_snapshot)
        self.context_button = QPushButton('Koble vurderinger / ekstern evidens...')
        self.context_button.clicked.connect(self.create_context)
        self.close_button = QPushButton('Lukk')
        self.close_button.clicked.connect(self.reject)
        buttons.addWidget(self.refresh_button)
        buttons.addWidget(self.external_discover_button)
        buttons.addWidget(self.build_button)
        buttons.addWidget(self.context_button)
        buttons.addStretch(1)
        buttons.addWidget(self.close_button)
        layout.addLayout(buttons)
        self._busy = False
        self.refresh()

    def _set_busy(self, busy: bool):
        self._busy = busy
        self.refresh_button.setEnabled(not busy)
        self.build_button.setEnabled(not busy)
        self.external_discover_button.setEnabled(not busy)
        self.context_button.setEnabled(not busy)
        self.close_button.setEnabled(not busy)
        self.tree.setEnabled(not busy)

    def _start(self, selection: dict | None):
        if self._busy:
            return
        self._set_busy(True)
        self.report.setPlainText('Leser Work...' if selection is None else 'Oppretter resultatindeks...')
        thread = QThread(self)
        task = _Task(self.work, selection)
        task.moveToThread(thread)
        thread.started.connect(task.run)
        task.finished.connect(self._complete)
        task.finished.connect(thread.quit)
        thread.finished.connect(task.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(self._clear_thread)
        self._thread = thread
        self._task = task
        thread.start()

    def _clear_thread(self):
        self._thread = None
        self._task = None
        self._set_busy(False)

    def _complete(self, result, error):
        if error:
            self.report.setPlainText('FEIL: ' + error)
            QMessageBox.warning(self, 'Kanoniske resultatdata', error)
            return
        if 'a5_candidates' in result:
            rows = result['a5_candidates']
            lines = [f'Eksterne evidenskandidater funnet: {len(rows)}',
                     'Ingen filer er valgt eller analysert. Velg dem eksplisitt ved kobling:']
            lines.extend('  ' + x['path'] for x in rows)
            if len(rows) >= 150:
                lines.append('Listen er avgrenset til 150 filer.')
            self.report.setPlainText('\n'.join(lines))
        elif 'a4_context' in result:
            totals = result['a4_context']
            self.report.setPlainText(
                'Kanonisk kontekstindeks lagret: noark5_evidence/canonical-context.json\n'
                f"Faglige vurderinger: {totals['human_assessments']}\n"
                f"Eksterne evidensfiler (ikke tolket): {totals['external_unparsed_files']}\n"
                f"Vurderinger uten test-ID-kobling: {totals['unlinked_assessments']}\n"
                f"Faglig ikke-verifiserte vurderinger: {totals['unverified_assessments']}\n"
                f"Siegfried JSON identifisert: {totals['identified_siegfried_files']}\n"
                'Testreferanse er IKKE en faglig verifisert M-ID-kobling.\n'
                'Formatidentifikasjon er IKKE testgodkjenning eller depotaksept.')
        elif 'candidates' in result:
            self.tree.clear()
            for category, candidates in result['candidates'].items():
                for candidate in candidates:
                    status = candidate['status']
                    row = QTreeWidgetItem(['', candidate['path'], status,
                        str(candidate.get('tests', candidate.get('bytes', '')))])
                    row.setData(0, Qt.ItemDataRole.UserRole,
                                (category, candidate['path'], status))
                    row.setFlags(row.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                    row.setCheckState(0, Qt.CheckState.Unchecked)
                    if status not in ALLOWED.get(category, set()):
                        row.setDisabled(True)
                    self.tree.addTopLevelItem(row)
            self.report.setPlainText(
                'Velg kilder og trykk Opprett resultatindeks. '\
                'Ingen kilder er valgt automatisk.')
        else:
            lines = [f"Observasjoner: {result['observations']}",
                     f"Jobb-ID: {result['extraction_stable_id']}",
                     'Kildedekning (ingen summering av arkivdata):']
            for row in result['source_coverage']:
                lines.append(f"  {row['source_kind']}: {row['observations']} "
                             f"(tilgjengelig {row['available']}, "
                             f"mangler {row['unavailable']}, ukjent {row['unknown']})")
            lines.append('Lagret: noark5_evidence/canonical-results.json')
            self.report.setPlainText('\n'.join(lines))

    def refresh(self):
        self._start(None)

    def create_snapshot(self):
        rows = []
        for i in range(self.tree.topLevelItemCount()):
            row = self.tree.topLevelItem(i)
            category, path, status = row.data(0, Qt.ItemDataRole.UserRole)
            rows.append((category, path,
                         row.checkState(0) == Qt.CheckState.Checked, status))
        try:
            selection = selected_sources(rows)
        except ValueError as exc:
            QMessageBox.information(self, 'Velg kilder', str(exc))
            return
        target = self.work / 'noark5_evidence' / 'canonical-results.json'
        replace = target.is_file()
        message = ('Erstatt eksisterende kanonisk resultatindeks?' if replace else
                   'Opprett kanonisk resultatindeks fra de valgte kildene?')
        message += '\n\nOriginale resultater og Source endres ikke.'
        if QMessageBox.question(self, 'Bekreft resultatindeks', message,
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No) != QMessageBox.StandardButton.Yes:
            return
        self._start(selection)

    def create_context(self):
        """Require explicit operator selection; no implicit ingestion of source XML."""
        canonical = self.work / 'noark5_evidence' / 'canonical-results.json'
        if not canonical.is_file():
            QMessageBox.information(self, 'Kanonisk resultatindeks',
                                    'Opprett resultatindeksen foerst.')
            return
        assessment_default = self.work / 'noark5_evidence' / 'experience_assessments.json'
        selected, _ = QFileDialog.getOpenFileName(
            self, 'Velg faglige vurderinger (valgfritt)',
            str(assessment_default if assessment_default.is_file() else self.work / 'noark5_evidence'),
            'JSON (*.json);;Alle filer (*)',
            options=QFileDialog.Option.DontUseNativeDialog)
        external, _ = QFileDialog.getOpenFileNames(
            self, 'Velg eksterne evidensfiler i Work (valgfritt)',
            str(self.work), 'Alle filer (*)',
            options=QFileDialog.Option.DontUseNativeDialog)
        if not selected and not external:
            return
        if QMessageBox.question(
                self, 'Koble evidens til kanonisk indeks',
                'Opprett/erstatt en separat kontekstindeks for de valgte filene?\n'
                'Kildene blir ikke endret. Bare gjenkjent Siegfried JSON tolkes som formatidentifikasjon; Arkade-filer uten kjent skjema beholdes som referanser.',
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No) != QMessageBox.StandardButton.Yes:
            return
        self._start({'__a4_context': {
            'assessments_path': selected or None,
            'external_paths': tuple(external),
        }})

    def reject(self):
        if not self._busy:
            super().reject()

    def closeEvent(self, event):
        if self._busy:
            event.ignore()
        else:
            super().closeEvent(event)


def install_canonical_results_menu(window):
    """Attach an opt-in GUI action without changing established result widgets."""
    menu = next((a.menu() for a in window.menuBar().actions()
                 if a.menu() is not None and a.text().replace('&', '') == 'Rapport'), None)
    if menu is None:
        return False
    action = QAction('Kanoniske resultatdata...', window)
    def launch():
        if getattr(window, '_worker', None) is not None:
            QMessageBox.warning(window, 'Pågående kjøring',
                                'Avslutt kontrollkjøringen før resultatindeksen bygges.')
            return
        active = getattr(window, '_active_id', None)
        if not active:
            QMessageBox.information(window, 'Velg jobb', 'Velg en eksisterende jobb først.')
            return
        try:
            job = window.api.job_details(active).job
            work = getattr(job, 'effective_work_operations', None)
            if not work:
                raise ValueError('Jobben mangler valgt Work operations.')
        except Exception as exc:
            QMessageBox.warning(window, 'Arbeidsområde', str(exc))
            return
        dialog = CanonicalResultsDialog(work, window)
        # Modal ownership: no dangling child or QThread when parent window closes.
        dialog.exec()
    action.triggered.connect(launch)
    menu.addAction(action)
    window._a15_canonical_action = action
    return True
