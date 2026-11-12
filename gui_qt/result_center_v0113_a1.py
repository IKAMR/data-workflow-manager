"""Annual view for v0.1.13-a1: direct Qt subclass, no bootstrap monkeypatch.

The annual chart/table are constructed in their final QSplitter ownership tree.
Existing tabs, data loading, PRONOM and Siegfried behavior remain inherited.
"""
from __future__ import annotations

import csv
from pathlib import Path

from PySide6.QtCore import Qt, QSettings, QTimer
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QFileDialog, QHBoxLayout, QHeaderView,
    QLabel, QMessageBox, QPushButton, QScrollArea, QSplitter,
    QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget,
)

from app.annual_v0113_a1 import annual_table_with_coverage
from app.result_evidence_v018_a13 import METRICS, kdrs_annual_table, safe_json
from .result_center_v018_a13 import YearBarChart
from .result_center_siegfried_v0111_a3 import ResultCenterWindow as _StableResultCenter


class ResultCenterWindow(_StableResultCenter):
    """Only extend Årsfordeling; preserve v0.1.12's other result views."""

    def _make_annual_tab(self):
        page = QWidget(self.tabs)
        body = QVBoxLayout(page)

        controls = QHBoxLayout()
        controls.addWidget(QLabel("Årsserie / omfang:"))
        self.year_scope = QComboBox(page)
        self.year_scope.setMinimumWidth(440)
        self.year_scope.currentIndexChanged.connect(self._update_annual)
        controls.addWidget(self.year_scope, 1)
        body.addLayout(controls)

        metrics_row = QHBoxLayout()
        metrics_row.addWidget(QLabel("Vis:"))
        self.metric_checks = {}
        for key, label in METRICS:
            checkbox = QCheckBox(label, page)
            checkbox.setChecked(True)
            checkbox.toggled.connect(self._update_annual)
            self.metric_checks[key] = checkbox
            metrics_row.addWidget(checkbox)
        metrics_row.addStretch(1)
        body.addLayout(metrics_row)

        mode_row = QHBoxLayout()
        self._annual_mode_buttons = {}
        for key, label in (
            ("both", "Diagram + tall"),
            ("chart", "Bare diagram"),
            ("table", "Bare tall"),
        ):
            button = QPushButton(label, page)
            button.setCheckable(True)
            button.clicked.connect(lambda _checked=False, mode=key: self._set_annual_mode(mode))
            mode_row.addWidget(button)
            self._annual_mode_buttons[key] = button
        mode_row.addStretch(1)
        body.addLayout(mode_row)

        self.year_note = QLabel(
            "Årsvolum fra lagret depotrapport. Manglende verdier er ukjent, ikke 0.", page
        )
        self.year_note.setWordWrap(True)
        body.addWidget(self.year_note)

        # No widget from v0.1.12 is moved or reparented.
        self.annual_splitter = QSplitter(Qt.Orientation.Vertical, page)
        self.annual_splitter.setChildrenCollapsible(False)
        self.chart_scroll = QScrollArea(self.annual_splitter)
        self.chart_scroll.setWidgetResizable(False)
        self.chart = YearBarChart()
        self.chart_scroll.setWidget(self.chart)
        self.chart_scroll.setMinimumHeight(85)
        self.year_table = QTreeWidget(self.annual_splitter)
        self.year_table.setMinimumHeight(90)
        self.year_table.setRootIsDecorated(False)
        self.year_table.setAlternatingRowColors(True)
        self.year_table.setHeaderLabels(["År"] + [name for _, name in METRICS])
        for col in range(len(METRICS) + 1):
            self.year_table.header().setSectionResizeMode(col, QHeaderView.ResizeMode.Stretch)
        self.annual_splitter.addWidget(self.chart_scroll)
        self.annual_splitter.addWidget(self.year_table)
        self.annual_splitter.setStretchFactor(0, 3)
        self.annual_splitter.setStretchFactor(1, 2)
        body.addWidget(self.annual_splitter, 1)

        export_row = QHBoxLayout()
        export = QPushButton("Eksporter årstabell til CSV…", page)
        export.clicked.connect(self._export_annual_csv)
        export_row.addWidget(export)
        export_row.addStretch(1)
        body.addLayout(export_row)

        self.tabs.addTab(page, "Årsfordeling")
        self._pages["Årsfordeling"] = page
        self._annual_settings = QSettings("IKAMR", "DWM-Qt")
        saved_mode = str(self._annual_settings.value("results/annual_mode", "both"))
        self._annual_mode = saved_mode if saved_mode in ("both", "chart", "table") else "both"
        for key, button in self._annual_mode_buttons.items():
            button.setChecked(key == self._annual_mode)
        # Apply visibility/geometry only after the complete result center is built.
        QTimer.singleShot(0, self._restore_annual_layout)
        self.annual_splitter.splitterMoved.connect(self._remember_annual_sizes)

    def _restore_annual_layout(self):
        self._set_annual_mode(self._annual_mode)
        saved = self._annual_settings.value("results/annual_splitter_sizes")
        if isinstance(saved, (list, tuple)) and len(saved) == 2:
            try:
                sizes = [max(90, int(number)) for number in saved]
            except (TypeError, ValueError):
                sizes = [330, 230]
        else:
            sizes = [330, 230]
        self.annual_splitter.setSizes(sizes)

    def _remember_annual_sizes(self, _pos, _index):
        if self._annual_mode == "both":
            self._annual_settings.setValue(
                "results/annual_splitter_sizes", self.annual_splitter.sizes()
            )

    def _set_annual_mode(self, mode):
        if mode not in ("both", "chart", "table"):
            return
        self._annual_mode = mode
        for key, button in self._annual_mode_buttons.items():
            button.setChecked(key == mode)
        self.chart_scroll.setVisible(mode != "table")
        self.year_table.setVisible(mode != "chart")
        self._annual_settings.setValue("results/annual_mode", mode)

    def _annual_report(self):
        key = self.year_scope.currentData() or "all"
        if str(key).startswith("kdrs:"):
            return kdrs_annual_table(self._snapshots, key, self._kdrs_sources)
        return annual_table_with_coverage(self._snapshots, key)

    def _update_annual(self, _event=None):
        try:
            report = self._annual_report()
        except (ValueError, AttributeError):
            return
        self._annual_scope_key = self.year_scope.currentData() or "all"
        metrics = tuple(key for key, check in self.metric_checks.items() if check.isChecked())
        self.chart.set_data(report, metrics)
        self.year_table.clear()
        has_partial = False
        for row in report.rows:
            cells = [str(row["year"])]
            coverage = row.get("coverage") or {}
            for metric, _label in METRICS:
                value = row.get(metric)
                text = "–" if value is None else f"{value:,}".replace(",", " ")
                available, total = coverage.get(metric, (report.source_count, report.source_count))
                is_partial = value is not None and available < total
                has_partial |= is_partial
                cells.append(text + " *" if is_partial else text)
            item = QTreeWidgetItem(cells)
            for idx, (metric, _label) in enumerate(METRICS, 1):
                if metric in coverage:
                    available, total = coverage[metric]
                    if available < total:
                        item.setToolTip(idx, (
                            f"Kjent delsum: {available} av {total} arkivdeler har verdi. "
                            "Manglende verdier er ukjent, ikke null."
                        ))
            self.year_table.addTopLevelItem(item)
        note = f"{report.source_count} arkivdel(er), {len(report.rows)} observerte år. "
        if has_partial:
            note += "* = kjent delsum, ikke en fullstendig total. "
        note += "  |  ".join(report.warnings[:2]) if report.warnings else (
            "«–» betyr manglende lagret verdi, ikke null."
        )
        self.year_note.setText(note)
        self.chart_scroll.widget().adjustSize()

    def _export_annual_csv(self):
        if not self._snapshots:
            return
        report = self._annual_report()
        filename, _ = QFileDialog.getSaveFileName(
            self, "Lagre årsfordeling (kun data fra Work)",
            "dwm-aarsfordeling.csv", "CSV-filer (*.csv)",
        )
        if not filename:
            return
        target = Path(filename).resolve(strict=False)
        for shot in self._snapshots:
            definition = (safe_json(shot.job.work, "job.json") or {}).get("job") or {}
            for prop in ("source_root", "source_extraction", "archive_root", "output_root"):
                raw = definition.get(prop)
                if raw:
                    source = Path(str(raw)).resolve(strict=False)
                    if target == source or target.is_relative_to(source):
                        QMessageBox.warning(
                            self, "Eksport", "Årstabellen kan ikke eksporteres til Source eller AIP."
                        )
                        return
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open("w", encoding="utf-8-sig", newline="") as stream:
                writer = csv.writer(stream, delimiter=";")
                writer.writerow(["År"] + [label for _, label in METRICS] +
                                ["Dekning " + label for _, label in METRICS])
                for row in report.rows:
                    coverage = row.get("coverage") or {}
                    writer.writerow(
                        [row["year"]] +
                        [row.get(metric) if row.get(metric) is not None else ""
                         for metric, _ in METRICS] +
                        [f"{coverage[metric][0]}/{coverage[metric][1]}"
                         if metric in coverage else "" for metric, _ in METRICS]
                    )
        except OSError as exc:
            QMessageBox.warning(self, "Eksport", str(exc))
            return
        QMessageBox.information(
            self, "Årsfordeling", f"Eksportert {len(report.rows)} år til:\n{target}\n"
            "Dekning viser antall arkivdeler med verdi / totalt antall arkivdeler."
        )
