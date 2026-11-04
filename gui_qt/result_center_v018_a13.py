"""a13: read-only, source-aware result analysis over DWM Work jobs.

Restores structured controls, annual volumes, separate external evidence,
period assessment display and links to the established multi-job report engine.
The only write in this window is a separate explicit professional-review dialog
using the existing period_assessment_a16 API.
"""
from __future__ import annotations

from datetime import datetime
import csv
import json
from pathlib import Path
from typing import Any, Callable

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QColor, QDesktopServices, QFont, QPainter, QPen
from PySide6.QtWidgets import (
    QAbstractItemView, QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFileDialog,
    QFormLayout, QHBoxLayout, QHeaderView, QLabel, QLineEdit, QMessageBox,
    QPlainTextEdit, QPushButton, QScrollArea, QSplitter, QTabWidget, QTreeWidget,
    QTreeWidgetItem, QVBoxLayout, QWidget,
)

from app.result_evidence_v018_a13 import (
    AnnualTable, METRICS, annual_scopes, annual_table, archive_part_details,
    arkade_rows, describe_span, evidence_alerts, kdrs_rows, kdrs_period_sources,
    kdrs_annual_scopes, kdrs_annual_table, open_work_job,
    overview_rows, period_rows, pronom_rows, report_links, technical_rows,
)

DETAIL_ROLE = Qt.ItemDataRole.UserRole
PATH_ROLE = Qt.ItemDataRole.UserRole + 1


def _val(value: Any) -> str:
    return "Ukjent" if value is None or value == "" else str(value)


def _json_text(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2, default=str)


class YearBarChart(QWidget):
    """Standalone Qt painter: five independent metrics, no QtCharts dependency."""

    COLORS = (QColor("#5aa7eb"), QColor("#79caa1"), QColor("#e9b25e"),
              QColor("#ab93e6"), QColor("#e78399"))

    def __init__(self, parent=None):
        super().__init__(parent)
        self.data: AnnualTable | None = None
        self.visible_metrics = tuple(key for key, _ in METRICS)
        self.setMinimumHeight(285)
        self.setToolTip("Søyler per år. Eksakte tall og ukjente verdier vises i tabellen under.")

    def set_data(self, data: AnnualTable, metrics: tuple[str, ...]):
        self.data = data
        self.visible_metrics = tuple(metrics)
        self.setMinimumWidth(max(810, 160 + len(data.rows) * 82))
        self.updateGeometry()
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.fillRect(self.rect(), self.palette().base())
        painter.setPen(self.palette().text().color())
        if self.data is None or not self.data.rows:
            painter.drawText(self.rect().adjusted(20, 15, -20, -20),
                             Qt.AlignmentFlag.AlignCenter,
                             "Ingen lagret årsfordeling for valgt uttrekk / arkivdel")
            painter.end()
            return
        metrics = [(key, name, self.COLORS[i]) for i, (key, name) in enumerate(METRICS)
                   if key in self.visible_metrics]
        if not metrics:
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "Velg minst ett måltall")
            painter.end()
            return
        left, top, bottom = 56, 58, self.height() - 43
        graph_h = max(75, bottom - top)
        maximum = max((int(row.get(key)) for row in self.data.rows for key, _, _ in metrics
                       if row.get(key) is not None), default=0)
        maximum = max(1, maximum)
        muted = self.palette().mid().color()
        painter.setPen(QPen(muted, 1))
        for tick in range(5):
            value = maximum * tick / 4
            y = bottom - int(graph_h * tick / 4)
            painter.drawLine(left, y, self.width() - 16, y)
            painter.setPen(self.palette().text().color())
            painter.drawText(3, y - 7, 46, 17, Qt.AlignmentFlag.AlignRight, f"{value:,.0f}".replace(",", " "))
            painter.setPen(QPen(muted, 1))
        painter.setFont(QFont(self.font().family(), max(8, self.font().pointSize()-1)))
        for i, (_key, title, color) in enumerate(metrics):
            x = left + 8 + i * 135
            painter.fillRect(x, 8, 12, 12, color)
            painter.setPen(self.palette().text().color())
            painter.drawText(x + 17, 4, 119, 19, Qt.AlignmentFlag.AlignLeft, title)
        for index, row in enumerate(self.data.rows):
            x0 = left + 13 + 82 * index
            group_width = max(50, 66)
            bar_width = max(5, (group_width - 5) // len(metrics) - 3)
            for m_index, (key, _name, color) in enumerate(metrics):
                value = row.get(key)
                if value is None:
                    continue
                height = max(2 if value > 0 else 0, round(graph_h * float(value) / maximum))
                if height:
                    painter.fillRect(x0 + m_index * (bar_width + 3),
                                     bottom - height, bar_width, height, color)
            painter.setPen(self.palette().text().color())
            painter.drawText(x0, bottom + 5, group_width, 25,
                             Qt.AlignmentFlag.AlignCenter, str(row["year"]))
        painter.end()


class ChooseJobsDialog(QDialog):
    def __init__(self, candidates, selected: set[str], parent=None):
        super().__init__(parent)
        self.setWindowTitle("Velg uttrekk til resultatvisningen")
        self.resize(820, 470)
        form = QVBoxLayout(self)
        note = QLabel("Hvert Noark 5-uttrekk har sitt eget Work. SIARD vises ikke som Noark 5-resultater. "
                      "Valget endrer ikke jobblisten eller lagrede rapporter.")
        note.setWordWrap(True)
        form.addWidget(note)
        self.list = QTreeWidget(self)
        self.list.setHeaderLabels(["Uttrekk", "Jobb", "Profil", "Work-status"])
        self.list.setRootIsDecorated(False)
        self.list.setAlternatingRowColors(True)
        self.list.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.list.header().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        for candidate in candidates:
            valid = bool(candidate.get("enabled") and candidate.get("work") and Path(str(candidate["work"])).is_dir())
            item = QTreeWidgetItem([
                str(candidate.get("name") or ""), str(candidate.get("job_id") or ""),
                str(candidate.get("profile_id") or ""), "Tilgjengelig" if valid else "Ikke tilgjengelig",
            ])
            item.setData(0, DETAIL_ROLE, str(candidate.get("job_id") or ""))
            item.setFlags((item.flags() | Qt.ItemFlag.ItemIsUserCheckable) if valid else item.flags() & ~Qt.ItemFlag.ItemIsEnabled)
            item.setCheckState(0, Qt.CheckState.Checked if valid and str(candidate.get("job_id")) in selected
                               else Qt.CheckState.Unchecked)
            self.list.addTopLevelItem(item)
        form.addWidget(self.list, 1)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self._valid_accept)
        buttons.rejected.connect(self.reject)
        form.addWidget(buttons)

    def selected_ids(self) -> tuple[str, ...]:
        return tuple(str(self.list.topLevelItem(i).data(0, DETAIL_ROLE))
                     for i in range(self.list.topLevelItemCount())
                     if self.list.topLevelItem(i).checkState(0) == Qt.CheckState.Checked)

    def _valid_accept(self):
        if not self.selected_ids():
            QMessageBox.information(self, "Uttrekk", "Velg minst ett tilgjengelig Noark 5-uttrekk.")
            return
        self.accept()


