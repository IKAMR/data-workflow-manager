"""a14: post-completion operation repair in the existing shared DWM workbench.

No new runner: existing operations use run_subjob; previously omitted
operations use the same A39 runner on an isolated, synthetic Job copy.
"""
from __future__ import annotations

from queue import Queue
from threading import Thread

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QComboBox, QDialog, QHBoxLayout, QLabel, QMessageBox, QPushButton,
    QTableWidget, QTableWidgetItem, QVBoxLayout,
)

from app.additional_subjobs_v027_a14 import (
    SIEGFRIED, additional_ids, add_additional_subjob, extended_workflow,
    inspect_additional_subjob, run_additional_subjob,
)
from app.workflow_dependencies_v022_a7 import BY_ID, dependency_label


def _full_name(operation_id: str, catalog: dict) -> str:
    return (f'{dependency_label(operation_id)}  '
            f'{catalog.get(operation_id, (operation_id, ""))[0]}')


class AdditionalSubjobsDialog(QDialog):
    def __init__(self, window):
        super().__init__(window)
        self.window = window
        self.api = window.api
        self.setWindowTitle('Legg til / kjør deljobb på nytt')
        self.resize(930, 545)
        self.catalog = self.api._registry_catalog()
        layout = QVBoxLayout(self)
        description = QLabel(
            'Velg én deljobb og ett eller flere uttrekk. Manglende deljobber legges til som '
            'separate tilleggskjøringer; ferdige hovedjobber blir ikke nullstilt. '
            'Eksisterende deljobber kan kjøres på nytt, også etter 100 %.', self,
        )
        description.setWordWrap(True)
        layout.addWidget(description)
        row = QHBoxLayout()
        row.addWidget(QLabel('Deljobb:', self))
        self.operation = QComboBox(self)
        # Show only operations for which the a14 dependency model can give a
        # reliable, checkable supplemental plan. Exclude AIP packaging.
        for oid in sorted(BY_ID, key=lambda k: BY_ID[k].number):
            if oid != 'dias_package' and oid in self.catalog:
                self.operation.addItem(_full_name(oid, self.catalog), oid)
        index = self.operation.findData(SIEGFRIED)
        if index >= 0:
            self.operation.setCurrentIndex(index)
        self.operation.currentIndexChanged.connect(self._update)
        row.addWidget(self.operation, 1)
        layout.addLayout(row)

        controls = QHBoxLayout()
        select_all = QPushButton('Velg alle', self)
        select_none = QPushButton('Fjern alle', self)
        select_all.clicked.connect(lambda: self._check_all(True))
        select_none.clicked.connect(lambda: self._check_all(False))
        controls.addWidget(select_all)
        controls.addWidget(select_none)
        controls.addStretch(1)
        layout.addLayout(controls)

        self.table = QTableWidget(self)
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(('Velg', 'Uttrekk', 'Planlagt handling'))
        self.table.setColumnWidth(0, 54)
        self.table.setColumnWidth(1, 330)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        layout.addWidget(self.table, 1)
        self._job_ids = []
        jobs = self.api.workspace().jobs
        self.table.setRowCount(len(jobs))
        for i, job in enumerate(jobs):
            check = QTableWidgetItem('')
            check.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsUserCheckable)
            check.setCheckState(Qt.CheckState.Checked)
            self.table.setItem(i, 0, check)
            name = job.name or job.job_id
            label = QTableWidgetItem(f'{job.job_id}  {name}')
            label.setToolTip(str(job.source_extraction or '') + '\n' +
                             str(job.effective_work_operations or ''))
            self.table.setItem(i, 1, label)
            self.table.setItem(i, 2, QTableWidgetItem(''))
            self._job_ids.append(job.job_id)

        self.note = QLabel('', self)
        self.note.setWordWrap(True)
        layout.addWidget(self.note)
        actions = QHBoxLayout()
        self.go = QPushButton('Kjør valgte deljobber…', self)
        self.go.clicked.connect(self._start)
        actions.addWidget(self.go)
        actions.addStretch(1)
        cancel = QPushButton('Lukk', self)
        cancel.clicked.connect(self.reject)
        actions.addWidget(cancel)
        layout.addLayout(actions)
        self._update()

    def _check_all(self, value: bool):
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            if item is not None:
                item.setCheckState(Qt.CheckState.Checked if value else Qt.CheckState.Unchecked)

    def _update(self, *_args):
        operation = self.operation.currentData()
        for i, job_id in enumerate(self._job_ids):
            try:
                job = self.api._require_job(job_id)
                if operation in job.workflow_ids:
                    text = 'Kjør eksisterende deljobb separat på nytt'
                else:
                    extended_workflow(job, operation, self.catalog)
                    text = ('Tidligere registrert tilleggskjøring – kjør på nytt'
                            if operation in additional_ids(job)
                            else 'Legg til som tilleggskjøring (uten å nullstille 100 %)')
            except Exception as exc:
                text = 'Kan ikke kjøres: ' + str(exc)
            item = self.table.item(i, 2)
            item.setText(text)
            item.setToolTip(text)
        self.note.setText(
            'Hver kjøring får egen logg i eksisterende Work. Teknisk ferdigstatus og '
            'hovedjobbens 100 % beholdes. Tillegg vises i egne Work-kjørelogger, ikke i 13/13. '
            'Tidligere resultater slettes ikke av dialogen, '
            'men den valgte deljobben kan skrive over egne resultatfiler. '
            'Rapporter og evidens oppdateres ikke automatisk etter en tilleggskjøring.'
        )

    def _start(self):
        operation = self.operation.currentData()
        jobs = [job_id for i, job_id in enumerate(self._job_ids)
                if self.table.item(i, 0).checkState() == Qt.CheckState.Checked]
        if not operation or not jobs:
            QMessageBox.information(self, 'Velg deljobb', 'Velg minst ett uttrekk.')
            return
        if self.window._worker is not None or self.api.running:
            QMessageBox.warning(self, 'Kjøring pågår', 'Avslutt kjøringen før endringer.')
            return
        if not self.api.workspace().job_list_path:
            QMessageBox.warning(self, 'Lagre først', 'Lagre jobblisten før tilleggskjøring.')
            return

        missing, warnings, errors = [], [], []
        for job_id in jobs:
            try:
                job = self.api._require_job(job_id)
                if operation not in job.workflow_ids:
                    missing.append(job_id)
                report = inspect_additional_subjob(self.api, job_id, operation)
                errors.extend(f'{job_id}: {item.message}' for item in report.errors)
                errors.extend(f'{job_id}: Work må klargjøres: {item.path}'
                              for item in report.actions)
                warnings.extend(f'{job_id}: {item.message}' for item in report.warnings)
            except Exception as exc:
                errors.append(f'{job_id}: {exc}')
        if operation == SIEGFRIED:
            from app.siegfried_tool_v0111_a3 import inspect_siegfried
            tool = inspect_siegfried(str(self.api.settings.get('sf_executable') or ''))
            if not tool.ok:
                errors.append('Siegfried er ikke klar: ' + tool.message)
        if errors:
            QMessageBox.warning(self, 'Deljobb blokkert', '\n'.join(errors[:12]))
            return
        question = QMessageBox(self)
        question.setWindowTitle('Bekreft selektiv kjøring')
        question.setIcon(QMessageBox.Icon.Warning)
        question.setText(
            f'{_full_name(operation, self.catalog)}\n'
            f'Antall jobber: {len(jobs)} | Nye tillegg: {len(missing)}\n\n'
            'Eksisterende kjørestatus og arbeidsflyt beholdes. '
            'Deljobben kan erstatte egne tidligere resultatfiler i Work. '
            'Avhengige rapporter oppdateres IKKE automatisk.\n\n'
            + ('Forhåndskontroll: ' + '\n'.join(warnings[:5]) + '\n\n' if warnings else '')
            + 'Gjennomføre disse enkeltkjøringene?'
        )
        yes = question.addButton('Start deljobbene', QMessageBox.ButtonRole.YesRole)
        question.addButton('Avbryt', QMessageBox.ButtonRole.NoRole)
        question.exec()
        if question.clickedButton() is not yes:
            return

        # Register missing IDs explicitly before launching the worker. The
        # parent workflow itself is not edited and 100% stays 100%.
        try:
            for job_id in missing:
                add_additional_subjob(self.api, job_id, operation)
        except Exception as exc:
            QMessageBox.warning(self, 'Kunne ikke lagre tilleggskjøring',
                'Ingen kjøring er startet. Kontroller jobblisten: ' + str(exc))
            return
        window = self.window
        window._batch_stop.clear()
        window._worker_messages = Queue()
        window._set_running_ui(True)
        window._append_log(
            f'a14: starter {_full_name(operation, self.catalog)} for {len(jobs)} jobb(er).'
        )
        def execute():
            try:
                for job_id in jobs:
                    if window._batch_stop.is_set():
                        window._worker_messages.put(('info', 'a14: avbrutt mellom jobber.'))
                        break
                    window._worker_messages.put(('selected', job_id))
                    try:
                        if operation in self.api._require_job(job_id).workflow_ids:
                            result = self.api.run_subjob(
                                job_id, operation, allow_rerun=True,
                                acknowledge_warnings=bool(warnings),
                            )
                        else:
                            result = run_additional_subjob(
                                self.api, job_id, operation,
                                acknowledge_warnings=bool(warnings),
                            )
                        window._worker_messages.put(('info',
                            f'{job_id}: {dependency_label(operation)} – '
                            + ('OK' if result else 'FEIL (se Work-logg)')))
                    except Exception as exc:
                        window._worker_messages.put(('info', f'{job_id}: FEIL: {exc}'))
            except Exception as exc:
                window._worker_messages.put(('error', str(exc)))
            finally:
                window._worker_messages.put(('done',
                    f'a14: selektiv {dependency_label(operation)}-kjøring avsluttet.'))

        worker = Thread(target=execute, name='dwm-a14-supplemental-subjob', daemon=True)
        window._worker = worker
        worker.start()
        self.accept()


