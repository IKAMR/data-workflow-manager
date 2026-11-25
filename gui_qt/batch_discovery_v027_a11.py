"""v0.2.7-a11: selectable multi-Noark5 discovery in one shared workbench.

No new runner and no separate job list. Discovery is read-only and asynchronous;
job creation is explicit and uses the existing Workbench API.
"""
from __future__ import annotations

from pathlib import Path
from queue import Empty, Queue
from threading import Thread

from PySide6.QtCore import Qt, QSettings, QTimer
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QDialog, QFileDialog, QFormLayout, QHBoxLayout, QLabel, QLineEdit,
    QMessageBox, QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout,
    QWidget, QCheckBox,
)

from app.noark5_batch_discovery_v027_a11 import (
    Candidate, assign_work, component, discover, resolve_info_xml,
)

KEY_SUFFIX = 'qt/v027_a11_batch_suffix'
KEY_INFO = 'qt/v027_a11_info_xml_directory'


class BatchDiscoveryDialog(QDialog):
    def __init__(self, window):
        super().__init__(window)
        self.window = window
        self.api = window.api
        self.settings = QSettings()
        self.setWindowTitle('Finn flere Noark 5-uttrekk – v0.2.7-a11')
        self.resize(1050, 610)
        self._queue = Queue()
        self._working = False
        self._candidates: tuple[Candidate, ...] = ()
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.root = QLineEdit()
        self.root.setPlaceholderText('Velg hovedmappe med flere Noark 5-uttrekk')
        row = QHBoxLayout()
        row.addWidget(self.root)
        browse = QPushButton('Velg…')
        browse.clicked.connect(self._choose_root)
        row.addWidget(browse)
        form.addRow('Søk under hovedmappe:', row)
        self.run_folder = QLineEdit(str(self.settings.value(KEY_SUFFIX, 'a01') or 'a01'))
        form.addRow('Felles kjøringsundermappe:', self.run_folder)
        self.info_root = QLineEdit(str(self.settings.value(KEY_INFO, '') or ''))
        info_row = QHBoxLayout()
        info_row.addWidget(self.info_root)
        info_choose = QPushButton('Velg…')
        info_choose.clicked.connect(self._choose_info)
        info_row.addWidget(info_choose)
        form.addRow('Ekstern info.xml-katalog (valgfri):', info_row)
        layout.addLayout(form)
        self.note = QLabel('DWM-mappen leses fra Setup. Søket hopper over DOKUMENT, Work og repository_operations.')
        self.note.setWordWrap(True)
        layout.addWidget(self.note)
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(('Velg', 'Noark 5-uttrekk (Source)', 'Planlagt Work', 'info.xml'))
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setColumnWidth(0, 55)
        self.table.setColumnWidth(1, 355)
        self.table.setColumnWidth(2, 400)
        layout.addWidget(self.table, 1)
        buttons = QHBoxLayout()
        self.search_button = QPushButton('Finn kandidater')
        self.search_button.clicked.connect(self._scan)
        buttons.addWidget(self.search_button)
        self.add_button = QPushButton('Legg valgte til jobblisten')
        self.add_button.setEnabled(False)
        self.add_button.clicked.connect(self._add)
        buttons.addWidget(self.add_button)
        close = QPushButton('Lukk')
        close.clicked.connect(self.reject)
        buttons.addWidget(close)
        layout.addLayout(buttons)
        self._timer = QTimer(self)
        self._timer.setInterval(150)
        self._timer.timeout.connect(self._poll)

    def _choose_root(self):
        path = QFileDialog.getExistingDirectory(self, 'Velg hovedmappe', self.root.text())
        if path:
            self.root.setText(path)

    def _choose_info(self):
        path = QFileDialog.getExistingDirectory(self, 'Velg katalog med info.xml', self.info_root.text())
        if path:
            self.info_root.setText(path)

    def _scan(self):
        try:
            component(self.run_folder.text())
            root = Path(self.root.text().strip()).resolve(strict=True)
            if not root.is_dir():
                raise ValueError('Velg en eksisterende hovedmappe.')
            info = self.info_root.text().strip()
            if info and not Path(info).is_dir():
                raise ValueError('info.xml-katalogen finnes ikke.')
        except (OSError, ValueError) as exc:
            QMessageBox.warning(self, 'Ugyldig søkeoppsett', str(exc))
            return
        self._working = True
        self.search_button.setEnabled(False)
        self.add_button.setEnabled(False)
        self.note.setText('Søker gjennom undermapper (ikke dokumentinnhold)…')
        self.table.setRowCount(0)
        self._candidates = ()
        def task():
            try:
                self._queue.put(('done', discover(root)))
            except Exception as exc:
                self._queue.put(('error', str(exc)))
        Thread(target=task, name='dwm-a11-noark5-discovery', daemon=True).start()
        self._timer.start()

    def _poll(self):
        try:
            kind, payload = self._queue.get_nowait()
        except Empty:
            return
        self._timer.stop()
        self._working = False
        self.search_button.setEnabled(True)
        if kind == 'error':
            self.note.setText('Søk feilet: ' + payload)
            return
        self._candidates = payload
        self._rendered_suffix = self.run_folder.text().strip()
        self._render_candidates()

    def _render_candidates(self):
        try:
            folder = str(self.api.settings.get('app_work_subfolder', 'dwm') or '')
            mapping = assign_work(self._candidates, dwm_folder=folder,
                                  run_folder=self.run_folder.text())
            info_root = self.info_root.text().strip() or None
        except (ValueError, OSError) as exc:
            QMessageBox.warning(self, 'Planlegging av Work', str(exc))
            return
        self.table.setRowCount(len(self._candidates))
        existing = {str(Path(j.source_extraction).resolve(strict=False)).casefold()
                    for j in self.api.workspace().jobs if j.source_extraction}
        for row, candidate in enumerate(self._candidates):
            old = str(candidate.source).casefold() in existing
            check = QTableWidgetItem('')
            check.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
            check.setCheckState(Qt.CheckState.Unchecked if old else Qt.CheckState.Checked)
            if old:
                check.setFlags(Qt.ItemFlag.ItemIsEnabled)
            self.table.setItem(row, 0, check)
            for column, text in ((1, str(candidate.source)), (2, str(mapping[candidate.source]))):
                item = QTableWidgetItem(text)
                item.setToolTip(text)
                item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
                self.table.setItem(row, column, item)
            info = resolve_info_xml(candidate, info_root)
            item = QTableWidgetItem(str(info) if info else 'Ikke funnet / tvetydig')
            item.setToolTip(item.text())
            self.table.setItem(row, 3, item)
        self.note.setText(f'{len(self._candidates)} Noark 5-kandidater funnet. '
                          'Eksisterende Source er ikke valgt. Ingen mapper eller jobber er opprettet.')
        self.add_button.setEnabled(bool(self._candidates))

    def _add(self):
        if self.run_folder.text().strip() != getattr(self, '_rendered_suffix', ''):
            QMessageBox.warning(self, 'Work-oppsett endret', 'Kjør Finn kandidater på nytt for å oppdatere Work-forhåndsvisningen.')
            return
        if self._working or getattr(self.window, '_worker', None) is not None or self.api.running:
            QMessageBox.warning(self, 'Kjøring pågår', 'Avslutt kjøringen før jobber legges til.')
            return
        selected = [c for row, c in enumerate(self._candidates)
                    if self.table.item(row, 0).checkState() == Qt.CheckState.Checked]
        if not selected:
            return
        folder = str(self.api.settings.get('app_work_subfolder', 'dwm') or '')
        try:
            paths = assign_work(tuple(selected), dwm_folder=folder,
                                run_folder=self.run_folder.text())
            active = {str(Path(j.source_extraction).resolve(strict=False)).casefold()
                      for j in self.api.workspace().jobs if j.source_extraction}
            work = {str(Path(self.api.job_details(j.job_id).job.effective_work_operations
                             or self.api.job_details(j.job_id).job.work_operations).resolve(strict=False)).casefold()
                    for j in self.api.workspace().jobs
                    if (self.api.job_details(j.job_id).job.effective_work_operations
                        or self.api.job_details(j.job_id).job.work_operations)}
            for c in selected:
                planned = paths[c.source]
                if str(c.source).casefold() in active:
                    raise ValueError('Source er allerede registrert: ' + str(c.source))
                if str(planned).casefold() in work:
                    raise ValueError('Work er allerede registrert: ' + str(planned))
                if planned.exists() and any(planned.iterdir()):
                    raise ValueError('Work inneholder allerede data; velg annen kjøringsundermappe: ' + str(planned))
                if planned.is_symlink():
                    raise ValueError('Work kan ikke være symbolsk lenke: ' + str(planned))
        except (ValueError, OSError) as exc:
            QMessageBox.warning(self, 'Kan ikke importere', str(exc))
            return
        answer = QMessageBox.question(self, 'Legg til Noark 5-jobber',
            f'Legge til {len(selected)} jobber i den eksisterende jobblisten?\n\n'
            f'DWM-mappe: {folder or "(ingen)"}\nKjøringsundermappe: {self.run_folder.text()}\n\n'
            'Ingen dokumentfiler flyttes, og ingen analyse starter.\n'
            'Tilknyttede info.xml-filer importeres som Work-evidens når mulig.',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No)
        if answer != QMessageBox.StandardButton.Yes:
            return
        created, errors = [], []
        for c in selected:
            view = None
            try:
                target = paths[c.source]
                view = self.api.create_job(source_extraction=str(c.source),
                                           name=c.package_root.name or c.source.name,
                                           profile_id='noark5')
                self.api.update_storage(view.job_id, {
                    'work_root': str(c.package_root), 'work_operations': str(target),
                })
                self.api.use_selected_work_directly(view.job_id)
                info = resolve_info_xml(c, self.info_root.text().strip() or None)
                if info:
                    from app.dias_info_v0113_a2 import persist_metadata, read_original
                    job = self.api.job_details(view.job_id).job
                    persist_metadata(job, read_original(info), info)
                created.append(view.job_id)
            except Exception as exc:
                errors.append(f'{c.source}: {exc}')
                if view is not None:
                    try:
                        self.api.remove_job(view.job_id)
                    except Exception:
                        pass
        if created:
            try:
                self.api.select_job(created[0])
                self.window._refresh(force=True)
                self.window._save()
            except Exception as exc:
                errors.append('Lagring av jobbliste: ' + str(exc))
        self.settings.setValue(KEY_SUFFIX, self.run_folder.text().strip())
        self.settings.setValue(KEY_INFO, self.info_root.text().strip())
        QMessageBox.information(self, 'Batch-import',
            f'{len(created)} jobb(er) lagt til. {len(errors)} feil.\n'
            + ('\n'.join(errors[:8]) if errors else 'Kontroller jobbene før kjøring.'))
        if created:
            self.accept()