class PeriodReviewDialog(QDialog):
    """A thin Qt form over the established, versioned legacy assessment API."""

    def __init__(self, job, report: dict, *, native_id: str = "", parent=None):
        super().__init__(parent)
        from noark5_workflow.reporting.period_assessment_a16 import (
            load_assessment, load_part_assessment, review_candidate, part_review_candidate,
        )
        self._job = job
        self._report = report
        self._native_id = native_id
        self.setWindowTitle("Faglig periodevurdering – " + str(job.name))
        self.resize(650, 470)
        container = QVBoxLayout(self)
        info = (part_review_candidate(report, native_id) if native_id else review_candidate(report))
        saved = (load_part_assessment(job, native_id) if native_id else load_assessment(job)) or {}
        hint = QLabel("Viser forslag og lagret vurdering separat. Det er bare brukerens eksplisitte lagring "
                      "som registrerer en faglig beslutning. Originale Noark 5-data endres aldri.")
        hint.setWordWrap(True)
        container.addWidget(hint)
        self.source = QPlainTextEdit(self)
        self.source.setReadOnly(True)
        self.source.setPlainText(_json_text({"kilde": info, "tidligere_vurdering": saved}))
        container.addWidget(self.source, 1)
        fields = QFormLayout()
        self.status = QComboBox()
        options = (("Ikke vurdert", "ikke_vurdert"), ("Undersøkes", "undersokes"),
                   ("Godkjent av faglig ansvarlig", "godkjent"))
        for label, key in options:
            self.status.addItem(label, key)
        current = self.status.findData(saved.get("status", "ikke_vurdert"))
        if current >= 0:
            self.status.setCurrentIndex(current)
        fields.addRow("Vurdering", self.status)
        proposed = saved.get("selected_years") or info.get("proposed_years") or info.get("dwm_observed_years") or []
        self.first = QLineEdit(str(proposed[0]) if len(proposed) == 2 else "")
        self.last = QLineEdit(str(proposed[1]) if len(proposed) == 2 else "")
        fields.addRow("Fra år", self.first)
        fields.addRow("Til år", self.last)
        self.comment = QPlainTextEdit()
        self.comment.setPlaceholderText("Kildegrunnlag, eventuelle avvik og faglig begrunnelse")
        self.comment.setPlainText(str(saved.get("comment") or ""))
        self.comment.setMaximumHeight(90)
        fields.addRow("Begrunnelse", self.comment)
        container.addLayout(fields)
        actions = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        actions.button(QDialogButtonBox.StandardButton.Save).setText("Lagre faglig vurdering")
        actions.accepted.connect(self._save)
        actions.rejected.connect(self.reject)
        container.addWidget(actions)

    def _save(self):
        from noark5_workflow.reporting.period_assessment_a16 import save_assessment, save_part_assessment
        years = None
        if self.first.text().strip() or self.last.text().strip():
            try:
                years = [int(self.first.text()), int(self.last.text())]
            except (ValueError, TypeError):
                QMessageBox.warning(self, "Periode", "Oppgi gyldige ytterår eller la begge feltene være tomme.")
                return
        try:
            options = {"status": self.status.currentData(), "years": years,
                       "comment": self.comment.toPlainText().strip()}
            if self._native_id:
                save_part_assessment(self._job, self._report, self._native_id, **options)
            else:
                save_assessment(self._job, self._report, **options)
        except (OSError, ValueError, TypeError) as exc:
            QMessageBox.warning(self, "Periodevurdering", str(exc))
            return
        self.accept()


