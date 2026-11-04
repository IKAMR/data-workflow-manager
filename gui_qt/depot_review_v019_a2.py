"""Qt presentation for explicit whole-extraction and archive-part depot reviews.

Reuses core decisions and the existing Qt period review. No analysis, Source
writes or implicit approvals are performed by this module.
"""
from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtCore import Qt, QTimer, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QAbstractItemView, QApplication, QComboBox, QDialog, QDialogButtonBox, QFormLayout,
    QHBoxLayout, QHeaderView, QLabel, QLineEdit, QMessageBox, QPlainTextEdit,
    QPushButton, QSizePolicy, QSplitter, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget,
)

from app.depot_review_v019_a2 import (
    STATUS_LABELS, DepotReviewRow, build_depot_review_rows, record_depot_review,
)


def _render(data, *, limit=100_000) -> str:
    try:
        value = json.dumps(data, ensure_ascii=False, indent=2, default=str)
    except (ValueError, TypeError):
        value = str(data)
    return value if len(value) <= limit else value[:limit] + "\n[Visningen er forkortet]"


def _dialog_size(parent, preferred_width: int, preferred_height: int) -> tuple[int, int]:
    """Give review dialogs substantial room without exceeding a laptop desktop."""
    screen = parent.screen() if parent is not None else QApplication.primaryScreen()
    if screen is None:
        return preferred_width, preferred_height
    area = screen.availableGeometry()
    return (
        min(preferred_width, max(640, int(area.width() * 0.92))),
        min(preferred_height, max(490, int(area.height() * 0.88))),
    )


def _review_payload(row: DepotReviewRow) -> dict:
    """The same traceable evidence is available in both compact and large views."""
    return {
        "omfang": row.scope,
        "uttrekk": row.job_name,
        "jobb_id": row.job_id,
        "system_id": row.native_id if row.scope == "arkivdel" else None,
        "teknisk_status": row.technical_status,
        "depotvurdering": row.professional_status,
        "periodevurdering": row.period_status,
        "historiske_depotbeslutninger": row.history_count,
        "sist_vurdert": row.updated_at or None,
        "mangler_eller_avvik": row.warning or None,
        "faglig_grunnlag": row.details,
    }


class ReviewUserProfileDialog(QDialog):
    """Edit the established local identity; never invent an anonymous approver."""

    def __init__(self, parent=None):
        from app.user_profile import load_user_profile
        super().__init__(parent)
        self.saved = None
        profile = load_user_profile()
        self.setWindowTitle("Brukerprofil for faglig vurdering")
        self.resize(520, 260)
        layout = QVBoxLayout(self)
        intro = QLabel("Faglige depotbeslutninger signeres med samme brukerprofil som DWM-legacy. "
                       "Bruker-ID beholdes ved endring av profil.")
        intro.setWordWrap(True)
        layout.addWidget(intro)
        form = QFormLayout()
        self.name = QLineEdit(str(profile.name) if profile else "")
        self.username = QLineEdit(str(profile.username) if profile else "")
        self.email = QLineEdit(str(profile.email) if profile else "")
        form.addRow("Navn", self.name)
        form.addRow("Brukernavn", self.username)
        form.addRow("E-post", self.email)
        layout.addLayout(form)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save |
                                   QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Save).setText("Lagre brukerprofil")
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _save(self):
        from app.user_profile import save_user_profile
        try:
            self.saved = save_user_profile(self.name.text(), self.username.text(), self.email.text())
        except (ValueError, OSError) as exc:
            QMessageBox.warning(self, "Brukerprofil", str(exc))
            return
        self.accept()


class ReviewEvidenceDialog(QDialog):
    """A large, resizable read-only evidence window for the selected review."""

    def __init__(self, row: DepotReviewRow, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Vurderingsgrunnlag – " + row.title)
        self.setWindowFlag(Qt.WindowType.WindowMaximizeButtonHint, True)
        self.setMinimumSize(660, 490)
        self.resize(*_dialog_size(parent, 1180, 900))
        layout = QVBoxLayout(self)
        note = QLabel(
            row.job_id + " – " + row.job_name + " / " + row.title + "\n"
            "Lesbar evidens fra lagret Work. Kildene er ikke automatisk faglig godkjent."
        )
        note.setWordWrap(True)
        layout.addWidget(note)
        self.evidence = QPlainTextEdit(self)
        self.evidence.setReadOnly(True)
        self.evidence.setPlainText(_render(_review_payload(row), limit=250_000))
        layout.addWidget(self.evidence, 1)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)