def install_setup_a11() -> None:
    """Append batch defaults to the existing Setup, preserving standard Save."""
    from gui_qt import setup_v0110_a3
    original = setup_v0110_a3.DwmSetupDialog
    if getattr(original, '_a11_batch_setup', False):
        return

    class SetupA11(original):
        _a11_batch_setup = True

        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            page = QWidget()
            form = QFormLayout(page)
            note = QLabel('Batch-import benytter global DWM-undermappe fra «Mapper og Work». '
                          'Kjøringsundermappen gjelder nye jobber og flytter aldri gamle resultater.')
            note.setWordWrap(True)
            form.addRow(note)
            self.a11_suffix = QLineEdit(str(QSettings().value(KEY_SUFFIX, 'a01') or 'a01'))
            form.addRow('Standard kjøringsundermappe:', self.a11_suffix)
            row = QHBoxLayout()
            self.a11_info = QLineEdit(str(QSettings().value(KEY_INFO, '') or ''))
            row.addWidget(self.a11_info)
            browse = QPushButton('Velg…')
            browse.clicked.connect(lambda: self._a11_choose_info())
            row.addWidget(browse)
            form.addRow('Ekstern info.xml-katalog:', row)
            self.tabs.addTab(page, 'Batch-import')

        def _a11_choose_info(self):
            path = QFileDialog.getExistingDirectory(self, 'Velg info.xml-katalog', self.a11_info.text())
            if path:
                self.a11_info.setText(path)

        def accept(self):
            try:
                component(self.a11_suffix.text())
                info = self.a11_info.text().strip()
                if info and not Path(info).is_dir():
                    raise ValueError('info.xml-katalogen finnes ikke.')
            except ValueError as exc:
                QMessageBox.warning(self, 'Batch-oppsett', str(exc))
                return
            settings = QSettings()
            settings.setValue(KEY_SUFFIX, self.a11_suffix.text().strip())
            settings.setValue(KEY_INFO, self.a11_info.text().strip())
            super().accept()

    setup_v0110_a3.DwmSetupDialog = SetupA11