class EvidenceChoiceDialog(QDialog):
    """Explicit KDRS Query evidence decision with source, scope and reason.

    Uses the established a5 source-mapping and decision API. Does not confuse
    a KDRS U2 part index with a DWM native archive-part system-ID.
    """

    REASONS = (("DWM-kontroll mangler", "missing_dwm_test"),
               ("DWM-resultat er ugyldig", "invalid_dwm_result"),
               ("Ekstern kilde er kontrollert", "verified_external_source"))

    def __init__(self, work: Path, parent=None):
        super().__init__(parent)
        from noark5_workflow.external_evidence.kdrs_query_mapping import build_mapped_pool
        from noark5_workflow.external_evidence.evidence_decisions_a5 import load_decisions
        self._work = Path(work)
        self._pool = build_mapped_pool(self._work)
        self._decisions = load_decisions(self._work)
        self._candidates = []
        self.setWindowTitle("KDRS Query – velg ekstern evidens")
        self.resize(890, 620)
        main = QVBoxLayout(self)
        note = QLabel("Kun eksakt mappede, dokumenterte observasjoner kan velges. "
                      "KDRS U2-arkivdelindeks er ikke en DWM system-ID. "
                      "Originale DWM-resultater endres aldri; valget logges separat i Work.")
        note.setWordWrap(True)
        main.addWidget(note)
        controls = QFormLayout()
        self.metric = QComboBox()
        self.scope = QComboBox()
        self.scope.addItem("Hele uttrekket", None)
        metric_names = set()
        part_ids = set()
        for resource in self._pool.get("resources") or []:
            for line in resource.get("semantic_lines") or []:
                for fact in line.get("facts") or []:
                    if fact.get("mapping_status") == "exact" and fact.get("value_kind") == "count":
                        metric_names.add(str(fact.get("metric_id") or ""))
                        index = fact.get("archive_part_index")
                        if isinstance(index, int) and not isinstance(index, bool) and index > 0:
                            part_ids.add(index)
        for key in sorted(metric_names):
            if key:
                self.metric.addItem(key.replace("_", " "), key)
        for index in sorted(part_ids):
            self.scope.addItem(f"KDRS U2-arkivdelindeks {index} (ikke DWM system-ID)", index)
        controls.addRow("Måltall", self.metric)
        controls.addRow("Kildeomfang", self.scope)
        main.addLayout(controls)
        self.table = QTreeWidget()
        self.table.setHeaderLabels(["Antall", "Rapporttype", "Kilde", "Linje", "Import-ID"])
        self.table.setRootIsDecorated(False)
        self.table.setAlternatingRowColors(True)
        self.table.header().setStretchLastSection(True)
        self.table.itemSelectionChanged.connect(self._preview)
        main.addWidget(self.table, 2)
        self.current = QLabel("Velg en eksakt mappet observasjon; tidligere valgt evidens vises nedenfor.")
        self.current.setWordWrap(True)
        main.addWidget(self.current)
        self.reason = QComboBox()
        for name, key in self.REASONS:
            self.reason.addItem(name, key)
        form = QFormLayout()
        form.addRow("Begrunnelse", self.reason)
        self.note = QPlainTextEdit()
        self.note.setPlaceholderText("Dokumenter hvorfor denne eksterne observasjonen brukes")
        self.note.setMaximumHeight(90)
        form.addRow("Notat", self.note)
        main.addLayout(form)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save |
                                   QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Save).setText("Lagre evidensvalg")
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        main.addWidget(buttons)
        self.metric.currentIndexChanged.connect(self._populate)
        self.scope.currentIndexChanged.connect(self._populate)
        self._populate()

    def _populate(self, _index=None):
        from noark5_workflow.external_evidence.evidence_decisions_a5 import exact_candidates
        self.table.clear()
        metric = str(self.metric.currentData() or "")
        scope = self.scope.currentData()
        self._candidates = exact_candidates(self._pool, metric, part_index=scope) if metric else []
        for row in self._candidates:
            item = QTreeWidgetItem([str(row.get("value")), str(row.get("report_type") or ""),
                                    str(row.get("source_file") or ""),
                                    str(row.get("source_line_number") or ""),
                                    str(row.get("source_import_id") or "")])
            item.setData(0, DETAIL_ROLE, str(row.get("id")))
            self.table.addTopLevelItem(item)
        key = f"{'whole' if scope is None else 'part:'+str(scope)}:{metric}"
        previous = self._decisions.get(key) or {}
        self.current.setText(f"{len(self._candidates)} entydige observasjoner. "
                             + (f"Tidligere valgt: {previous.get('value')} – {previous.get('source_file')}"
                                if previous else "Ingen tidligere faglig evidensvalgt verdi."))

    def _preview(self):
        selected = self.table.currentItem()
        if selected is None:
            return
        item = next((r for r in self._candidates if str(r.get("id")) ==
                     str(selected.data(0, DETAIL_ROLE))), None)
        if item:
            self.current.setText(f"Verdi: {item.get('value')} | Kilde: {item.get('source_file')} | "
                                 f"SHA-256: {item.get('source_sha256')} | "
                                 f"KDRS-kildeindeks: {item.get('archive_part_index')}")

    def _save(self):
        from noark5_workflow.external_evidence.evidence_decisions_a5 import select_evidence
        selected = self.table.currentItem()
        if selected is None:
            QMessageBox.information(self, "Evidens", "Velg en observasjon.")
            return
        if not self.note.toPlainText().strip():
            QMessageBox.warning(self, "Evidens", "Oppgi en kort faglig begrunnelse i notatfeltet.")
            return
        try:
            select_evidence(self._work, self._pool,
                            metric=str(self.metric.currentData()),
                            evidence_id=str(selected.data(0, DETAIL_ROLE)),
                            reason=str(self.reason.currentData()),
                            part_index=self.scope.currentData(),
                            note=self.note.toPlainText().strip())
        except (ValueError, OSError, TypeError) as exc:
            QMessageBox.warning(self, "Evidens", str(exc))
            return
        self.accept()