def install_additional_subjobs(window):
    """Install one shared advanced menu action and Simple entry point."""
    if getattr(window, '_a14_extra_installed', False):
        return
    window._a14_extra_installed = True
    # 'Velg arbeidsflyt' previously opened obsolete, Siegfried-free sequences.
    # Rewire ONLY the old button to the already-supported modern run profiles;
    # never rewrite a saved workflow on opening the window.
    preset = getattr(window, 'workflow_preset_button', None)
    if preset is not None:
        try:
            preset.clicked.disconnect()
        except (RuntimeError, TypeError):
            pass
        preset.setText('Velg kjøreprofil…')
        preset.setToolTip('Bruk samme moderne profiler som i Setup og batch-import.')
        preset.clicked.connect(window._a8_choose_run_profile)

    action = QAction('Legg til / kjør deljobb på nytt…', window)
    action.setObjectName('v027_a14_additional_subjobs')
    action.triggered.connect(lambda: AdditionalSubjobsDialog(window).exec())
    for top in window.menuBar().actions():
        menu = top.menu()
        if menu and menu.title().replace('&', '').strip() == 'Kjør':
            menu.addAction(action)
            break
    window.a14_additional_subjobs_action = action
    basic = getattr(window, '_a2_step_groups', {}).get('run')
    if basic is not None and basic.layout() is not None:
        button = QPushButton('Legg til / kjør deljobb på nytt…', basic)
        button.setObjectName('v027_a14_basic_additional_subjobs')
        button.clicked.connect(lambda: AdditionalSubjobsDialog(window).exec())
        basic.layout().addWidget(button)
        window.a14_basic_button = button
