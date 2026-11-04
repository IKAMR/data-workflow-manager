"""v0.1.9-a1: source audit and verified Arkade 5 coverage in the Qt result center.

All earlier v0.1.8 tabs, annual graphs, external evidence choices, period
reviews and both existing report families remain available unchanged.
"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import (
    QApplication, QComboBox, QFileDialog, QHBoxLayout, QLabel, QLineEdit, QMessageBox,
    QMenu, QPushButton, QSizePolicy, QToolButton, QTreeWidgetItem,
)

from app.evidence_workbench_v019_a1 import (
    arkade_coverage, export_inventory, source_inventory,
)
from .result_center_v018_a13 import ResultCenterWindow as _PreviousResultCenter


_RELATION_LABELS = {
    "equivalent": "Ekvivalent (dokumentert)",
    "partial": "Delvis overlapp",
    "complementary": "Komplementær",
    "arkade_only": "Kun Arkade 5",
    "unmapped": "Ikke kartlagt",
}


def _normal_window_geometry(area) -> tuple[int, int, int, int]:
    """A readable initial window, centered and bounded on ultrawide/laptop screens.

    The operator may resize or maximize manually; initial display never fills
    an entire ultrawide monitor. Coordinates use QScreen.availableGeometry so
    a secondary monitor's origin and Windows taskbar are respected.
    """
    width = min(1380, max(760, area.width() - 80), area.width())
    height = min(860, max(540, area.height() - 70), area.height())
    x = area.x() + (area.width() - width) // 2
    y = area.y() + (area.height() - height) // 2
    return x, y, width, height


class ResultCenterWindow(_PreviousResultCenter):
    """Add specialist legacy coverage and provenance to the shared Work UI."""

    def __init__(self, *args, **kwargs):
        self._a1_ready = False
        self._a1_sources = ()
        self._a1_coverage = ()
        super().__init__(*args, **kwargs)

        self._make_tree_tab(
            "Kildeoversikt",
            ("Uttrekk", "Kildetype", "Import / omfang", "Status", "Antall", "Enhet", "SHA-256"),
        )
        self._make_tree_tab(
            "Arkade-dekning",
            ("Uttrekk", "Import-ID", "Arkade-test", "Testnavn", "Arkade-status", "Relasjon", "DWM-test(er)"),
        )
        self._create_source_controls()
        self._create_coverage_controls()
        self._create_kdrs_controls()
        # a2 reuses the same Work snapshots and the established decision APIs.
        from .depot_review_v019_a2 import DepotReviewPanel
        self._a2_panel = DepotReviewPanel(self, self.tabs)
        self.tabs.addTab(self._a2_panel, "Depotvurdering")
        self._a1_ready = True
        self._configure_responsive_window()
        self.refresh()

    def _configure_responsive_window(self):
        """Readable normal window with left-aligned, natural-width controls.

        Keep every inherited button and signal. No maximize on startup, and
        no layout columns that stretch the buttons across an ultrawide screen.
        """
        self.setMinimumSize(760, 540)
        outer = self.layout()
        # a13 creates a single horizontal footer with seven buttons.
        # Place them in two compact rows: 4 + 3, aligned to the left.
        footer_item = outer.takeAt(outer.count() - 1)
        old_footer = footer_item.layout()
        if old_footer is not None:
            buttons = []
            while old_footer.count():
                item = old_footer.takeAt(0)
                if item.widget() is not None:
                    buttons.append(item.widget())
            for start in range(0, len(buttons), 4):
                row = QHBoxLayout()
                row.setSpacing(6)
                for button in buttons[start:start + 4]:
                    button.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
                    row.addWidget(button)
                row.addStretch(1)
                outer.addLayout(row)
        else:
            # Preserve the original footer if a13 changes its structure.
            outer.addItem(footer_item)

        # Every tab is accessible from the compact menu on narrow monitors.
        heading = outer.itemAt(0).layout()
        self.tab_menu_button = QToolButton(self)
        self.tab_menu_button.setText("Faner...")
        self.tab_menu_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self._tab_menu = QMenu(self.tab_menu_button)
        self._tab_menu.aboutToShow.connect(self._populate_tab_menu)
        self.tab_menu_button.setMenu(self._tab_menu)
        heading.insertWidget(1, self.tab_menu_button)
        self.tabs.tabBar().setUsesScrollButtons(True)

        parent = self.parentWidget()
        screen = parent.screen() if parent is not None else self.screen()
        if screen is None:
            screen = QApplication.primaryScreen()
        if screen is not None:
            self.setGeometry(*_normal_window_geometry(screen.availableGeometry()))
        else:
            self.resize(1280, 800)

    def _populate_tab_menu(self):
        self._tab_menu.clear()
        active = self.tabs.currentIndex()
        for index in range(self.tabs.count()):
            action = self._tab_menu.addAction(self.tabs.tabText(index))
            action.setCheckable(True)
            action.setChecked(index == active)
            action.triggered.connect(lambda _checked=False, i=index: self.tabs.setCurrentIndex(i))

    def _create_source_controls(self):
        title = "Kildeoversikt"
        form = QHBoxLayout()
        form.addWidget(QLabel("Kilde:"))
        self.source_kind = QComboBox()
        self.source_kind.addItem("Alle kilder", "")
        for category in ("DWM – tekniske kontroller", "Arkade 5 – Noark 5",
                         "Arkade 5 – PRONOM", "KDRS Query", "Depotrapporter"):
            self.source_kind.addItem(category, category)
        form.addWidget(self.source_kind)
        form.addWidget(QLabel("Søk:"))
        self.source_search = QLineEdit()
        self.source_search.setPlaceholderText("Uttrekk, import, kilde, status eller SHA-256")
        form.addWidget(self.source_search, 1)
        self._pages[title].layout().insertLayout(0, form)
        self.source_count = QLabel()
        self.source_count.setWordWrap(True)
        self._pages[title].layout().insertWidget(1, self.source_count)
        buttonrow = QHBoxLayout()
        export = QPushButton("Eksporter kildeoversikt…")
        export.clicked.connect(self._export_source_overview)
        buttonrow.addWidget(export)
        note = QLabel("CSV, HTML eller JSON. Ingen analyser eller faglige valg endres.")
        note.setWordWrap(True)
        buttonrow.addWidget(note, 1)
        self._pages[title].layout().addLayout(buttonrow)
        self.source_kind.currentIndexChanged.connect(self._filter_sources)
        self.source_search.textChanged.connect(self._filter_sources)

    def _create_coverage_controls(self):
        title = "Arkade-dekning"
        form = QHBoxLayout()
        form.addWidget(QLabel("Relasjon:"))
        self.coverage_kind = QComboBox()
        self.coverage_kind.addItem("Alle relasjoner", "")
        for value, label in _RELATION_LABELS.items():
            self.coverage_kind.addItem(label, value)
        form.addWidget(self.coverage_kind)
        form.addWidget(QLabel("Søk:"))
        self.coverage_search = QLineEdit()
        self.coverage_search.setPlaceholderText("Test-ID, navn, uttrekk eller DWM-test")
        form.addWidget(self.coverage_search, 1)
        self._pages[title].layout().insertLayout(0, form)
        self.coverage_count = QLabel()
        self.coverage_count.setWordWrap(True)
        self._pages[title].layout().insertWidget(1, self.coverage_count)
        footnote = QLabel(
            "Relasjoner hentes fra den verifiserte DWM–Arkade 5-mappingen i legacy. "
            "Lik Noark-nummerering innebærer ikke automatisk likeverdige tester. "
            "Arkade-status og DWM-status er to separate observasjoner."
        )
        footnote.setWordWrap(True)
        self._pages[title].layout().addWidget(footnote)
        self.coverage_kind.currentIndexChanged.connect(self._filter_coverage)
        self.coverage_search.textChanged.connect(self._filter_coverage)

    def _create_kdrs_controls(self):
        # Restore the filterable legacy KDRS result browsing, while retaining
        # the v0.1.8 source-preserving and explicit evidence-choice workflow.
        title = "KDRS Query"
        form = QHBoxLayout()
        form.addWidget(QLabel("Rapport:"))
        self.kdrs_kind = QComboBox()
        for label, kind in (("Alle", ""), ("Standard", "standard"),
                            ("U1", "u1"), ("U2", "u2")):
            self.kdrs_kind.addItem(label, kind)
        form.addWidget(self.kdrs_kind)
        form.addWidget(QLabel("Søk:"))
        self.kdrs_search = QLineEdit()
        self.kdrs_search.setPlaceholderText("Uttrekk, rapport, import-ID, kilde eller SHA-256")
        form.addWidget(self.kdrs_search, 1)
        self._pages[title].layout().insertLayout(0, form)
        self.kdrs_count = QLabel()
        self.kdrs_count.setWordWrap(True)
        self._pages[title].layout().insertWidget(1, self.kdrs_count)
        self.kdrs_kind.currentIndexChanged.connect(self._filter_kdrs)
        self.kdrs_search.textChanged.connect(self._filter_kdrs)

    def refresh(self):
        super().refresh()
        if not getattr(self, "_a1_ready", False):
            return
        self._a1_sources = source_inventory(self._snapshots)
        self._a1_coverage = arkade_coverage(self._snapshots)
        self._trees["Kildeoversikt"].clear()
        self._details["Kildeoversikt"].clear()
        for record in self._a1_sources:
            self._row(
                "Kildeoversikt",
                (record.job_label, record.source, record.import_id,
                 record.status, record.count if record.count is not None else "Ukjent",
                 record.unit, record.sha256),
                details=record.details, file=record.file,
            )
        self._trees["Arkade-dekning"].clear()
        self._details["Arkade-dekning"].clear()
        for record in self._a1_coverage:
            self._row(
                "Arkade-dekning",
                (record.job_label, record.import_id, record.test_id, record.test_name,
                 record.arkade_status, _RELATION_LABELS.get(record.relation, record.relation),
                 ", ".join(record.dwm_test_ids) if record.dwm_test_ids else "–"),
                details={"dokumentert_relasjon": record.relation,
                         "begrunnelse": record.reason,
                         "DWM_testkandidater": record.dwm_test_ids,
                         "kilde_sha256": record.sha256,
                         "jobb_uid": record.job_uid},
                file=record.file,
            )
        self._filter_sources()
        self._filter_coverage()
        self._filter_kdrs()
        self._a2_panel.set_snapshots(self._snapshots, sources=self._a1_sources)

    def show_depot_review(self):
        self.tabs.setCurrentWidget(self._a2_panel)

    @staticmethod
    def _match(item: QTreeWidgetItem, needle: str) -> bool:
        return not needle or any(needle in item.text(col).casefold()
                                 for col in range(item.columnCount()))

    def _filter_sources(self, _ignored=None):
        table = self._trees["Kildeoversikt"]
        wanted = str(self.source_kind.currentData() or "")
        search = self.source_search.text().strip().casefold()
        count = 0
        for index in range(table.topLevelItemCount()):
            item = table.topLevelItem(index)
            visible = (not wanted or item.text(1) == wanted) and self._match(item, search)
            item.setHidden(not visible)
            count += bool(visible)
        self.source_count.setText(
            f"{count} av {table.topLevelItemCount()} kildeoppføringer. "
            "Manglende data er ukjent, ikke null. Eksterne kilder er ikke automatisk godkjent."
        )

    def _filter_coverage(self, _ignored=None):
        table = self._trees["Arkade-dekning"]
        wanted = str(self.coverage_kind.currentData() or "")
        search = self.coverage_search.text().strip().casefold()
        count = 0
        relation_counts: dict[str, int] = {}
        for index, record in enumerate(self._a1_coverage):
            item = table.topLevelItem(index)
            relation_counts[record.relation] = relation_counts.get(record.relation, 0) + 1
            visible = (not wanted or record.relation == wanted) and self._match(item, search)
            item.setHidden(not visible)
            count += bool(visible)
        summary = " | ".join(f"{_RELATION_LABELS.get(key, key)}: {n}"
                             for key, n in relation_counts.items())
        self.coverage_count.setText(
            f"{count} av {len(self._a1_coverage)} Arkade-tester. " +
            (summary if summary else "Ingen lagret Arkade 5-testgrunnlag i valgt Work.")
        )

    def _filter_kdrs(self, _ignored=None):
        table = self._trees["KDRS Query"]
        wanted = str(self.kdrs_kind.currentData() or "")
        search = self.kdrs_search.text().strip().casefold()
        count = 0
        for index in range(table.topLevelItemCount()):
            item = table.topLevelItem(index)
            report_type = item.text(2).strip().casefold()
            placeholder = item.text(0).startswith("Ingen lagret evidens")
            # Legacy reports may call a variant "U1"/"U2"; never infer
            # identical semantics between separate report types.
            matches_kind = (not wanted or report_type == wanted
                            or report_type.startswith(wanted + " ")
                            or report_type.startswith(wanted + "-"))
            visible = matches_kind and self._match(item, search)
            # Keep the existing empty-state text visible, but never count it as evidence.
            if placeholder:
                visible = not wanted and not search
            item.setHidden(not visible)
            count += bool(visible and not placeholder)
        self.kdrs_count.setText(
            f"{count} av {table.topLevelItemCount()} lagrede kildeoppføringer. "
            "Standard, U1 og U2 blandes ikke til én måleverdi."
        )

    def _export_source_overview(self):
        if not self._snapshots:
            QMessageBox.information(self, "Kildeoversikt", "Ingen tilgjengelige Work-data å eksportere.")
            return
        settings = QSettings("IKAMR", "DWM-Qt")
        previous = str(settings.value("qt/last_report_output_dir", "") or "")
        base = Path(previous) if previous and Path(previous).is_dir() else Path.home()
        filename, selected_filter = QFileDialog.getSaveFileName(
            self, "Eksporter sporbar kildeoversikt", str(base / "dwm-evidensoversikt.csv"),
            "CSV (*.csv);;HTML (*.html);;JSON (*.json)",
        )
        if not filename:
            return
        target = Path(filename)
        if not target.suffix:
            target = target.with_suffix(".html" if "HTML" in selected_filter else
                                        ".json" if "JSON" in selected_filter else ".csv")
        overwrite = False
        if target.exists():
            reply = QMessageBox.question(
                self, "Eksisterende eksportfil", f"Overskrive eksisterende fil?\n{target}",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                return
            overwrite = True
        try:
            path = export_inventory(target, self._a1_sources, self._snapshots, overwrite=overwrite)
        except (OSError, ValueError) as error:
            QMessageBox.warning(self, "Eksport av kildeoversikt", str(error))
            return
        settings.setValue("qt/last_report_output_dir", str(path.parent))
        QMessageBox.information(self, "Kildeoversikt", f"Sporbar kildeoversikt er lagret:\n{path}")