class ResultCenterWindow(QDialog):
    """Structured evidence for one or more Noark 5 Work jobs, separate from joblist."""

    def __init__(self, work: str | Path | None, *, display_name: str,
                 available_jobs=(), report_api=None,
                 on_generate_report: Callable[[], None] | None = None, parent=None):
        super().__init__(parent, Qt.WindowType.Window)
        self.setWindowTitle("Resultatvisninger – " + str(display_name))
        self.setMinimumSize(930, 590)
        self.resize(1250, 820)
        self._available = tuple(available_jobs)
        self._report_api = report_api
        self._on_generate_report = on_generate_report
        self._initial_work = Path(work) if work else None
        self._initial_name = str(display_name)
        self._snapshots = ()
        self._kdrs_sources = ()
        self._period_items: dict[tuple[str, str], dict] = {}
        self._annual_scope_key = "all"
        self._selected_ids = set()
        if self._available:
            for item in self._available:
                if item.get("enabled") and item.get("work") and self._initial_work:
                    try:
                        if Path(str(item["work"])).resolve(strict=False) == self._initial_work.resolve(strict=False):
                            self._selected_ids.add(str(item["job_id"]))
                    except (ValueError, OSError):
                        pass
            if not self._selected_ids and self._initial_work is None:
                self._selected_ids = {str(c["job_id"]) for c in self._available
                                      if c.get("enabled") and c.get("work") and Path(str(c["work"])).is_dir()}
        outer = QVBoxLayout(self)
        heading = QHBoxLayout()
        self.title_label = QLabel("Resultatvisninger – " + self._initial_name)
        self.title_label.setStyleSheet("font-size: 17px; font-weight: 600;")
        heading.addWidget(self.title_label, 1)
        select = QPushButton("Velg uttrekk…")
        select.clicked.connect(self._choose_jobs)
        select.setEnabled(bool(self._available))
        heading.addWidget(select)
        outer.addLayout(heading)
        self.note = QLabel("Lagrede Work-resultater, faglige vurderinger og eksterne kilder holdes adskilt.")
        self.note.setWordWrap(True)
        outer.addWidget(self.note)
        self.tabs = QTabWidget(self)
        self.tabs.setDocumentMode(True)
        outer.addWidget(self.tabs, 1)
        self._trees: dict[str, QTreeWidget] = {}
        self._details: dict[str, QPlainTextEdit] = {}
        self._pages: dict[str, QWidget] = {}
        self._make_tree_tab("Oversikt", ("Uttrekk", "Arkivdeler", "Mapper", "Registreringer", "Dokumentobjekter", "Teknisk", "Vurdering"))
        self._make_tree_tab("Arkivdeler", ("Uttrekk", "Arkivdel", "Status", "Mapper", "Registreringer", "Dokumentobjekter", "Ytterår"))
        self._make_annual_tab()
        self._make_tree_tab("Tekniske kontroller", ("Uttrekk", "Test-ID", "Noark-punkt", "Status", "Kontroller", "Avvik"))
        self._make_tree_tab("Arkade 5", ("Uttrekk", "Test", "Navn", "Status", "Feil", "Import-ID"))
        self._make_tree_tab("PRONOM", ("Uttrekk", "Format-ID / PUID", "Filtype", "Versjon", "Antall", "RAF"))
        self._make_tree_tab("KDRS Query", ("Uttrekk", "Import-ID", "Rapport", "Kilde", "SHA-256"))
        self._make_tree_tab("Periodevurdering", ("Uttrekk", "Omfang", "Oppgitt", "Observert", "Lagret vurdering", "Godkjent periode"))
        self._make_tree_tab("Depotrapporter", ("Uttrekk", "Rapportfil", "Plassering", "Dato"))
        self._make_tree_tab("Evidensfiler", ("Uttrekk", "Kilde", "Fil", "Plassering"))
        actions = QHBoxLayout()
        for title, fn in (("Oppdater visning", self.refresh),
                          ("Åpne kildefil", self._open_current),
                          ("Vurder periode…", self._open_period_review),
                          ("Velg KDRS-evidens…", self._open_kdrs_evidence),
                          ("Lag rapport / samlerapport…", self._open_report_dialog),
                          ("Klassisk uttrekksoversikt…", self._open_legacy_multi),
                          ("Åpne Work-mappe", self._open_work)):
            button = QPushButton(title)
            button.clicked.connect(fn)
            if title.startswith("Lag rapport"):
                button.setEnabled(bool(on_generate_report))
            actions.addWidget(button)
        actions.addStretch(1)
        outer.addLayout(actions)
        self.refresh()

    def _make_tree_tab(self, title: str, columns: tuple[str, ...]):
        page = QWidget(self.tabs)
        body = QVBoxLayout(page)
        splitter = QSplitter(Qt.Orientation.Vertical, page)
        table = QTreeWidget(splitter)
        table.setHeaderLabels(list(columns))
        table.setRootIsDecorated(False)
        table.setAlternatingRowColors(True)
        table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        table.header().setStretchLastSection(True)
        table.header().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        table.itemSelectionChanged.connect(lambda key=title: self._show_detail(key))
        table.itemDoubleClicked.connect(self._open_item)
        detail = QPlainTextEdit(splitter)
        detail.setReadOnly(True)
        detail.setPlaceholderText("Velg en rad for kilder, detaljer, funn og lagret evidens.")
        splitter.addWidget(table)
        splitter.addWidget(detail)
        splitter.setStretchFactor(0, 4)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([580, 190])
        body.addWidget(splitter)
        self._trees[title] = table
        self._details[title] = detail
        self.tabs.addTab(page, title)
        self._pages[title] = page

    def _make_annual_tab(self):
        page = QWidget(self.tabs)
        body = QVBoxLayout(page)
        controls = QHBoxLayout()
        controls.addWidget(QLabel("Årsserie / omfang:"))
        self.year_scope = QComboBox()
        self.year_scope.setMinimumWidth(440)
        self.year_scope.currentIndexChanged.connect(self._update_annual)
        controls.addWidget(self.year_scope, 1)
        body.addLayout(controls)
        metrics_row = QHBoxLayout()
        metrics_row.addWidget(QLabel("Vis:"))
        self.metric_checks: dict[str, QCheckBox] = {}
        for metric, text in METRICS:
            control = QCheckBox(text)
            control.setChecked(True)
            control.toggled.connect(self._update_annual)
            self.metric_checks[metric] = control
            metrics_row.addWidget(control)
        metrics_row.addStretch(1)
        body.addLayout(metrics_row)
        self.year_note = QLabel("Årsvolum fra lagret depotrapport. Manglende verdier er ukjent, ikke 0.")
        self.year_note.setWordWrap(True)
        body.addWidget(self.year_note)
        self.chart = YearBarChart(page)
        self.chart_scroll = QScrollArea(page)
        self.chart_scroll.setWidgetResizable(False)
        self.chart_scroll.setWidget(self.chart)
        self.chart_scroll.setMinimumHeight(250)
        body.addWidget(self.chart_scroll, 3)
        self.year_table = QTreeWidget(page)
        self.year_table.setRootIsDecorated(False)
        self.year_table.setAlternatingRowColors(True)
        self.year_table.setHeaderLabels(["År"] + [label for _, label in METRICS])
        for col in range(len(METRICS)+1):
            self.year_table.header().setSectionResizeMode(col, QHeaderView.ResizeMode.Stretch)
        body.addWidget(self.year_table, 2)
        export_row = QHBoxLayout()
        export = QPushButton("Eksporter årstabell til CSV…")
        export.clicked.connect(self._export_annual_csv)
        export_row.addWidget(export)
        export_row.addStretch(1)
        body.addLayout(export_row)
        self.tabs.addTab(page, "Årsfordeling")
        self._pages["Årsfordeling"] = page

    def _row(self, tab: str, columns, *, details=None, file=None, payload=None):
        item = QTreeWidgetItem([_val(value) for value in columns])
        item.setData(0, DETAIL_ROLE, details)
        item.setData(0, PATH_ROLE, str(file) if file else "")
        if payload is not None:
            item.setData(0, Qt.ItemDataRole.UserRole + 2, payload)
        self._trees[tab].addTopLevelItem(item)
        return item

    def _choose_jobs(self):
        dialog = ChooseJobsDialog(self._available, self._selected_ids, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._selected_ids = set(dialog.selected_ids())
            self._annual_scope_key = "all"
            self.refresh()

    def _load(self):
        snapshots = []
        if self._available:
            for item in self._available:
                if str(item.get("job_id")) not in self._selected_ids or not item.get("enabled"):
                    continue
                snap = open_work_job(str(item["job_id"]), str(item.get("name") or item["job_id"]),
                                     str(item.get("work") or ""), profile_id=str(item.get("profile_id") or "noark5"))
                if snap is not None:
                    snapshots.append(snap)
        elif self._initial_work is not None:
            snap = open_work_job("JOB-001", self._initial_name, self._initial_work)
            if snap:
                snapshots.append(snap)
        # Multiple joblist references may point to the same Work. Never
        # double-count a UUID in cross-extraction results or annual sums.
        unique = {}
        for shot in snapshots:
            unique.setdefault(shot.job.job_uid, shot)
        self._snapshots = tuple(unique.values())

    def refresh(self):
        self._load()
        for table in self._trees.values():
            table.clear()
        for detail in self._details.values():
            detail.clear()
        shots = self._snapshots
        self.title_label.setText("Resultatvisninger – " + (f"{len(shots)} valgte uttrekk" if len(shots) > 1
                                                      else shots[0].job.job_id + " – " + shots[0].job.name if shots
                                                      else "ingen tilgjengelige uttrekk"))
        alerts = evidence_alerts(shots)
        self.note.setText((f"{len(shots)} uttrekk valgt. " + "  |  ".join(alerts[:2]) if alerts
                           else f"{len(shots)} uttrekk valgt. Kilder og status vises separat. "
                                "Fullført arbeidsflyt er ikke automatisk depotgodkjenning."))
        for record in overview_rows(shots):
            job = record["job"]
            self._row("Oversikt", (job.name, record["archive_parts"], record["folders"],
                     record["registrations"], record["document_objects"], record["technical_status"],
                     record["assessment_status"]), details={
                         "job_uid": job.job_uid, "report_path": record["report_path"],
                         "vurderingspunkter": record["deviations"],
                         "arkade_imports": record["arkade_imports"],
                     }, file=record["report_path"])
        for record in archive_part_details(shots):
            part = record["archive_part"]
            period = record.get("period_evidence") or {}
            self._row("Arkivdeler", (record["job"].name, record["title"],
                     (part.get("archive_part") or {}).get("status"), part.get("folder_count"),
                     part.get("registration_count"), part.get("document_object_count"),
                     describe_span(period.get("observed_period"))),
                     details={"arkivdel": part, "periodeevidens": period,
                              "system_id": record["system_id"], "jobb_uid": record["job"].job_uid},
                     file=record["report_path"],
                     payload=(record["job"].job_uid, record["system_id"]))
        for record in technical_rows(shots):
            self._row("Tekniske kontroller", (record["job"].name, record["legacy_id"] or record["test_id"],
                     record["noark_point"], record["status"], record["checks"], record["mismatches"]),
                     details=record["details"], file=record["file"])
        for record in arkade_rows(shots):
            self._row("Arkade 5", (record["job"].name, record["test_id"], record["title"],
                     record["status"], record["errors"], record["import_id"]),
                     details={"import_id": record["import_id"], "tested_at": record["tested_at"],
                              "version": record["version"], "sha256": record["source_sha256"],
                              "test": record["details"]}, file=record["file"])
        for record in pronom_rows(shots):
            self._row("PRONOM", (record["job"].name, record["format_id"], record["format"],
                     record["version"], record["count"], record["raf"]),
                     details={"import_id": record["import_id"], "sha256": record["source_sha256"],
                              "source_row": record["details"]}, file=record["file"])
        for record in kdrs_rows(shots):
            self._row("KDRS Query", (record["job"].name, record["import_id"], record["report_type"],
                     record["source"], record["sha256"]),
                     details=record["details"], file=record["file"])
        self._kdrs_sources = kdrs_period_sources(shots)
        for evidence in self._kdrs_sources:
            self._row("KDRS Query", (
                evidence["job"].name, evidence["import_id"],
                evidence["report_type"], evidence["scope_label"],
                f"{len((evidence['source'].get('series') or {}))} årsserier"),
                details={"KDRS_kilde": evidence["source_files"],
                         "omfang": evidence["scope_label"],
                         "årsserier": evidence["source"]})
        self._period_items.clear()
        for record in period_rows(shots):
            assessment = record["assessment"]
            years = assessment.get("selected_years")
            review_years = "–" if not years else "–".join(str(y) for y in years)
            declared = describe_span(record["declared"])
            observed = (describe_span(record["observed"])
                        if record["native_id"] else " / ".join(
                            key + ": " + describe_span(value) for key, value in record["observed"].items()
                            if isinstance(value, dict) and describe_span(value) != "Ukjent") or "Ukjent")
            item = self._row("Periodevurdering", (record["job"].name, record["scope"],
                            declared, observed, assessment.get("status", "ikke_vurdert"), review_years),
                            details={"evidens": record["details"], "vurdering": assessment},
                            file=record["file"], payload=(record["job"].job_uid, record["native_id"]))
            self._period_items[(record["job"].job_uid, record["native_id"])] = record
        for record in report_links(shots):
            self._row("Depotrapporter", (record["job"].name, record["filename"], record["relative_path"],
                     datetime.fromtimestamp(record["date"]).strftime("%Y-%m-%d %H:%M")),
                     details={"kilde": record["relative_path"], "jobb_uid": record["job"].job_uid},
                     file=record["file"])
        for shot in shots:
            for artifact in shot.results.artifacts:
                self._row("Evidensfiler", (shot.job.name, artifact.category, artifact.title,
                         artifact.relative_path),
                         details={"jobb_uid": shot.job.job_uid, "bytes": artifact.size,
                                  "endret": datetime.fromtimestamp(artifact.modified_at).isoformat(timespec="seconds")},
                         file=artifact.path)
        if not shots:
            self._row("Oversikt", ("Ingen tilgjengelig Work", "", "", "", "", "", ""),
                      details="Velg en Noark 5-jobb med tilgjengelig DWM Work-område.")
        for name in ("Tekniske kontroller", "Arkade 5", "PRONOM", "KDRS Query"):
            if self._trees[name].topLevelItemCount() == 0:
                count = self._trees[name].columnCount()
                self._row(name, ("Ingen lagret evidens for denne kilden",) + ("",)*(count-1))
        current_scope = self._annual_scope_key
        self.year_scope.blockSignals(True)
        self.year_scope.clear()
        for item in annual_scopes(shots) + kdrs_annual_scopes(shots, self._kdrs_sources):
            self.year_scope.addItem(item.label, item.key)
        target = self.year_scope.findData(current_scope)
        self.year_scope.setCurrentIndex(max(0, target))
        self.year_scope.blockSignals(False)
        self._update_annual()

    def _update_annual(self, _event=None):
        key = self.year_scope.currentData() or "all"
        try:
            report = (kdrs_annual_table(self._snapshots, key, self._kdrs_sources) if str(key).startswith("kdrs:")
                      else annual_table(self._snapshots, key))
        except ValueError:
            return
        self._annual_scope_key = key
        metrics = tuple(name for name, box in self.metric_checks.items() if box.isChecked())
        self.chart.set_data(report, metrics)
        self.year_table.clear()
        for row in report.rows:
            values = [str(row["year"])]+["–" if row[metric] is None else f"{row[metric]:,}".replace(",", " ")
                                         for metric, _ in METRICS]
            self.year_table.addTopLevelItem(QTreeWidgetItem(values))
        self.year_note.setText(f"{report.source_count} arkivdel(er), {len(report.rows)} observerte år. "
                               + ("  |  ".join(report.warnings[:2]) if report.warnings else
                                  "«–» betyr manglende lagret verdi, ikke 0. "
                                  "Journalposter og registreringer er separate måltall."))
        self.chart_scroll.widget().adjustSize()

    def _show_detail(self, tab: str):
        item = self._trees[tab].currentItem()
        if item is None:
            return
        detail = item.data(0, DETAIL_ROLE)
        self._details[tab].setPlainText(_json_text(detail) if not isinstance(detail, str) else detail)

    def _open_item(self, item, _column=0):
        self._open_file_path(item.data(0, PATH_ROLE))

    def _open_file_path(self, raw):
        if not raw:
            return
        file = Path(str(raw))
        # Revalidate against each known Work when opened. Do not follow a
        # replaced symlink or an artifact moved out of a Work directory.
        allowed = False
        for shot in self._snapshots:
            try:
                root = shot.job.work.resolve(strict=True)
                file_resolved = file.resolve(strict=True)
                if file_resolved.is_file() and file_resolved.is_relative_to(root):
                    allowed = True
                    break
            except (OSError, ValueError, RuntimeError):
                continue
        if not allowed:
            QMessageBox.warning(self, "Evidens", "Kildefilen finnes ikke lenger innenfor valgt Work.")
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(file)))

    def _open_current(self):
        tab = self.tabs.tabText(self.tabs.currentIndex())
        if tab == "Årsfordeling":
            QMessageBox.information(self, "Årsfordeling",
                "Grafen er en sammenstilling av lagrede årsserier. Velg Depotrapporter "
                "eller Evidensfiler for å åpne originalgrunnlaget.")
            return
        row = self._trees[tab].currentItem()
        if row:
            self._open_item(row)

    def _open_work(self):
        if self._snapshots:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(self._snapshots[0].job.work)))
        else:
            QMessageBox.information(self, "Work", "Ingen tilgjengelig Work-mappe.")

    def _open_report_dialog(self):
        if self._on_generate_report:
            self._on_generate_report()

    def _export_annual_csv(self):
        if not self._snapshots:
            return
        scope_key = self.year_scope.currentData() or "all"
        report = (kdrs_annual_table(self._snapshots, scope_key, self._kdrs_sources) if str(scope_key).startswith("kdrs:")
                  else annual_table(self._snapshots, scope_key))
        filename, _ = QFileDialog.getSaveFileName(
            self, "Lagre årsfordeling (kun data fra Work)", "dwm-aarsfordeling.csv",
            "CSV-filer (*.csv)")
        if not filename:
            return
        target = Path(filename).resolve(strict=False)
        # Explicit export must never create output inside the original Source or AIP.
        from app.result_evidence_v018_a13 import safe_json
        for shot in self._snapshots:
            definition = (safe_json(shot.job.work, "job.json") or {}).get("job") or {}
            for prop in ("source_root", "source_extraction", "archive_root", "output_root"):
                raw = definition.get(prop)
                if not raw:
                    continue
                source = Path(str(raw)).resolve(strict=False)
                if target == source or target.is_relative_to(source):
                    QMessageBox.warning(self, "Eksport", "Årstabellen kan ikke eksporteres til Source eller AIP.")
                    return
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open("w", encoding="utf-8-sig", newline="") as fh:
                writer = csv.writer(fh, delimiter=";")
                writer.writerow(["År"] + [name for _, name in METRICS])
                for row in report.rows:
                    writer.writerow([row["year"]] + [row.get(metric) if row.get(metric) is not None else ""
                                                         for metric, _ in METRICS])
        except OSError as exc:
            QMessageBox.warning(self, "Eksport", str(exc))
            return
        QMessageBox.information(self, "Årsfordeling", f"Eksportert {len(report.rows)} observerte år til:\n{target}\n"
                                "Tomme felt betyr ukjent, ikke null.")

    def _open_kdrs_evidence(self):
        if not self._snapshots:
            QMessageBox.information(self, "KDRS Query", "Velg et uttrekk med tilgjengelig Work.")
            return
        if len(self._snapshots) != 1:
            QMessageBox.information(self, "KDRS Query", "Velg ett uttrekk for å registrere et faglig evidensvalg.")
            return
        if not kdrs_rows(self._snapshots):
            QMessageBox.information(self, "KDRS Query", "Ingen importert KDRS Query-evidens for valgt uttrekk.")
            return
        try:
            dialog = EvidenceChoiceDialog(self._snapshots[0].job.work, parent=self)
            if dialog.exec() == QDialog.DialogCode.Accepted:
                self.refresh()
        except (ValueError, OSError, TypeError) as exc:
            QMessageBox.warning(self, "KDRS Query", str(exc))

    def _open_legacy_multi(self):
        if not self._snapshots:
            QMessageBox.information(self, "Samlet uttrekksoversikt", "Velg ett eller flere uttrekk med Work og depotrapporter.")
            return
        from .legacy_multi_report_v018_a13 import LegacyMultiOverviewDialog
        dialog = LegacyMultiOverviewDialog(self._snapshots, parent=self)
        dialog.exec()

    def _open_period_review(self):
        if self.tabs.tabText(self.tabs.currentIndex()) != "Periodevurdering":
            self.tabs.setCurrentWidget(self._pages["Periodevurdering"])
            QMessageBox.information(self, "Periode", "Velg en rad i fanen Periodevurdering først.")
            return
        current = self._trees["Periodevurdering"].currentItem()
        if current is None:
            QMessageBox.information(self, "Periode", "Velg uttrekk eller arkivdel.")
            return
        identity = current.data(0, Qt.ItemDataRole.UserRole + 2)
        record = self._period_items.get(tuple(identity)) if isinstance(identity, (list, tuple)) else None
        if record is None or self._report_api is None:
            QMessageBox.information(self, "Periode", "Lagret vurdering kan vises, men jobb må være tilgjengelig for lagring.")
            return
        try:
            job = self._report_api.selected_report_jobs((record["job"].job_id,))[0]
            report = next(shot.depot for shot in self._snapshots
                          if shot.job.job_uid == record["job"].job_uid)
            if report is None:
                raise ValueError("Mangler depotrapport")
            dialog = PeriodReviewDialog(job, report, native_id=record["native_id"], parent=self)
            if dialog.exec() == QDialog.DialogCode.Accepted:
                self.refresh()
        except (ValueError, OSError, RuntimeError) as exc:
            QMessageBox.warning(self, "Periode", str(exc))
