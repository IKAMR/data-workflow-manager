"""Read-only Depotkontroll tab attached to the existing Resultatvisninger.

This is a navigation and evidence projection, not another review ledger or a
validator. File hashing and large-report streaming run off the Qt UI thread.
"""
from __future__ import annotations

from queue import Empty, Queue
from threading import Thread

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QHBoxLayout, QLabel, QMessageBox, QPlainTextEdit, QPushButton,
    QSplitter, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget,
)

from app.depot_process_v027_a1 import DepotProcessRow, build_depot_process_rows
from app.result_tabs_v020_a6 import grouped_result_titles


def _load_in_worker(snapshots, queue: Queue) -> None:
    try:
        queue.put(('rows', build_depot_process_rows(snapshots)))
    except Exception as exc:
        # The worker never uses Qt widgets. An error cannot be mistaken for
        # successful/complete evidence.
        queue.put(('error', str(exc)))


class DepotProcessPanel(QWidget):
    """One overview for Work evidence, individual findings and depot decisions."""

    def __init__(self, viewer, main_window):
        super().__init__(viewer.tabs)
        self.viewer = viewer
        self.main_window = main_window
        self._rows: tuple[DepotProcessRow, ...] = ()
        self._queue: Queue | None = None
        self._thread: Thread | None = None
        self._pending = False
        self._requested_snapshot_keys: tuple = ()

        layout = QVBoxLayout(self)
        title = QLabel('Depotkontroll – teknikk, evidens, avvik og faglig vurdering')
        title.setStyleSheet('font-weight: bold; font-size: 15px;')
        layout.addWidget(title)
        self.note = QLabel(
            'Teknisk OK, koblet evidens, behandlet avvik og depotets beslutning er '
            'ulike statuser. Antall funn vises bare når det komplette A260-registeret '
            'er kildeverifisert. Ingen automatisk godkjenning.')
        self.note.setWordWrap(True)
        layout.addWidget(self.note)

        controls = QHBoxLayout()
        self.refresh_button = QPushButton('Oppdater fra Work')
        self.refresh_button.clicked.connect(self.refresh_from_work)
        controls.addWidget(self.refresh_button)
        self.ks_button = QPushButton('Åpne Veiledet KS…')
        self.ks_button.clicked.connect(self._open_guided_ks)
        self.ks_button.setToolTip('Bruker eksisterende Veiledet KS for aktiv jobb i hovedvinduet')
        controls.addWidget(self.ks_button)
        self.depot_button = QPushButton('Åpne Depotvurdering…')
        self.depot_button.clicked.connect(self._open_depot_review)
        controls.addWidget(self.depot_button)
        self.technical_button = QPushButton('Tekniske kontroller')
        self.technical_button.clicked.connect(self._open_technical)
        controls.addWidget(self.technical_button)
        controls.addStretch(1)
        layout.addLayout(controls)

        self.info = QLabel('Velg fanen for å lese resultatgrunnlaget fra valgt Work.')
        self.info.setWordWrap(True)
        layout.addWidget(self.info)
        splitter = QSplitter(Qt.Orientation.Vertical, self)
        self.tree = QTreeWidget(splitter)
        self.tree.setHeaderLabels((
            'Uttrekk / arkivdel', 'Kjøring', 'Teknisk', 'Evidens A230',
            'Funn A260', 'Faglig depotvurdering',
        ))
        self.tree.setAlternatingRowColors(True)
        self.tree.setRootIsDecorated(True)
        self.tree.setUniformRowHeights(True)
        self.tree.setColumnWidth(0, 265)
        self.tree.setColumnWidth(1, 110)
        self.tree.setColumnWidth(2, 115)
        self.tree.setColumnWidth(3, 275)
        self.tree.setColumnWidth(4, 195)
        self.tree.setColumnWidth(5, 225)
        self.tree.itemSelectionChanged.connect(self._show_selected)
        splitter.addWidget(self.tree)
        self.details = QPlainTextEdit(splitter)
        self.details.setReadOnly(True)
        self.details.setPlaceholderText('Velg et uttrekk eller en arkivdel for kildegrunnlag og advarsler.')
        splitter.addWidget(self.details)
        splitter.setStretchFactor(0, 5)
        splitter.setStretchFactor(1, 2)
        splitter.setSizes((580, 220))
        layout.addWidget(splitter, 1)

        self._timer = QTimer(self)
        self._timer.setInterval(125)
        self._timer.timeout.connect(self._poll)
        self.ks_button.setEnabled(False)
        self.depot_button.setEnabled(False)
        self.technical_button.setEnabled(False)

    def _snapshot_keys(self) -> tuple:
        return tuple((str(shot.job.job_uid), str(shot.job.work))
                     for shot in getattr(self.viewer, '_snapshots', ()))

    def refresh_from_work(self):
        if self._thread is not None and self._thread.is_alive():
            self._pending = True
            self.info.setText('Et nytt utvalg er registrert. Oppdaterer når pågående innlesing er ferdig.')
            return
        snapshots = tuple(getattr(self.viewer, '_snapshots', ()))
        self._requested_snapshot_keys = self._snapshot_keys()
        if not snapshots:
            self._rows = ()
            self.tree.clear()
            self.details.clear()
            self.info.setText('Ingen tilgjengelige Work-jobber er valgt i Resultatvisninger.')
            self._update_buttons()
            return
        self.refresh_button.setEnabled(False)
        self.info.setText('Kontrollerer depotrapporter og evidens i bakgrunnen. Store Work kan ta tid.')
        queue: Queue = Queue(maxsize=1)
        self._queue = queue
        self._thread = Thread(target=_load_in_worker, args=(snapshots, queue), daemon=True)
        self._thread.start()
        self._timer.start()

    def _poll(self):
        if self._queue is None:
            self._timer.stop()
            return
        try:
            kind, data = self._queue.get_nowait()
        except Empty:
            return
        self._timer.stop()
        self._queue = None
        self._thread = None
        self.refresh_button.setEnabled(True)
        if self._pending or self._snapshot_keys() != self._requested_snapshot_keys:
            self._pending = False
            self.refresh_from_work()
            return
        if kind == 'error':
            self.tree.clear()
            self.details.clear()
            self.info.setText('Kontrollgrunnlaget kunne ikke leses: ' + str(data))
            self._rows = ()
            self._update_buttons()
            return
        self._rows = tuple(data)
        self._render()

    def _render(self):
        self.tree.clear()
        parents = {}
        warnings = 0
        for index, row in enumerate(self._rows):
            item = QTreeWidgetItem((
                (row.job_id + ' – ' + row.job_name if row.scope == 'uttrekk'
                 else row.title + ' [' + row.system_id + ']'),
                row.run_status, row.technical, row.evidence, row.findings, row.assessment,
            ))
            item.setData(0, Qt.ItemDataRole.UserRole, index)
            for col in range(item.columnCount()):
                item.setToolTip(col, item.text(col))
            warnings += bool(row.warnings)
            if row.scope == 'uttrekk':
                self.tree.addTopLevelItem(item)
                parents[row.job_uid] = item
            else:
                parent = parents.get(row.job_uid)
                if parent is not None:
                    parent.addChild(item)
                else:
                    self.tree.addTopLevelItem(item)
        self.tree.expandAll()
        jobs = sum(row.scope == 'uttrekk' for row in self._rows)
        parts = len(self._rows) - jobs
        self.info.setText(
            f'{jobs} uttrekk, {parts} arkivdeler. {warnings} omfang med advarsler. '
            'Funn A260 gjelder verifisert register fra kjøringen, ikke oppdatert KS-fremdrift. '
            'Manglende data vises som ukjent, aldri som 0 eller godkjent.')
        if self.tree.topLevelItemCount():
            self.tree.setCurrentItem(self.tree.topLevelItem(0))
        self._update_buttons()

    def _current(self) -> DepotProcessRow | None:
        item = self.tree.currentItem()
        if item is None:
            return None
        index = item.data(0, Qt.ItemDataRole.UserRole)
        return self._rows[index] if isinstance(index, int) and 0 <= index < len(self._rows) else None

    def _show_selected(self):
        row = self._current()
        if row is None:
            self.details.clear()
            self._update_buttons()
            return
        lines = [
            f'Jobb: {row.job_id} – {row.job_name}',
            f'Jobb-UID: {row.job_uid}',
            f'Omfang: {row.scope} – {row.title}',
            f'System-ID: {row.system_id or "(hele uttrekket)"}',
            f'Jobbens kjørestatus: {row.run_status}',
            f'Teknisk status i lagret depotrapport: {row.technical}',
            f'Evidensdekning A230: {row.evidence}',
            f'Funnregister A260: {row.findings}',
            f'Faglig depotvurdering: {row.assessment}',
            f'Grunnlag: {row.basis}',
            f'Work: {row.work}',
            f'Originalrapport: {row.report_path if row.report_path else "ikke tilgjengelig"}',
        ]
        if row.archive_part_count is not None:
            lines.append(f'Arkivdeler i depotrapport: {row.archive_part_count}')
        if row.warnings:
            lines.extend(('', 'Kontrollpunkter / advarsler:', *('- ' + w for w in row.warnings)))
        lines.extend((
            '',
            'Lagrede rapporter og A230-evidens kan stamme fra ulike kjøringer i samme Work.',
            'En teknisk fullført arbeidsflyt er ikke et depotvedtak.',
            'Ingen status endres fra denne oversikten.',
        ))
        self.details.setPlainText('\n'.join(lines))
        self._update_buttons()

    def _update_buttons(self):
        row = self._current()
        self.ks_button.setEnabled(bool(row))
        self.depot_button.setEnabled(bool(row and row.report_path is not None))
        self.technical_button.setEnabled(bool(row))

    def _open_guided_ks(self):
        row = self._current()
        if row is None:
            return
        if row.job_id != getattr(self.main_window, '_active_id', None):
            QMessageBox.information(self, 'Veiledet KS',
                                    'Velg samme jobb i DWM-hovedvinduet før Veiledet KS åpnes.')
            return
        # The existing entry point checks active runs and preserves the a13 ledger.
        self.main_window._a12_open_ks_workshop()

    def _open_depot_review(self):
        row = self._current()
        if row is None:
            return
        panel = getattr(self.viewer, '_a2_panel', None)
        if panel is None:
            QMessageBox.information(self, 'Depotvurdering', 'Depotvurdering er ikke tilgjengelig.')
            return
        self.viewer.show_depot_review()
        item = getattr(panel, '_items', {}).get(row.key)
        if item is not None:
            panel.tree.setCurrentItem(item)
        else:
            QMessageBox.information(self, 'Depotvurdering',
                                    'Valgt omfang mangler i den ordinære depotvurderingen. '
                                    'Kontroller om depotrapporten er for stor eller om system-ID mangler.')

    def _open_technical(self):
        page = getattr(self.viewer, '_pages', {}).get('Tekniske kontroller')
        if page is not None:
            self.viewer.tabs.setCurrentWidget(page)