def install_batch_discovery(window) -> None:
    """Expose the same action in Advanced and Simple without replacing either."""
    if not hasattr(window, '_toolbar'):
        return
    action = QAction('Finn flere Noark 5-uttrekk…', window)
    action.setObjectName('v027_a11_find_multiple_extractions')
    action.triggered.connect(lambda: BatchDiscoveryDialog(window).exec())
    window.a11_batch_action = action
    for top in window.menuBar().actions():
        if top.menu() is not None and top.text().replace('&', '').strip() == 'Fil':
            top.menu().addAction(action)
            break
    window._toolbar.addAction(action)
    basic = getattr(window, '_a2_overview_page', None)
    if basic is not None and basic.layout() is not None:
        button = QPushButton('Finn flere Noark 5-uttrekk…', basic)
        button.setObjectName('v027_a11_basic_find_multiple')
        button.clicked.connect(lambda: BatchDiscoveryDialog(window).exec())
        basic.layout().insertWidget(0, button)
        window.a11_basic_button = button
    source_group = getattr(window, '_a2_step_groups', {}).get('source')
    if source_group is not None and source_group.layout() is not None:
        source_button = QPushButton('Finn flere Noark 5-uttrekk…', source_group)
        source_button.setObjectName('v027_a11_source_find_multiple')
        source_button.clicked.connect(lambda: BatchDiscoveryDialog(window).exec())
        source_group.layout().addWidget(source_button)
        window.a11_source_button = source_button
