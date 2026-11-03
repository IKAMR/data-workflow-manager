"""Shared DWM Setup for the independent PySide6 interface.

The global settings are intentionally organised by purpose; Arkade 5 is one
external integration, not the definition of Setup. The job-list output rule
belongs to the job list and is edited in the Jobs dock, not here.
"""
from __future__ import annotations

import json
from pathlib import Path
from queue import Empty, Queue
from threading import Thread

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (
    QComboBox, QDialog, QDialogButtonBox, QFileDialog, QFormLayout,
    QFrame, QHBoxLayout, QInputDialog, QLabel, QLineEdit, QMessageBox,
    QPushButton, QScrollArea, QTabWidget, QVBoxLayout, QWidget,
)

from app.arkade5_setup_v018_a7 import find_arkade5_candidates, requires_arkade_cli
from app.operation_metadata import VISIBILITY_LABELS
from app.settings_portable import (
    FILE_TYPE, FORMAT_VERSION, export_settings, import_settings, reset_settings,
)
from app.workflow_sequences import load_workflow_sequences


def _note(message: str) -> QLabel:
    label = QLabel(message)
    label.setWordWrap(True)
    return label


class _PathField(QWidget):
    """Path editor with a stable .edit attribute (no dynamic Qt properties)."""

    def __init__(self, initial: str, title: str, parent=None):
        super().__init__(parent)
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        self.edit = QLineEdit(initial)
        row.addWidget(self.edit, 1)
        button = QPushButton("Velg…")

        def browse():
            current = self.edit.text().strip()
            target = QFileDialog.getExistingDirectory(self, title, current)
            if target:
                self.edit.setText(target)

        button.clicked.connect(browse)
        row.addWidget(button)


