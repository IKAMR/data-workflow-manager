"""Dockable desktop workbench for Data Workflow Manager v0.1.8-a9.

Qt owns presentation only. DwmWorkbenchAPI is the authoritative job-list and
execution boundary. The legacy CustomTkinter GUI is not imported here.
"""
from __future__ import annotations

from datetime import datetime
import base64
import json
import sys
from pathlib import Path
from queue import Empty, Queue
from threading import Event, Thread

from PySide6.QtCore import QSettings, QTimer, Qt, QProcess, QUrl
from PySide6.QtGui import QAction, QActionGroup, QDesktopServices, QFont
from PySide6.QtWidgets import (
    QApplication, QAbstractItemView, QCheckBox, QDialog, QDialogButtonBox,
    QComboBox, QDockWidget, QFileDialog, QFileSystemModel, QFormLayout, QFrame,
    QHBoxLayout, QHeaderView, QInputDialog, QLabel, QLineEdit, QMainWindow,
    QMenu, QMessageBox, QPlainTextEdit, QProgressBar, QPushButton, QSplitter, QStatusBar,
    QTabWidget, QTableWidget, QTableWidgetItem, QToolBar, QTreeView,
    QTreeWidget, QTreeWidgetItem, QToolButton, QVBoxLayout, QWidget,
)

from app.application_api import DwmApiError
from app.workbench_api_v018_a3 import DwmWorkbenchAPI, STORAGE_FIELDS
from app.workbench_recent_v018_a4 import recent_joblists, remember_joblist
from app.job_preflight_v018_a6 import (
    check_extraction_folder, propose_work_location,
)
from version import APP_NAME, VERSION
from app.result_navigation_v018_a8 import latest_depot_report
from app.run_progress_v018_a8 import saved_progress
from app.subjob_history_v018_a9 import run_history_lines
from app.run_request_audit_v018_a9 import RunRequestAudit, new_request_id, rerun_reason
from .detached_log_window_v018_a9 import (
    DetachedJobLogWindow, DetachedRunWindow, DetachableDockTitleBar,
)


# Explicitly separate presentation presets from workflow/report/storage profiles.
DOCK_NAMES = ("jobs", "workflow", "storage", "log", "run", "system", "info")
LAYOUT_MODES = ("Laptop", "Analyse", "Depot", "Full", "Workshop", "Topp og bunn")
COMPLEXITY_MODES = ("Enkel", "Standard", "Avansert")

STYLE = """
QMainWindow, QWidget { background-color: #10141c; color: #dce5f2; }
QMenuBar, QMenu, QToolBar, QStatusBar { background: #161c27; color: #e2e8f0; }
QMenuBar::item:selected, QMenu::item:selected { background: #29496c; }
QDockWidget { color: #dce5f2; font-weight: 600; }
QDockWidget::title { background: #202a39; padding: 7px 9px; text-align: left; }
QTreeWidget, QTableWidget, QPlainTextEdit, QTreeView, QTabWidget::pane {
  background: #151c28; color: #dce5f2; border: 1px solid #2b3748;
  selection-background-color: #315e95; selection-color: white;
  alternate-background-color: #1b2432;
}
QHeaderView::section { background: #202c3c; color: #dce5f2; padding: 7px; border: 0; }
QTabBar::tab { background: #1d2735; color: #b8c5d5; padding: 9px 15px; border: 1px solid #273545; }
QTabBar::tab:selected { background: #325a82; color: white; }
QPushButton { background: #26374b; color: #e8edf5; border: 1px solid #33485f;
  padding: 7px 12px; border-radius: 4px; }
QPushButton:hover { background: #365273; }
QToolButton { background: #26374b; color: #e8edf5; border: 1px solid #33485f; padding: 7px 12px; border-radius: 4px; }
QToolButton:hover { background: #365273; }
QPushButton:disabled { color: #697688; background: #1b2531; }
QLineEdit { background: #1b2634; color: #e2e8f0; border: 1px solid #405066;
  padding: 7px; border-radius: 4px; }
QLabel#subtle { color: #9aabbd; }
QSplitter::handle { background: #34445a; }
QScrollBar:vertical { background: #121923; width: 12px; }
QScrollBar::handle:vertical { background: #40526a; min-height: 22px; border-radius: 4px; }
"""


def _muted(text: str) -> QLabel:
    label = QLabel(text)
    label.setObjectName("subtle")
    label.setWordWrap(True)
    label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
    return label


def _format_path(path: str | None) -> str:
    return path or "(ikke angitt)"


def _is_running_status(status: str) -> bool:
    return status == "Kjører"


def _is_completed_status(status: str) -> bool:
    return status in {"Ferdig", "Feil", "Hoppet over"}


def _is_waiting_status(status: str) -> bool:
    return status == "Venter ved kontrollpunkt"


