"""v0.2.3-a1: line-by-line Arkade finding inspection in the existing KS UI.

The Basic-mode "Kvalitetssikring / rapport" button uses this dialog too.
Inspect first, then return to the unchanged professional review editor.
"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QThread, Signal, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QApplication, QDialog, QHBoxLayout, QLabel, QMessageBox,
    QPlainTextEdit, QPushButton, QSplitter, QTreeWidget, QTreeWidgetItem,
    QVBoxLayout, QWidget,
)

from app.ks_inspector_v023_a1 import arkade_occurrences, inspect_xml_line
from app.ks_workshop_v022_a12 import WorkshopError, work_file
from gui_qt.ks_workshop_v022_a12 import KsWorkshopDialog as _A12KsWorkshopDialog


class _XmlReader(QThread):
    completed = Signal(dict)
    failed = Signal(str)

    def __init__(self, work: Path, row: dict, parent=None):
        super().__init__(parent)
        self.work = work
        self.row = dict(row)

    def run(self):
        try:
            result = inspect_xml_line(self.work, self.row,
                                      cancel=self.isInterruptionRequested)
        except (OSError, RuntimeError, ValueError) as exc:
            self.failed.emit(str(exc))
        else:
            self.completed.emit(result)


class OccurrenceInspectDialog(QDialog):
    """No new test runs, XML writes, expert decisions, or implicit approvals."""

    def __init__(self, work: str | Path, snapshot: dict,
                 finding: dict | None = None, *, test_id: str | None = None, parent=None):
        super().__init__(parent)
        self.work = Path(work).resolve(strict=True)
        self.data = arkade_occurrences(self.work, snapshot, finding, test_id=test_id)
        self.rows = self.data["rows"]
        self._reader = None
        self._active_line = 0
        self.setWindowTitle("Inspiser Arkade-funn – kilde og XML (kun lesing)")
        self.setMinimumSize(780, 540)
        screen = (parent.screen() if parent is not None else QApplication.primaryScreen())
        rect = screen.availableGeometry() if screen else None
        self.resize(min(1380, max(800, rect.width() - 80)) if rect else 1200,
                    min(860, max(550, rect.height() - 100)) if rect else 750)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        title = QLabel(f"Arkade 5 / {self.data['test_id']} – originale feillinjer")
        title.setStyleSheet("font-weight:bold; font-size:16px")
        layout.addWidget(title)
        counts = sum(g["reported_count"] or 0 for g in self.data["groups"])
        intro = QLabel(
            f"{len(self.data['groups'])} rapporterte avvikslinjer · {counts} rapporterte "
            f"forekomster · {len(self.rows)} dokumenterte XML-linjereferanser.\n"
            "Dette er Arkades lagrede funn, ikke nye tester. Velg en linje og trykk "
            "«Vis XML-kontekst» for å kontrollere faktisk arkivobjekt i Source. "
            "Tilbake i KS-arbeidsflaten kan du registrere faglig vurdering.")
        intro.setWordWrap(True)
        layout.addWidget(intro)

        splitter = QSplitter(Qt.Orientation.Vertical)
        splitter.setChildrenCollapsible(False)
        table_widget = QWidget()
        table_layout = QVBoxLayout(table_widget)
        table_layout.setContentsMargins(0, 0, 0, 0)
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["Nr.", "Arkade-funn", "Arkivdel fra Arkade", "XML-fil", "Linje", "Objekt-ID i XML"])
        self.tree.setRootIsDecorated(False)
        self.tree.setUniformRowHeights(True)
        self.tree.setAlternatingRowColors(True)
        self.tree.setSelectionMode(QTreeWidget.SelectionMode.SingleSelection)
        for col, width in enumerate((50, 335, 220, 165, 95, 230)):
            self.tree.setColumnWidth(col, width)
        self.tree.header().setStretchLastSection(False)
        for i, row in enumerate(self.rows):
            item = QTreeWidgetItem([str(i + 1), row['message'],
                                    row['archive_part_title'] or row['archive_part_id'],
                                    row['file'] or '(mangler)', str(row['line']), 'Ikke undersøkt'])
            item.setData(0, Qt.ItemDataRole.UserRole, i)
            item.setToolTip(1, row['message'])
            item.setToolTip(2, row['archive_part_id'])
            self.tree.addTopLevelItem(item)
        table_layout.addWidget(self.tree)
        splitter.addWidget(table_widget)

        detail_widget = QWidget()
        detail_layout = QVBoxLayout(detail_widget)
        detail_layout.setContentsMargins(0, 0, 0, 0)
        self.detail = QPlainTextEdit()
        self.detail.setReadOnly(True)
        self.detail.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        detail_layout.addWidget(self.detail)
        splitter.addWidget(detail_widget)
        splitter.setSizes([350, 300])
        layout.addWidget(splitter, 1)

        actions = QHBoxLayout()
        self.inspect = QPushButton("Vis XML-kontekst for valgt forekomst")
        self.inspect.clicked.connect(self._inspect_selected)
        actions.addWidget(self.inspect)
        open_evidence = QPushButton("Åpne Arkades originalgrunnlag")
        open_evidence.clicked.connect(self._open_evidence)
        actions.addWidget(open_evidence)
        actions.addStretch(1)
        back = QPushButton("Tilbake til KS-vurdering")
        back.clicked.connect(self.accept)
        actions.addWidget(back)
        layout.addLayout(actions)
        self.tree.currentItemChanged.connect(self._selected)
        self.tree.itemDoubleClicked.connect(lambda _item, _column: self._inspect_selected())
        if self.rows:
            self.tree.setCurrentItem(self.tree.topLevelItem(0))
        else:
            self.inspect.setEnabled(False)
            messages = []
            for group in self.data['groups']:
                messages.append(group['message'] + '\n' +
                                ('Arkade har ikke levert konkrete XML-linjer. ' if group['aggregate_only'] else '') +
                                'Kilde: ' + self.data['source_ref'])
            self.detail.setPlainText('\n\n'.join(messages) or
                                     'Ingen originale feilobservasjoner knyttet til valgt test.')

    def _selected(self, current, _previous):
        if current is None:
            return
        i = current.data(0, Qt.ItemDataRole.UserRole)
        if type(i) is not int or not 0 <= i < len(self.rows):
            return
        row = self.rows[i]
        group = self.data['groups'][row['group_index']]
        detail = (
            'KILDE: Arkade 5 (lagret, SHA-256-verifisert resultat)\n'
            f'Test: {row["test_id"]} · {row["message"]}\n'
            f'Arkivdel: {row["archive_part_title"] or "Ikke oppgitt"}\n'
            f'Arkivdel systemID: {row["archive_part_id"] or "Ikke oppgitt"}\n'
            f'XML-kilde: {row["file"] or "Ikke oppgitt"} · Linje: {row["line"]}\n'
            f'Antall rapportert for feillinjen: {group["reported_count"] if group["reported_count"] is not None else "Ukjent"}\n'
            f'Antall kildeankre: {group["anchors"]}\n'
            f'Importert evidens: {self.data["source_ref"]}\n'
            f'SHA-256: {self.data["source_sha256"]}\n\n'
            'Velg «Vis XML-kontekst» for å åpne linjen og det aktuelle objektet '
            'fra jobbens registrerte Source. Ingen data endres.')
        if group['count_mismatch']:
            detail += ('\n\nMERK: Rapportert antall og antall dokumenterte linjer er ulike. '
                       'Det mangler dermed en fullstendig forekomstliste i denne importen.')
        self.detail.setPlainText(detail)
        self.inspect.setEnabled(self._reader is None)

    def _inspect_selected(self):
        if self._reader is not None:
            return
        item = self.tree.currentItem()
        if item is None:
            return
        i = item.data(0, Qt.ItemDataRole.UserRole)
        if type(i) is not int or not 0 <= i < len(self.rows):
            return
        self._active_line = self.rows[i]['line']
        self.inspect.setEnabled(False)
        self.tree.setEnabled(False)
        self.detail.appendPlainText("\nLeser XML fra Source (uten å endre filer)…")
        self._reader = _XmlReader(self.work, self.rows[i])
        self._reader.completed.connect(self._reader_completed)
        self._reader.failed.connect(self._reader_failed)
        self._reader.finished.connect(self._reader_finished)
        self._reader.start()

    def _reader_completed(self, result: dict):
        if not result.get('available'):
            self.detail.appendPlainText('\n' + result['message'])
            return
        metadata = result.get('metadata') or {}
        out = (f"\nORIGINAL XML FRA SOURCE: {result['source_path']}\n"
               f"Linje: {result['line']}\n"
               f"Objekttype: {metadata.get('object_type') or 'Ikke identifisert'}\n"
               f"Objekt systemID: {metadata.get('system_id') or 'Ikke dokumentert i dette elementet'}\n"
               f"Tittel: {metadata.get('title') or 'Ikke dokumentert'}\n"
               f"Element: {metadata.get('element') or 'Ikke entydig identifisert'}\n"
               f"Verdi: {metadata.get('xml_value') or 'Se XML-tekst'}\n"
               f"XPath: {metadata.get('xpath') or 'Ikke entydig beregnet'}\n"
               f"XML-tolkning: {metadata.get('xml_parse_note') or 'OK / se resultat'}\n\n"
               f"{result['provenance_note']}\n\n"
               + result['excerpt'])
        self.detail.setPlainText(out)
        item = self.tree.currentItem()
        if item is not None and item.text(4) == str(self._active_line):
            item.setText(5, metadata.get('system_id') or 'Ikke identifisert')

    def _reader_failed(self, error: str):
        self.detail.appendPlainText('\nKunne ikke inspisere XML: ' + error)

    def _reader_finished(self):
        self._reader = None
        self.tree.setEnabled(True)
        self.inspect.setEnabled(bool(self.tree.currentItem()))

    def _open_evidence(self):
        try:
            path = work_file(self.work, self.data['source_ref'])
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))
        except (OSError, ValueError) as exc:
            QMessageBox.warning(self, 'Arkade-evidens', str(exc))

    def reject(self):
        self._close_reader()
        super().reject()

    def accept(self):
        self._close_reader()
        super().accept()

    def _close_reader(self):
        if self._reader is not None and self._reader.isRunning():
            self._reader.requestInterruption()
            # The scanner checks interruption regularly and is strictly read-only.
            self._reader.wait()


class KsWorkshopDialog(_A12KsWorkshopDialog):
    """Add evidence inspection to the shared KS dialog used from Basic mode."""

    def _build_findings_tab(self):
        super()._build_findings_tab()
        # The tree lives in a splitter: tab 0 is the finding page.
        page = self.tabs.widget(0)
        self.inspect_finding_button = QPushButton('Inspiser valgt funn – objekter og XML…', page)
        self.inspect_finding_button.setObjectName('v023_a1_inspect_finding')
        self.inspect_finding_button.setToolTip('Se originale Arkade-linjer og åpne tilhørende XML før vurdering')
        page.layout().insertWidget(1, self.inspect_finding_button)
        self.inspect_finding_button.clicked.connect(self._inspect_finding)
        self.findings_tree.itemDoubleClicked.connect(lambda _item, _column: self._inspect_finding())

    def _build_tests_tab(self):
        super()._build_tests_tab()
        page = self.tabs.widget(1)
        self.inspect_test_button = QPushButton('Inspiser Arkade-test – konkrete XML-forekomster…', page)
        self.inspect_test_button.setObjectName('v023_a1_inspect_test')
        page.layout().insertWidget(2, self.inspect_test_button)
        self.inspect_test_button.clicked.connect(self._inspect_test)
        # Arkade tests now inspect individual findings; all other double-clicks
        # retain the original a12 read-only source-file opening.
        self.tests_tree.itemDoubleClicked.disconnect()
        self.tests_tree.itemDoubleClicked.connect(self._test_double_clicked)

    def _inspect_finding(self):
        row = next((r for r in self.all_findings if r['finding_key'] == self._selected_key), None)
        if row is None:
            QMessageBox.information(self, 'Inspiser funn', 'Velg først et konkret funn.')
            return
        if str(row.get('source') or '') != 'Arkade 5':
            QMessageBox.information(self, 'Inspiser funn',
                'Denne første forekomstvisningen åpner linjebundet Arkade 5-evidens. '
                'Andre funn har fortsatt sine eksisterende kilde- og resultatvisninger.')
            return
        self._show_inspector(finding=row)

    def _inspect_test(self):
        item = self.tests_tree.currentItem()
        if item is None:
            QMessageBox.information(self, 'Inspiser test', 'Velg en test først.')
            return
        if item.text(0) != 'Arkade 5 Noark' or item.text(3).upper() != 'FEIL':
            QMessageBox.information(self, 'Inspiser test',
                'Velg en Arkade 5-test med FEIL for kildebundet forekomstvisning. '
                'For andre tester kan du dobbeltklikke for å åpne den lagrede evidensfilen.')
            return
        self._show_inspector(test_id=item.text(1))

    def _test_double_clicked(self, item, _column):
        if item.text(0) == 'Arkade 5 Noark' and item.text(3).upper() == 'FEIL':
            self._show_inspector(test_id=item.text(1))
        else:
            self._open_relative(item.data(0, Qt.ItemDataRole.UserRole))

    def _show_inspector(self, finding: dict | None = None, test_id: str | None = None):
        try:
            dialog = OccurrenceInspectDialog(self.work, self.snapshot,
                                             finding=finding, test_id=test_id, parent=self)
            dialog.exec()
        except (OSError, RuntimeError, ValueError) as exc:
            QMessageBox.warning(self, 'Inspiser Arkade-funn', str(exc))
