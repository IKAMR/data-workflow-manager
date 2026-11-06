"""v0.1.9-a4: read-only preview and explicit confirmation of storage-root mapping."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QSettings
from PySide6.QtWidgets import (
    QCheckBox, QDialog, QFileDialog, QGridLayout, QHBoxLayout,
    QHeaderView, QLabel, QLineEdit, QMessageBox, QPlainTextEdit,
    QPushButton, QTreeWidget, QTreeWidgetItem, QVBoxLayout,
)

from app.storage_portability_v019_a4 import RootRebasePlan


class StorageRootsDialog(QDialog):
    """One physical/logical root at a time; never move or copy data."""

    def __init__(self, api, parent=None):
        super().__init__(parent)
        self.api = api
        self.settings = QSettings("IKAMR", "DWM-Qt")
        self._preview: RootRebasePlan | None = None
        self.applied_jobs: tuple[str, ...] = ()
        self.setWindowTitle("Omkoble lagringsrot – Source, Work og AIP")
        self.resize(1120, 740)
        self.setMinimumSize(760, 520)
        layout = QVBoxLayout(self)
        intro = QLabel(
            "Velg én gammel og én ny rotmappe, for eksempel D:\\ og F:\\. "
            "DWM bruker relative delstier innenfor roten. Source, Work og AIP "
            "som ligger på andre disker forblir uendret. Ingen data kopieres, "
            "flyttes eller analyseres på nytt."
        )
        intro.setWordWrap(True)
        layout.addWidget(intro)

        grid = QGridLayout()
        self.old = QLineEdit(str(self.settings.value("qt/a4_last_old_root", "") or ""))
        self.old.setPlaceholderText("Eksempel: D:\\ eller \\\\server\\gammel-andel")
        self.new = QLineEdit(str(self.settings.value("qt/a4_last_new_root", "") or ""))
        self.new.setPlaceholderText("Eksempel: F:\\ eller \\\\server\\ny-andel")
        grid.addWidget(QLabel("Gammel rotmappe:"), 0, 0)
        grid.addWidget(self.old, 0, 1)
        grid.addWidget(QLabel("Ny rotmappe:"), 1, 0)
        grid.addWidget(self.new, 1, 1)
        browse = QPushButton("Velg ny mappe…")
        browse.clicked.connect(self._browse_new)
        grid.addWidget(browse, 1, 2)
        layout.addLayout(grid)
        self.old.textChanged.connect(self._invalidate)
        self.new.textChanged.connect(self._invalidate)

        controls = QHBoxLayout()
        self.details = QCheckBox("Vis alle relative lagringsstier")
        self.details.setChecked(True)
        self.details.toggled.connect(self._populate)
        controls.addWidget(self.details)
        controls.addStretch(1)
        self.preview_button = QPushButton("Kontroller stier")
        self.preview_button.clicked.connect(self._make_preview)
        controls.addWidget(self.preview_button)
        layout.addLayout(controls)

        self.summary = QLabel("Ingen kontroll gjennomført. En forhåndsvisning endrer ingenting.")
        self.summary.setWordWrap(True)
        layout.addWidget(self.summary)
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(("Jobb / lagringsrolle", "Gammel sti", "Ny sti", "Kontroll"))
        self.tree.setUniformRowHeights(True)
        self.tree.setAlternatingRowColors(True)
        self.tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.tree.header().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.tree.header().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.tree.header().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        layout.addWidget(self.tree, 4)
        self.messages = QPlainTextEdit()
        self.messages.setReadOnly(True)
        self.messages.setPlaceholderText("Avvik, usikre lagringsroller og nødvendige kontroller vises her.")
        self.messages.setMaximumHeight(190)
        layout.addWidget(self.messages, 1)

        bottom = QHBoxLayout()
        self.apply_button = QPushButton("Bruk godkjent omkobling")
        self.apply_button.setEnabled(False)
        self.apply_button.clicked.connect(self._apply)
        bottom.addWidget(self.apply_button)
        bottom.addStretch(1)
        close = QPushButton("Lukk")
        close.clicked.connect(self.reject)
        bottom.addWidget(close)
        layout.addLayout(bottom)

    def _browse_new(self):
        current = self.new.text().strip()
        folder = QFileDialog.getExistingDirectory(self, "Velg ny lagringsrot", current)
        if folder:
            self.new.setText(folder)

    def _invalidate(self, _value=None):
        self._preview = None
        self.apply_button.setEnabled(False)
        self.summary.setText("Stiene er endret. Kontroller på nytt før omkobling.")
        self.tree.clear()
        self.messages.clear()

    def _make_preview(self):
        try:
            self._preview = self.api.preview_storage_root_rebase(
                self.old.text().strip(), self.new.text().strip()
            )
        except Exception as exc:
            self._preview = None
            self.apply_button.setEnabled(False)
            QMessageBox.warning(self, "Lagringsrot", str(exc))
            return
        self._populate()

    def _populate(self, _checked=None):
        self.tree.clear()
        plan = self._preview
        if plan is None:
            return
        for job in plan.jobs:
            state = "BLOKKERT" if job.errors else "Kontrollert – krever godkjenning"
            parent = QTreeWidgetItem(self.tree, (
                f"{job.job_id} – {job.name}", job.work_manifest_before,
                job.work_manifest_after, state,
            ))
            parent.setToolTip(0, "Varig jobb-ID: " + (job.job_uid or "utkast"))
            if self.details.isChecked():
                for role in job.roles:
                    item = QTreeWidgetItem(parent, (
                        role.field, role.before, role.after, role.note,
                    ))
                    item.setToolTip(0, "Relativt til valgt rot: " + role.relative)
            parent.setExpanded(True)
        self.summary.setText(
            f"{len(plan.jobs)} berørte jobber · {plan.role_count} lagringsstier · "
            f"{len(plan.errors)} blokkerende feil · {len(plan.warnings)} kontrollmerknader"
        )
        errors = "\n".join("FEIL: " + text for text in plan.errors)
        warnings = "\n".join("MERKNAD: " + text for text in plan.warnings)
        self.messages.setPlainText(
            "\n".join(filter(None, (errors, warnings))) or
            "Stiene er kontrollert. Ingen endringer er gjort."
        )
        self.apply_button.setEnabled(bool(plan.jobs) and not plan.errors)

    def _apply(self):
        plan = self._preview
        if plan is None or not plan.jobs or plan.errors:
            return
        confirmation = (
            f"Koble om {len(plan.jobs)} jobber og {plan.role_count} lagringsroller "
            f"fra {plan.old_root} til {plan.new_root}?\n\n"
            "Kun valgte stier som ligger under gammel rot endres. "
            "Work-ID kontrolleres på nytt. Ingen mapper, kildefiler eller AIP-data "
            "kopieres eller flyttes.\n\n"
            "Endringen skrives i autoritativ Work per jobb; dette er ikke én "
            "atomisk transaksjon for hele jobblisten. Ved feil stoppes omkoblingen. "
            "Lagre .n5jobs når omkoblingen er fullført, og kjør preflight før neste kjøring."
        )
        if plan.warnings:
            confirmation += f"\n\n{len(plan.warnings)} merknader krever faglig kontroll."
        answer = QMessageBox.question(
            self, "Godkjenn rotomkobling", confirmation,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            self.applied_jobs = self.api.rebase_storage_root(plan, consent=True)
        except Exception as exc:
            QMessageBox.critical(self, "Rotomkobling stoppet", str(exc))
            self._invalidate()
            return
        self.settings.setValue("qt/a4_last_old_root", plan.old_root)
        self.settings.setValue("qt/a4_last_new_root", plan.new_root)
        self.accept()