class DwmMainWindow(QMainWindow):
    """Independent, dock-based Qt frontend; no Tk widgets or old GUI classes."""

    def __init__(self, api: DwmWorkbenchAPI, parent=None):
        super().__init__(parent)
        self.api = api
        self.config = QSettings("IKAMR", "DWM-Qt")
        self._active_id: str | None = None
        self._worker: Thread | None = None
        self._job_controls_running = False
        self._worker_messages: Queue[tuple[str, str]] = Queue()
        self._batch_stop = Event()
        # Per-click request guard and local diagnostic log.
        self._run_request_busy = False
        self._run_audit = RunRequestAudit()
        self._run_audit_announced = False
        self._run_audit_warning_shown = False
        self._render_key: tuple | None = None
        self._complexity = "Standard"
        self._layout_name = "Laptop"
        self._file_model = None
        self._file_root: Path | None = None
        self._open_report_root: Path | None = None
        self._job_log_selected_job: tuple[str, str, str] | None = None
        self._job_log_last_options: tuple[tuple[str, str], ...] = ()
        self._a8_floating_once: set[str] = set()
        self._detached_log_window: DetachedJobLogWindow | None = None
        self._detached_run_window: DetachedRunWindow | None = None
        self._a8_run_context: tuple[str, str] | None = None
        self._a8_live_job: str | None = None
        self._a11_history_cache = ()  # Work-only real operation executions
        self._a12_result_windows: list = []  # Independent normal Windows
        self._a12_system_split_active = False
        self._a12_run_splitter_initialized = False

        self.setObjectName("DwmMainWindow")
        self.setWindowTitle(f"{APP_NAME} v{VERSION} – arbeidsflate")
        self.setStyleSheet(STYLE)
        self.setFont(QFont("Segoe UI", 10))
        self.setMinimumSize(720, 480)
        self.resize(1180, 780)
        self.setDockNestingEnabled(True)
        # A9 dock stability: avoid floating tabbed dock groups. Some Windows
        # Qt 6 builds can crash natively when a floating group is split.
        # Individual docks remain movable, floatable and resizable.
        self.setDockOptions(QMainWindow.DockOption.AllowNestedDocks)
        # Left job/workflow column extends below the central activity area.
        self.setCorner(Qt.Corner.BottomLeftCorner, Qt.DockWidgetArea.LeftDockWidgetArea)
        self.setStatusBar(QStatusBar())
        self._create_central()
        self._create_docks()
        self._create_actions_and_menu()
        self._restore_settings()
        # Connect AFTER restore: initial hidden/show dock signals must not
        # rearrange a restored user layout before its geometry exists.
        self.activity_tabs.currentChanged.connect(self._a12_activity_tab_changed)
        # A12: menu checks indicate the actually visible activity tab,
        # not just the shared dock's visibility.
        self.activity_tabs.currentChanged.connect(self._a12_sync_activity_menu)
        self.dock_log.visibilityChanged.connect(self._a12_sync_activity_menu)
        self.dock_system.visibilityChanged.connect(self._a12_system_visibility_changed)
        self._a12_sync_activity_menu()
        # A saved compact dock can be too small for all 9 status lines.
        # Grow only undersized layouts, never shrink a user-sized panel.
        QTimer.singleShot(0, self._a12_ensure_activity_height)
        QTimer.singleShot(0, self._a12_restore_cramped_system_log)

        self._poller = QTimer(self)
        self._poller.setInterval(200)
        self._poller.timeout.connect(self._poll)
        self._poller.start()
        app = QApplication.instance()
        if app:
            app.screenRemoved.connect(lambda _screen: QTimer.singleShot(250, self._recover_windows))
        self._refresh(force=True)

    # ---------- Main surfaces ----------
    def _create_central(self):
        self.pages = QTabWidget(self)
        self.pages.setDocumentMode(True)
        self.pages.setMovable(True)
        self.pages.currentChanged.connect(self._page_changed)
        self.setCentralWidget(self.pages)

        overview = QWidget()
        v = QVBoxLayout(overview)
        v.setContentsMargins(18, 18, 18, 14)
        heading = QLabel("Oversikt over aktiv jobb")
        heading.setFont(QFont("Segoe UI", 15, QFont.Weight.DemiBold))
        v.addWidget(heading)
        self.overview_label = _muted("Åpne en eksisterende .n5jobs-jobbliste for å begynne.")
        v.addWidget(self.overview_label)
        self.progress_label = QLabel("")
        self.progress_label.setWordWrap(True)
        v.addWidget(self.progress_label)
        quick = QHBoxLayout()
        self.overview_run = QPushButton("Kjør valgt")
        self.overview_run.clicked.connect(self._run_selected)
        quick.addWidget(self.overview_run)
        self.overview_continue = QPushButton("Fortsett ved kontrollpunkt")
        self.overview_continue.clicked.connect(self._continue_job)
        quick.addWidget(self.overview_continue)
        self.overview_work = QPushButton("Åpne DWM-arbeidsområde")
        self.overview_work.clicked.connect(self._open_work_dir)
        quick.addWidget(self.overview_work)
        self.overview_preflight = QPushButton("Kontroller / klargjør")
        self.overview_preflight.setToolTip("Sjekk uttrekk, lagringsroller og Work-mapper før kjøring")
        self.overview_preflight.clicked.connect(self._prepare_selected_only)
        quick.addWidget(self.overview_preflight)
        self.overview_change_work = QPushButton("Velg annen Work-mappe…")
        self.overview_change_work.setToolTip(
            "Endre Work-plassering med forhåndsvisning og godkjenning. "
            "Ingen mapper opprettes ved valget."
        )
        self.overview_change_work.clicked.connect(self._change_selected_work_location)
        quick.addWidget(self.overview_change_work)
        quick.addStretch(1)
        v.addLayout(quick)
        v.addSpacing(12)
        self.overview_storage = _muted("")
        v.addWidget(self.overview_storage)
        v.addStretch(1)
        self.pages.addTab(overview, "Oversikt")

        result = QWidget()
        result_layout = QVBoxLayout(result)
        result_layout.addWidget(_muted(
            "DWM-resultater leses fra lagret Work – operations for valgt jobb. "
            "Ingen uttrekksfiler flyttes eller endres."
        ))
        top = QHBoxLayout()
        self.results_root_label = _muted("Velg jobb for å finne resultatområdet.")
        top.addWidget(self.results_root_label, 1)
        button = QPushButton("Vis filer")
        button.clicked.connect(self._load_result_files)
        top.addWidget(button)
        open_button = QPushButton("Åpne mappe")
        open_button.clicked.connect(self._open_work_dir)
        top.addWidget(open_button)
        view_results = QPushButton("Resultatvisninger…")
        view_results.clicked.connect(self._a12_open_result_center)
        top.addWidget(view_results)
        self.results_report_button = QPushButton("Lag rapport…")
        self.results_report_button.clicked.connect(self._a12_open_selected_report)
        top.addWidget(self.results_report_button)
        result_layout.addLayout(top)
        self.file_tree = QTreeView()
        self.file_tree.setAlternatingRowColors(True)
        self.file_tree.setSortingEnabled(True)
        self.file_tree.doubleClicked.connect(self._open_selected_result)
        result_layout.addWidget(self.file_tree, 1)
        self.pages.addTab(result, "Resultater / filer")

        depot = QWidget()
        depot_layout = QVBoxLayout(depot)
        label = QLabel("Depotvurdering og rapporter")
        label.setFont(QFont("Segoe UI", 14, QFont.Weight.DemiBold))
        depot_layout.addWidget(label)
        depot_layout.addWidget(_muted(
            "Bruk den etablerte rapportmotoren til rapport for én jobb eller "
            "samlerapport for flere Noark 5-jobber. Depotvurdering finnes nå her; "
            "enkelte avanserte metadatafunksjoner ligger fortsatt i gammelt GUI."
        ))
        rbuttons = QHBoxLayout()
        b = QPushButton("Resultatvisninger…")
        b.clicked.connect(self._a12_open_result_center)
        rbuttons.addWidget(b)
        b = QPushButton("Lag rapport / samlerapport…")
        b.clicked.connect(self._a12_open_selected_report)
        rbuttons.addWidget(b)
        b = QPushButton("Vis rapportfiler")
        b.clicked.connect(self._show_result_files)
        rbuttons.addWidget(b)
        b = QPushButton("Depotvurdering…")
        b.clicked.connect(self._a2_open_depot_review)
        rbuttons.addWidget(b)
        b = QPushButton("Åpne siste depotrapport")
        b.clicked.connect(self._open_latest_depot_report)
        rbuttons.addWidget(b)
        rbuttons.addStretch(1)
        depot_layout.addLayout(rbuttons)
        self.depot_path_label = _muted("")
        depot_layout.addWidget(self.depot_path_label)
        depot_layout.addStretch(1)
        self.pages.addTab(depot, "Depot / rapport")

    def _dock(self, name: str, title: str, widget: QWidget, area):
        dock = QDockWidget(title, self)
        dock.setObjectName("dwm_" + name)
        dock.setWidget(widget)
        dock.setFeatures(
            QDockWidget.DockWidgetFeature.DockWidgetClosable
            | QDockWidget.DockWidgetFeature.DockWidgetMovable
            | QDockWidget.DockWidgetFeature.DockWidgetFloatable
        )
        if name in {"log", "run"}:
            # Native floating QDockWidget is a parent-owned Qt.Tool on Windows
            # and can jump back inside the main window during drag/drop. Keep
            # log/progress docks fixed and use normal, independent Qt.Windows.
            dock.setFeatures(QDockWidget.DockWidgetFeature.DockWidgetClosable)
            header = DetachableDockTitleBar(title)
            if name == "log":
                # The unified activity dock opens whichever tab is selected.
                header.detachRequested.connect(self._a12_detach_active_tab)
            else:
                header.detachRequested.connect(self._a9_float_run)
            header.hideRequested.connect(dock.hide)
            dock.setTitleBarWidget(header)
        dock.setAllowedAreas(Qt.DockWidgetArea.AllDockWidgetAreas)
        self.addDockWidget(area, dock)
        setattr(self, "dock_" + name, dock)
        if name in {"log", "run", "system"}:
            dock.topLevelChanged.connect(
                lambda floating, n=name: self._a8_dock_floating(n, floating)
            )
        return dock

    def _create_docks(self):
        # Job list – no separate top-level window is required.
        jobs = QWidget()
        j = QVBoxLayout(jobs)
        j.setContentsMargins(7, 6, 7, 6)
        j.setSpacing(5)
        self.joblist_label = _muted("Ingen jobbliste åpnet")
        j.addWidget(self.joblist_label)
        self.job_search = QLineEdit()
        self.job_search.setPlaceholderText("Søk i jobblisten (navn, ID, status, Source eller Work)…")
        self.job_search.setClearButtonEnabled(True)
        self.job_search.textChanged.connect(self._filter_jobs)
        search_row = QHBoxLayout()
        search_row.setSpacing(5)
        search_row.addWidget(self.job_search, 1)
        # Work-output rules are important, but should not permanently squeeze
        # the job table. Keep the original editor in a collapsible panel.
        self.job_rule_toggle = QPushButton("Regel ▸")
        self.job_rule_toggle.setToolTip("Vis eller skjul jobblistens Work-undermappe-regel")
        self.job_rule_toggle.setFixedWidth(69)
        self.job_rule_toggle.clicked.connect(self._a12_toggle_job_rule)
        search_row.addWidget(self.job_rule_toggle)
        j.addLayout(search_row)
        self.jobs_tree = QTreeWidget()
        self.jobs_tree.setMinimumHeight(110)
        self.jobs_tree.setHeaderLabels(["Jobb", "Navn / uttrekk", "Status", "%"])
        self.jobs_tree.setAlternatingRowColors(True)
        self.jobs_tree.setRootIsDecorated(False)
        self.jobs_tree.setUniformRowHeights(True)
        self.jobs_tree.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.jobs_tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.jobs_tree.header().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.jobs_tree.header().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.jobs_tree.header().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.jobs_tree.currentItemChanged.connect(self._job_clicked)
        self.jobs_tree.itemDoubleClicked.connect(self._job_double_clicked)
        self.jobs_tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.jobs_tree.customContextMenuRequested.connect(self._job_context_menu)
        j.addWidget(self.jobs_tree, 1)
        job_buttons = QHBoxLayout()
        job_buttons.setSpacing(3)
        self.job_add_button = QPushButton("+ Ny")
        self.job_add_button.setToolTip("Legg til en jobb i jobblisten")
        self.job_add_button.clicked.connect(self._new_job)
        job_buttons.addWidget(self.job_add_button)
        self.job_rename_button = QPushButton("Navn")
        self.job_rename_button.setToolTip("Endre navnet på valgt jobb")
        self.job_rename_button.clicked.connect(self._rename_job)
        job_buttons.addWidget(self.job_rename_button)
        self.job_up_button = QPushButton("↑")
        self.job_up_button.setToolTip("Flytt valgt jobb opp")
        self.job_up_button.clicked.connect(lambda: self._move_job(-1))
        job_buttons.addWidget(self.job_up_button)
        self.job_down_button = QPushButton("↓")
        self.job_down_button.setToolTip("Flytt valgt jobb ned")
        self.job_down_button.clicked.connect(lambda: self._move_job(1))
        job_buttons.addWidget(self.job_down_button)
        self.job_remove_button = QPushButton("Fjern")
        self.job_remove_button.setToolTip("Fjern bare jobbhenvisningen; ingen filer slettes")
        self.job_remove_button.clicked.connect(self._remove_job)
        job_buttons.addWidget(self.job_remove_button)
        j.addLayout(job_buttons)
        # Per-job-list output rule is stored in .n5jobs, independently of
        # the global app_work_subfolder setting in Setup.  Preserve all
        # original edit controls, but collapse them by default.
        self.job_rule_box = QWidget()
        rule_box_layout = QVBoxLayout(self.job_rule_box)
        rule_box_layout.setContentsMargins(0, 0, 0, 0)
        rule_box_layout.setSpacing(3)
        rule_form = QHBoxLayout()
        rule_form.setSpacing(5)
        rule_form.addWidget(QLabel("Undermappe-regel:"))
        self.job_output_rule = QLineEdit()
        self.job_output_rule.setPlaceholderText("Tom = ingen | a01 | <nnn> | <jobno> | <name> …")
        self.job_output_rule.setToolTip(
            "Jobblistens undermappe-regel for Work – operations. "
            "Global DWM-undermappe administreres i Setup."
        )
        self.job_output_rule.returnPressed.connect(self._apply_job_output_rule)
        rule_form.addWidget(self.job_output_rule, 1)
        self.job_rule_apply = QPushButton("Bruk regel")
        self.job_rule_apply.clicked.connect(self._apply_job_output_rule)
        rule_form.addWidget(self.job_rule_apply)
        rule_box_layout.addLayout(rule_form)
        self.job_rule_preview = _muted("Ingen jobbliste-regel valgt")
        self.job_rule_preview.setMaximumHeight(42)
        self.job_rule_preview.setToolTip(
            "Eksempel: Work operations / dwm / a01. "
            "Resultatmappene opprettes først etter kontroll og godkjenning."
        )
        rule_box_layout.addWidget(self.job_rule_preview)
        j.addWidget(self.job_rule_box)
        self._a12_job_rule_visible = self.config.value(
            "qt/a12_job_rule_visible", False, type=bool,
        )
        self.job_rule_box.setVisible(self._a12_job_rule_visible)
        self.job_rule_toggle.setText("Regel ▾" if self._a12_job_rule_visible else "Regel ▸")
        self._job_action_buttons = (
            self.job_rename_button, self.job_up_button,
            self.job_down_button, self.job_remove_button,
        )
        self._dock("jobs", "Jobber", jobs, Qt.DockWidgetArea.LeftDockWidgetArea)
        self.dock_jobs.setMinimumWidth(320)

        flow = QWidget()
        f = QVBoxLayout(flow)
        f.setContentsMargins(7, 6, 7, 6)
        f.setSpacing(5)
        self.workflow_label = _muted("Velg jobb for å se arbeidsflyten.")
        f.addWidget(self.workflow_label)
        self.workflow_tree = QTreeWidget()
        self.workflow_tree.setMinimumHeight(192)
        self.workflow_tree.setHeaderLabels(["#", "Deljobb", "Status", "Stopp"])
        self.workflow_tree.setRootIsDecorated(False)
        self.workflow_tree.setAlternatingRowColors(True)
        self.workflow_tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.workflow_tree.header().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.workflow_tree.header().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.workflow_tree.header().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.workflow_tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.workflow_tree.customContextMenuRequested.connect(self._a9_workflow_context_menu)
        f.addWidget(self.workflow_tree, 1)
        action_row = QHBoxLayout()
        self.workflow_preset_button = QPushButton("Velg arbeidsflyt…")
        self.workflow_preset_button.clicked.connect(self._choose_workflow)
        action_row.addWidget(self.workflow_preset_button)
        self.workflow_checkpoint_button = QPushButton("Kontrollpunkt av/på")
        self.workflow_checkpoint_button.clicked.connect(self._toggle_checkpoint)
        action_row.addWidget(self.workflow_checkpoint_button)
        f.addLayout(action_row)
        subjobs_row = QHBoxLayout()
        self.subjob_run_button = QPushButton("Kj\u00f8r valgt deljobb")
        self.subjob_run_button.clicked.connect(self._a9_run_selected_subjob)
        subjobs_row.addWidget(self.subjob_run_button)
        self.subjob_check_button = QPushButton("Kontroller deljobb")
        self.subjob_check_button.clicked.connect(self._a9_check_selected_subjob)
        subjobs_row.addWidget(self.subjob_check_button)
        f.addLayout(subjobs_row)
        self._dock("workflow", "Arbeidsflyt", flow, Qt.DockWidgetArea.LeftDockWidgetArea)
        self.dock_workflow.setMinimumWidth(320)

        storage = QWidget()
        s = QVBoxLayout(storage)
        s.addWidget(_muted("Uavhengige plasseringer for Source, Work og AIP."))
        self.storage_text = QPlainTextEdit()
        self.storage_text.setReadOnly(True)
        self.storage_text.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        s.addWidget(self.storage_text, 1)
        self.storage_edit_button = QPushButton("Rediger lagringsroller…")
        self.storage_edit_button.clicked.connect(self._edit_storage)
        s.addWidget(self.storage_edit_button)
        self.storage_prepare_button = QPushButton("Kontroller og klargjør Work…")
        self.storage_prepare_button.clicked.connect(self._prepare_selected_only)
        s.addWidget(self.storage_prepare_button)
        self.storage_change_work = QPushButton("Velg annen Work-mappe…")
        self.storage_change_work.clicked.connect(self._change_selected_work_location)
        s.addWidget(self.storage_change_work)
        self._dock("storage", "Kilde og lagring", storage, Qt.DockWidgetArea.RightDockWidgetArea)

        # A8: three independent dockable views, not a mixed session log.
        logger = QWidget()
        l = QVBoxLayout(logger)
        log_row = QHBoxLayout()
        log_row.addWidget(QLabel("Kjøring:"))
        self.job_run_combo = QComboBox()
        self.job_run_combo.setMinimumWidth(120)
        self.job_run_combo.setToolTip("Velg tidligere kjøring for den aktive jobben")
        self.job_run_combo.currentIndexChanged.connect(self._a8_show_selected_run)
        log_row.addWidget(self.job_run_combo, 1)
        refresh = QPushButton("Oppdater")
        refresh.clicked.connect(lambda: self._a8_refresh_job_log(force=True))
        log_row.addWidget(refresh)
        l.addLayout(log_row)
        self.job_log_text = QPlainTextEdit()
        self.job_log_text.setReadOnly(True)
        self.job_log_text.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.job_log_text.setMaximumBlockCount(10000)
        l.addWidget(self.job_log_text, 1)
        logtools = QHBoxLayout()
        self.log_follow = QCheckBox("Følg siste linje")
        self.log_follow.setChecked(self.config.value("qt/a8_log_follow", True, type=bool))
        self.log_follow.toggled.connect(lambda value: self.config.setValue("qt/a8_log_follow", value))
        logtools.addWidget(self.log_follow)
        clear = QPushButton("Tøm visning")
        clear.setToolTip("Tøm bare visningen, ikke den lagrede kjøreloggen")
        clear.clicked.connect(self.job_log_text.clear)
        logtools.addWidget(clear)
        self.log_window_button = QPushButton("Eget vindu")
        self.log_window_button.setToolTip("Frikoble eller feste Kjørelogg til hovedvinduet")
        self.log_window_button.clicked.connect(self._a8_float_job_log)
        logtools.addWidget(self.log_window_button)
        logtools.addStretch(1)
        l.addLayout(logtools)
        self.job_log_text.textChanged.connect(self._a9_sync_detached_log_text)
        self.log_follow.toggled.connect(self._a9_sync_detached_log_follow)
        self._a8_update_log_window_buttons()

        flow_progress = QWidget()
        rp = QVBoxLayout(flow_progress)
        self.run_summary = _muted("Ingen kjøring startet i denne økten.")
        rp.addWidget(self.run_summary)
        self.run_progress_bar = QProgressBar()
        self.run_progress_bar.setRange(0, 100)
        rp.addWidget(self.run_progress_bar)
        self.run_history_tree = QTreeWidget()
        self.run_history_tree.setHeaderLabels(["Tid", "Deljobb", "Kjøring", "Teknisk", "Resultater"])
        self.run_history_tree.setRootIsDecorated(False)
        self.run_history_tree.setAlternatingRowColors(True)
        self.run_history_tree.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.run_history_tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.run_history_tree.header().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.run_history_tree.header().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.run_history_tree.header().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.run_history_tree.header().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        self.run_history_tree.itemDoubleClicked.connect(self._a11_show_selected_results)
        self.run_events = QPlainTextEdit()
        self.run_events.setReadOnly(True)
        self.run_events.setMaximumBlockCount(400)
        history_splitter = QSplitter(Qt.Orientation.Vertical)
        history_splitter.addWidget(self.run_history_tree)
        history_splitter.addWidget(self.run_events)
        history_splitter.setStretchFactor(0, 3)
        history_splitter.setStretchFactor(1, 2)
        self.run_history_splitter = history_splitter
        rp.addWidget(history_splitter, 1)
        run_tools = QHBoxLayout()
        rp.addWidget(_muted("Faktiske deljobbkjøringer – teknisk status, ikke depotgodkjenning"))
        run_tools.addStretch(1)
        self.a11_run_log_button = QPushButton("Logg")
        self.a11_run_log_button.setToolTip("Åpne faktisk kjørelogg for valgt deljobbkjøring")
        self.a11_run_log_button.clicked.connect(self._a11_show_selected_history_log)
        run_tools.addWidget(self.a11_run_log_button)
        self.a11_result_button = QPushButton("Resultater")
        self.a11_result_button.setToolTip("Åpne eksisterende resultatfil for valgt kjøring i Work")
        self.a11_result_button.clicked.connect(self._a11_show_selected_results)
        run_tools.addWidget(self.a11_result_button)
        self.run_window_button = QPushButton("Eget vindu")
        self.run_window_button.clicked.connect(self._a9_float_run)
        run_tools.addWidget(self.run_window_button)
        rp.addLayout(run_tools)
        # A12: ONE safe dock with two normal QWidget tabs. Not native Qt dock
        # tabification, which previously crashed when floating groups on Windows.
        self.activity_tabs = QTabWidget()
        self.activity_tabs.setDocumentMode(True)
        self.activity_tabs.setTabsClosable(False)
        self.activity_tabs.setMovable(False)
        self.activity_tabs.addTab(logger, "Kjørelogg")
        self.activity_tabs.addTab(flow_progress, "Kjøreløp")
        self.activity_tabs.setCurrentIndex(1)
        self.activity_tabs.currentChanged.connect(
            lambda index: self.config.setValue("qt/a12_activity_tab", index)
        )
        self._dock("log", "Aktivitet", self.activity_tabs,
                   Qt.DockWidgetArea.BottomDockWidgetArea)
        # Retain a hidden legacy dock name for QSettings state compatibility.
        # It must never hold a second visible progress panel.
        self._dock("run", "Kjøreløp", QWidget(),
                   Qt.DockWidgetArea.BottomDockWidgetArea)
        self.dock_run.hide()

        system = QWidget()
        sy = QVBoxLayout(system)
        sy.addWidget(_muted("Hendelser i GUI, åpning av jobblister og Setup. "
                            "Kjøreloggen for en jobb ligger i eget panel."))
        self.system_text = QPlainTextEdit()
        self.system_text.setReadOnly(True)
        self.system_text.setMaximumBlockCount(2500)
        sy.addWidget(self.system_text, 1)
        sysclear = QPushButton("Tøm systemvisning")
        sysclear.clicked.connect(self.system_text.clear)
        sy.addWidget(sysclear)
        self._dock("system", "Systemlogg", system, Qt.DockWidgetArea.BottomDockWidgetArea)

        info = QWidget()
        i = QVBoxLayout(info)
        self.info_text = _muted(
            "Kjørelogg og Kjøreløp har hver sin Eget vindu-knapp. "
            "Du kan også dra i paneltittelen for å åpne et vanlig Windows-vindu.\n\n"
            "Andre paneler kan plasseres til venstre, høyre, øverst eller nederst.\n\n"
            "Velg Vis → Arbeidsflate for ferdige oppsett.\n\n"
            "Vis → Lagre arbeidsflate som … lagrer egen plassering.\n\n"
            "Kjøring og analyser gjøres av DWM-motoren, ikke Qt-GUI-et."
        )
        self.info_text.setAlignment(Qt.AlignmentFlag.AlignTop)
        i.addWidget(self.info_text)
        i.addStretch(1)
        self._dock("info", "Hjelp og informasjon", info, Qt.DockWidgetArea.RightDockWidgetArea)

        self.splitDockWidget(self.dock_jobs, self.dock_workflow, Qt.Orientation.Vertical)
        self.splitDockWidget(self.dock_storage, self.dock_info,
                             Qt.Orientation.Vertical)
        self.dock_storage.raise_()
        self.dock_run.hide()
        self.dock_system.hide()

    # ---------- Menus and layout persistence ----------
    def _action(self, title, method, shortcut: str | None = None):
        action = QAction(title, self)
        action.triggered.connect(method)
        if shortcut:
            action.setShortcut(shortcut)
        return action

    def _create_actions_and_menu(self):
        mb = self.menuBar()
        file_menu = mb.addMenu("Fil")
        self.open_action = self._action("Åpne jobbliste…", self._open_dialog, "Ctrl+O")
        self.new_list_action = self._action("Ny jobbliste", self._new_list, "Ctrl+N")
        self.save_action = self._action("Lagre jobbliste", self._save, "Ctrl+S")
        self.save_as_action = self._action("Lagre jobbliste som…", self._save_as)
        self.new_job_action = self._action("Legg til jobb…", self._new_job)
        file_menu.addAction(self.open_action)
        self._recent_menu = file_menu.addMenu("Nylige jobblister")
        file_menu.addAction(self.new_list_action)
        file_menu.addAction(self.save_action)
        file_menu.addAction(self.save_as_action)
        file_menu.addAction(self.new_job_action)
        file_menu.addSeparator()
        self.recover_work_job_action = self._action(
            "Åpne jobb fra DWM-arbeidsområde…", self._a10_recover_work_job,
        )
        self.migrate_work_job_action = self._action(
            "Lagre valgt jobb i Work…", self._a10_migrate_work_job,
        )
        file_menu.addAction(self.recover_work_job_action)
        file_menu.addAction(self.migrate_work_job_action)
        self.rename_job_action = self._action("Endre navn på jobb…", self._rename_job)
        self.remove_job_action = self._action("Fjern jobb fra listen…", self._remove_job)
        file_menu.addAction(self.rename_job_action)
        file_menu.addAction(self.remove_job_action)
        file_menu.addSeparator()
        self.setup_action = self._action("Setup", self._open_setup)
        file_menu.addAction(self.setup_action)
        file_menu.addSeparator()
        file_menu.addAction(self._action("Start gammel CustomTkinter-GUI", self._open_legacy))
        file_menu.addAction(self._action("Avslutt", self.close, "Ctrl+Q"))

        run_menu = mb.addMenu("Kjør")
        self.run_action = self._action("Kjør valgt jobb", self._run_selected, "F5")
        self.continue_action = self._action("Fortsett ved kontrollpunkt", self._continue_job)
        self.ready_action = self._action("Kjør klare jobber (sekvensielt)", self._run_ready)
        self.preflight_action = self._action("Kontroller og klargjør valgt jobb…", self._prepare_selected_only)
        self.stop_action = self._action("Stopp etter gjeldende operasjon", self._request_stop, "Shift+F5")
        for a in (self.run_action, self.continue_action, self.ready_action, self.preflight_action, self.stop_action):
            run_menu.addAction(a)
        self.stop_action.setEnabled(False)
        self.subjob_run_action = self._action("Kj\u00f8r valgt deljobb...", self._a9_run_selected_subjob)
        self.subjob_check_action = self._action("Kontroller valgt deljobb...", self._a9_check_selected_subjob)
        run_menu.addSeparator()
        run_menu.addAction(self.subjob_run_action)
        run_menu.addAction(self.subjob_check_action)

        reports_menu = mb.addMenu("Rapport")
        self.result_center_action = self._action("Resultatvisninger…", self._a12_open_result_center)
        self.report_selected_action = self._action(
            "Lag rapport / samlerapport…", self._a12_open_selected_report,
        )
        reports_menu.addAction(self.result_center_action)
        reports_menu.addAction(self.report_selected_action)
        reports_menu.addAction(self._action("Depotvurdering…", self._a2_open_depot_review))
        reports_menu.addAction(self._action("Åpne siste depotrapport", self._open_latest_depot_report))

        view = mb.addMenu("Vis")
        # Refresh checks whenever the menu opens (also handles returning from
        # independent Windows windows and a restored native Qt layout).
        view.aboutToShow.connect(self._a12_sync_activity_menu)
        for name in DOCK_NAMES:
            if name == "run":
                continue  # Legacy placeholder is NEVER exposed as a second dock.
            toggle = getattr(self, "dock_" + name).toggleViewAction()
            view.addAction(toggle)
        view.addSeparator()
        # "Aktivitet" above is the NATIVE panel show/hide toggle.
        # These two actions select its contents; neither is a visibility
        # toggle. Putting them under a named submenu avoids the misleading
        # old "Vis kjørelogg" command alongside the panel toggle.
        activity_view_menu = view.addMenu("Aktivitetsfane")
        self.show_job_log_action = self._action("Kjørelogg", self._a8_show_job_log)
        self.show_job_log_action.setCheckable(True)
        self.show_job_log_action.setToolTip(
            "Velg Kjørelogg i Aktivitet (eller hent frem separat loggvindu)."
        )
        activity_view_menu.addAction(self.show_job_log_action)
        self.show_run_tab_action = self._action(
            "Kjøreløp", self._a12_show_run_tab,
        )
        self.show_run_tab_action.setCheckable(True)
        self.show_run_tab_action.setToolTip(
            "Velg Kjøreløp i Aktivitet (eller hent frem separat kjøreløpvindu)."
        )
        activity_view_menu.addAction(self.show_run_tab_action)
        view.addSeparator()
        self.float_job_log_action = self._action("Åpne kjørelogg i eget vindu", self._a8_float_job_log)
        view.addAction(self.float_job_log_action)
        self.float_run_action = self._action("Åpne kjøreløp i eget vindu", self._a9_float_run)
        view.addAction(self.float_run_action)
        self._a8_update_log_window_buttons()
        self._a9_update_run_window_buttons()
        self.auto_show_log_action = self._action("Vis kjørelogg automatisk ved jobbstart", lambda: None)
        self.auto_show_log_action.setCheckable(True)
        self.auto_show_log_action.setChecked(self.config.value("qt/a8_auto_show_log", True, type=bool))
        self.auto_show_log_action.toggled.connect(lambda value: self.config.setValue("qt/a8_auto_show_log", value))
        view.addAction(self.auto_show_log_action)
        view.addSeparator()
        preset = view.addMenu("Arbeidsflate")
        self._layout_actions = {}
        group = QActionGroup(self)
        group.setExclusive(True)
        for name in LAYOUT_MODES:
            action = self._action(name, lambda _checked=False, n=name: self._apply_builtin(n))
            action.setCheckable(True)
            group.addAction(action)
            preset.addAction(action)
            self._layout_actions[name] = action
        self._preset_menu = preset
        view.addAction(self._action("Lagre arbeidsflate som…", self._save_named_layout))
        self._saved_layout_menu = view.addMenu("Mine arbeidsflater")
        self._refresh_named_layout_menu()
        view.addAction(self._action("Tilbakestill vinduer", lambda: self._apply_builtin("Laptop")))
        view.addSeparator()
        complexity_menu = view.addMenu("Kompleksitet")
        group_complexity = QActionGroup(self)
        group_complexity.setExclusive(True)
        self._complexity_actions = {}
        self._complexity_menu = complexity_menu
        for mode in COMPLEXITY_MODES:
            action = self._action(mode, lambda _checked=False, n=mode: self._set_complexity(n))
            action.setCheckable(True)
            group_complexity.addAction(action)
            complexity_menu.addAction(action)
            self._complexity_actions[mode] = action

        toolbar = QToolBar("Hovedhandlinger", self)
        toolbar.setObjectName("main_toolbar")
        toolbar.setMovable(False)
        toolbar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        self.addToolBar(toolbar)
        toolbar.addAction(self.open_action)
        toolbar.addAction(self.save_action)
        toolbar.addAction(self.new_job_action)
        toolbar.addSeparator()
        toolbar.addAction(self.run_action)
        toolbar.addAction(self.continue_action)
        toolbar.addAction(self.stop_action)
        toolbar.addSeparator()
        self.layout_tool = QToolButton(self)
        self.layout_tool.setText("Arbeidsflate ▾")
        self.layout_tool.setToolTip("Velg eller gjenopprett plassering av panelene")
        self.layout_tool.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.layout_tool.setMenu(self._preset_menu)
        toolbar.addWidget(self.layout_tool)
        self.complexity_tool = QToolButton(self)
        self.complexity_tool.setText("Kompleksitet ▾")
        self.complexity_tool.setToolTip("Enkel, Standard eller Avansert")
        self.complexity_tool.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.complexity_tool.setMenu(self._complexity_menu)
        toolbar.addWidget(self.complexity_tool)
        toolbar.addSeparator()
        toolbar.addAction(self.setup_action)
        # Toolbar buttons are commands, not checked/unchecked tab indicators.
        # A separate QAction prevents its visual state from being confused
        # with the checkmark that marks the active tab in the Vis submenu.
        self.goto_job_log_action = self._action(
            "Gå til kjørelogg", self._a8_show_job_log,
        )
        self.goto_job_log_action.setToolTip(
            "Aktiver Kjørelogg-fanen i Aktivitet. Viser panelet hvis det er skjult."
        )
        toolbar.addAction(self.goto_job_log_action)
        self._toolbar = toolbar
        self._refresh_recent_menu()

    def _apply_builtin(self, name: str):
        if name not in LAYOUT_MODES:
            raise ValueError(f"Ukjent arbeidsflate: {name}")
        self._a12_system_split_active = False
        # Re-dock all panels deterministically, even after a floating-window session.
        target = {
            "Laptop": {"jobs": "left", "workflow": "left", "storage": "right", "log": "bottom", "info": "right"},
            "Analyse": {"jobs": "left", "workflow": "left", "storage": "right", "log": "bottom", "info": "right"},
            "Depot": {"jobs": "left", "workflow": "bottom", "storage": "right", "log": "bottom", "info": "right"},
            "Full": {"jobs": "left", "workflow": "left", "storage": "right", "log": "bottom", "info": "right"},
            "Workshop": {"jobs": "left", "workflow": "bottom", "storage": "right", "log": "bottom", "info": "right"},
            "Topp og bunn": {"jobs": "top", "workflow": "left", "storage": "right", "log": "bottom", "info": "right"},
        }[name]
        area_map = {
            "left": Qt.DockWidgetArea.LeftDockWidgetArea,
            "right": Qt.DockWidgetArea.RightDockWidgetArea,
            "bottom": Qt.DockWidgetArea.BottomDockWidgetArea,
            "top": Qt.DockWidgetArea.TopDockWidgetArea,
        }
        for key in ("jobs", "workflow", "storage", "log", "info"):
            dock = getattr(self, "dock_" + key)
            dock.setFloating(False)
            self.removeDockWidget(dock)
            self.addDockWidget(area_map[target[key]], dock)
            dock.show()
        for key in ("run", "system"):
            dock = getattr(self, "dock_" + key)
            dock.setFloating(False)
            self.removeDockWidget(dock)
            self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, dock)
            dock.hide()
        if name in {"Laptop", "Full", "Analyse"}:
            self.splitDockWidget(self.dock_jobs, self.dock_workflow, Qt.Orientation.Vertical)
        if name == "Full":
            self.splitDockWidget(self.dock_storage, self.dock_info,
                                 Qt.Orientation.Vertical)
            self.dock_info.hide()
            self._set_complexity("Avansert")
        elif name == "Analyse":
            self.dock_info.hide()
            self._set_complexity("Standard")
        elif name == "Depot":
            self.dock_workflow.hide()
            self.dock_info.hide()
            self.dock_log.hide()
            self._set_complexity("Standard")
            self.pages.setCurrentIndex(2)
        elif name == "Topp og bunn":
            self.dock_info.hide()
            self._set_complexity("Standard")
            self.pages.setCurrentIndex(0)
        elif name == "Workshop":
            self.dock_storage.hide()
            self.dock_info.hide()
            self.dock_log.hide()
            self._set_complexity("Enkel")
            self.pages.setCurrentIndex(0)
        else:
            self.dock_storage.hide()
            self.dock_info.hide()
            self.dock_log.show()
            self._set_complexity("Enkel")
            self.pages.setCurrentIndex(0)
        if name == "Full":
            self.pages.setCurrentIndex(0)
        if name == "Analyse":
            self.pages.setCurrentIndex(1)
        # Preset changes must not bring back the hidden dock while an
        # independent (normally stacked) viewer is showing the same log.
        if self._detached_log_window is not None:
            self.dock_log.hide()
        self.dock_run.hide()  # Never allow the old second bottom dock.
        self._a12_reconcile_activity_tabs()
        if name == "Laptop" and self._detached_run_window is None:
            self.activity_tabs.setCurrentIndex(1)
        self._layout_name = name
        # Resize only built-in layouts, never arbitrarily move saved custom ones.
        QTimer.singleShot(0, self._a12_balance_workspace)
        for label, action in self._layout_actions.items():
            action.setChecked(label == name)
        self.statusBar().showMessage(f"Arbeidsflate: {name}", 5000)

    def _set_complexity(self, mode: str):
        if mode not in COMPLEXITY_MODES:
            return
        self._complexity = mode
        for name, action in self._complexity_actions.items():
            action.setChecked(name == mode)
        advanced = mode == "Avansert"
        self.workflow_preset_button.setVisible(mode != "Enkel")
        self.workflow_checkpoint_button.setVisible(advanced)
        self.storage_edit_button.setVisible(advanced)
        self.ready_action.setVisible(mode != "Enkel")
        # Creating a job remains available at every complexity level.
        self.new_job_action.setVisible(True)
        self.config.setValue("qt/complexity", mode)

    def _profiles(self) -> dict[str, dict]:
        text = str(self.config.value("qt/named_layouts", "{}") or "{}")
        try:
            parsed = json.loads(text)
        except (TypeError, ValueError):
            return {}
        if not isinstance(parsed, dict):
            return {}
        return {str(k): (v if isinstance(v, dict) else {"state": str(v)})
                for k, v in parsed.items()}

    def _save_named_layout(self):
        name, ok = QInputDialog.getText(self, "Lagre arbeidsflate", "Navn på arbeidsflaten:")
        if not ok or not name.strip():
            return
        name = name.strip()
        if len(name) > 80:
            QMessageBox.warning(self, "Ugyldig navn", "Bruk maksimalt 80 tegn.")
            return
        profiles = self._profiles()
        if name in profiles:
            answer = QMessageBox.question(self, "Erstatte?", f"Erstatte arbeidsflaten «{name}»?")
            if answer != QMessageBox.StandardButton.Yes:
                return
        profiles[name] = {
            "state": bytes(self.saveState(4).toBase64()).decode("ascii"),
            "complexity": self._complexity,
            "page": self.pages.currentIndex(),
        }
        self.config.setValue("qt/named_layouts", json.dumps(profiles, ensure_ascii=False))
        self._refresh_named_layout_menu()
        self.statusBar().showMessage(f"Arbeidsflate lagret: {name}", 5000)

    def _refresh_named_layout_menu(self):
        menu = self._saved_layout_menu
        menu.clear()
        for name in sorted(self._profiles()):
            menu.addAction(self._action(name, lambda _checked=False, n=name: self._load_named_layout(n)))
        if not menu.actions():
            placeholder = menu.addAction("Ingen lagrede oppsett")
            placeholder.setEnabled(False)

    # ---------- a4: recent job lists, including last known legacy job list ----------
    def _recent_paths(self) -> tuple[str, ...]:
        return recent_joblists(
            str(self.config.value("qt/last_job_list", "") or ""),
            self.config.value("qt/recent_job_lists", []),
            self.api.settings,
        )

    def _refresh_recent_menu(self):
        self._recent_menu.clear()
        candidates = self._recent_paths()
        if not candidates:
            empty = self._recent_menu.addAction("Ingen tilgjengelige jobblister")
            empty.setEnabled(False)
            return
        for path in candidates:
            # File name for readability; complete path available as tooltip.
            action = self._action(Path(path).name,
                                  lambda _checked=False, p=path: self._open_recent(p))
            action.setToolTip(path)
            self._recent_menu.addAction(action)

    def _remember_joblist(self, path: str):
        items = remember_joblist(path, self.config.value("qt/recent_job_lists", []))
        self.config.setValue("qt/recent_job_lists", list(items))
        self.config.setValue("qt/last_job_list", path)
        self.config.setValue("qt/skip_auto_reopen", False)
        self._refresh_recent_menu()

    def _open_recent(self, path: str):
        if not self._maybe_save():
            return
        self._open_path(path)

    def _load_named_layout(self, name: str):
        profile = self._profiles().get(name)
        if not profile:
            return
        from PySide6.QtCore import QByteArray
        encoded = str(profile.get("state", ""))
        if not self.restoreState(QByteArray.fromBase64(encoded.encode("ascii")), 4):
            QMessageBox.warning(self, "Arbeidsflate", "Kunne ikke gjenopprette lagret arbeidsflate.")
            return
        self._a9_normalize_log_dock()
        self.dock_run.hide()
        self._a12_reconcile_activity_tabs()
        self._layout_name = name
        self._set_complexity(str(profile.get("complexity", "Standard")))
        page = profile.get("page", 0)
        if isinstance(page, int) and 0 <= page < self.pages.count():
            self.pages.setCurrentIndex(page)
        for action in self._layout_actions.values():
            action.setChecked(False)
        self._recover_windows()

    def _restore_settings(self):
        preferred_complexity = str(self.config.value("qt/complexity", "Standard"))
        geometry = self.config.value("qt/window_geometry")
        if geometry:
            try:
                self.restoreGeometry(geometry)
            except (TypeError, ValueError):
                pass
        state = self.config.value("qt/window_state")
        restored = False
        # The old a12 state contains two separate bottom docks and cannot
        # produce a clean one-panel layout. Migrate it ONCE, then save the new
        # native Qt state normally on close; named layouts remain untouched.
        migrated = self.config.value(
            "qt/a12_unified_activity_initialized", False, type=bool,
        )
        if state and migrated:
            try:
                restored = self.restoreState(state, 4)
            except (TypeError, ValueError):
                pass
        if not restored:
            self._apply_builtin("Laptop")
        self.dock_run.hide()
        self._a12_reconcile_activity_tabs()
        if restored and self._detached_run_window is None:
            value = self.config.value("qt/a12_activity_tab", 1)
            selected = int(value) if value is not None else 1
            self.activity_tabs.setCurrentIndex(1 if selected == 1 else 0)
        self.config.setValue("qt/a12_unified_activity_initialized", True)
        self._a9_normalize_log_dock()
        self._set_complexity(preferred_complexity)
        self._recover_windows()
        if not self.config.value("qt/skip_auto_reopen", False, type=bool):
            candidates = self._recent_paths()
            if candidates:
                try:
                    self.open_job_list(candidates[0])
                except Exception as exc:
                    self._append_log(f"Kunne ikke åpne sist brukte jobbliste: {exc}")
        self._refresh_recent_menu()
        # A10/A11 could persist a dock geometry that hides the job row behind
        # the horizontal scrollbar. Repair only this invalid state, without
        # discarding valid, deliberately saved window positions.
        QTimer.singleShot(0, self._a12_repair_cramped_job_panel)

    def _a12_repair_cramped_job_panel(self):
        if (self.dock_jobs.isVisible() and self.dock_workflow.isVisible()
                and not self.dock_jobs.isFloating()
                and self.jobs_tree.viewport().height() < 68):
            self._a12_balance_left_docks()

    def _recover_windows(self):
        # Recover after a second monitor is disconnected. Never resize job data.
        if self._detached_log_window is not None:
            self._a9_recover_detached_log_geometry()
        if self._detached_run_window is not None:
            self._a9_recover_detached_run_geometry()
        screens = QApplication.screens()
        if not screens:
            return
        geometries = [screen.availableGeometry() for screen in screens]
        safe = screens[0].availableGeometry()
        windows = [self] + [getattr(self, "dock_" + key) for key in DOCK_NAMES]
        for window in windows:
            if window is not self and not window.isFloating():
                continue
            geo = window.frameGeometry()
            visible = any(geo.intersected(area).width() >= 60 and geo.intersected(area).height() >= 40
                          for area in geometries)
            if not visible:
                window.move(safe.x() + 32, safe.y() + 32)
            elif window is self and not self.isMaximized():
                # Avoid restoring a wider window than the active laptop monitor.
                owner = next((area for area in geometries if area.intersects(geo)), safe)
                if geo.width() > owner.width() or geo.height() > owner.height():
                    self.resize(min(self.width(), owner.width()),
                                min(self.height(), owner.height()))

    # ---------- Job list & editable context ----------
    def _maybe_save(self) -> bool:
        if not self.api.dirty:
            return True
        response = QMessageBox.question(
            self, "Ulagrede endringer", "Lagre endringene i jobblisten først?",
            QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Save,
        )
        if response == QMessageBox.StandardButton.Cancel:
            return False
        if response == QMessageBox.StandardButton.Save:
            return self._save()
        return True

    def _open_dialog(self):
        if not self._maybe_save():
            return
        start = str(self.config.value("qt/last_job_list", "") or "")
        path, _ = QFileDialog.getOpenFileName(self, "Åpne jobbliste", start, "DWM-jobblister (*.n5jobs);;Alle filer (*)")
        if path:
            self._open_path(path)

    def open_job_list(self, path: str):
        self._open_path(path)

    def _open_path(self, path: str):
        try:
            self.api.open_job_list(path)
        except Exception as exc:
            QMessageBox.critical(self, "Jobbliste", str(exc))
            return
        self._active_id = self.api.workspace().active_job_id
        self._remember_joblist(path)
        self._render_key = None
        self._job_log_selected_job = None
        self._job_log_last_options = ()
        self._a8_run_context = None
        self._a8_live_job = None
        self._append_log(f"Åpnet jobbliste: {path}")
        self._refresh(force=True)

    def _new_list(self):
        if not self._maybe_save():
            return
        try:
            self.api.new_job_list()
        except Exception as exc:
            self._error(exc)
            return
        self._active_id = None
        self._render_key = None
        self._a8_run_context = None
        self._a8_live_job = None
        self.config.setValue("qt/skip_auto_reopen", True)
        self.config.setValue("qt/last_job_list", "")
        self._refresh_recent_menu()
        self._refresh(force=True)

    def _save(self) -> bool:
        if not self.api.workspace().job_list_path:
            return self._save_as()
        try:
            output = self.api.save_job_list()
        except Exception as exc:
            self._error(exc)
            return False
        self._remember_joblist(str(output))
        self.statusBar().showMessage("Jobbliste lagret", 4000)
        self._refresh(force=True)
        return True

    def _save_as(self) -> bool:
        start = self.api.workspace().job_list_path or str(self.config.value("qt/last_job_list", "") or "")
        path, _ = QFileDialog.getSaveFileName(self, "Lagre jobbliste som", start, "DWM-jobbliste (*.n5jobs)")
        if not path:
            return False
        try:
            output = self.api.save_job_list(path)
        except Exception as exc:
            self._error(exc)
            return False
        self._remember_joblist(str(output))
        self._refresh(force=True)
        return True

    # ---------- a10: a Work job is independent of the job list ----------
    def _a10_recover_work_job(self):
        if self._worker is not None or self.api.running:
            QMessageBox.warning(self, "Jobb kjører", "Avslutt kjøringen før gjenoppretting.")
            return
        selected = QFileDialog.getExistingDirectory(
            self, "Åpne jobb fra DWM-arbeidsområde (mappen med job.json)",
            str(self.config.value("qt/last_recover_work_dir", "") or self.config.value("qt/last_work_dir", "") or ""),
        )
        if not selected:
            return
        try:
            view = self.api.recover_job_from_work(selected)
        except Exception as exc:
            self._error(exc)
            return
        self.config.setValue("qt/last_recover_work_dir", selected)
        self._active_id = view.job_id
        self._render_key = None
        self._refresh(force=True)
        QMessageBox.information(
            self, "Jobb gjenopprettet",
            f"{view.job_id} er hentet fra:\n{selected}\n\n"
            "Jobben er rekonstruert fra Work, uten den opprinnelige jobblisten. "
            "Velg «Lagre jobbliste» for å bevare den nye referansen. "
            "Ingen filer i Work ble flyttet eller slettet.",
        )

    def _a10_migrate_work_job(self):
        if self._worker is not None or self.api.running:
            QMessageBox.warning(self, "Jobb kjører", "Avslutt kjøringen før lagring i Work.")
            return
        if not self._active_id:
            QMessageBox.information(self, "Ingen jobb", "Velg først en jobb i jobblisten.")
            return
        try:
            info = self.api.work_job_info(self._active_id)
        except Exception as exc:
            self._error(exc)
            return
        if info["work_is_authoritative"]:
            QMessageBox.information(
                self, "Jobbdata i Work",
                "Jobbens autoritative data ligger allerede i Work:\n\n"
                + str(info["work_manifest"])
                + "\n\nVarig jobb-ID: " + str(info["job_uid"]),
            )
            return
        try:
            # No files are created by this read-only inspection.
            current = self.api.preflight_job(self._active_id)
        except Exception as exc:
            self._error(exc)
            return
        if current.actions:
            QMessageBox.information(
                self, "Work må klargjøres",
                "Work mangler godkjente mapper. Bruk «Kontroller / klargjør» "
                "og godkjenn mappeopprettelsen først.",
            )
            return
        if current.errors:
            QMessageBox.warning(
                self, "Work-kontroll", "Jobbdata kan ikke lagres i Work ennå:\n\n"
                + "\n".join(issue.message for issue in current.errors),
            )
            return
        answer = QMessageBox.question(
            self, "Ta i bruk Work som jobblager?",
            "DWM lagrer nå full jobbdefinisjon, status og historikk i eksisterende, "
            "godkjent Work-mappe. Etterpå inneholder jobblisten bare en referanse "
            "og sist kjent status. Ingen eldre filer slettes. Vil du fortsette?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            path = self.api.migrate_job_to_work(self._active_id)
        except Exception as exc:
            self._error(exc)
            return
        self._refresh(force=True)
        QMessageBox.information(
            self, "Jobbdata lagret i Work",
            f"Autoritativ jobbdefinisjon:\n{path}\n\n"
            "Lagre jobblisten for å oppdatere indeksreferansen.",
        )

    def _a12_toggle_job_rule(self):
        """Temporarily show the original Work-output rule editor, not a new setting."""
        self._a12_job_rule_visible = not self._a12_job_rule_visible
        self.job_rule_box.setVisible(self._a12_job_rule_visible)
        self.job_rule_toggle.setText("Regel ▾" if self._a12_job_rule_visible else "Regel ▸")
        self.config.setValue("qt/a12_job_rule_visible", self._a12_job_rule_visible)
        if self._a12_job_rule_visible:
            # Give the editor space without hiding the first job row.
            QTimer.singleShot(0, self._a12_balance_left_docks)

    def _a12_balance_left_docks(self):
        """Protect the job table when Qt restores a cramped old dock ratio."""
        if self.dock_jobs.isFloating() or self.dock_workflow.isFloating():
            return
        if not (self.dock_jobs.isVisible() and self.dock_workflow.isVisible()):
            return
        if (self.dockWidgetArea(self.dock_jobs) != Qt.DockWidgetArea.LeftDockWidgetArea
                or self.dockWidgetArea(self.dock_workflow) != Qt.DockWidgetArea.LeftDockWidgetArea):
            return
        available = self.dock_jobs.height() + self.dock_workflow.height()
        if available <= 0:
            return
        # The rule editor requires more height when explicitly expanded.
        minimum_job = 292 if self._a12_job_rule_visible else 228
        wanted = max(minimum_job, int(available * 0.43))
        if wanted >= available - 255:
            wanted = max(0, available - 255)
        if wanted > 0:
            self.resizeDocks(
                [self.dock_jobs, self.dock_workflow],
                [wanted, available - wanted], Qt.Orientation.Vertical,
            )

    def _apply_job_output_rule(self):
        """Preview changes to Work paths and save rule only with consent."""
        if self._worker is not None or self.api.running:
            QMessageBox.information(self, "Jobbliste-regel", "Avslutt kjøringen før du endrer Work-regelen.")
            return
        proposed = self.job_output_rule.text().strip()
        current = self.api.output_subfolder_rule
        if proposed == current:
            self.statusBar().showMessage("Jobblistens Work-regel er uendret", 3000)
            return
        try:
            preview = self.api.preview_output_subfolder_rule(proposed)
        except Exception as exc:
            self._error(exc)
            return
        changed = [item for item in preview if item[1] != item[2]]
        if changed:
            rows = [f"{job_id}:\n  Fra: {before}\n  Til:  {after}"
                    for job_id, before, after in changed[:5]]
            more = f"\n… og {len(changed) - 5} andre jobber" if len(changed) > 5 else ""
            answer = QMessageBox.question(
                self, "Endre jobblistens Work-regel",
                "Ny regel vil endre hvor DWM forventer å finne resultater:\n\n"
                + "\n\n".join(rows) + more
                + "\n\nIngen eksisterende filer flyttes, kopieres eller slettes. "
                  "Manglende mapper blir først foreslått ved klargjøring.\n\n"
                  "Vil du bruke denne regelen?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                return
        try:
            self.api.set_output_subfolder_rule(proposed, confirm_changes=bool(changed))
        except Exception as exc:
            self._error(exc)
            return
        self._render_key = None
        self._refresh(force=True)
        self.statusBar().showMessage("Work-regel endret. Lagre jobblisten for å bevare den.", 6000)

    def _refresh_joblist_rule(self):
        """Show the persisted rule and a short effective path example."""
        rule = self.api.output_subfolder_rule
        if not self.job_output_rule.hasFocus():
            self.job_output_rule.setText(rule)
        self.job_output_rule.setEnabled(self._worker is None)
        self.job_rule_apply.setEnabled(self._worker is None)
        try:
            preview = self.api.preview_output_subfolder_rule(rule)
            if preview:
                examples = []
                for job_id, _before, after in preview[:2]:
                    components = after.replace("\\", "/").split("/")
                    short = "/".join(components[-3:]) if len(components) > 3 else after
                    examples.append(f"{job_id} → …/{short}")
                extra = f" | +{len(preview)-2}" if len(preview) > 2 else ""
                self.job_rule_preview.setText(" | ".join(examples) + extra)
                self.job_rule_preview.setToolTip("\n".join(
                    f"{job_id}: {after}" for job_id, _before, after in preview
                ))
            else:
                self.job_rule_preview.setText("Ingen jobber – regel: " + (rule or "(tom)"))
        except Exception as exc:
            self.job_rule_preview.setText("Work-regel har avvik: " + str(exc))

    def _new_job(self):
        if self._complexity == "Enkel":
            self._new_job_easy()
            return
        dialog = QDialog(self)
        dialog.setWindowTitle("Legg til Noark 5-jobb")
        # Long Windows/UNC paths must be readable before the job is created.
        # Keep the dialog resizable and inside the current screen on laptops.
        screen = self.screen()
        available_width = screen.availableGeometry().width() if screen is not None else 1200
        dialog_width = min(1100, max(360, available_width - 100))
        dialog.resize(dialog_width, 370)
        dialog.setMinimumWidth(min(720, dialog_width))
        dialog.setSizeGripEnabled(True)
        form = QFormLayout(dialog)
        # Labels above the editors give each path almost the full dialog width.
        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapAllRows)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        form.setContentsMargins(18, 18, 18, 18)
        form.setVerticalSpacing(9)
        name = QLineEdit()
        source = QLineEdit()
        work = QLineEdit()
        for editor in (source, work):
            # Full path remains accessible if it exceeds the current screen.
            editor.textChanged.connect(editor.setToolTip)
        form.addRow("Jobbnavn (valgfritt)", name)
        self._path_form_row(form, "Source – uttrekk", source)
        self._path_form_row(form, "Work – operations", work)
        form.addRow(_muted("Ingen mapper opprettes når du lagrer. DWM vil spørre om klargjøring før kjøring."))
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        form.addRow(buttons)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        if not source.text().strip():
            QMessageBox.warning(self, "Mangler Source", "Velg et Noark 5-uttrekk.")
            return
        try:
            view = self.api.create_job(
                source_extraction=source.text().strip(),
                work_operations=work.text().strip() or None,
                name=name.text().strip(),
            )
            self._active_id = view.job_id
        except Exception as exc:
            self._error(exc)
            return
        self._refresh(force=True)

    def _new_job_easy(self):
        """Two choices for beginners: real extraction and existing Work location.

        DWM proposes repository_operations / dwm / job nesting. Nothing is
        created until the separate preflight confirmation is accepted.
        """
        if self._worker is not None:
            return
        source = QFileDialog.getExistingDirectory(
            self, "1/2 – Velg Noark 5-uttrekksmappe (arkivstruktur.xml)",
            str(self.config.value("qt/last_new_source_dir", "") or ""),
        )
        if not source:
            return
        source_issues = check_extraction_folder(source, profile_id="noark5")
        if source_issues:
            QMessageBox.warning(
                self, "Feil uttrekksmappe",
                "\n\n".join(issue.message for issue in source_issues)
                + "\n\nVelg mappen med selve Noark 5-uttrekket. Ingen jobb er opprettet.",
            )
            return
        self.config.setValue("qt/last_new_source_dir", source)
        work_root = QFileDialog.getExistingDirectory(
            self, "2/2 – Velg hvor DWM skal lagre arbeidsfiler (eksisterende hovedmappe)",
            str(self.config.value("qt/last_work_dir", "") or ""),
        )
        if not work_root:
            return
        self.config.setValue("qt/last_work_dir", work_root)
        try:
            proposal = propose_work_location(
                work_root, app_subfolder=str(self.api.settings.get("app_work_subfolder", "dwm") or ""),
            )
        except ValueError as exc:
            QMessageBox.warning(self, "Ugyldig Work-valg", str(exc))
            return
        planned_base = proposal.work_operations
        answer = QMessageBox.question(
            self, "Ny jobb – kontroller plasseringene",
            f"Source – uttrekk:\n{source}\n\n"
            f"Valgt Work-mappe:\n{work_root}\n\n"
            f"Work – hovedmappe:\n{proposal.work_root}\n\n"
            f"DWM vil foreslå Work – operations:\n{planned_base}\n\n"
            "DWM flytter eller kopierer aldri uttrekket. Opprett jobb med disse "
            "forslagene? Du får godkjenne de nøyaktige nye mappene i neste steg.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            view = self.api.create_job(source_extraction=source, name=Path(source).name)
            self._active_id = view.job_id
            self.api.update_storage(view.job_id, {"work_root": str(proposal.work_root)})
        except Exception as exc:
            self._error(exc)
            return
        self._refresh(force=True)
        if self._review_preflight((view.job_id,)) is not None:
            self._refresh(force=True)
        else:
            self._append_log(f"{view.job_id}: Klargjøring utsatt. Ingen Work-mapper ble opprettet.")

    def _path_form_row(self, form, title, editor: QLineEdit, *, file=False):
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(editor, 1)
        select = QPushButton("…")
        select.setMaximumWidth(38)
        if file:
            select.clicked.connect(lambda: self._choose_file(editor))
        else:
            select.clicked.connect(lambda: self._choose_directory(editor))
        layout.addWidget(select)
        form.addRow(title, row)

    def _choose_directory(self, editor: QLineEdit):
        folder = QFileDialog.getExistingDirectory(self, "Velg mappe", editor.text())
        if folder:
            editor.setText(folder)

    def _choose_file(self, editor: QLineEdit):
        filename, _ = QFileDialog.getOpenFileName(self, "Velg fil", editor.text())
        if filename:
            editor.setText(filename)

    def _job_clicked(self, current, _previous):
        if current is None:
            return
        job_id = current.data(0, Qt.ItemDataRole.UserRole)
        if job_id and job_id != self._active_id:
            try:
                self.api.select_job(job_id)
            except DwmApiError as exc:
                self._error(exc)
                return
            self._active_id = job_id
            self._file_root = None
            self._refresh(force=True)

    # ---------- a4: job-list actions (no disk mutation) ----------
    def _job_double_clicked(self, item, _column):
        if item is not None:
            self.jobs_tree.setCurrentItem(item)
            self.pages.setCurrentIndex(0)

    def _job_context_menu(self, point):
        item = self.jobs_tree.itemAt(point)
        if item is None or self._worker is not None:
            return
        self.jobs_tree.setCurrentItem(item)
        menu = QMenu(self)
        menu.addAction("Åpne jobb", lambda: self._job_double_clicked(item, 0))
        menu.addAction("Endre navn…", self._rename_job)
        menu.addSeparator()
        menu.addAction("Flytt opp", lambda: self._move_job(-1))
        menu.addAction("Flytt ned", lambda: self._move_job(1))
        menu.addSeparator()
        menu.addAction("Fjern fra jobblisten…", self._remove_job)
        menu.exec(self.jobs_tree.viewport().mapToGlobal(point))

    def _rename_job(self):
        if not self._active_id or self._worker is not None:
            return
        try:
            current = self.api.job_details(self._active_id).job.name
        except Exception as exc:
            self._error(exc)
            return
        name, ok = QInputDialog.getText(
            self, "Endre jobbnavn", f"{self._active_id} – nytt navn:",
            QLineEdit.EchoMode.Normal, current,
        )
        if not ok or name.strip() == current:
            return
        try:
            self.api.rename_job(self._active_id, name)
        except Exception as exc:
            self._error(exc)
            return
        self._render_key = None
        self._refresh(force=True)

    def _move_job(self, direction: int):
        if not self._active_id or self._worker is not None:
            return
        try:
            self.api.move_job(self._active_id, direction)
        except Exception as exc:
            self._error(exc)
            return
        self._render_key = None
        self._refresh(force=True)

    def _remove_job(self):
        if not self._active_id or self._worker is not None:
            return
        details = self.api.job_details(self._active_id)
        answer = QMessageBox.question(
            self, "Fjern jobb fra listen?",
            f"Fjerne {details.job.job_id} – {details.job.name} fra denne jobblisten?\n\n"
            "Ingen filer eller mapper i Source, Work eller AIP blir slettet.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            workspace = self.api.remove_job(self._active_id)
        except Exception as exc:
            self._error(exc)
            return
        self._active_id = workspace.active_job_id
        self._render_key = None
        self._file_root = None
        self.file_tree.setModel(None)
        self._refresh(force=True)

    def _filter_jobs(self, text: str):
        needle = str(text or "").strip().casefold()
        workspace = self.api.workspace()
        mapping = {job.job_id: job for job in workspace.jobs}
        shown = 0
        for index in range(self.jobs_tree.topLevelItemCount()):
            item = self.jobs_tree.topLevelItem(index)
            job = mapping.get(item.data(0, Qt.ItemDataRole.UserRole))
            if job is None:
                item.setHidden(True)
                continue
            haystack = " ".join((
                job.job_id, job.name, job.status,
                str(job.source_extraction or ""),
                str(job.effective_work_operations or ""),
            )).casefold()
            visible = not needle or needle in haystack
            item.setHidden(not visible)
            shown += int(visible)
        source = workspace.job_list_path or "(ikke lagret)"
        self.joblist_label.setText(
            f"{Path(source).name} · {shown}/{len(workspace.jobs)} jobber"
        )
        self.joblist_label.setToolTip(source)

    def _update_job_actions(self):
        idle = (not self._job_controls_running
                and self._worker is None and not self.api.running)
        order = [job.job_id for job in self.api.workspace().jobs]
        selected = self._active_id in order
        self.job_add_button.setEnabled(idle)
        self.job_rename_button.setEnabled(idle and selected)
        self.job_remove_button.setEnabled(idle and selected)
        self.job_up_button.setEnabled(idle and selected and order.index(self._active_id) > 0)
        self.job_down_button.setEnabled(idle and selected and order.index(self._active_id) < len(order) - 1)
        self.rename_job_action.setEnabled(idle and selected)
        self.remove_job_action.setEnabled(idle and selected)

    def _edit_storage(self):
        if not self._active_id:
            return
        try:
            details = self.api.job_details(self._active_id)
        except Exception as exc:
            self._error(exc)
            return
        dialog = QDialog(self)
        dialog.setWindowTitle("Lagringsroller – " + self._active_id)
        dialog.resize(820, 420)
        form = QFormLayout(dialog)
        labels = {
            "source_root": "Source – hovedmappe",
            "source_tar": "Source – TAR",
            "source_unzipped": "Source – utpakket",
            "source_extraction": "Source – uttrekk",
            "work_root": "Work – hovedmappe",
            "work_content": "Work – content",
            "work_operations": "Work – repository_operations",
            "archive_root": "AIP / arkiv",
        }
        editors: dict[str, QLineEdit] = {}
        for key in STORAGE_FIELDS:
            editor = QLineEdit(details.storage.get(key, ""))
            self._path_form_row(form, labels[key], editor, file=key == "source_tar")
            editors[key] = editor
        form.addRow(_muted("Hver rolle kan ligge på forskjellig disk/UNC-sti. Ingen filer flyttes."))
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        form.addRow(buttons)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            self.api.update_storage(self._active_id, {key: editor.text().strip() for key, editor in editors.items()})
            problems = self.api.check_storage()
            if problems:
                QMessageBox.warning(self, "Lagringskontroll", "Kontroller lagring før kjøring:\n" + "\n".join(problems))
        except Exception as exc:
            self._error(exc)
            return
        self._file_root = None
        self._refresh(force=True)

    def _choose_workflow(self):
        if not self._active_id:
            return
        from app.workflow_sequences import load_workflow_sequences
        candidates = [x for x in load_workflow_sequences(settings=self.api.settings) if x.profile_id == "noark5"]
        if not candidates:
            QMessageBox.warning(self, "Arbeidsflyt", "Ingen Noark 5-profiler tilgjengelige.")
            return
        names = [f"{p.name} [{p.sequence_id}]" for p in candidates]
        selection, ok = QInputDialog.getItem(self, "Velg arbeidsflyt", "Profil:", names, 0, False)
        if not ok:
            return
        chosen = candidates[names.index(selection)]
        if self.api.job_details(self._active_id).job.status != "Klar":
            answer = QMessageBox.question(self, "Endre tidligere kjørt jobb?",
                "Arbeidsflyten erstattes, og kjørestatus må starte på nytt. Historiske resultatfiler slettes ikke. Fortsette?")
            if answer != QMessageBox.StandardButton.Yes:
                return
        try:
            self.api.set_workflow(self._active_id, chosen.operation_ids)
        except Exception as exc:
            self._error(exc)
            return
        self._refresh(force=True)

    def _toggle_checkpoint(self):
        selected = self.workflow_tree.currentItem()
        if not self._active_id or selected is None:
            return
        operation_id = selected.data(0, Qt.ItemDataRole.UserRole)
        details = self.api.job_details(self._active_id)
        current = next((op for op in details.operations if op.operation_id == operation_id), None)
        if current is None:
            return
        try:
            self.api.set_checkpoint(self._active_id, operation_id, not current.checkpoint)
        except Exception as exc:
            self._error(exc)
            return
        self._refresh(force=True)

    # ---------- Run lifecycle: never block Qt's event loop ----------
    # ---------- a9: single-operation actions (deljobber) ----------
    def _a9_selected_operation_id(self) -> str | None:
        current = self.workflow_tree.currentItem()
        if current is None:
            return None
        return current.data(0, Qt.ItemDataRole.UserRole)

    def _a9_workflow_context_menu(self, point):
        item = self.workflow_tree.itemAt(point)
        if item is None or self._worker is not None or self.api.running:
            return
        self.workflow_tree.setCurrentItem(item)
        menu = QMenu(self)
        menu.addAction("Kj\u00f8r denne deljobben...", self._a9_run_selected_subjob)
        menu.addAction("Kontroller forutsetninger", self._a9_check_selected_subjob)
        menu.addSeparator()
        menu.addAction("Vis tidligere kj\u00f8ringer", self._a9_show_selected_subjob_history)
        menu.addAction("Åpne resultater fra denne deljobben…", self._a11_open_selected_workflow_results)
        menu.addAction("\u00c5pne Work-mappe", self._open_work_dir)
        menu.exec(self.workflow_tree.viewport().mapToGlobal(point))

    def _a9_check_selected_subjob(self):
        job_id = self._active_id
        operation_id = self._a9_selected_operation_id()
        if not job_id or not operation_id:
            QMessageBox.information(self, "Deljobb", "Velg en deljobb i Arbeidsflyt-panelet.")
            return
        try:
            report = self.api.preflight_subjob(job_id, operation_id)
        except Exception as exc:
            self._error(exc)
            return
        parts = []
        if report.errors:
            parts += ["BLOKKERT: " + issue.message for issue in report.errors]
        if report.warnings:
            parts += ["AVVIK SOM M\u00c5 GODKJENNES: " + issue.message for issue in report.warnings]
        if report.actions:
            parts += ["KREVER KLARGJ\u00d8RING: " + action.path for action in report.actions]
        if not parts:
            parts = ["Deljobben er klar for selektiv kj\u00f8ring."]
        QMessageBox.information(self, "Kontroll av deljobb", "\n\n".join(parts))

    def _a9_run_selected_subjob(self):
        if self._worker is not None or self.api.running:
            return
        job_id = self._active_id
        operation_id = self._a9_selected_operation_id()
        if not job_id or not operation_id:
            QMessageBox.information(self, "Deljobb", "Velg en deljobb i Arbeidsflyt-panelet.")
            return
        details = self.api.job_details(job_id)
        if details.job.status == "Venter ved kontrollpunkt":
            QMessageBox.warning(self, "Kontrollpunkt", "Fortsett hovedjobben ved kontrollpunkt f\u00f8rst.")
            return
        operation = next((op for op in details.operations if op.operation_id == operation_id), None)
        if operation is None:
            QMessageBox.warning(self, "Deljobb", "Valgt deljobb finnes ikke lenger.")
            return
        if operation.completed:
            answer = QMessageBox.question(
                self, "Kj\u00f8r deljobb p\u00e5 nytt?",
                f"{operation.name} er registrert fullf\u00f8rt i hovedjobben. "
                "Vil du kj\u00f8re den alene p\u00e5 nytt?\n\n"
                "Hovedjobbens fremdrift endres ikke. Deljobben kan skrive nye "
                "resultatfiler til Work, men eksisterende filer slettes ikke av GUI-et.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                return
        self._a9_start_subjob_worker(job_id, operation_id, operation.completed)

    def _a9_show_selected_subjob_history(self):
        job_id = self._active_id
        operation_id = self._a9_selected_operation_id()
        if not job_id or not operation_id:
            return
        try:
            runs = [r for r in self.api.run_log_history(job_id)
                    if getattr(r, "run_kind", "workflow") == "subjob"
                    and getattr(r, "operation_id", "") == operation_id]
        except Exception as exc:
            self._error(exc)
            return
        if not runs:
            QMessageBox.information(self, "Deljobb", "Ingen separat logg er lagret for denne deljobben enn\u00e5.")
            return
        self._a8_show_job_log()
        index = self.job_run_combo.findData(runs[0].run_id)
        if index >= 0:
            self.job_run_combo.setCurrentIndex(index)
            self._a8_show_selected_run()

    def _a9_start_subjob_worker(self, job_id: str, operation_id: str,
                                allow_rerun: bool):
        approved = self._review_preflight((job_id,), operation_id=operation_id)
        if approved is None:
            return
        if not self.api.workspace().job_list_path or self.api.dirty:
            if not self._save():
                return
        issues = self.api.check_storage()
        if issues:
            QMessageBox.warning(self, "Lagringskontroll", "\n".join(issues))
            return
        self._batch_stop.clear()
        self._worker_messages = Queue()
        self._set_running_ui(True)
        self._append_log(f"Startet deljobb {operation_id} for {job_id}.")

        def run():
            try:
                ok = self.api.run_subjob(
                    job_id, operation_id, allow_rerun=allow_rerun,
                    acknowledge_warnings=job_id in approved,
                )
                if not ok:
                    self._worker_messages.put(("info", f"Deljobb {operation_id} fullf\u00f8rte ikke."))
            except Exception as exc:
                self._worker_messages.put(("error", str(exc)))
            finally:
                self._worker_messages.put(("done", f"Deljobb {operation_id}: kj\u00f8ringen er avsluttet."))

        worker = Thread(target=run, name="dwm-qt-subjob", daemon=True)
        self._worker = worker
        worker.start()

    def _a9_trace_run(self, event: str, request_id: str, *, job_id: str | None = None,
                      **details) -> None:
        """Log the decision path even if the job list was not saved yet."""
        try:
            workspace = self.api.workspace()
            current_id = job_id or self._active_id
            current = next((item for item in workspace.jobs
                            if item.job_id == current_id), None)
            values = {
                "request_id": request_id,
                "joblist": workspace.job_list_path or "(ikke lagret)",
                "job_id": current_id or "",
                "status": current.status if current else "(ikke funnet)",
                "progress": current.progress if current else None,
                "operation_index": current.current_operation if current else None,
                "operation_count": current.operation_count if current else None,
                "worker_present": self._worker is not None,
                "api_running": self.api.running,
                "request_busy": self._run_request_busy,
            }
            values.update(details)
            self._run_audit.record(event, **values)
            if not self._run_audit_announced:
                self._run_audit_announced = True
                self._append_log("Sporing av Kjør-forespørsler: " + str(self._run_audit.path))
            if self._run_audit.last_error and not self._run_audit_warning_shown:
                self._run_audit_warning_shown = True
                self._append_log("ADVARSEL: Kunne ikke skrive kjøresporing: " + self._run_audit.last_error)
        except Exception as exc:
            if not self._run_audit_warning_shown:
                self._run_audit_warning_shown = True
                self._append_log("ADVARSEL: Kjøresporing utilgjengelig: " + str(exc))

    def _run_selected(self):
        """One GUI request creates at most one worker start attempt."""
        request_id = new_request_id()
        sender = self.sender()
        source = sender.text() if sender is not None and callable(getattr(sender, "text", None)) else "Ukjent"
        job_id = self._active_id
        self._a9_trace_run("ui.run_clicked", request_id, job_id=job_id, source=source)
        if (not job_id or self._run_request_busy or self._worker is not None
                or self.api.running or self._job_controls_running):
            self._a9_trace_run("ui.run_ignored", request_id, job_id=job_id,
                               reason="no_selection_or_busy")
            return
        self._run_request_busy = True
        try:
            details = self.api.job_details(job_id)
            view = details.job
            self._a9_trace_run("ui.run_state_checked", request_id, job_id=job_id,
                               message=details.message)
            if _is_waiting_status(view.status):
                self._a9_trace_run("ui.run_blocked", request_id, job_id=job_id,
                                   reason="waiting_at_checkpoint")
                QMessageBox.information(self, "Kontrollpunkt",
                                        "Bruk Fortsett ved kontrollpunkt for denne jobben.")
                return
            reason = rerun_reason(view.status, details.message)
            allow_rerun = bool(reason)
            if allow_rerun:
                self._a9_trace_run("ui.rerun_prompt_shown", request_id, job_id=job_id,
                                   reason=reason, message=details.message)
                answer = QMessageBox.question(
                    self, "Kjøre på nytt?",
                    f"{view.job_id} har status {view.status} ("
                    f"{view.current_operation}/{view.operation_count} deljobber).\n"
                    "Start en NY kjøring? Eksisterende resultatfiler slettes ikke av GUI-et."
                )
                if answer != QMessageBox.StandardButton.Yes:
                    self._a9_trace_run("ui.rerun_prompt_answer", request_id, job_id=job_id,
                                       decision="no")
                    return
                self._a9_trace_run("ui.rerun_prompt_answer", request_id, job_id=job_id,
                                   decision="yes")
            else:
                self._a9_trace_run("ui.first_run", request_id, job_id=job_id,
                                   reason="no_previous_execution_state")
            self._start_worker([(job_id, allow_rerun, False)], request_id=request_id)
        except Exception as exc:
            self._a9_trace_run("ui.run_exception", request_id, job_id=job_id,
                               reason=type(exc).__name__)
            self._error(exc)
        finally:
            self._run_request_busy = False

    def _continue_job(self):
        if not self._active_id or self._worker is not None:
            return
        status = self.api.job_details(self._active_id).job.status
        if not _is_waiting_status(status):
            QMessageBox.information(self, "Kontrollpunkt", "Jobben venter ikke ved et kontrollpunkt.")
            return
        self._start_worker([(self._active_id, False, True)])

    def _run_ready(self):
        if self._worker is not None:
            return
        targets = []
        changed = 0
        for job in self.api.workspace().jobs:
            if job.status != "Klar":
                continue
            rerun = self.api.job_details(job.job_id).message == "Konfigurasjon endret - klar for ny kjøring"
            changed += int(rerun)
            targets.append((job.job_id, rerun, False))
        if not targets:
            QMessageBox.information(self, "Kjør klare jobber", "Ingen klare jobber å kjøre.")
            return
        answer = QMessageBox.question(self, "Kjør klare jobber",
            f"Kjør {len(targets)} klare jobber sekvensielt? "
            f"{changed} har endret konfigurasjon og vil bli kjørt på nytt. "
            "Avslutt ved første tekniske feil.")
        if answer == QMessageBox.StandardButton.Yes:
            self._start_worker(targets)

    def _open_setup(self):
        """Edit the global DWM setup, without importing any Tk GUI layer."""
        if self._worker is not None or self.api.running:
            QMessageBox.information(self, "Setup", "Avslutt kjøringen før du endrer Setup.")
            return
        from gui_qt.setup_v018_a7 import DwmSetupDialog
        dialog = DwmSetupDialog(self.api, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._append_log("Setup lagret. CLI-avhengigheter kontrolleres på nytt før neste kjøring.")
            self._refresh(force=True)

    def _prepare_selected_only(self):
        """User-invoked read-only check followed by explicit consent if needed."""
        if not self._active_id or self._worker is not None:
            return
        approved = self._review_preflight((self._active_id,))
        if approved is not None:
            self._refresh(force=True)
            QMessageBox.information(self, "Klargjøring", "Jobben er kontrollert og klar for kjøring.")

    def _change_selected_work_location(self):
        """Explicit Work selection, also available after a previous proposal."""
        if self._active_id and self._worker is None and not self.api.running:
            self._choose_work_location(self._active_id)

    def _choose_work_location(self, job_id: str) -> bool:
        """Select, preview and approve Work roles; never mkdir or change Source.

        The role update remains in-memory until the user saves the job list.
        Existing results are not moved when a user changes the Work base.
        """
        try:
            details = self.api.job_details(job_id)
        except Exception as exc:
            self._error(exc)
            return False
        previous = details.storage
        current_work = previous.get("work_root") or previous.get("work_operations") or ""
        starting = current_work if current_work and Path(current_work).is_dir() else str(
            self.config.value("qt/last_work_dir", "") or "")
        while True:
            selected = QFileDialog.getExistingDirectory(
                self, "Velg Work-hovedmappe eller repository_operations for " + job_id,
                starting,
            )
            if not selected:
                return False
            starting = selected
            self.config.setValue("qt/last_work_dir", selected)
            try:
                proposal = propose_work_location(
                    selected,
                    app_subfolder=str(self.api.settings.get("app_work_subfolder", "dwm") or ""),
                )
            except ValueError as exc:
                QMessageBox.warning(self, "Ugyldig Work-valg", str(exc))
                continue
            app_folder = str(self.api.settings.get("app_work_subfolder", "dwm") or "").strip()
            rule = str(self.api.output_subfolder_rule or "").strip()
            suffix = (app_folder + " / " if app_folder else "") + (rule or "(ingen jobbregel)")
            preview = QMessageBox(self)
            preview.setWindowTitle("Bekreft Work-plassering – " + job_id)
            preview.setIcon(QMessageBox.Icon.Question)
            preview.setText("DWM foreslår følgende lagringsroller:")
            preview.setInformativeText(
                "Valgt mappe:\n" + str(proposal.selected)
                + "\n\nWork – hovedmappe:\n" + str(proposal.work_root)
                + "\n\nWork – operations:\n" + str(proposal.work_operations)
                + "\n\nUndermapper etter gjeldende regler:\n" + suffix
                + "\n\nEksisterende Work – operations:\n"
                + (previous.get("work_operations") or "(ikke angitt)")
                + "\n\nIngen filer eller mapper opprettes, flyttes eller slettes nå. "
                  "Ny plassering må klargjøres og godkjennes før kjøring."
            )
            use = preview.addButton("Bruk denne mappen", QMessageBox.ButtonRole.AcceptRole)
            again = preview.addButton("Velg annen mappe", QMessageBox.ButtonRole.ActionRole)
            cancel = preview.addButton("Avbryt", QMessageBox.ButtonRole.RejectRole)
            preview.setDefaultButton(cancel)
            preview.exec()
            if preview.clickedButton() is again:
                continue
            if preview.clickedButton() is not use:
                return False
            changes = {
                "work_root": str(proposal.work_root),
                "work_operations": str(proposal.work_operations),
            }
            if all(previous.get(field, "") == value for field, value in changes.items()):
                return True
            try:
                self.api.update_storage(job_id, changes)
                errors = self.api.check_storage()
                if errors:
                    self.api.update_storage(job_id, {
                        "work_root": previous.get("work_root", ""),
                        "work_operations": previous.get("work_operations", ""),
                    })
                    QMessageBox.warning(self, "Work-konflikt", "\n".join(errors))
                    continue
            except Exception as exc:
                try:
                    self.api.update_storage(job_id, {
                        "work_root": previous.get("work_root", ""),
                        "work_operations": previous.get("work_operations", ""),
                    })
                except Exception:
                    pass
                self._error(exc)
                return False
            self._file_root = None
            self._open_report_root = None
            self._job_log_selected_job = None
            self._refresh(force=True)
            self.statusBar().showMessage(
                "Work-plassering valgt. Kontroller / klargjør og lagre jobblisten.", 7000,
            )
            return True

    def _review_preflight(self, job_ids: tuple[str, ...], *,
                          operation_id: str | None = None) -> set[str] | None:
        """Read-only checks, with explicit consent for every Work mutation.

        The user may choose a different Work directory *inside* the approval
        flow. Cancel never starts execution or creates folders.
        """
        approved_warnings: set[str] = set()
        global_errors = self.api.check_storage()
        if global_errors:
            QMessageBox.warning(self, "Lagringskontroll", "\n".join(global_errors))
            return None
        def read_report(job_id: str):
            if operation_id:
                return self.api.preflight_subjob(job_id, operation_id)
            return self.api.preflight_job(job_id)

        for job_id in job_ids:
            for _attempt in range(12):
                try:
                    report = read_report(job_id)
                except Exception as exc:
                    self._error(exc)
                    return None
                if any(issue.code in {"WORK_NOT_CONFIGURED", "WORK_ROOT_AMBIGUOUS"}
                       for issue in report.errors):
                    if not self._choose_work_location(job_id):
                        return None
                    continue
                if report.errors:
                    arkade_error = any(issue.code.startswith("ARKADE5_CLI_") for issue in report.errors)
                    response = QMessageBox.question(
                        self, "Kontroll før kjøring – " + job_id,
                        "Kjøring er blokkert:\n\n"
                        + "\n".join("• " + issue.message for issue in report.errors)
                        + "\n\n"
                        + ("Åpne Setup for å rette CLI?" if arkade_error
                           else "Åpne lagringsrollene for å rette valgene?"),
                        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                        QMessageBox.StandardButton.Yes,
                    )
                    if response == QMessageBox.StandardButton.Yes:
                        self._active_id = job_id
                        if arkade_error:
                            self._open_setup()
                        else:
                            self._edit_storage()
                    return None  # Recheck explicitly; never auto-run after edits.
                if report.actions or report.warnings:
                    details = []
                    if report.warnings:
                        details.extend("AVVIK: " + issue.message for issue in report.warnings)
                    if report.actions:
                        details.extend("GODKJENN: " + action.description + "\n  " + action.path
                                       for action in report.actions)
                    dialog = QMessageBox(self)
                    dialog.setIcon(QMessageBox.Icon.Question)
                    dialog.setWindowTitle("Godkjenn klargjøring – " + job_id)
                    dialog.setText("DWM har funnet forhold som krever ditt samtykke.")
                    dialog.setInformativeText(
                        "\n\n".join(details)
                        + "\n\nSource endres aldri; eksisterende data flyttes eller slettes ikke."
                    )
                    approve = dialog.addButton("Godkjenn og klargjør", QMessageBox.ButtonRole.AcceptRole)
                    choose = dialog.addButton("Velg annen Work-mappe", QMessageBox.ButtonRole.ActionRole)
                    cancel = dialog.addButton("Avbryt", QMessageBox.ButtonRole.RejectRole)
                    dialog.setDefaultButton(cancel)
                    dialog.exec()
                    if dialog.clickedButton() is choose:
                        if not self._choose_work_location(job_id):
                            return None
                        continue  # New proposal must always go through preflight again.
                    if dialog.clickedButton() is not approve:
                        self._append_log(f"{job_id}: Klargjøring avbrutt uten mappeopprettelse.")
                        return None
                    approved_warnings.add(job_id)
                    if report.actions:
                        try:
                            after = self.api.provision_preflight(
                                job_id, approved_report=report, consent=True,
                                operation_id=operation_id,
                            )
                        except Exception as exc:
                            self._error(exc)
                            return None
                        if after.errors or after.actions:
                            QMessageBox.warning(
                                self, "Klargjøring", "Fortsatt uavklarte forhold. Kontroller på nytt.",
                            )
                            return None
                        self._append_log(f"{job_id}: Godkjente Work/AIP-mapper er klargjort.")
                try:
                    final = read_report(job_id)
                except Exception as exc:
                    self._error(exc)
                    return None
                if final.errors or final.actions:
                    QMessageBox.warning(self, "Klargjøring", "Lagringsforholdene er endret. Kontroller på nytt.")
                    return None
                if final.warnings and job_id not in approved_warnings:
                    QMessageBox.warning(self, "Klargjøring", "Avvik må godkjennes før kjøring.")
                    return None
                break
            else:
                QMessageBox.warning(self, "Klargjøring", "For mange endringer. Start kontrollen på nytt.")
                return None
        return approved_warnings

    def _start_worker(self, jobs: list[tuple[str, bool, bool]], *,
                      request_id: str | None = None):
        request_id = request_id or new_request_id()
        first_job = jobs[0][0] if jobs else None
        self._a9_trace_run("ui.preflight_started", request_id, job_id=first_job,
                           run_count=len(jobs))
        warning_approvals = self._review_preflight(tuple(job_id for job_id, _rerun, _cont in jobs))
        if warning_approvals is None:
            self._a9_trace_run("ui.preflight_cancelled", request_id, job_id=first_job)
            return
        self._a9_trace_run("ui.preflight_approved", request_id, job_id=first_job)
        if not self.api.workspace().job_list_path or self.api.dirty:
            if not self._save():
                self._a9_trace_run("ui.save_cancelled", request_id, job_id=first_job)
                return
        issues = self.api.check_storage()
        if issues:
            self._a9_trace_run("ui.storage_blocked", request_id, job_id=first_job,
                               reason="; ".join(issues)[:800])
            QMessageBox.warning(self, "Lagringskontroll", "\n".join(issues))
            return
        # A modal preflight/save may have let the user change the job list.
        # Never execute a different job under an earlier approval.
        present = {job.job_id for job in self.api.workspace().jobs}
        if any(job_id not in present for job_id, _rerun, _cont in jobs):
            self._a9_trace_run("ui.selection_changed", request_id, job_id=first_job,
                               reason="job_not_in_current_list")
            QMessageBox.warning(self, "Jobbliste endret",
                                "Jobblisten er endret under klargjøring. Start kontrollen på nytt.")
            return
        self._batch_stop.clear()
        self._worker_messages = Queue()
        self._set_running_ui(True)
        self._append_log(f"Starter kjøring av {len(jobs)} jobb(er). Forespørsel: {request_id}")
        self._a9_trace_run("ui.worker_queued", request_id, job_id=first_job,
                           run_count=len(jobs))
        # Freeze the job-list identity before entering the worker thread.
        joblist = self.api.workspace().job_list_path or "(ikke lagret)"
        audit = self._run_audit

        def run():
            audit.record("worker.started", request_id=request_id,
                         joblist=joblist, job_id=first_job or "", run_count=len(jobs))
            try:
                for job_id, allow_rerun, continuing in jobs:
                    if self._batch_stop.is_set():
                        audit.record("worker.cancelled", request_id=request_id,
                                     joblist=joblist, job_id=job_id)
                        break
                    self._worker_messages.put(("selected", job_id))
                    audit.record("api.run_job_called", request_id=request_id,
                                 joblist=joblist, job_id=job_id,
                                 reason="rerun" if allow_rerun else "continue" if continuing else "first_run")
                    ok = self.api.run_job(
                        job_id, allow_rerun=allow_rerun,
                        continue_waiting=continuing,
                        acknowledge_warnings=job_id in warning_approvals,
                    )
                    state = next((j for j in self.api.workspace().jobs if j.job_id == job_id), None)
                    audit.record("api.run_job_returned", request_id=request_id,
                                 joblist=joblist, job_id=job_id, result=bool(ok),
                                 status=state.status if state else "unknown")
                    if not ok:
                        self._worker_messages.put(("info", f"{job_id}: Stoppet ved feil/avbrudd."))
                        break
            except Exception as exc:
                audit.record("api.run_job_exception", request_id=request_id,
                             joblist=joblist, job_id=job_id if jobs else "",
                             reason=type(exc).__name__)
                self._worker_messages.put(("error", str(exc)))
            finally:
                audit.record("worker.finished", request_id=request_id,
                             joblist=joblist, job_id=first_job or "")
                self._worker_messages.put(("done", "Kjøringen er avsluttet."))

        self._worker = Thread(target=run, name="dwm-qt-runner", daemon=True)
        self._worker.start()

    def _request_stop(self):
        if self._worker is not None:
            self._batch_stop.set()
            self.api.request_cancel()
            self._append_log("Stopp forespurt. Gjeldende operasjon må selv støtte avbrudd.")

    def _set_running_ui(self, running: bool):
        self._job_controls_running = bool(running)
        self._recent_menu.setEnabled(not running)
        for action in (self.open_action, self.new_list_action, self.save_action,
                       self.save_as_action, self.new_job_action, self.run_action,
                       self.ready_action, self.continue_action, self.preflight_action,
                       self.setup_action, self.recover_work_job_action,
                       self.migrate_work_job_action):
            action.setEnabled(not running)
        self.stop_action.setEnabled(running)
        self.overview_run.setEnabled(not running)
        self.overview_continue.setEnabled(not running)
        self.storage_edit_button.setEnabled(not running)
        self.storage_prepare_button.setEnabled(not running)
        self.storage_change_work.setEnabled(not running)
        self.overview_change_work.setEnabled(not running)
        self.overview_preflight.setEnabled(not running and bool(self._active_id))
        self.workflow_preset_button.setEnabled(not running)
        self.workflow_checkpoint_button.setEnabled(not running)
        self.workflow_tree.setEnabled(not running)
        self.subjob_run_button.setEnabled(not running)
        self.subjob_check_button.setEnabled(not running)
        self.subjob_run_action.setEnabled(not running)
        self.subjob_check_action.setEnabled(not running)
        self.jobs_tree.setEnabled(not running)
        self.job_output_rule.setEnabled(not running)
        self.job_rule_apply.setEnabled(not running)
        self._update_job_actions()

    # ---------- A8: durable job history and independent dock windows ----------
    def _a8_show_job_log(self):
        viewer = self._detached_log_window
        if viewer is not None:
            # A real Qt.Window participates in the normal OS Z-order.
            # Raise it only when the user explicitly opens/shows the log.
            viewer.show()
            viewer.raise_()
        else:
            self._a12_show_log_tab()
        self._a8_refresh_job_log(force=True)

    def _a8_float_job_log(self):
        """Toggle log dock vs an independent, normally stacked Qt.Window.

        Do not mutate a QDockWidget's native window flags during docking:
        Qt owns its transitions, and doing so can crash on Windows.
        """
        if self._detached_log_window is not None:
            self._a9_redock_job_log()
            return
        self._a8_refresh_job_log(force=True)
        viewer = DetachedJobLogWindow()  # no QMainWindow parent/owner
        viewer.setStyleSheet(STYLE)
        viewer.redockRequested.connect(self._a9_redock_job_log)
        viewer.runSelected.connect(self._a9_detached_run_selected)
        viewer.refreshRequested.connect(lambda: self._a8_refresh_job_log(force=True))
        viewer.followChanged.connect(self.log_follow.setChecked)
        self._detached_log_window = viewer
        self._a9_sync_detached_log_follow()
        self._a9_sync_detached_log_choices()
        self._a9_sync_detached_log_text()
        # Hide just the log TAB; Kjoereloep remains available in the dock.
        if hasattr(self, "activity_tabs"):
            self._a12_reconcile_activity_tabs()
        else:
            self.dock_log.hide()
            self.dock_log.toggleViewAction().setEnabled(False)
        geometry = self.config.value("qt/a9_independent_log_geometry")
        if geometry:
            try:
                viewer.restoreGeometry(geometry)
            except (TypeError, ValueError):
                pass
        self._a9_recover_detached_log_geometry()
        viewer.show()
        viewer.raise_()
        viewer.activateWindow()
        self._a8_update_log_window_buttons()

    def _a9_redock_job_log(self):
        viewer = self._detached_log_window
        if viewer is None:
            return
        self.config.setValue("qt/a9_independent_log_geometry", viewer.saveGeometry())
        # Clear reference *before* destroying the window: signal callbacks
        # must never create a second viewer or recursively redock.
        self._detached_log_window = None
        viewer.hide()
        viewer.deleteLater()
        if hasattr(self, "activity_tabs"):
            self._a12_show_log_tab()
        else:
            self.dock_log.toggleViewAction().setEnabled(True)
            self.dock_log.show()
            self.dock_log.raise_()
        self._a8_update_log_window_buttons()
        self._a8_refresh_job_log(force=True)

    def _a12_sync_activity_menu(self, _event=None) -> None:
        """Keep Vis menu checks in sync with real tab/window visibility.

        Qt checks the native QDockWidget action for 'Aktivitet' automatically.
        The submenu named 'Aktivitetsfane' marks only the CURRENT visible tab;
        independent windows are controlled by the separate open/fest actions.
        Never use a menu action's temporary triggered/unchecked state as truth.
        """
        if not hasattr(self, "show_job_log_action"):
            return
        dock_visible = self.dock_log.isVisible()
        index = self.activity_tabs.currentIndex()
        log_visible = (
            dock_visible and index == 0 and self.activity_tabs.isTabVisible(0)
        )
        run_visible = (
            dock_visible and index == 1 and self.activity_tabs.isTabVisible(1)
        )
        # A detached ordinary Window is not a tab in Aktivitets-panelet.
        # Therefore a detached log and an active run tab never both receive
        # checkmarks in the *tab selection* submenu.
        self.show_job_log_action.setChecked(log_visible)
        self.show_run_tab_action.setChecked(run_visible)

    def _a12_detach_active_tab(self) -> None:
        """Header detach is routed to the active tab; no native Qt float."""
        if self.activity_tabs.currentIndex() == 1:
            self._a9_float_run()
        else:
            self._a8_float_job_log()

    def _a12_reconcile_activity_tabs(self) -> None:
        """Show only tabs that do not have independent normal windows."""
        self.activity_tabs.setTabVisible(0, self._detached_log_window is None)
        self.activity_tabs.setTabVisible(1, self._detached_run_window is None)
        self.dock_run.hide()
        if not any(self.activity_tabs.isTabVisible(i) for i in (0, 1)):
            self.dock_log.hide()

    def _a12_activate_activity_tab(self, index: int) -> None:
        viewer = (self._detached_log_window if index == 0
                  else self._detached_run_window)
        if viewer is not None:
            viewer.show()
            viewer.raise_()
            if hasattr(self, "_a12_sync_activity_menu"):
                self._a12_sync_activity_menu()
            return
        self.activity_tabs.setTabVisible(index, True)
        self.dock_log.show()
        self.activity_tabs.setCurrentIndex(index)
        self.dock_log.raise_()
        # Selecting an ALREADY active checkable menu item briefly toggles it
        # off. QTabWidget emits no currentChanged in that case, so explicitly
        # restore the checked state even if the dock/tab didn't change.
        if hasattr(self, "_a12_sync_activity_menu"):
            self._a12_sync_activity_menu()

    def _a12_show_run_tab(self) -> None:
        self._a12_activate_activity_tab(1)

    def _a12_show_log_tab(self) -> None:
        self._a12_activate_activity_tab(0)

    def _a12_activity_target_height(self) -> int:
        """Different usable heights for log text and nine-line run progress."""
        height = self.height()
        if self.activity_tabs.currentIndex() == 1:
            desired = max(355, min(460, int(height * 0.39)))
        else:
            desired = max(240, min(315, int(height * 0.28)))
        # A small laptop window must retain a usable central workspace.
        return min(desired, max(175, height - 360))

    def _a12_activity_tab_changed(self, index: int) -> None:
        """Make a newly selected Kjoereloep tab readable without manual drag."""
        if index == 1:
            QTimer.singleShot(0, self._a12_ensure_activity_height)

    def _a12_ensure_activity_height(self) -> None:
        """Only expand a cramped activity area; preserve manual sizes."""
        if not self.dock_log.isVisible() or self.dock_log.isFloating():
            return
        if self.dockWidgetArea(self.dock_log) != Qt.DockWidgetArea.BottomDockWidgetArea:
            return
        target = self._a12_activity_target_height()
        if self.dock_log.height() < target - 20:
            self.resizeDocks([self.dock_log], [target], Qt.Orientation.Vertical)
        # The internal history/status splitter sometimes inherits tiny sizes
        # from the formerly hidden tab. Size it only once, not after user drags.
        if (self.activity_tabs.currentIndex() == 1
                and not self._a12_run_splitter_initialized):
            QTimer.singleShot(0, self._a12_size_initial_run_details)

    def _a12_size_initial_run_details(self) -> None:
        """Give saved nine-operation status readable space beside run history."""
        if self.activity_tabs.currentIndex() != 1:
            return
        available = self.run_history_splitter.height()
        if available >= 185:
            upper = max(80, int(available * 0.40))
            self.run_history_splitter.setSizes([upper, available - upper])
            self._a12_run_splitter_initialized = True

    def _a12_restore_cramped_system_log(self) -> None:
        """Repair only a previously saved tiny Systemlogg on a large screen."""
        if (self.width() >= 1050 and self.dock_system.isVisible()
                and 0 < self.dock_system.width() < 225):
            self._a12_arrange_system_log()

    def _a12_system_visibility_changed(self, visible: bool) -> None:
        """Opening Systemlogg must not collapse the Kjoereloep view."""
        if not visible:
            self._a12_system_split_active = False
            return
        QTimer.singleShot(0, self._a12_arrange_system_log)

    def _a12_arrange_system_log(self) -> None:
        """Split only the bottom activity/system docks, not custom areas."""
        if (not self.dock_system.isVisible() or self.dock_system.isFloating()
                or not self.dock_log.isVisible() or self.dock_log.isFloating()):
            return
        if (self.dockWidgetArea(self.dock_log) != Qt.DockWidgetArea.BottomDockWidgetArea
                or self.dockWidgetArea(self.dock_system) != Qt.DockWidgetArea.BottomDockWidgetArea):
            return
        if not self._a12_system_split_active:
            self._a12_system_split_active = True
            # Native horizontal split of two DIFFERENT docks is safe; never
            # tabify docks or float a grouped dock on Windows.
            self.splitDockWidget(self.dock_log, self.dock_system, Qt.Orientation.Horizontal)
        content_width = max(
            self.dock_log.width() + self.dock_system.width(),
            self.width() - self.dock_jobs.width() - 28,
        )
        self.resizeDocks(
            [self.dock_log, self.dock_system],
            [int(content_width * 0.70), int(content_width * 0.30)],
            Qt.Orientation.Horizontal,
        )
        self._a12_ensure_activity_height()
        # Let Qt finish the horizontal split before checking vertical sizes.
        QTimer.singleShot(0, self._a12_ensure_activity_height)

    def _a12_balance_workspace(self) -> None:
        """Readable left panels and one shared activity dock for both tabs."""
        if (self.dock_jobs.isVisible() and self.dock_workflow.isVisible()
                and not self.dock_jobs.isFloating()
                and not self.dock_workflow.isFloating()
                and self.dockWidgetArea(self.dock_jobs) == Qt.DockWidgetArea.LeftDockWidgetArea
                and self.dockWidgetArea(self.dock_workflow) == Qt.DockWidgetArea.LeftDockWidgetArea):
            self.resizeDocks(
                [self.dock_jobs, self.dock_workflow], [350, 350],
                Qt.Orientation.Horizontal,
            )
            self._a12_balance_left_docks()
        if (self.dock_log.isVisible() and not self.dock_log.isFloating()
                and self.dockWidgetArea(self.dock_log) == Qt.DockWidgetArea.BottomDockWidgetArea):
            self.resizeDocks(
                [self.dock_log], [self._a12_activity_target_height()],
                Qt.Orientation.Vertical,
            )

    def _a9_float_run(self):
        """Toggle Kjøreløp between a dock and a normal Windows window."""
        if self._detached_run_window is not None:
            self._a9_redock_run()
            return
        viewer = DetachedRunWindow()  # independent Qt.Window, not Qt.Tool
        viewer.setStyleSheet(STYLE)
        viewer.redockRequested.connect(self._a9_redock_run)
        if hasattr(viewer, "historyLogRequested"):
            viewer.historyLogRequested.connect(self._a11_open_history_log)
        if hasattr(viewer, "historyResultsRequested"):
            viewer.historyResultsRequested.connect(self._a11_open_history_results)
        self._detached_run_window = viewer
        self._a9_sync_detached_run()
        if hasattr(self, "activity_tabs"):
            self._a12_reconcile_activity_tabs()
        else:
            self.dock_run.hide()
            self.dock_run.toggleViewAction().setEnabled(False)
        geometry = self.config.value("qt/a9_independent_run_geometry")
        if geometry:
            try:
                viewer.restoreGeometry(geometry)
            except (TypeError, ValueError):
                pass
        self._a9_recover_detached_run_geometry()
        viewer.show()
        viewer.raise_()
        viewer.activateWindow()
        self._a9_update_run_window_buttons()

    def _a9_redock_run(self):
        viewer = self._detached_run_window
        if viewer is None:
            return
        self.config.setValue("qt/a9_independent_run_geometry", viewer.saveGeometry())
        self._detached_run_window = None
        viewer.hide()
        viewer.deleteLater()
        if hasattr(self, "activity_tabs"):
            self._a12_show_run_tab()
        else:
            self.dock_run.toggleViewAction().setEnabled(True)
            self.dock_run.show()
            self.dock_run.raise_()
        self._a9_update_run_window_buttons()

    def _a9_sync_detached_run(self):
        viewer = self._detached_run_window
        if viewer is not None:
            viewer.set_run_data(
                self.run_summary.text(),
                self.run_progress_bar.value(),
                self.run_events.toPlainText(),
            )
            if hasattr(viewer, "set_history"):
                viewer.set_history(self._a11_history_display_rows(),
                                   self._a11_selected_history_key())

    def _a9_recover_detached_run_geometry(self):
        viewer = self._detached_run_window
        if viewer is None:
            return
        screens = QApplication.screens()
        if not screens:
            return
        geometries = [screen.availableGeometry() for screen in screens]
        frame = viewer.frameGeometry()
        if not any(frame.intersected(area).width() >= 60
                   and frame.intersected(area).height() >= 40 for area in geometries):
            safe = screens[0].availableGeometry()
            viewer.move(safe.x() + 36, safe.y() + 36)

    def _a9_update_run_window_buttons(self):
        detached = self._detached_run_window is not None
        button = getattr(self, "run_window_button", None)
        if button is not None:
            button.setText("Fest til hovedvindu" if detached else "Eget vindu")
        action = getattr(self, "float_run_action", None)
        if action is not None:
            action.setText(
                "Fest kjøreløp til hovedvindu" if detached
                else "Åpne kjøreløp i eget vindu"
            )

    def _a9_normalize_log_dock(self):
        """Restore old saved Qt.Tool log/run layouts to safe docked state."""
        for dock in (self.dock_log, self.dock_run):
            if dock.isFloating():
                dock.setFloating(False)

    def _a9_sync_detached_log_choices(self):
        viewer = self._detached_log_window
        if viewer is None:
            return
        source = self.job_run_combo
        choices = [(source.itemText(i), str(source.itemData(i)))
                   for i in range(source.count())]
        viewer.set_runs(choices, source.currentData())

    def _a9_sync_detached_log_text(self):
        viewer = self._detached_log_window
        if viewer is not None:
            viewer.set_log_text(self.job_log_text.toPlainText())

    def _a9_sync_detached_log_follow(self, _checked=None):
        viewer = self._detached_log_window
        if viewer is not None:
            viewer.set_follow(self.log_follow.isChecked())

    def _a9_detached_run_selected(self, run_id: str):
        index = self.job_run_combo.findData(run_id)
        if index >= 0:
            if index == self.job_run_combo.currentIndex():
                self._a8_show_selected_run()
            else:
                # currentIndexChanged is already connected to show the run.
                self.job_run_combo.setCurrentIndex(index)

    def _a9_recover_detached_log_geometry(self):
        viewer = self._detached_log_window
        if viewer is None:
            return
        screens = QApplication.screens()
        if not screens:
            return
        geometries = [screen.availableGeometry() for screen in screens]
        frame = viewer.frameGeometry()
        if not any(frame.intersected(area).width() >= 60
                   and frame.intersected(area).height() >= 40 for area in geometries):
            safe = screens[0].availableGeometry()
            viewer.move(safe.x() + 36, safe.y() + 36)

    def _a8_update_log_window_buttons(self):
        floating = self._detached_log_window is not None
        button = getattr(self, "log_window_button", None)
        if button is not None:
            button.setText("Fest til hovedvindu" if floating else "Eget vindu")
        action = getattr(self, "float_job_log_action", None)
        if action is not None:
            action.setText(
                "Fest kjørelogg til hovedvindu" if floating
                else "Åpne kjørelogg i eget vindu"
            )

    def _a8_dock_floating(self, name: str, floating: bool):
        # Never touch a dock synchronously inside Qt's reparenting signal.
        # Restore old native floating log/run docks after the event returns.
        if name in {"log", "run"} and floating:
            QTimer.singleShot(0, lambda n=name: self._a9_correct_native_float(n))
        elif floating:
            QTimer.singleShot(0, lambda n=name: self._a8_finish_floating(n))

    def _a9_correct_native_float(self, name: str):
        dock = getattr(self, "dock_" + name, None)
        if dock is None or not dock.isFloating():
            return
        dock.setFloating(False)
        if name == "log" and self._detached_log_window is None:
            self._a8_float_job_log()
        elif name == "run" and self._detached_run_window is None:
            self._a9_float_run()

    def _a8_finish_floating(self, name: str):
        dock = getattr(self, "dock_" + name, None)
        if dock is None or not dock.isFloating():
            return
        if name not in self._a8_floating_once:
            self._a8_floating_once.add(name)
            if dock.width() < 680 or dock.height() < 380:
                dock.resize(940, 540)
        self._recover_windows()

    # ---------- a11: real execution history per deljobb; a13 navigation ----------
    @staticmethod
    def _a11_execution_label(run):
        if run.execution_status == "blocked":
            return "Blokkert"
        if run.execution_status == "exception":
            return "Teknisk feil"
        if run.execution_ok is True:
            return "Gjennomført"
        if run.execution_ok is False:
            return "Avvik / feil"
        return "Ukjent"

    def _a11_selected_history_key(self):
        if not hasattr(self, "run_history_tree"):
            return None
        item = self.run_history_tree.currentItem()
        return str(item.data(0, Qt.ItemDataRole.UserRole)) if item else None

    def _a11_history_display_rows(self):
        def shown_time(stamp):
            try:
                # Stored UTC timestamps must be displayed in the operator's
                # local Windows timezone; do not silently label UTC as local.
                return datetime.fromisoformat(stamp).astimezone().strftime("%Y-%m-%d %H:%M:%S")
            except (TypeError, ValueError):
                return str(stamp).replace("T", " ")[:19]
        return [(
            shown_time(item.recorded_at),
            item.operation_name,
            "Enkelt" if item.run_kind == "subjob" else "Arbeidsflyt",
            self._a11_execution_label(item),
            str(len(item.work_results)), item.run_id, item.operation_id,
        ) for item in self._a11_history_cache]

    def _a11_refresh_operation_history(self):
        if not hasattr(self, "run_history_tree"):
            return  # compatibility with old a8 headless GUI source tests
        selected = self._a11_selected_history_key()
        self._a11_history_cache = ()
        if self._active_id:
            try:
                self._a11_history_cache = self.api.operation_history(self._active_id)
            except (OSError, ValueError, DwmApiError):
                self._a11_history_cache = ()
        existing = self.run_history_tree.blockSignals(True)
        try:
            self.run_history_tree.clear()
            for (at, operation, kind, state, files, run_id, operation_id), event in zip(
                self._a11_history_display_rows(), self._a11_history_cache
            ):
                row = QTreeWidgetItem([at, operation, kind, state, files])
                key = run_id + "|" + operation_id
                row.setData(0, Qt.ItemDataRole.UserRole, key)
                row.setToolTip(1, (
                    "Faktisk kjøring – dette er teknisk utførelse, ikke depotgodkjenning.\n"
                    "Kjøring: " + run_id + "\n" +
                    "Resultat: " + event.message[:600] + "\n" +
                    "Advarsler: " + str(event.warning_count) +
                    " | Filer: " + str(len(event.work_results))
                ))
                self.run_history_tree.addTopLevelItem(row)
                if key == selected:
                    self.run_history_tree.setCurrentItem(row)
            if self.run_history_tree.currentItem() is None and self.run_history_tree.topLevelItemCount():
                self.run_history_tree.setCurrentItem(self.run_history_tree.topLevelItem(0))
        finally:
            self.run_history_tree.blockSignals(existing)
        self._a9_sync_detached_run()

    def _a11_open_history_log(self, key: str):
        if not key or "|" not in key:
            return
        run_id, _operation_id = key.split("|", 1)
        self._a8_show_job_log()
        index = self.job_run_combo.findData(run_id)
        if index >= 0:
            self.job_run_combo.setCurrentIndex(index)
            self._a8_show_selected_run()
        else:
            QMessageBox.information(self, "Kjørelogg", "Ingen detaljlogg for denne kjøringen er tilgjengelig.")

    def _a11_show_selected_history_log(self, _checked=False):
        self._a11_open_history_log(self._a11_selected_history_key() or "")

    def _a11_open_history_results(self, key: str):
        if not self._active_id or not key or "|" not in key:
            return
        run_id, operation_id = key.split("|", 1)
        self._a11_open_operation_results(operation_id, run_id=run_id)

    def _a11_show_selected_results(self, _checked=False, _column=None):
        self._a11_open_history_results(self._a11_selected_history_key() or "")

    def _a11_open_selected_workflow_results(self):
        operation_id = self._a9_selected_operation_id()
        if operation_id:
            self._a11_open_operation_results(operation_id)

    def _a11_open_operation_results(self, operation_id: str, *, run_id=None):
        if not self._active_id:
            return
        try:
            links = self.api.operation_result_links(self._active_id, operation_id, run_id=run_id)
        except (OSError, ValueError, DwmApiError) as exc:
            self._error(exc)
            return
        if not links:
            QMessageBox.information(
                self, "Resultater for deljobb",
                "Ingen direkte resultatfiler er registrert for valgt kjøring.\n"
                "Eldre kjøringer før a11 har ikke nødvendigvis en strukturert resultatindeks.\n"
                "Bruk Resultater / filer for å undersøke Work manuelt."
            )
            return
        if len(links) == 1:
            chosen = links[0]
        else:
            labels = [link.relative_path + ("/" if link.is_directory else "") for link in links]
            answer, ok = QInputDialog.getItem(self, "Resultatfiler", "Velg lagret resultat i Work:", labels, 0, False)
            if not ok:
                return
            chosen = links[labels.index(answer)]
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(chosen.path)))

    def _a8_refresh_job_log(self, *, force: bool = False):
        job_id = self._active_id
        if not job_id:
            self._job_log_selected_job = None
            self._job_log_last_options = ()
            self.job_run_combo.blockSignals(True)
            self.job_run_combo.clear()
            self.job_run_combo.blockSignals(False)
            self.job_log_text.setPlainText("Velg en jobb for å se kjøreloggen.")
            self._a9_sync_detached_log_choices()
            return
        workspace = self.api.workspace()
        view = next((row for row in workspace.jobs if row.job_id == job_id), None)
        key = (workspace.job_list_path or "", job_id,
               str(view.effective_work_operations or "") if view else "")
        try:
            runs = self.api.run_log_history(job_id)
            legacy_text = self.api.saved_job_log(job_id)
        except Exception as exc:
            self.job_log_text.setPlainText("Kan ikke hente jobblogg: " + str(exc))
            return
        options = tuple((run.run_id, run.status) for run in runs)
        if legacy_text:
            options += (("__legacy__", "saved"),)
        job_changed = key != self._job_log_selected_job
        changed = options != self._job_log_last_options
        if job_changed or changed:
            previous = self.job_run_combo.currentData() if not job_changed else None
            self.job_run_combo.blockSignals(True)
            self.job_run_combo.clear()
            for run in runs:
                category = "Deljobb: " + (
                    str(getattr(run, "operation_name", "") or "")
                    or str(getattr(run, "operation_id", "") or "")
                ) if getattr(run, "run_kind", "workflow") == "subjob" else "Arbeidsflyt"
                label = f"{run.started_at.replace('T', ' ')[:19]}  ·  {category}  ·  {run.status}"
                self.job_run_combo.addItem(label, run.run_id)
            if legacy_text:
                self.job_run_combo.addItem("Eldre loggoppføringer fra jobblisten", "__legacy__")
            # Always pick a real run when one first appears. A saved status
            # snapshot is not an actual log and is shown only in Kjøreløp.
            wanted = (
                options[0][0] if options and changed and self._a8_live_job == job_id
                else previous if previous != "__legacy__" and any(item[0] == previous for item in options)
                else (options[0][0] if options else None)
            )
            if wanted is not None:
                idx = self.job_run_combo.findData(wanted)
                self.job_run_combo.setCurrentIndex(max(0, idx))
            self.job_run_combo.blockSignals(False)
            self._job_log_selected_job = key
            self._job_log_last_options = options
        if force or job_changed or changed:
            self._a8_show_selected_run()
        self._a9_sync_detached_log_choices()

    def _a8_show_selected_run(self, _index=None):
        job_id = self._active_id
        if not job_id:
            return
        run_id = self.job_run_combo.currentData()
        if run_id == "__legacy__":
            content = self.api.saved_job_log(job_id)
        elif run_id:
            try:
                content = self.api.read_run_log(job_id, run_id)
            except (OSError, ValueError) as exc:
                content = "Kunne ikke åpne lagret kjørelogg: " + str(exc)
        else:
            content = (
                "Ingen faktisk kjørelogg er lagret for denne jobben.\n"
                "Kjøreløp viser lagret jobbstatus og fremdrift."
            )
        scrollbar = self.job_log_text.verticalScrollBar()
        position = scrollbar.value()
        self.job_log_text.setPlainText(content)
        if self.log_follow.isChecked():
            scrollbar.setValue(scrollbar.maximum())
        else:
            scrollbar.setValue(min(position, scrollbar.maximum()))

    def _a8_restore_run_context(self, *, force: bool = False):
        """Show persisted per-operation state when opening/switching jobs.

        A job list snapshot is not presented as a recovered chronological log.
        """
        workspace = self.api.workspace()
        key = (workspace.job_list_path or "", self._active_id or "")
        if key == self._a8_run_context and not force:
            return
        self._a8_run_context = key
        if not self._active_id:
            self.run_summary.setText("Velg en jobb for å se kjøreløp og lagret status.")
            self.run_progress_bar.setValue(0)
            self.run_events.clear()
            self._a8_live_job = None
            getattr(self, "_a11_refresh_operation_history", lambda: None)()
            self._a9_sync_detached_run()
            return
        try:
            snapshot = saved_progress(self.api.job_details(self._active_id))
        except Exception as exc:
            self.run_summary.setText("Kan ikke hente lagret jobbstatus: " + str(exc))
            self.run_progress_bar.setValue(0)
            self.run_events.clear()
            self._a9_sync_detached_run()
            return
        self.run_summary.setText(snapshot.title)
        self.run_progress_bar.setValue(snapshot.percent)
        lines = ["Lagret jobbstatus (ikke hendelseslogg):", *snapshot.lines]
        try:
            runs = self.api.run_log_history(self._active_id)
            if runs:
                details = self.api.job_details(self._active_id)
                names = {op.operation_id: op.name for op in details.operations}
                lines += ["", "Faktiske, lagrede kj\u00f8ringer (nyeste f\u00f8rst):",
                          *run_history_lines(runs, names=names)]
        except (OSError, ValueError):
            pass
        self.run_events.setPlainText("\n".join(lines))
        self._a8_live_job = None
        getattr(self, "_a11_refresh_operation_history", lambda: None)()
        self._a9_sync_detached_run()

    def _a8_process_run_event(self, event):
        job_id = event.job_id or ""
        if job_id != self._active_id:
            return
        message = str(event.message or "")
        if event.kind == "run.started":
            self._a8_live_job = job_id
            self.run_events.clear()
            self.run_events.appendPlainText(f"{job_id}: Startet")
            self.run_summary.setText(f"Kjører {job_id} – operasjonene oppdateres fortløpende")
            self.run_progress_bar.setValue(0)
            if self.auto_show_log_action.isChecked():
                self._a8_show_job_log()
        elif event.kind == "run.progress":
            self.run_summary.setText(f"{job_id}: {message[:180]}")
            if event.progress is not None:
                self.run_progress_bar.setValue(round(100 * float(event.progress)))
        elif event.kind == "run.state":
            if event.progress is not None:
                self.run_progress_bar.setValue(round(100 * float(event.progress)))
        elif event.kind == "run.log":
            if message.startswith(("START:", "OK:", "FEIL:", "AVBRUTT")):
                self.run_events.appendPlainText(f"{job_id}: {message[:280]}")
        elif event.kind in {"run.error", "run.finished", "run.cancel_requested"}:
            self.run_events.appendPlainText(f"{job_id}: {event.kind} {message}")
            if event.kind == "run.finished":
                self.run_summary.setText(f"{job_id}: Kjøringen er avsluttet")
                self.run_progress_bar.setValue(round(100 * float(event.progress or 0)))
            if event.kind == "run.error":
                self.run_summary.setText(f"{job_id}: Feil – {message[:180]}")
            if event.kind in {"run.finished", "run.error"}:
                self._a8_live_job = None
        self._a9_sync_detached_run()

    def _a9_process_subjob_event(self, event):
        if event.job_id != self._active_id:
            return
        job_id = event.job_id
        message = str(event.message or "")
        if event.kind == "subjob.started":
            self._a8_live_job = job_id
            self.run_events.clear()
            self.run_events.appendPlainText(job_id + ": " + message)
            self.run_summary.setText("Kj\u00f8rer deljobb: " + message)
            self.run_progress_bar.setValue(0)
            if self.auto_show_log_action.isChecked():
                self._a8_show_job_log()
        elif event.kind == "subjob.progress":
            self.run_summary.setText("Deljobb: " + message[:180])
            if event.progress is not None:
                self.run_progress_bar.setValue(round(100 * float(event.progress)))
        elif event.kind == "subjob.log":
            if message.startswith(("START:", "OK:", "FEIL:", "AVBRUTT", "SELEKTIV")):
                self.run_events.appendPlainText(job_id + ": " + message[:280])
        elif event.kind in {"subjob.finished", "subjob.error"}:
            self.run_events.appendPlainText(message)
            self.run_summary.setText("Deljobb avsluttet: " + message)
            if event.kind == "subjob.finished" and event.progress is not None:
                self.run_progress_bar.setValue(100)
            self._a8_live_job = None
        self._a9_sync_detached_run()

    def _poll(self):
        events = self.api.poll_events(150)
        job_log_changed = False
        for event in events:
            if event.kind.startswith("run."):
                self._a8_process_run_event(event)
                if event.kind in {"run.log", "run.error", "run.finished", "run.started"}:
                    job_log_changed = job_log_changed or event.job_id == self._active_id
            elif event.kind.startswith("subjob."):
                self._a9_process_subjob_event(event)
                if event.kind in {"subjob.started", "subjob.log", "subjob.finished", "subjob.error"}:
                    job_log_changed = job_log_changed or event.job_id == self._active_id
            elif event.kind in {"joblist.opened", "joblist.new"}:
                self._append_log(f"{event.kind}: {event.message}")
            elif event.kind == "joblist.index_write_failed":
                self._append_log("ADVARSEL: " + str(event.message))
        try:
            while True:
                kind, data = self._worker_messages.get_nowait()
                if kind == "error":
                    self._error(data)
                elif kind == "selected":
                    self._active_id = data
                elif kind == "info":
                    self._append_log(data)
                elif kind == "done":
                    self._append_log(data)
                    self._worker = None
                    self._set_running_ui(False)
                    self._a8_refresh_job_log(force=True)
                    self._a8_restore_run_context(force=True)
                    if self.api.run_log_warning:
                        self._append_log("ADVARSEL: " + self.api.run_log_warning)
        except Empty:
            pass
        self._refresh(force=any(event.kind in {"joblist.opened", "run.state", "run.finished", "job.selected", "subjob.finished", "subjob.error"} for event in events))
        if job_log_changed or any(event.kind in {"run.started", "subjob.started"} for event in events):
            self._a8_refresh_job_log(force=True)
        if (self._active_id and any(
            event.job_id == self._active_id and (
                event.kind in {"subjob.finished", "subjob.error", "run.finished", "run.error"}
                or (event.kind == "run.log" and str(event.message or "").startswith(("OK:", "FEIL:")))
            ) for event in events)):
            getattr(self, "_a11_refresh_operation_history", lambda: None)()

    def _append_log(self, message: str):
        content = str(message or "")
        if len(content) > 4500:
            content = content[:4500] + "\n[Loggvisning avkortet; råresultat bevares i DWM-arbeidsområdet.]"
        self.system_text.appendPlainText(content)

    # ---------- Read models and result navigation ----------
    def _refresh(self, *, force: bool = False):
        workspace = self.api.workspace()
        if self._active_id not in {item.job_id for item in workspace.jobs}:
            self._active_id = workspace.active_job_id
        rows = tuple((job.job_id, job.name, job.status, round(job.progress, 3)) for job in workspace.jobs)
        key = (workspace.job_list_path, self._active_id, rows, self.api.dirty)
        if not force and key == self._render_key:
            return
        self._render_key = key
        self._refresh_joblist_rule()
        existing = self.jobs_tree.blockSignals(True)
        self.jobs_tree.clear()
        for job in workspace.jobs:
            item = QTreeWidgetItem([job.job_id, job.name, job.status, f"{job.progress:.0%}"])
            item.setData(0, Qt.ItemDataRole.UserRole, job.job_id)
            item.setToolTip(1, "\n".join([_format_path(job.source_extraction), _format_path(job.effective_work_operations)]))
            self.jobs_tree.addTopLevelItem(item)
            if job.job_id == self._active_id:
                self.jobs_tree.setCurrentItem(item)
        self.jobs_tree.blockSignals(existing)
        display_path = workspace.job_list_path or "(ikke lagret)"
        self._filter_jobs(self.job_search.text())
        self._update_job_actions()
        self.setWindowTitle(f"{APP_NAME} v{VERSION} · {Path(display_path).name}{' *' if self.api.dirty else ''}")
        self.statusBar().showMessage(f"Jobbliste: {display_path}    |    Aktiv: {self._active_id or '-'}", 0)
        previous_subjob = self._a9_selected_operation_id()
        self.workflow_tree.clear()
        if not self._active_id:
            self._open_report_root = None
            self._file_root = None
            self.file_tree.setModel(None)
            self.depot_path_label.setText("")
            self.progress_label.setText("")
            self.overview_label.setText("Ingen jobb valgt")
            self.overview_storage.setText("")
            self.storage_text.clear()
            self.workflow_label.setText("Velg en jobb.")
            self.results_root_label.setText("Ingen resultatområde valgt")
            self._set_empty_actions()
            self._a8_restore_run_context()
            self._a8_refresh_job_log(force=True)
            return
        try:
            details = self.api.job_details(self._active_id)
        except Exception as exc:
            self._append_log("Kunne ikke lese jobbdetaljer: " + str(exc))
            return
        job = details.job
        self.overview_label.setText(f"{job.job_id}  ·  {job.name}  ·  {job.status}")
        self.progress_label.setText(f"Fremdrift: {job.progress:.0%}   |   Operasjoner: {job.current_operation}/{job.operation_count}   |   {details.message[:240]}")
        a10_info = self.api.work_job_info(self._active_id)
        a10_storage_note = (
            "Jobbdata: Autoritative i Work | Varig ID: " + str(a10_info["job_uid"])
            if a10_info["work_is_authoritative"] and a10_info["work_available"]
            else "Jobbdata: Work frakoblet – status fra jobblisten er ikke oppdatert"
            if a10_info["work_is_authoritative"]
            else "Jobbdata: Utkast – ikke lagret i Work ennå"
        )
        self.overview_storage.setText(
            f"Source: {_format_path(job.source_extraction)}\n"
            f"Work content: {_format_path(job.work_content)}\n"
            f"Work operations: {_format_path(job.effective_work_operations)}\n"
            f"AIP: {_format_path(job.archive_root)}\n"
            f"{a10_storage_note}"
        )
        self.storage_text.setPlainText("\n\n".join(f"{field}:\n{details.storage[field] or '(ikke angitt)'}" for field in STORAGE_FIELDS))
        self.workflow_label.setText(f"{job.job_id} · {len(details.operations)} deljobber")
        for op in details.operations:
            item = QTreeWidgetItem([
                str(op.position), op.name,
                "OK" if op.completed else "—",
                "Ja" if op.checkpoint else "",
            ])
            item.setData(0, Qt.ItemDataRole.UserRole, op.operation_id)
            item.setToolTip(1, f"{op.operation_id} · {op.category}")
            self.workflow_tree.addTopLevelItem(item)
            if op.operation_id == previous_subjob:
                self.workflow_tree.setCurrentItem(item)
        self._open_report_root = Path(job.effective_work_operations) if job.effective_work_operations else None
        self.results_root_label.setText(str(self._open_report_root) if self._open_report_root else "Work operations ikke satt")
        self.depot_path_label.setText(f"Resultatmappe: {_format_path(job.effective_work_operations)}")
        if self._file_root is not None and self._file_root != self._open_report_root:
            # Never show files belonging to a previously selected extraction.
            self.file_tree.setModel(None)
            self._file_root = None
        self.overview_preflight.setEnabled(self._worker is None)
        self.preflight_action.setEnabled(self._worker is None)
        self.overview_run.setEnabled(self._worker is None and not _is_waiting_status(job.status))
        self.overview_continue.setEnabled(self._worker is None and _is_waiting_status(job.status))
        self.run_action.setEnabled(self._worker is None and not _is_waiting_status(job.status))
        self.continue_action.setEnabled(self._worker is None and _is_waiting_status(job.status))
        self.overview_change_work.setEnabled(self._worker is None)
        self.storage_change_work.setEnabled(self._worker is None)
        self._a8_restore_run_context()
        self._a8_refresh_job_log()

    def _set_empty_actions(self):
        self.overview_preflight.setEnabled(False)
        self.preflight_action.setEnabled(False)
        self.overview_run.setEnabled(False)
        self.overview_continue.setEnabled(False)
        self.run_action.setEnabled(False)
        self.continue_action.setEnabled(False)
        self.overview_change_work.setEnabled(False)
        self.storage_change_work.setEnabled(False)

    def _page_changed(self, _index):
        # Never walk a work directory automatically at page change.
        pass

    def _show_result_files(self):
        self.pages.setCurrentIndex(1)
        self._load_result_files()

    def _load_result_files(self):
        root = self._open_report_root
        if root is None:
            QMessageBox.information(self, "Resultater", "Ingen Work operations-mappe for aktiv jobb.")
            return
        if not root.is_dir():
            QMessageBox.warning(self, "Resultater", f"Arbeidsområdet finnes ikke eller er frakoblet:\n{root}")
            return
        if self._file_model is None:
            self._file_model = QFileSystemModel(self)
            self._file_model.setReadOnly(True)
            self.file_tree.setModel(self._file_model)
        index = self._file_model.setRootPath(str(root))
        self.file_tree.setRootIndex(index)
        self.file_tree.setColumnWidth(0, 380)
        self._file_root = root

    def _open_selected_result(self, index):
        if self._file_model is None:
            return
        path = Path(self._file_model.filePath(index))
        if path.is_file():
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))

    # ---------- a12: result center and established multi-job report service ----------
    def _a2_open_depot_review(self, _checked=False):
        self._a12_open_result_center(depot=True)

    def _a12_open_result_center(self, _checked=False, *, depot=False):
        if not self._active_id:
            QMessageBox.information(self, "Resultatvisninger", "Velg en jobb i jobblisten.")
            return
        try:
            job = self.api.job_details(self._active_id).job
        except DwmApiError as exc:
            self._error(exc)
            return
        # Keep v0.1.8 result-center available as a read-only compatibility layer.
        from .result_center_v018_a13 import ResultCenterWindow
        from .result_center_v019_a1 import ResultCenterWindow as EvidenceResultCenter
        dialog = EvidenceResultCenter(
            job.effective_work_operations,
            display_name=job.job_id + " – " + job.name,
            available_jobs=self.api.report_candidates(),
            report_api=self.api,
            on_generate_report=self._a12_open_selected_report,
        )
        if depot:
            dialog.show_depot_review()
        dialog.setStyleSheet(STYLE)
        dialog.setFont(self.font())
        dialog.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        self._a12_result_windows.append(dialog)
        dialog.destroyed.connect(
            lambda _obj=None, win=dialog: (
                self._a12_result_windows.remove(win)
                if win in self._a12_result_windows else None
            )
        )
        dialog.show()

    def _a12_open_selected_report(self, _checked=False):
        if not self.api.workspace().jobs:
            QMessageBox.information(self, "Rapport", "Åpne en jobbliste med Noark 5-jobber først.")
            return
        if self._worker is not None:
            QMessageBox.warning(self, "Rapport", "Avslutt pågående jobbkjøring før rapportgenerering.")
            return
        from .report_selected_v018_a12 import SelectedReportDialog
        dialog = SelectedReportDialog(self.api, active_job_id=self._active_id, parent=self)
        dialog.setStyleSheet(STYLE)
        dialog.setFont(self.font())
        dialog.exec()

    def _open_latest_depot_report(self):
        report = latest_depot_report(self._open_report_root)
        if report is None:
            QMessageBox.information(
                self, "Depotrapport", "Ingen generert depotrapport ble funnet for aktiv jobb. "
                "Bruk Resultater / filer for å undersøke Work operations."
            )
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(report)))

    def _open_work_dir(self):
        if self._open_report_root and self._open_report_root.is_dir():
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(self._open_report_root)))
        else:
            QMessageBox.information(self, "Arbeidsområde", "Work operations er ikke tilgjengelig for aktiv jobb.")

    def _open_legacy(self):
        if self._worker is not None:
            QMessageBox.warning(self, "Jobb kjører",
                "Start ikke to grensesnitt mot samme jobbliste mens en kjøring pågår.")
            return
        if not self._maybe_save():
            return
        main = Path(__file__).resolve().parents[1] / "main.py"
        if not main.is_file():
            self._error("Finner ikke main.py for gammel GUI.")
            return
        ok, _pid = QProcess.startDetached(sys.executable, [str(main)], str(main.parent))
        if not ok:
            self._error("Kunne ikke starte gammel GUI.")
        else:
            self._append_log("Gammelt GUI startet separat; åpne ønsket jobbliste der.")

    def _error(self, error):
        QMessageBox.critical(self, "DWM", str(error))

    def closeEvent(self, event):
        if self._worker is not None:
            QMessageBox.information(self, "Jobb kjører", "Stopp og avslutt kjøringen før du lukker DWM.")
            event.ignore()
            return
        if not self._maybe_save():
            event.ignore()
            return
        # Independent result windows must not keep the app alive after the
        # main workbench closes. These are read-only and have no unsaved data.
        for window in tuple(self._a12_result_windows):
            try:
                window.close()
            except RuntimeError:
                pass
        self._a12_result_windows.clear()
        # Close a normal independent viewer without sending a dock-close signal.
        if self._detached_log_window is not None:
            self._a9_redock_job_log()
        if self._detached_run_window is not None:
            self._a9_redock_run()
        self.dock_run.hide()  # Do not persist obsolete bottom split.
        self.config.setValue("qt/window_geometry", self.saveGeometry())
        self.config.setValue("qt/window_state", self.saveState(4))
        self.config.setValue("qt/complexity", self._complexity)
        self.config.sync()
        event.accept()