def install_depot_process_tab(viewer, main_window):
    """Install once on a real Resultatvisninger window, retaining its API."""
    if getattr(viewer, '_v027_a1_depot_process', None) is not None:
        return viewer._v027_a1_depot_process
    if not hasattr(viewer, 'tabs') or not hasattr(viewer, '_snapshots'):
        return None
    panel = DepotProcessPanel(viewer, main_window)
    viewer.tabs.addTab(panel, 'Depotkontroll')
    viewer._v027_a1_depot_process = panel
    # The grouping was built when the inherited Resultatvisninger opened.
    # Refresh it so this new tab is reachable without exposing the hidden tabbar.
    nav = getattr(viewer, '_v020_a6_navigation', None)
    if nav is not None:
        nav.groups = grouped_result_titles(
            viewer.tabs.tabText(i) for i in range(viewer.tabs.count()))
        nav.sync_from_original(viewer.tabs.currentIndex())
    viewer.tabs.currentChanged.connect(
        lambda index: panel.refresh_from_work()
        if viewer.tabs.widget(index) is panel else None)
    return panel


def install_depot_process_results_class(main_window):
    """Extend the existing Qt result class only after the real GUI is ready.

    The headless startup/test window does not load this module. The old result
    class remains the superclass and every existing tab/action stays intact.
    """
    from gui_qt import result_center_v0110_a4 as source
    old_class = source.ResultCenterWindow
    if getattr(old_class, '_v027_a1_depot_installed', False):
        return old_class

    class ResultCenterWindow(old_class):
        _v027_a1_depot_installed = True

        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            install_depot_process_tab(self, main_window)

    source.ResultCenterWindow = ResultCenterWindow
    return ResultCenterWindow
