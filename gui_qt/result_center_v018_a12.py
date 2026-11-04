"""Read-only, independent Qt result window backed by the DWM Work directory.

The window never imports Tk or starts analysis. It can be kept open while
switching the active job in the main application, with the job name in title.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QAbstractItemView, QDialog, QHBoxLayout, QLabel, QMessageBox,
    QPushButton, QTabWidget, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget,
    QHeaderView,
)

from app.result_center_v018_a12 import (
    CATEGORY_ORDER, archive_part_rows, depot_facts, discover_results,
)


class ResultCenterWindow(QDialog):
    """One read-only view bound to a single job's Work, not a joblist alias."""

    def __init__(self, work: str | Path | None, *, display_name: str, parent=None):
        super().__init__(parent, Qt.WindowType.Window)
        self._work = Path(work) if work is not None else None
        self._name = str(display_name)
        self.setWindowTitle("Resultatvisninger – " + self._name)
        self.setMinimumSize(770, 490)
        self.resize(1050, 720)
        outer = QVBoxLayout(self)
        heading = QLabel("Resultatvisninger – " + self._name)
        heading.setStyleSheet("font-size: 17px; font-weight: 600;")
        outer.addWidget(heading)
        self.note = QLabel("Viser lagrede resultater i Work. Ingen ny analyse eller import utføres.")
        self.note.setWordWrap(True)
        outer.addWidget(self.note)
        self.tabs = QTabWidget(self)
        outer.addWidget(self.tabs, 1)
        self.trees: dict[str, QTreeWidget] = {}
        layouts = {
            "Oversikt": ("Egenskap", "Verdi"),
            "Arkivdeler": ("Arkivdel", "Status", "Mapper", "Registreringer", "Dokumentobjekter"),
            "Tekniske kontroller": ("Resultat", "Plassering", "Dato"),
            "Arkade 5 / PRONOM": ("Resultat", "Plassering", "Dato"),
            "KDRS Query": ("Resultat", "Plassering", "Dato"),
            "Depotrapporter": ("Resultat", "Plassering", "Dato"),
            "Alle resultater": ("Kilde", "Resultat", "Plassering"),
        }
        for title, columns in layouts.items():
            page = QWidget(self.tabs)
            form = QVBoxLayout(page)
            tree = QTreeWidget(page)
            tree.setHeaderLabels(list(columns))
            tree.setRootIsDecorated(False)
            tree.setAlternatingRowColors(True)
            tree.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
            tree.header().setStretchLastSection(True)
            tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
            if len(columns) >= 3:
                tree.header().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
            tree.itemDoubleClicked.connect(self._open_item)
            form.addWidget(tree)
            self.trees[title] = tree
            self.tabs.addTab(page, title)
        actions = QHBoxLayout()
        refresh = QPushButton("Oppdater visning")
        refresh.clicked.connect(self.refresh)
        actions.addWidget(refresh)
        open_result = QPushButton("Åpne valgt fil")
        open_result.clicked.connect(self._open_current)
        actions.addWidget(open_result)
        open_work = QPushButton("Åpne Work-mappe")
        open_work.clicked.connect(self._open_work)
        actions.addWidget(open_work)
        actions.addStretch(1)
        outer.addLayout(actions)
        self.refresh()

    def _add_artifacts(self, tab_name, entries, *, all_groups=False):
        tree = self.trees[tab_name]
        for entry in sorted(entries, key=lambda v: (v.modified_at, v.relative_path), reverse=True):
            timestamp = datetime.fromtimestamp(entry.modified_at).strftime("%Y-%m-%d %H:%M")
            values = ([entry.category, entry.title, entry.relative_path]
                      if all_groups else [entry.title, entry.relative_path, timestamp])
            row = QTreeWidgetItem(values)
            row.setData(0, Qt.ItemDataRole.UserRole, str(entry.path))
            row.setToolTip(0, str(entry.path))
            tree.addTopLevelItem(row)

    def refresh(self):
        model = discover_results(self._work)
        for tree in self.trees.values():
            tree.clear()
        if model.warnings:
            self.note.setText("Viser lagret Work-evidens. " + "; ".join(model.warnings[:3]))
        else:
            self.note.setText("Tallene er fra den sist lagrede depotrapporten, ikke nødvendigvis "
                              "fra nyere evidens i Work. Ingen analyse eller import utføres. "
                              "Fullført arbeidsflyt betyr ikke depotgodkjenning.")
        if model.depot_report:
            for key, value in depot_facts(model.depot_report):
                self.trees["Oversikt"].addTopLevelItem(QTreeWidgetItem([key, value]))
            for item in archive_part_rows(model.depot_report):
                info = item.get("archive_part") or {}
                self.trees["Arkivdeler"].addTopLevelItem(QTreeWidgetItem([
                    str(info.get("title") or info.get("system_id") or "(uten navn)"),
                    str(info.get("status") or "Ikke vurdert"),
                    str(item.get("folder_count", "–")),
                    str(item.get("registration_count", "–")),
                    str(item.get("document_object_count", "–")),
                ]))
        else:
            self.trees["Oversikt"].addTopLevelItem(QTreeWidgetItem([
                "Depotrapport", "Ingen lesbar depotvalideringsrapport i dette Work-området",
            ]))
        groups = model.by_category
        self._add_artifacts("Tekniske kontroller", groups["XPath / Noark 5"] + groups["Analysevisninger"] + groups["XML / XSD"] + groups["Andre resultater"])
        self._add_artifacts("Arkade 5 / PRONOM", groups["Arkade 5"] + groups["PRONOM"])
        self._add_artifacts("KDRS Query", groups["KDRS Query"])
        self._add_artifacts("Depotrapporter", groups["Depotrapporter"])
        self._add_artifacts("Alle resultater", model.artifacts, all_groups=True)
        if not groups["KDRS Query"]:
            self.trees["KDRS Query"].addTopLevelItem(QTreeWidgetItem([
                "Ingen importerte KDRS Query-filer funnet", "", "",
            ]))
        if not model.artifacts:
            self.trees["Alle resultater"].addTopLevelItem(QTreeWidgetItem([
                "Ingen lagrede DWM-resultater funnet", "", "",
            ]))

    def _open_item(self, item, _column=0):
        raw = item.data(0, Qt.ItemDataRole.UserRole)
        if not raw:
            return
        path = Path(str(raw))
        overview = discover_results(self._work)
        # Re-check the authority at click time; do not follow changed symlinks.
        if not any(artifact.path == path for artifact in overview.artifacts) or not path.is_file():
            QMessageBox.warning(self, "Resultat", "Filen er ikke tilgjengelig i dette Work-området.")
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))

    def _open_current(self):
        tree = self.trees[self.tabs.tabText(self.tabs.currentIndex())]
        item = tree.currentItem()
        if item is not None:
            self._open_item(item)

    def _open_work(self):
        if self._work is not None and self._work.is_dir():
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(self._work)))
        else:
            QMessageBox.information(self, "Work", "Work-mappen er ikke tilgjengelig.")