class DepotDecisionDialog(QDialog):
    """A recorded decision for the selected scope, never a suggested status."""

    def __init__(self, row: DepotReviewRow, user, parent=None):
        super().__init__(parent)
        self.row = row
        self.user = user
        self.result = None
        self.setWindowTitle("Faglig depotvurdering – " + row.title)
        self.setWindowFlag(Qt.WindowType.WindowMaximizeButtonHint, True)
        self.setMinimumSize(660, 510)
        self.resize(*_dialog_size(parent, 1180, 900))
        layout = QVBoxLayout(self)
        introduction = QLabel(
            ("Hele uttrekket" if row.scope == "uttrekk" else "Arkivdel med system-ID: " + row.native_id)
            + "  |  " + row.job_id + " – " + row.job_name + "\n"
            "Teknisk gjennomf\u00f8rt er ikke faglig godkjent. Beslutningen gjelder kun "
            "denne rapportversjonen. Originalen og eksisterende historikk bevares."
        )
        introduction.setWordWrap(True)
        layout.addWidget(introduction)
        # One expanding reader, not a one-child splitter that can starve the form.
        evidence = QPlainTextEdit(self)
        evidence.setReadOnly(True)
        evidence.setMinimumHeight(170)
        evidence.setPlainText(_render(_review_payload(row), limit=250_000))
        evidence.setPlaceholderText("Lagret Work-evidens")
        layout.addWidget(evidence, 1)
        form = QFormLayout()
        self.status = QComboBox()
        self.status.addItem("Velg faglig vurdering", "")
        for code, label in STATUS_LABELS.items():
            self.status.addItem(label, code)
        form.addRow("Beslutning", self.status)
        form.addRow("Signeres av", QLabel(user.name + " (" + user.username + ")"))
        self.reason = QPlainTextEdit()
        self.reason.setPlaceholderText("Dokumenter grunnlaget, avvik, manglende evidens og begrunnelse for beslutningen")
        self.reason.setMinimumHeight(100)
        self.reason.setMaximumHeight(180)
        form.addRow("Begrunnelse (p\u00e5krevd)", self.reason)
        layout.addLayout(form)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save |
                                   QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Save).setText("Lagre faglig beslutning")
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _save(self):
        code = str(self.status.currentData() or "")
        note = self.reason.toPlainText().strip()
        if not code:
            QMessageBox.warning(self, "Depotvurdering", "Velg en faglig vurderingsstatus.")
            return
        if not note:
            QMessageBox.warning(self, "Depotvurdering", "Skriv en faglig begrunnelse.")
            return
        reply = QMessageBox.question(
            self, "Bekreft faglig beslutning",
            f"Registrere {STATUS_LABELS[code]} for {self.row.title}?\n\n"
            "Beslutningen lagres med tidspunkt, bruker og historikk. "
            "Eksisterende vurderinger blir ikke slettet.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        try:
            self.result = record_depot_review(self.row, status=code, reason=note, user=self.user)
        except (OSError, ValueError, TypeError, json.JSONDecodeError, RuntimeError) as exc:
            QMessageBox.warning(self, "Depotvurdering", str(exc))
            return
        self.accept()


class DepotReviewPanel(QWidget):
    """A multi-job review index inside the existing result center."""

    def __init__(self, result_center, parent=None):
        super().__init__(parent)
        self._center = result_center
        self._rows: tuple[DepotReviewRow, ...] = ()
        self._items: dict[tuple[str, str], QTreeWidgetItem] = {}
        self._initial_split_applied = False
        layout = QVBoxLayout(self)
        note = QLabel("Depotvurdering per uttrekk og per arkivdel. "
                      "DWM, Arkade 5 og KDRS Query er separate evidenskilder. "
                      "En ferdig arbeidsflyt betyr ikke at arkivuttrekket er godkjent.")
        note.setWordWrap(True)
        layout.addWidget(note)
        options = QHBoxLayout()
        options.addWidget(QLabel("Vis:"))
        self.filter = QComboBox()
        self.filter.addItem("Alle uttrekk og arkivdeler", "all")
        self.filter.addItem("Trenger faglig vurdering", "pending")
        self.filter.addItem("Faglig vurderte", "reviewed")
        self.filter.addItem("Manglende eller usikkert grunnlag", "missing")
        self.filter.currentIndexChanged.connect(self._apply_filter)
        options.addWidget(self.filter)
        options.addWidget(QLabel("S\u00f8k:"))
        self.search = QLineEdit()
        self.search.setPlaceholderText("Uttrekk, arkivdel, status, system-ID")
        self.search.textChanged.connect(self._apply_filter)
        options.addWidget(self.search, 1)
        layout.addLayout(options)
        self.summary = QLabel("Velg uttrekk med tilgjengelige Work-resultater.")
        self.summary.setWordWrap(True)
        layout.addWidget(self.summary)
        self.splitter = QSplitter(Qt.Orientation.Vertical, self)
        splitter = self.splitter
        splitter.setChildrenCollapsible(False)
        self.tree = QTreeWidget(splitter)
        self.tree.setMinimumHeight(230)
        self.tree.setHeaderLabels([
            "Uttrekk / arkivdel", "Faglig depotstatus", "Teknisk status", "Periodevurdering",
            "Vurderingspunkter", "Sist vurdert",
        ])
        self.tree.setAlternatingRowColors(True)
        self.tree.setRootIsDecorated(True)
        self.tree.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        # Keep the status columns legible at 930 px; give remaining width
        # to the archive-part name. Manual header resizing remains available.
        self.tree.header().setStretchLastSection(False)
        self.tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for column, width in ((1, 155), (2, 105), (3, 140), (4, 105), (5, 125)):
            self.tree.header().setSectionResizeMode(column, QHeaderView.ResizeMode.Interactive)
            self.tree.setColumnWidth(column, width)
        self.tree.itemSelectionChanged.connect(self._selection_changed)
        self.tree.itemDoubleClicked.connect(lambda *_: self._review_selected())
        splitter.addWidget(self.tree)
        self.detail = QPlainTextEdit(splitter)
        self.detail.setMinimumHeight(130)
        self.detail.setReadOnly(True)
        self.detail.setPlaceholderText("Velg uttrekk eller arkivdel for vurderingsgrunnlag, kilder og historikk.")
        splitter.addWidget(self.detail)
        splitter.setStretchFactor(0, 6)
        splitter.setStretchFactor(1, 4)
        splitter.setSizes([630, 370])
        layout.addWidget(splitter, 1)
        # Compact buttons with natural width, not full-width grid columns.
        self.detail_button = QPushButton("Vis grunnlag i stort vindu...")
        self.detail_button.clicked.connect(self._open_large_details)
        self.review_button = QPushButton("Vurder valgt uttrekk / arkivdel...")
        self.review_button.clicked.connect(self._review_selected)
        self.period_button = QPushButton("Vurder periode...")
        self.period_button.clicked.connect(self._period_selected)
        report = QPushButton("Åpne kilde-rapport")
        report.clicked.connect(self._open_report)
        profile = QPushButton("Brukerprofil...")
        profile.clicked.connect(self._edit_profile)
        refresh = QPushButton("Oppdater")
        refresh.clicked.connect(result_center.refresh)
        for items in ((self.review_button, self.period_button, self.detail_button),
                      (report, profile, refresh)):
            row = QHBoxLayout()
            row.setSpacing(6)
            for button in items:
                button.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
                row.addWidget(button)
            row.addStretch(1)
            layout.addLayout(row)
        self.detail_button.setEnabled(False)
        self.review_button.setEnabled(False)
        self.period_button.setEnabled(False)

    def showEvent(self, event):
        super().showEvent(event)
        # Apply once after Qt has measured the visible tab. Later manual drags
        # of the splitter must never be overwritten by tab changes or refresh.
        if not self._initial_split_applied:
            self._initial_split_applied = True
            QTimer.singleShot(0, self._allocate_initial_space)

    def _allocate_initial_space(self):
        available = self.splitter.height()
        if available > 0:
            self.splitter.setSizes([int(available * 0.62), int(available * 0.38)])

    def set_snapshots(self, snapshots, *, sources=()):
        previous = self.current_row()
        selected_key = previous.key if previous else None
        self._rows = build_depot_review_rows(snapshots, sources=sources)
        self.tree.clear()
        self._items.clear()
        parent_by_uid = {}
        for index, row in enumerate(self._rows):
            status = str(row.professional_status)
            count = "Ukjent" if row.deviation_count is None else str(row.deviation_count)
            name = (row.job_id + " – " + row.job_name if row.scope == "uttrekk"
                    else (row.title + " [" + (row.native_id if row.editable else "system-ID mangler") + "]"))
            item = QTreeWidgetItem((name, status, row.technical_status, row.period_status,
                                    count, row.updated_at[:19].replace("T", " ")))
            for column in range(item.columnCount()):
                item.setToolTip(column, item.text(column))
            item.setData(0, Qt.ItemDataRole.UserRole, index)
            if row.scope == "uttrekk":
                self.tree.addTopLevelItem(item)
                parent_by_uid[row.job_uid] = item
            else:
                root = parent_by_uid.get(row.job_uid)
                if root is not None:
                    root.addChild(item)
                else:
                    self.tree.addTopLevelItem(item)
            self._items[row.key] = item
        self.tree.expandAll()
        self._apply_filter()
        if selected_key and selected_key in self._items:
            self.tree.setCurrentItem(self._items[selected_key])
        elif self.tree.topLevelItemCount():
            self.tree.setCurrentItem(self.tree.topLevelItem(0))
        self._selection_changed()

    def current_row(self) -> DepotReviewRow | None:
        item = self.tree.currentItem()
        if item is None:
            return None
        index = item.data(0, Qt.ItemDataRole.UserRole)
        return self._rows[index] if isinstance(index, int) and 0 <= index < len(self._rows) else None

    def _apply_filter(self, _unused=None):
        kind = str(self.filter.currentData() or "all")
        needle = self.search.text().strip().casefold()
        visible = 0
        for row in self._rows:
            item = self._items.get(row.key)
            if item is None:
                continue
            checked = row.professional_status in ("Akseptert", "Akseptert med avvik",
                    "Krever avklaring", "Nytt uttrekk kreves") and row.history_count > 0
            matches = (kind == "all" or kind == "reviewed" and checked
                       or kind == "pending" and not checked
                       or kind == "missing" and bool(row.warning or not row.report_path))
            matches = matches and (not needle or any(needle in value.casefold() for value in (
                row.job_name, row.job_id, row.native_id, row.title, row.professional_status,
                row.technical_status, row.period_status,
            )))
            item.setHidden(not matches)
            visible += bool(matches)
        # Keep extraction-level parent visible if a matching child is visible.
        for idx in range(self.tree.topLevelItemCount()):
            parent = self.tree.topLevelItem(idx)
            if any(not parent.child(i).isHidden() for i in range(parent.childCount())):
                parent.setHidden(False)
        self.summary.setText(
            f"{visible} av {len(self._rows)} vurderingsomfang. "
            "Et manglende funn er ukjent, ikke automatisk null eller godkjent."
        )

    def _selection_changed(self):
        row = self.current_row()
        self.detail_button.setEnabled(bool(row))
        self.review_button.setEnabled(bool(row and row.editable))
        self.period_button.setEnabled(bool(row and row.report_path))
        if not row:
            self.detail.clear()
            return
        self.detail.setPlainText(_render(_review_payload(row)))

    def _open_large_details(self):
        row = self.current_row()
        if row is not None:
            ReviewEvidenceDialog(row, self).exec()

    def _identity(self):
        from app.identity_provider import LocalUserProfileIdentityProvider
        value = LocalUserProfileIdentityProvider().current_identity()
        if value is not None:
            return value
        reply = QMessageBox.question(
            self, "Brukerprofil mangler",
            "Faglig depotvurdering krever registrert brukerprofil. Opprette profil n\u00e5?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return None
        if ReviewUserProfileDialog(self).exec() != QDialog.DialogCode.Accepted:
            return None
        return LocalUserProfileIdentityProvider().current_identity()

    def _edit_profile(self):
        ReviewUserProfileDialog(self).exec()

    def _review_selected(self):
        row = self.current_row()
        if not row or not row.editable:
            QMessageBox.information(self, "Depotvurdering", "Velg et omfang med entydig, lesbar rapport.")
            return
        user = self._identity()
        if user is None:
            return
        dialog = DepotDecisionDialog(row, user, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._center.refresh()

    def _period_selected(self):
        row = self.current_row()
        if row is None or not row.report_path:
            return
        center = self._center
        if center._report_api is None:
            QMessageBox.information(self, "Periodevurdering",
                "Periodevurdering trenger jobben tilkoblet en jobbliste. "
                "Den lagrede evidensen er fortsatt synlig her.")
            return
        key = (row.job_uid, row.native_id if row.scope == "arkivdel" else "")
        table = center._trees.get("Periodevurdering")
        if table is not None:
            for index in range(table.topLevelItemCount()):
                item = table.topLevelItem(index)
                identity = item.data(0, Qt.ItemDataRole.UserRole + 2)
                if isinstance(identity, (list, tuple)) and tuple(identity) == key:
                    table.setCurrentItem(item)
                    center.tabs.setCurrentWidget(center._pages["Periodevurdering"])
                    center._open_period_review()
                    return
        QMessageBox.information(self, "Periodevurdering",
            "Fant ikke tilsvarende periodegrunnlag. Velg en rad i fanen Periodevurdering.")

    def _open_report(self):
        row = self.current_row()
        if row and row.report_path and row.report_path.is_file():
            self._center._open_file_path(str(row.report_path))
        else:
            QMessageBox.warning(self, "Depotrapport", "Rapporten er ikke tilgjengelig.")