class DwmSetupDialog(QDialog):
    """Edit all shared/global settings; never modify a job or Source implicitly."""

    def __init__(self, api, parent=None):
        super().__init__(parent)
        self.api = api
        self.settings = dict(api.settings)
        self._results = Queue()
        self._probing = False
        self.setWindowTitle("Setup – Data Workflow Manager")
        self.resize(880, 640)
        self.setMinimumSize(660, 490)
        self.setModal(True)

        layout = QVBoxLayout(self)
        header = QLabel("Setup")
        header.setStyleSheet("font-size: 17px; font-weight: 600;")
        layout.addWidget(header)
        layout.addWidget(_note(
            "Felles applikasjonsinnstillinger for PySide6 og CustomTkinter. "
            "Endringer lagres bare når du velger Lagre."
        ))
        self.tabs = QTabWidget(self)
        layout.addWidget(self.tabs, 1)
        self._build_general_tab()
        self._build_workflow_tab()
        self._build_storage_tab()
        self._build_external_tab()

        actions = QHBoxLayout()
        self.export_button = QPushButton("Eksporter setup…")
        self.export_button.clicked.connect(self._export)
        actions.addWidget(self.export_button)
        self.import_button = QPushButton("Importer setup…")
        self.import_button.clicked.connect(self._import)
        actions.addWidget(self.import_button)
        self.reset_button = QPushButton("Nullstill setup")
        self.reset_button.clicked.connect(self._reset)
        actions.addWidget(self.reset_button)
        actions.addStretch(1)
        layout.addLayout(actions)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.button(QDialogButtonBox.StandardButton.Save).setText("Lagre")
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("Avbryt")
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self._probe_timer = QTimer(self)
        self._probe_timer.setInterval(150)
        self._probe_timer.timeout.connect(self._read_probe_result)

    def _tab(self, name: str) -> tuple[QWidget, QFormLayout]:
        """Scrollable form so every Setup section fits a laptop window."""
        page = QWidget()
        root = QVBoxLayout(page)
        scroll = QScrollArea(page)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        content = QWidget()
        content_layout = QVBoxLayout(content)
        form = QFormLayout()
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        content_layout.addLayout(form)
        content_layout.addStretch(1)
        scroll.setWidget(content)
        root.addWidget(scroll)
        self.tabs.addTab(page, name)
        return content, form

    def _path_field(self, initial: str, title: str) -> _PathField:
        return _PathField(initial, title, self)

    def _build_general_tab(self):
        content, form = self._tab("Generelt")
        self.temp_dir = self._path_field(str(self.settings.get("temp_dir", "") or ""), "Velg Temp-mappe")
        form.addRow("Temp-mappe:", self.temp_dir)
        self.run_log_dir = self._path_field(str(self.settings.get("run_log_dir", "") or ""), "Velg kjøreloggmappe")
        form.addRow("Overordnet kjørelogg:", self.run_log_dir)
        self.setup_dir = self._path_field(str(self.settings.get("setup_dir", "") or ""), "Velg setup-mappe")
        form.addRow("Setup standardmappe:", self.setup_dir)
        self.job_list_dir = self._path_field(str(self.settings.get("job_list_dir", "") or ""), "Velg jobblistemappe")
        form.addRow("Jobblister standardmappe:", self.job_list_dir)
        form.addRow("", _note(
            "Tomt felt bruker eksisterende DWM-standardmappe. "
            "Ingen mapper opprettes når du bare åpner Setup."
        ))
        backend = str(self.settings.get("execution_backend", "local") or "local")
        form.addRow("Kjørebackend:", _note(
            f"{backend} (gjeldende). Qt-arbeidsmotoren kjører lokalt i denne versjonen; "
            "eksisterende backend-innstilling endres ikke her."
        ))

    def _build_workflow_tab(self):
        content, form = self._tab("Arbeidsflyt")
        self.workflow = QComboBox()
        self._workflow_has_arkade = {}
        for sequence in load_workflow_sequences(settings=self.settings):
            if sequence.profile_id != "noark5":
                continue
            self.workflow.addItem(sequence.name, sequence.sequence_id)
            self._workflow_has_arkade[sequence.sequence_id] = requires_arkade_cli(
                sequence.operation_ids
            )
        selected_workflow = str(self.settings.get("noark5_discovery_workflow", "noark5_standard"))
        index = self.workflow.findData(selected_workflow)
        if index >= 0:
            self.workflow.setCurrentIndex(index)
        form.addRow("Standard arbeidsflyt for nye Noark 5-jobber:", self.workflow)
        self.visibility = QComboBox()
        for level, label in VISIBILITY_LABELS.items():
            self.visibility.addItem(label, level)
        try:
            selected_level = int(self.settings.get("operation_visibility", 2))
        except (ValueError, TypeError):
            selected_level = 2
        index = self.visibility.findData(selected_level)
        if index >= 0:
            self.visibility.setCurrentIndex(index)
        form.addRow("Vis operasjoner:", self.visibility)
        form.addRow("", _note(
            "Valgt standard gjelder nye jobber. Eksisterende arbeidsflyter endres ikke. "
            "Beta/Alpha-synlighet påvirker bare hvilke operasjoner som tilbys i GUI."
        ))

    def _build_storage_tab(self):
        content, form = self._tab("Mapper og Work")
        self.work_subfolder = QLineEdit(str(self.settings.get("app_work_subfolder", "dwm") or ""))
        form.addRow("DWM-undermappe under Work – operations:", self.work_subfolder)
        form.addRow("", _note(
            "Dette er en GLOBAL regel. Eksempel: repository_operations / dwm. "
            "Tomt felt betyr at Work – operations brukes direkte."
        ))
        form.addRow("", _note(
            "Jobblistens egen undermappe-regel (eksempel a01 eller <nnn>) "
            "endres i panelet Jobber og lagres i .n5jobs, ikke i global Setup."
        ))
        form.addRow("", _note(
            "Endring av DWM-undermappen kan endre hvor eksisterende jobber finner "
            "resultater. Ingenting blir flyttet automatisk."
        ))

    def _build_external_tab(self):
        content, form = self._tab("Eksterne verktøy")
        form.addRow("", _note(
            "Her konfigureres integrasjoner og tredjepartsprogrammer. "
            "Arkade 5 er én av flere mulige integrasjoner; Setup er ikke avgrenset til Arkade."
        ))
        form.addRow("", _note("ARKADE 5 – ekstern Noark 5-test og PRONOM"))
        self.cli_path = QLineEdit(str(self.settings.get("arkade5_cli_path", "") or ""))
        self.cli_path.setPlaceholderText("Velg Arkade 5 CLI-programfil …")
        self.cli_path.textChanged.connect(self._clear_test_status)
        cli_row = QWidget()
        cli_layout = QHBoxLayout(cli_row)
        cli_layout.setContentsMargins(0, 0, 0, 0)
        cli_layout.addWidget(self.cli_path, 1)
        choose = QPushButton("Bla gjennom…")
        choose.clicked.connect(self._browse_cli)
        cli_layout.addWidget(choose)
        detect = QPushButton("Finn automatisk")
        detect.clicked.connect(self._find_cli)
        cli_layout.addWidget(detect)
        form.addRow("Arkade 5 CLI:", cli_row)

        status_row = QWidget()
        status_layout = QHBoxLayout(status_row)
        status_layout.setContentsMargins(0, 0, 0, 0)
        self.test_cli_button = QPushButton("Test CLI / versjon")
        self.test_cli_button.clicked.connect(self._test_cli)
        status_layout.addWidget(self.test_cli_button)
        self.cli_status = QLabel("Ikke testet i denne dialogen")
        self.cli_status.setWordWrap(True)
        status_layout.addWidget(self.cli_status, 1)
        form.addRow("Kontroll:", status_row)

        self.arkade_output = QLineEdit(str(
            self.settings.get("arkade5_output_subfolder", "arkade5_<ver>") or "arkade5_<ver>"
        ))
        form.addRow("Arkade 5 resultat-undermappe:", self.arkade_output)
        form.addRow("", _note(
            "Bare jobber med Arkade 5-test eller PRONOM-analyse trenger Arkade CLI. "
            "Import av eksisterende Arkade-rapporter kan brukes uten CLI."
        ))

    def _clear_test_status(self, _text=""):
        if not self._probing:
            self.cli_status.setText("Ikke testet i denne dialogen")

    def _browse_cli(self):
        initial = self.cli_path.text().strip()
        filename, _ = QFileDialog.getOpenFileName(
            self, "Velg Arkade 5 CLI-programfil", initial,
            "CLI-program (*.exe *.cmd *.bat);;Alle filer (*)",
        )
        if filename:
            self.cli_path.setText(filename)

    def _find_cli(self):
        candidates = find_arkade5_candidates()
        if not candidates:
            QMessageBox.information(
                self, "Arkade 5 CLI",
                "Ingen Arkade 5 CLI ble funnet i PATH eller kjente installasjonsmapper. "
                "Bruk «Bla gjennom…» og velg programfilen. "
                "DWM har ikke endret noen innstillinger."
            )
            return
        names = [str(path) for path in candidates]
        choice, ok = QInputDialog.getItem(
            self, "Arkade 5 CLI funnet", "Velg ønsket programfil:", names, 0, False
        )
        if ok and choice:
            self.cli_path.setText(choice)
            self.cli_status.setText("Kandidat valgt. Klikk «Test CLI / versjon» før lagring.")

    def _test_cli(self):
        if self._probing:
            return
        path = self.cli_path.text().strip()
        if not path:
            self.cli_status.setText("Ingen programsti angitt")
            return
        self._probing = True
        self.test_cli_button.setEnabled(False)
        self.cli_status.setText("Kontrollerer CLI uten å starte noen arkivtest …")
        self._tested_path = path

        def execute():
            try:
                status = self.api.check_arkade5_cli(path=path, refresh=True)
                self._results.put((path, status, None))
            except Exception as exc:
                self._results.put((path, None, str(exc)))

        Thread(target=execute, name="dwm-arkade-cli-check", daemon=True).start()
        self._probe_timer.start()

    def _read_probe_result(self):
        try:
            path, status, error = self._results.get_nowait()
        except Empty:
            return
        self._probe_timer.stop()
        self._probing = False
        self.test_cli_button.setEnabled(True)
        if path != self.cli_path.text().strip():
            self.cli_status.setText("Programstien ble endret; test på nytt.")
        elif error:
            self.cli_status.setText("FEIL: " + error)
        else:
            prefix = {"ok": "OK", "warning": "AVVIK", "error": "FEIL"}.get(status.severity, "INFO")
            self.cli_status.setText(prefix + ": " + status.message)

    def _updates(self) -> dict:
        return {
            "arkade5_cli_path": self.cli_path.text().strip(),
            "arkade5_output_subfolder": self.arkade_output.text().strip(),
            "noark5_discovery_workflow": str(self.workflow.currentData() or ""),
            "app_work_subfolder": self.work_subfolder.text().strip(),
            "temp_dir": self.temp_dir.edit.text().strip(),
            "run_log_dir": self.run_log_dir.edit.text().strip(),
            "setup_dir": self.setup_dir.edit.text().strip(),
            "job_list_dir": self.job_list_dir.edit.text().strip(),
            "operation_visibility": self.visibility.currentData(),
        }

    def _save(self):
        updates = self._updates()
        candidate = updates["arkade5_cli_path"]
        if candidate and not Path(candidate).is_file():
            choice = QMessageBox.question(
                self, "Arkade 5 CLI mangler",
                "Den valgte CLI-filen finnes ikke nå. Lagre likevel? "
                "Jobber som trenger CLI, vil bli blokkert ved førkjøringskontrollen.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if choice != QMessageBox.StandardButton.Yes:
                return
        workflow_id = updates["noark5_discovery_workflow"]
        if self._workflow_has_arkade.get(workflow_id, False) and not candidate:
            choice = QMessageBox.question(
                self, "Arkade 5 CLI mangler",
                "Valgt standardarbeidsflyt inneholder Arkade 5-operasjoner, "
                "men CLI er ikke konfigurert. Lagre likevel? "
                "Disse jobbene kan ikke kjøres før CLI er konfigurert.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if choice != QMessageBox.StandardButton.Yes:
                return
        if updates["app_work_subfolder"] != str(self.settings.get("app_work_subfolder", "dwm") or ""):
            choice = QMessageBox.question(
                self, "Endret Work-undermappe",
                "Du endrer den globale DWM-undermappen. Eksisterende jobbers "
                "resultatstier kan bli annerledes. Ingen resultater flyttes automatisk. "
                "Vil du lagre endringen?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if choice != QMessageBox.StandardButton.Yes:
                return
        try:
            self.api.save_setup(updates)
        except Exception as exc:
            QMessageBox.warning(self, "Setup kunne ikke lagres", str(exc))
            return
        self.accept()

    def _export(self):
        filename, _ = QFileDialog.getSaveFileName(
            self, "Eksporter setup", "dwm-setup.json", "JSON (*.json)"
        )
        if not filename:
            return
        try:
            # The existing portable exporter reads the saved, global config.
            output = export_settings(Path(filename))
        except (OSError, ValueError) as exc:
            QMessageBox.warning(self, "Eksportfeil", str(exc))
            return
        QMessageBox.information(self, "Setup eksportert", str(output))

    def _import(self):
        filename, _ = QFileDialog.getOpenFileName(self, "Importer setup", "", "JSON (*.json)")
        if not filename:
            return
        try:
            payload = json.loads(Path(filename).read_text(encoding="utf-8"))
            if not isinstance(payload, dict) or payload.get("file_type") != FILE_TYPE:
                raise ValueError("Filen er ikke en DWM-oppsetteksport.")
            if payload.get("format_version") != FORMAT_VERSION:
                raise ValueError("Ukjent versjon av oppsetteksport.")
        except (OSError, ValueError) as exc:
            QMessageBox.warning(self, "Importfeil", str(exc))
            return
        choice = QMessageBox.question(
            self, "Importer globalt Setup",
            "Dette erstatter felles DWM-innstillinger for begge GUI-ene. "
            "Eksisterende arbeidsmapper og jobbdata flyttes ikke. Importere nå?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if choice != QMessageBox.StandardButton.Yes:
            return
        try:
            import_settings(Path(filename))
            self.api.reload_setup()
        except (OSError, ValueError, RuntimeError) as exc:
            QMessageBox.warning(self, "Importfeil", str(exc))
            return
        QMessageBox.information(self, "Setup importert", "Setup er importert. Åpne Setup på nytt for å se de nye verdiene.")
        self.accept()

    def _reset(self):
        choice = QMessageBox.question(
            self, "Nullstill globalt Setup",
            "Alle felles DWM-innstillinger blir tilbakestilt til standard, "
            "inkludert kjøreoppsett og nylig brukte mapper. Fortsette?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if choice != QMessageBox.StandardButton.Yes:
            return
        try:
            reset_settings()
            self.api.reload_setup()
        except (OSError, ValueError, RuntimeError) as exc:
            QMessageBox.warning(self, "Nullstilling feilet", str(exc))
            return
        QMessageBox.information(self, "Setup nullstilt", "Standardinnstillinger er lagret. Åpne Setup på nytt for å kontrollere dem.")
        self.accept()
