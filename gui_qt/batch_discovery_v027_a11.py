"""Selectable multi-Noark5 discovery in the existing Simple/Advanced workbench.

Discovery is read-only. Operators explicitly choose any alternative Work folder
before jobs are created. No Source content or existing Work is overwritten.
"""
from __future__ import annotations

from pathlib import Path
from queue import Empty, Queue
from threading import Thread

from PySide6.QtCore import Qt, QSettings, QTimer
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFileDialog, QFormLayout,
    QHBoxLayout, QHeaderView, QLabel, QLineEdit, QMessageBox, QPushButton,
    QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

from app.noark5_batch_discovery_v027_a11 import (
    Candidate, activate_batch_job_in_window, assign_work, component,
    create_direct_work_job, discover, extraction_id,
    info_xml_candidates, rejected_sip_packages, suggest_batch_joblist_path,
    work_folder_alternatives,
    work_target_state,
)

KEY_SUFFIX = 'qt/v027_a11_batch_suffix'
KEY_INFO = 'qt/v027_a11_info_xml_directory'


class DirectoryDropEdit(QLineEdit):
    """Accept a single directory URL from Explorer, including drive paths."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)

    @staticmethod
    def _directory(event) -> str | None:
        mime = event.mimeData()
        if not mime.hasUrls():
            return None
        urls = mime.urls()
        if len(urls) != 1 or not urls[0].isLocalFile():
            return None
        path = Path(urls[0].toLocalFile())
        if (path.is_dir() and not path.is_symlink()
                and not getattr(path, 'is_junction', lambda: False)()):
            return str(path)
        return None

    def dragEnterEvent(self, event):
        if self._directory(event):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        if self._directory(event):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event):
        directory = self._directory(event)
        if directory:
            self.setText(directory)
            event.acceptProposedAction()
        else:
            event.ignore()


class WorkFolderChoiceDialog(QDialog):
    """Never silently replace a configured folder with an existing sibling."""

    def __init__(self, package: Path, configured: str, alternatives: tuple[str, ...],
                 run_folder: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle('Velg DWM-mappe for uttrekk')
        self.resize(720, 330)
        layout = QVBoxLayout(self)
        note = QLabel(
            'Den konfigurerte DWM-mappen finnes ikke, men andre DWM-mapper er funnet. '
            'Velg hvor NYE analyser skal lagres. Eksisterende resultater endres ikke.\n\n'
            + 'Uttrekk: ' + package.name
        )
        note.setWordWrap(True)
        layout.addWidget(note)
        form = QFormLayout()
        self.choice = QComboBox(self)
        self.choice.addItem('Bruk standard ' + configured + ' (opprett ved import)', configured)
        for alternative in alternatives:
            self.choice.addItem('Bruk eksisterende ' + alternative, alternative)
        self.choice.addItem('Oppgi annet mappenavn', '__custom__')
        form.addRow('DWM-mappe:', self.choice)
        self.custom = QLineEdit(self)
        self.custom.setPlaceholderText('Navn p\u00e5 DWM-mappe (ett mappenavn)')
        self.custom.setEnabled(False)
        form.addRow('Eget navn:', self.custom)
        layout.addLayout(form)
        self.target = QLabel('')
        self.target.setWordWrap(True)
        layout.addWidget(self.target)
        self.repeat_choice = QCheckBox('Bruk samme mappenavn for resterende uttrekk', self)
        self.repeat_choice.setChecked(False)
        layout.addWidget(self.repeat_choice)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok |
                                   QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText('Bruk dette valget')
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText('Avbryt')
        buttons.accepted.connect(self._accept_choice)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.package = package
        self.run_folder = run_folder
        self.choice.currentIndexChanged.connect(self._update_target)
        self.custom.textChanged.connect(self._update_target)
        self._update_target()

    def selected_folder(self) -> str:
        value = self.choice.currentData()
        return component(self.custom.text()) if value == '__custom__' else component(value)

    def _update_target(self):
        custom = self.choice.currentData() == '__custom__'
        self.custom.setEnabled(custom)
        try:
            folder = self.selected_folder()
            target = self.package / 'repository_operations' / folder / self.run_folder
            status = work_target_state(target)
            detail = (' - finnes allerede med data: velg ny kj\u00f8ringsundermappe'
                      if status == 'occupied' else
                      ' - blir opprettet ved import' if status == 'new' else
                      ' - blokkert' if status == 'blocked' else ' - ledig')
            self.target.setText('Planlagt Work: ' + str(target) + detail)
        except ValueError:
            self.target.setText('Oppgi et gyldig, enkelt mappenavn.')

    def _accept_choice(self):
        try:
            self.selected_folder()
        except ValueError as exc:
            QMessageBox.warning(self, 'DWM-mappe', str(exc))
            return
        self.accept()


class BatchJobListSaveDialog(QDialog):
    """Fast save with a suggested full path; file-system browsing is optional."""

    def __init__(self, initial: Path, parent=None):
        super().__init__(parent)
        self.setWindowTitle('Lagre felles jobbliste')
        self.resize(830, 195)
        layout = QVBoxLayout(self)
        explanation = QLabel(
            'Jobbene er registrert. Velg hvor den felles .n5jobs-filen skal lagres. '
            'Foresl\u00e5tt mappe ligger ved siden av uttrekkene, ikke i Work eller temp.'
        )
        explanation.setWordWrap(True)
        layout.addWidget(explanation)
        path_row = QHBoxLayout()
        self.path_edit = QLineEdit(str(initial))
        self.path_edit.setToolTip('Full sti til jobblisten. Du kan lime inn en sti direkte.')
        path_row.addWidget(self.path_edit, 1)
        browse = QPushButton('Velg mappe...')
        browse.clicked.connect(self._choose_directory)
        path_row.addWidget(browse)
        layout.addLayout(path_row)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save |
            QDialogButtonBox.StandardButton.Cancel
        )
        buttons.button(QDialogButtonBox.StandardButton.Save).setText('Lagre jobbliste')
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText('Ikke n\u00e5')
        buttons.accepted.connect(self._accept_path)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _choose_directory(self):
        path = Path(self.path_edit.text().strip()).expanduser()
        start = path.parent
        while not start.is_dir() and start != start.parent:
            start = start.parent
        directory = QFileDialog.getExistingDirectory(
            self, 'Velg mappe for jobblisten', str(start),
            QFileDialog.Option.DontUseNativeDialog,
        )
        if directory:
            self.path_edit.setText(str(Path(directory) / path.name))

    def selected_path(self) -> Path:
        name = self.path_edit.text().strip()
        if not name:
            raise ValueError('Oppgi filnavn for jobblisten.')
        target = Path(name).expanduser()
        if not target.is_absolute():
            raise ValueError('Oppgi full sti til jobblisten.')
        if target.suffix.casefold() != '.n5jobs':
            target = target.with_suffix('.n5jobs')
        if target == target.parent or not target.name:
            raise ValueError('Oppgi et gyldig filnavn.')
        return target

    def _accept_path(self):
        try:
            target = self.selected_path()
            if target.exists():
                choice = QMessageBox.question(
                    self, 'Jobblisten finnes allerede',
                    'Erstatt denne eksisterende jobblisten?\n' + str(target),
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No,
                )
                if choice != QMessageBox.StandardButton.Yes:
                    return
        except ValueError as exc:
            QMessageBox.warning(self, 'Ugyldig filnavn', str(exc))
            return
        self.accept()


class BatchDiscoveryDialog(QDialog):
    def __init__(self, window):
        super().__init__(window)
        self.window = window
        self.api = window.api
        self.settings = QSettings()
        self.setWindowTitle('Finn flere Noark 5-uttrekk')
        self.resize(1100, 690)
        self._queue = Queue()
        self._working = False
        self._candidates: tuple[Candidate, ...] = ()
        self._work_choices: dict[Path, str] = {}
        self._info_choices: dict[Path, Path] = {}
        self._info_matches: dict[Path, tuple[Path, ...]] = {}
        self._found_root = ''
        self._rendered_run = ''
        self._rendered_info = ''
        self._rejected: tuple[tuple[str, str], ...] = ()

        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.root = DirectoryDropEdit()
        self.root.setPlaceholderText('Dra en mappe hit, eller velg hovedmappe med flere Noark 5-uttrekk')
        root_row = QHBoxLayout()
        root_row.addWidget(self.root)
        browse = QPushButton('Velg...')
        browse.clicked.connect(self._choose_root)
        root_row.addWidget(browse)
        form.addRow('S\u00f8k under hovedmappe:', root_row)

        self.run_folder = QLineEdit(str(self.settings.value(KEY_SUFFIX, 'a01') or 'a01'))
        self.run_folder.editingFinished.connect(self._update_preview)
        form.addRow('Felles kj\u00f8ringsundermappe:', self.run_folder)
        self.info_root = DirectoryDropEdit()
        self.info_root.setText(str(self.settings.value(KEY_INFO, '') or ''))
        self.info_root.editingFinished.connect(self._update_preview)
        info_row = QHBoxLayout()
        info_row.addWidget(self.info_root)
        info_choose = QPushButton('Velg...')
        info_choose.clicked.connect(self._choose_info)
        info_row.addWidget(info_choose)
        form.addRow('Ekstern info.xml-katalog (valgfri):', info_row)
        layout.addLayout(form)

        self.note = QLabel(
            'DWM-mappen leses fra Setup. Mapper med eksisterende resultater brukes aldri '
            'uten nytt, ledig kj\u00f8ringsnavn. Dokumentinnhold skannes ikke.'
        )
        self.note.setWordWrap(True)
        layout.addWidget(self.note)
        controls = QHBoxLayout()
        self.select_all_button = QPushButton('Velg alle')
        self.select_none_button = QPushButton('Fjern alle')
        self.select_all_button.clicked.connect(lambda: self._set_all_checked(True))
        self.select_none_button.clicked.connect(lambda: self._set_all_checked(False))
        self.selection_label = QLabel('0 valgt')
        controls.addWidget(self.select_all_button)
        controls.addWidget(self.select_none_button)
        controls.addWidget(self.selection_label)
        controls.addStretch(1)
        layout.addLayout(controls)
        self.select_all_button.setEnabled(False)
        self.select_none_button.setEnabled(False)

        # Each extraction occupies TWO readable lines, rather than seven
        # horizontally scrolling columns. Full paths remain in tooltips.
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels((
            'Velg', 'Uttrekk', 'Source / info.xml', 'Work / status',
        ))
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.table.setColumnWidth(0, 52)
        self.table.setColumnWidth(1, 113)
        self.table.setWordWrap(True)
        self.table.setTextElideMode(Qt.TextElideMode.ElideRight)
        self.table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.cellDoubleClicked.connect(self._select_info_xml)
        self.table.itemChanged.connect(self._on_item_changed)
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
            self._update_preview()

    def _configured_folder(self):
        return str(self.api.settings.get('app_work_subfolder', 'dwm') or '')

    def _scan(self):
        try:
            component(self.run_folder.text())
            root = Path(self.root.text().strip()).resolve(strict=True)
            if not root.is_dir() or root.is_symlink():
                raise ValueError('Velg en eksisterende hovedmappe.')
            info = self.info_root.text().strip()
            if info and not Path(info).is_dir():
                raise ValueError('info.xml-katalogen finnes ikke.')
        except (OSError, ValueError) as exc:
            QMessageBox.warning(self, 'Ugyldig s\u00f8keoppsett', str(exc))
            return
        self._working = True
        self.search_button.setEnabled(False)
        self.add_button.setEnabled(False)
        self.note.setText('S\u00f8ker gjennom undermapper (ikke dokumentinnhold)...')
        self.table.setRowCount(0)
        self._candidates = ()
        self._work_choices.clear()
        self._info_choices.clear()
        self._found_root = str(root)

        def task():
            try:
                candidates = discover(root)
                rejected = rejected_sip_packages(root, candidates)
                self._queue.put(('done', (candidates, rejected)))
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
            self.note.setText('S\u00f8k feilet: ' + payload)
            return
        self._candidates, self._rejected = payload
        if not self._choose_work_folders():
            self._candidates = ()
            self._work_choices.clear()
            self.note.setText('Valg av DWM-mappe avbrutt. Ingen jobber eller mapper er opprettet.')
            self.add_button.setEnabled(False)
            return
        self._render_candidates()

    def _choose_work_folders(self) -> bool:
        configured = self._configured_folder()
        common_folder = None
        for candidate in self._candidates:
            if common_folder is not None:
                self._work_choices[candidate.source] = common_folder
                continue
            base = candidate.package_root / 'repository_operations'
            alternatives = work_folder_alternatives(candidate.package_root, configured)
            configured_path = base / configured if configured else base
            if not configured or configured_path.exists() or not alternatives:
                self._work_choices[candidate.source] = configured
                continue
            choice = WorkFolderChoiceDialog(
                candidate.package_root, configured, alternatives, self.run_folder.text().strip(), self,
            )
            if choice.exec() != QDialog.DialogCode.Accepted:
                return False
            chosen = choice.selected_folder()
            self._work_choices[candidate.source] = chosen
            if choice.repeat_choice.isChecked():
                common_folder = chosen
        return True

    def _update_preview(self):
        if not self._working and self._candidates and self._work_choices:
            try:
                component(self.run_folder.text())
                info = self.info_root.text().strip()
                if info and not Path(info).is_dir():
                    raise ValueError('info.xml-katalogen finnes ikke.')
                self._render_candidates()
            except (OSError, ValueError) as exc:
                self.add_button.setEnabled(False)
                self.note.setText('Oppdater planlagt Work: ' + str(exc))

    @staticmethod
    def _relative_caption(path: Path, package_root: Path) -> str:
        try:
            return str(Path(path).relative_to(package_root))
        except ValueError:
            return str(path)

    def _set_all_checked(self, checked: bool):
        self.table.blockSignals(True)
        try:
            for row in range(self.table.rowCount()):
                item = self.table.item(row, 0)
                if item is not None and (item.flags() & Qt.ItemFlag.ItemIsUserCheckable):
                    item.setCheckState(Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked)
        finally:
            self.table.blockSignals(False)
        self._update_selection_count()

    def _on_item_changed(self, item):
        if item.column() == 0:
            self._update_selection_count()

    def _update_selection_count(self):
        selectable = 0
        selected = 0
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            if item is not None and (item.flags() & Qt.ItemFlag.ItemIsUserCheckable):
                selectable += 1
                if item.checkState() == Qt.CheckState.Checked:
                    selected += 1
        self.selection_label.setText(f'{selected} valgt av {selectable} tilgjengelige')
        self.select_all_button.setEnabled(selectable > 0)
        self.select_none_button.setEnabled(selectable > 0)
        self.add_button.setEnabled(selected > 0 and not self._working)

    def _render_candidates(self):
        configured = self._configured_folder()
        mapping = assign_work(self._candidates, dwm_folder=configured,
                              run_folder=self.run_folder.text().strip(),
                              folder_overrides=self._work_choices)
        info_root = self.info_root.text().strip() or None
        old_checked = {}
        for row in range(self.table.rowCount()):
            identity = self.table.item(row, 1)
            checked = self.table.item(row, 0)
            if identity is not None and checked is not None:
                source = identity.data(Qt.ItemDataRole.UserRole)
                if source:
                    old_checked[str(source).casefold()] = checked.checkState() == Qt.CheckState.Checked
        existing = {str(Path(job.source_extraction).resolve(strict=False)).casefold()
                    for job in self.api.workspace().jobs if job.source_extraction}
        self.table.blockSignals(True)
        try:
            self.table.setRowCount(len(self._candidates))
            self._info_matches.clear()
            for row, candidate in enumerate(self._candidates):
                source = str(candidate.source)
                already = source.casefold() in existing
                folder = self._work_choices.get(candidate.source, configured)
                planned = mapping[candidate.source]
                state = work_target_state(planned)
                available = not already and state not in ('blocked', 'occupied')

                check = QTableWidgetItem('')
                if available:
                    check.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
                    check.setCheckState(Qt.CheckState.Checked if old_checked.get(source.casefold(), True)
                                        else Qt.CheckState.Unchecked)
                else:
                    check.setFlags(Qt.ItemFlag.ItemIsEnabled)
                    check.setCheckState(Qt.CheckState.Unchecked)
                self.table.setItem(row, 0, check)

                identity = QTableWidgetItem(extraction_id(candidate))
                identity.setData(Qt.ItemDataRole.UserRole, source)
                identity.setToolTip(str(candidate.package_root))
                identity.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
                self.table.setItem(row, 1, identity)

                try:
                    matches = info_xml_candidates(candidate, info_root)
                except OSError as exc:
                    matches = ()
                    self.note.setToolTip('Kan ikke lese info.xml: ' + str(exc))
                self._info_matches[candidate.source] = matches
                chosen = self._info_choices.get(candidate.source)
                if chosen and chosen.is_file():
                    info = chosen
                    info_caption = self._relative_caption(info, candidate.package_root)
                elif len(matches) == 1:
                    info = matches[0]
                    info_caption = self._relative_caption(info, candidate.package_root)
                elif len(matches) > 1:
                    info = None
                    info_caption = f'TVETYDIG ({len(matches)}) - dobbeltklikk for valg'
                else:
                    info = None
                    info_caption = 'Ikke funnet - dobbeltklikk for manuelt valg'

                source_item = QTableWidgetItem(
                    'Source: ' + self._relative_caption(candidate.source, candidate.package_root)
                    + '\ninfo.xml: ' + info_caption
                )
                source_item.setToolTip('Source: ' + source + '\ninfo.xml: '
                                       + (str(info) if info else info_caption)
                                       + '\nDobbeltklikk for manuelt valg av info.xml')
                source_item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
                self.table.setItem(row, 2, source_item)

                if already:
                    status = 'Finnes allerede i jobblisten'
                elif state == 'occupied':
                    status = 'OPPTATT - velg ny kj\u00f8ringsundermappe'
                elif state == 'blocked':
                    status = 'BLOKKERT - ulovlig m\u00e5l'
                elif state == 'empty':
                    status = 'Ledig, eksisterende mappe'
                else:
                    status = 'Ny Work (opprettes ved import)'
                work_item = QTableWidgetItem(
                    'Work: ' + self._relative_caption(planned, candidate.package_root)
                    + '\nStatus: ' + status
                )
                work_item.setToolTip('DWM-mappe: ' + (folder or '(ingen)')
                                     + '\nFull Work: ' + str(planned)
                                     + '\nStatus: ' + status)
                work_item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
                self.table.setItem(row, 3, work_item)
                self.table.setRowHeight(row, 68)
        finally:
            self.table.blockSignals(False)
        summary = f'{len(self._candidates)} Noark 5-kandidater funnet.'
        if self._rejected:
            compact = '; '.join(f'{name}: {reason}' for name, reason in self._rejected[:3])
            summary += f' {len(self._rejected)} avvist: {compact}.'
        summary += ' Ingen mapper eller jobber er opprettet.'
        self.note.setText(summary)
        self.note.setToolTip('\n'.join(f'{name}: {reason}' for name, reason in self._rejected))
        self._rendered_run = self.run_folder.text().strip()
        self._rendered_info = self.info_root.text().strip()
        self._update_selection_count()

    def _select_info_xml(self, row: int, column: int):
        if column != 2 or row < 0 or row >= len(self._candidates):
            return
        candidate = self._candidates[row]
        path, _ = QFileDialog.getOpenFileName(
            self, 'Velg info.xml for ' + extraction_id(candidate),
            str(candidate.package_root), 'XML (*.xml);;Alle filer (*)',
        )
        if not path:
            return
        from app.noark5_batch_discovery_v027_a11 import _info_name_for_package
        file = Path(path)
        if not file.is_file() or file.is_symlink() or file.stat().st_size > 8_000_000 or not (
                file.name.casefold() == 'info.xml'
                or _info_name_for_package(file.name, candidate.package_root.name)):
            QMessageBox.warning(self, 'info.xml',
                                'Velg info.xml eller en info.xml-fil med samme uttrekks-ID.')
            return
        self._info_choices[candidate.source] = file.resolve(strict=True)
        self._render_candidates()

    def _add(self):
        if (self.run_folder.text().strip() != self._rendered_run
                or self.info_root.text().strip() != self._rendered_info
                or str(Path(self.root.text().strip()).resolve(strict=False)) != self._found_root):
            QMessageBox.warning(self, 'Oppsett endret',
                                'Oppdater s\u00f8ket/forh\u00e5ndsvisningen f\u00f8r jobbene legges til.')
            return
        if self._working or getattr(self.window, '_worker', None) is not None or self.api.running:
            QMessageBox.warning(self, 'Kj\u00f8ring p\u00e5g\u00e5r',
                                'Avslutt kj\u00f8ringen f\u00f8r jobber legges til.')
            return
        selected = [candidate for row, candidate in enumerate(self._candidates)
                    if self.table.item(row, 0).checkState() == Qt.CheckState.Checked]
        if not selected:
            return
        if (getattr(self.window, '_basic_active', False)
                and getattr(self.window, '_v022_draft', False)
                and (self.window.basic_source_path.text().strip()
                     or self.window.basic_work_path.text().strip())):
            QMessageBox.warning(
                self, 'Uferdig uttrekk',
                'Fullf\u00f8r eller forkast det uregistrerte uttrekket i Enkel modus '
                'f\u00f8r du importerer flere jobber.',
            )
            return
        try:
            paths = assign_work(tuple(selected), dwm_folder=self._configured_folder(),
                                run_folder=self.run_folder.text().strip(),
                                folder_overrides=self._work_choices)
            active = {str(Path(job.source_extraction).resolve(strict=False)).casefold()
                      for job in self.api.workspace().jobs if job.source_extraction}
            work = {str(Path(self.api.job_details(job.job_id).job.effective_work_operations
                             or self.api.job_details(job.job_id).job.work_operations).resolve(strict=False)).casefold()
                    for job in self.api.workspace().jobs
                    if (self.api.job_details(job.job_id).job.effective_work_operations
                        or self.api.job_details(job.job_id).job.work_operations)}
            for candidate in selected:
                planned = paths[candidate.source]
                if str(candidate.source).casefold() in active:
                    raise ValueError('Source er allerede registrert: ' + str(candidate.source))
                if str(planned).casefold() in work:
                    raise ValueError('Work er allerede registrert: ' + str(planned))
                if work_target_state(planned) in ('occupied', 'blocked'):
                    raise ValueError('Work kan ikke overskrives: ' + str(planned)
                                     + '. Velg en annen kj\u00f8ringsundermappe.')
                matches = self._info_matches.get(candidate.source, ())
                if len(matches) > 1 and candidate.source not in self._info_choices:
                    raise ValueError('info.xml er tvetydig for ' + extraction_id(candidate)
                                     + '. Dobbeltklikk info.xml-feltet for manuelt valg.')
        except (ValueError, OSError) as exc:
            QMessageBox.warning(self, 'Kan ikke importere', str(exc))
            return
        lines = [f'{extraction_id(candidate)}: '
                 + self._relative_caption(paths[candidate.source], candidate.package_root)
                 for candidate in selected]
        question = QMessageBox(self)
        question.setWindowTitle('Legg til Noark 5-jobber')
        question.setIcon(QMessageBox.Icon.Question)
        question.setText(
            f'Legge til {len(selected)} jobber i den eksisterende jobblisten?\n\n'
            + '\n'.join(lines[:8]) + '\n\n'
            'Ingen dokumentfiler flyttes, og ingen analyse starter.\n'
            'Tilknyttede info.xml-filer importeres som Work-evidens n\u00e5r mulig.'
        )
        approve = question.addButton('Legg til jobbene', QMessageBox.ButtonRole.YesRole)
        question.addButton('Avbryt', QMessageBox.ButtonRole.NoRole)
        question.exec()
        if question.clickedButton() is not approve:
            return
        created, errors = [], []
        for candidate in selected:
            try:
                target = paths[candidate.source]
                info = self._info_choices.get(candidate.source)
                if info is None:
                    matches = self._info_matches.get(candidate.source, ())
                    info = matches[0] if len(matches) == 1 else None
                callback = None
                if info:
                    from app.dias_info_v0113_a2 import persist_metadata, read_original
                    # Parse before any Work directory or job is created.
                    parsed_info = read_original(info)
                    callback = lambda job, source_info=info, values=parsed_info: (
                        persist_metadata(job, values, source_info)
                    )
                new_id = create_direct_work_job(self.api, candidate, target,
                                                on_created=callback)
                created.append(new_id)
            except Exception as exc:
                errors.append(str(candidate.source) + ': ' + str(exc))
        saved_path = None
        if created:
            try:
                # Important: Basic's form and selector keep their own draft
                # state even though API already contains all imported jobs.
                # Reset it and load the real Source/Work of JOB-001.
                activate_batch_job_in_window(self.window, created[0])
            except Exception as exc:
                errors.append('Visning av aktiv jobb: ' + str(exc))

            # Avoid Windows' slow drive-enumerating Qt Save As. Offer a full,
            # editable path based on the common parent of the selected SIPs.
            try:
                existing_list = self.api.workspace().job_list_path
                if existing_list:
                    # Additions to an existing job list should be saved to the
                    # SAME file, not accidentally split into another list.
                    saved_path = self.api.save_job_list()
                else:
                    suggestion = suggest_batch_joblist_path(
                        tuple(selected), search_root=self._found_root,
                        dwm_folder=self._configured_folder(),
                        run_folder=self.run_folder.text().strip(),
                        folder_overrides=self._work_choices,
                        settings=self.api.settings,
                    )
                    save_dialog = BatchJobListSaveDialog(suggestion, self)
                    if save_dialog.exec() == QDialog.DialogCode.Accepted:
                        target = save_dialog.selected_path()
                        target.parent.mkdir(parents=True, exist_ok=True)
                        saved_path = self.api.save_job_list(target)
                if saved_path:
                    self.window._remember_joblist(str(saved_path))
                    self.window._v022_save_failed = False
                else:
                    errors.append('Jobblisten er ikke lagret til fil. Bruk Lagre senere.')
            except Exception as exc:
                errors.append('Lagring av jobbliste: ' + str(exc))
            self.window._refresh(force=True)
            if hasattr(self.window, '_v022_refresh_selector'):
                self.window._v022_refresh_selector(force=True)
        self.settings.setValue(KEY_SUFFIX, self.run_folder.text().strip())
        self.settings.setValue(KEY_INFO, self.info_root.text().strip())
        QMessageBox.information(
            self, 'Batch-import',
            f'{len(created)} jobb(er) lagt til. {len(errors)} merknad(er).\n'
            + (('Lagret jobbliste: ' + str(saved_path) + '\n') if saved_path else '')
            + ('\n'.join(errors[:8]) if errors else 'Kontroller jobbene f\u00f8r kj\u00f8ring.'),
        )
        if created:
            self.accept()


def install_setup_a11() -> None:
    """Keep the established Setup implementation and its Save semantics."""
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
            note = QLabel('Batch-import benytter global DWM-undermappe fra "Mapper og Work". '
                          'Kj\u00f8ringsundermappen gjelder nye jobber og flytter aldri gamle resultater.')
            note.setWordWrap(True)
            form.addRow(note)
            self.a11_suffix = QLineEdit(str(QSettings().value(KEY_SUFFIX, 'a01') or 'a01'))
            form.addRow('Standard kj\u00f8ringsundermappe:', self.a11_suffix)
            row = QHBoxLayout()
            self.a11_info = QLineEdit(str(QSettings().value(KEY_INFO, '') or ''))
            row.addWidget(self.a11_info)
            browse = QPushButton('Velg...')
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
    action = QAction('Finn flere Noark 5-uttrekk...', window)
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
        button = QPushButton('Finn flere Noark 5-uttrekk...', basic)
        button.setObjectName('v027_a11_basic_find_multiple')
        button.clicked.connect(lambda: BatchDiscoveryDialog(window).exec())
        basic.layout().insertWidget(0, button)
        window.a11_basic_button = button
    source_group = getattr(window, '_a2_step_groups', {}).get('source')
    if source_group is not None and source_group.layout() is not None:
        source_button = QPushButton('Finn flere Noark 5-uttrekk...', source_group)
        source_button.setObjectName('v027_a11_source_find_multiple')
        source_button.clicked.connect(lambda: BatchDiscoveryDialog(window).exec())
        source_group.layout().addWidget(source_button)
        window.a11_source_button = source_button
