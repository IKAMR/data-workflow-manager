"""Dockable desktop workbench for Data Workflow Manager v0.1.8-a4.

Qt owns presentation only. DwmWorkbenchAPI is the authoritative job-list and
execution boundary. The legacy CustomTkinter GUI is not imported here.
"""
from __future__ import annotations

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
    QDockWidget, QFileDialog, QFileSystemModel, QFormLayout, QFrame,
    QHBoxLayout, QHeaderView, QInputDialog, QLabel, QLineEdit, QMainWindow,
    QMenu, QMessageBox, QPlainTextEdit, QPushButton, QSplitter, QStatusBar,
    QTabWidget, QTableWidget, QTableWidgetItem, QToolBar, QTreeView,
    QTreeWidget, QTreeWidgetItem, QToolButton, QVBoxLayout, QWidget,
)

from app.application_api import DwmApiError
from app.workbench_api_v018_a3 import DwmWorkbenchAPI, STORAGE_FIELDS
from app.workbench_recent_v018_a4 import recent_joblists, remember_joblist
from version import APP_NAME, VERSION


# Explicitly separate presentation presets from workflow/report/storage profiles.
DOCK_NAMES = ("jobs", "workflow", "storage", "log", "info")
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
        self._render_key: tuple | None = None
        self._complexity = "Standard"
        self._layout_name = "Laptop"
        self._file_model = None
        self._file_root: Path | None = None
        self._open_report_root: Path | None = None

        self.setObjectName("DwmMainWindow")
        self.setWindowTitle(f"{APP_NAME} v{VERSION} – arbeidsflate")
        self.setStyleSheet(STYLE)
        self.setFont(QFont("Segoe UI", 10))
        self.setMinimumSize(720, 480)
        self.resize(1180, 780)
        self.setDockNestingEnabled(True)
        self.setDockOptions(
            QMainWindow.DockOption.AllowNestedDocks
            | QMainWindow.DockOption.AllowTabbedDocks
            | QMainWindow.DockOption.GroupedDragging
            | QMainWindow.DockOption.AnimatedDocks
        )
        self.setStatusBar(QStatusBar())
        self._create_central()
        self._create_docks()
        self._create_actions_and_menu()
        self._restore_settings()

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
            "Denne første Qt-versjonen gir tilgang til genererte DWM-rapporter og evidens. "
            "Full faglig redigering og batch-/metadatafunksjoner er fortsatt i det gamle GUI-et."
        ))
        rbuttons = QHBoxLayout()
        b = QPushButton("Vis rapportfiler")
        b.clicked.connect(self._show_result_files)
        rbuttons.addWidget(b)
        b = QPushButton("Åpne gammelt GUI for depotvurdering")
        b.clicked.connect(self._open_legacy)
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
        dock.setAllowedAreas(Qt.DockWidgetArea.AllDockWidgetAreas)
        self.addDockWidget(area, dock)
        setattr(self, "dock_" + name, dock)
        return dock

    def _create_docks(self):
        # Job list – no separate top-level window is required.
        jobs = QWidget()
        j = QVBoxLayout(jobs)
        self.joblist_label = _muted("Ingen jobbliste åpnet")
        j.addWidget(self.joblist_label)
        self.job_search = QLineEdit()
        self.job_search.setPlaceholderText("Søk i jobblisten (navn, ID, status, Source eller Work)…")
        self.job_search.setClearButtonEnabled(True)
        self.job_search.textChanged.connect(self._filter_jobs)
        j.addWidget(self.job_search)
        self.jobs_tree = QTreeWidget()
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
        self._job_action_buttons = (
            self.job_rename_button, self.job_up_button,
            self.job_down_button, self.job_remove_button,
        )
        self._dock("jobs", "Jobber", jobs, Qt.DockWidgetArea.LeftDockWidgetArea)

        flow = QWidget()
        f = QVBoxLayout(flow)
        self.workflow_label = _muted("Velg jobb for å se arbeidsflyten.")
        f.addWidget(self.workflow_label)
        self.workflow_tree = QTreeWidget()
        self.workflow_tree.setHeaderLabels(["#", "Operasjon", "Status", "Stopp"])
        self.workflow_tree.setRootIsDecorated(False)
        self.workflow_tree.setAlternatingRowColors(True)
        self.workflow_tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.workflow_tree.header().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.workflow_tree.header().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.workflow_tree.header().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        f.addWidget(self.workflow_tree, 1)
        action_row = QHBoxLayout()
        self.workflow_preset_button = QPushButton("Velg arbeidsflyt…")
        self.workflow_preset_button.clicked.connect(self._choose_workflow)
        action_row.addWidget(self.workflow_preset_button)
        self.workflow_checkpoint_button = QPushButton("Kontrollpunkt av/på")
        self.workflow_checkpoint_button.clicked.connect(self._toggle_checkpoint)
        action_row.addWidget(self.workflow_checkpoint_button)
        f.addLayout(action_row)
        self._dock("workflow", "Arbeidsflyt", flow, Qt.DockWidgetArea.LeftDockWidgetArea)

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
        self._dock("storage", "Kilde og lagring", storage, Qt.DockWidgetArea.RightDockWidgetArea)

        logger = QWidget()
        l = QVBoxLayout(logger)
        self.log_text = QPlainTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMaximumBlockCount(2500)
        l.addWidget(self.log_text, 1)
        logtools = QHBoxLayout()
        clear = QPushButton("Tøm visning")
        clear.clicked.connect(self.log_text.clear)
        logtools.addWidget(clear)
        logtools.addStretch(1)
        l.addLayout(logtools)
        self._dock("log", "Kjøreløp og logg", logger, Qt.DockWidgetArea.BottomDockWidgetArea)

        info = QWidget()
        i = QVBoxLayout(info)
        self.info_text = _muted(
            "Trekk paneler i tittellinjen for å flytte dem.\n\n"
            "Alle paneler kan plasseres til venstre, høyre, øverst eller nederst, "
            "grupperes som faner, skjules eller løsnes til egen skjerm.\n\n"
            "Velg Vis → Arbeidsflate for ferdige oppsett.\n\n"
            "Vis → Lagre arbeidsflate som … lagrer egen plassering.\n\n"
            "Kjøring og analyser gjøres av DWM-motoren, ikke Qt-GUI-et."
        )
        self.info_text.setAlignment(Qt.AlignmentFlag.AlignTop)
        i.addWidget(self.info_text)
        i.addStretch(1)
        self._dock("info", "Hjelp og informasjon", info, Qt.DockWidgetArea.RightDockWidgetArea)

        self.splitDockWidget(self.dock_jobs, self.dock_workflow, Qt.Orientation.Vertical)
        self.tabifyDockWidget(self.dock_storage, self.dock_info)
        self.dock_storage.raise_()

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
        self.rename_job_action = self._action("Endre navn på jobb…", self._rename_job)
        self.remove_job_action = self._action("Fjern jobb fra listen…", self._remove_job)
        file_menu.addAction(self.rename_job_action)
        file_menu.addAction(self.remove_job_action)
        file_menu.addSeparator()
        file_menu.addAction(self._action("Start gammel CustomTkinter-GUI", self._open_legacy))
        file_menu.addAction(self._action("Avslutt", self.close, "Ctrl+Q"))

        run_menu = mb.addMenu("Kjør")
        self.run_action = self._action("Kjør valgt jobb", self._run_selected, "F5")
        self.continue_action = self._action("Fortsett ved kontrollpunkt", self._continue_job)
        self.ready_action = self._action("Kjør klare jobber (sekvensielt)", self._run_ready)
        self.stop_action = self._action("Stopp etter gjeldende operasjon", self._request_stop, "Shift+F5")
        for a in (self.run_action, self.continue_action, self.ready_action, self.stop_action):
            run_menu.addAction(a)
        self.stop_action.setEnabled(False)

        view = mb.addMenu("Vis")
        for name in DOCK_NAMES:
            view.addAction(getattr(self, "dock_" + name).toggleViewAction())
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
        self._toolbar = toolbar
        self._refresh_recent_menu()

    def _apply_builtin(self, name: str):
        if name not in LAYOUT_MODES:
            raise ValueError(f"Ukjent arbeidsflate: {name}")
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
        for key in DOCK_NAMES:
            dock = getattr(self, "dock_" + key)
            dock.setFloating(False)
            self.removeDockWidget(dock)
            self.addDockWidget(area_map[target[key]], dock)
            dock.show()
        if name in {"Laptop", "Full", "Analyse"}:
            self.splitDockWidget(self.dock_jobs, self.dock_workflow, Qt.Orientation.Vertical)
        if name == "Full":
            self.tabifyDockWidget(self.dock_storage, self.dock_info)
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
            self.dock_log.hide()
            self._set_complexity("Enkel")
            self.pages.setCurrentIndex(0)
        if name == "Full":
            self.pages.setCurrentIndex(0)
        if name == "Analyse":
            self.pages.setCurrentIndex(1)
        self._layout_name = name
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
            "state": bytes(self.saveState(3).toBase64()).decode("ascii"),
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
        if not self.restoreState(QByteArray.fromBase64(encoded.encode("ascii")), 3):
            QMessageBox.warning(self, "Arbeidsflate", "Kunne ikke gjenopprette lagret arbeidsflate.")
            return
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
        if state:
            try:
                restored = self.restoreState(state, 3)
            except (TypeError, ValueError):
                pass
        if not restored:
            self._apply_builtin("Laptop")
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

    def _recover_windows(self):
        # Recover after a second monitor is disconnected. Never resize job data.
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
                    self.resize(min(max(self.minimumWidth(), 720), owner.width()),
                                min(max(self.minimumHeight(), 480), owner.height()))

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

    def _new_job(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("Legg til Noark 5-jobb")
        form = QFormLayout(dialog)
        name = QLineEdit()
        source = QLineEdit()
        work = QLineEdit()
        form.addRow("Jobbnavn (valgfritt)", name)
        self._path_form_row(form, "Source – uttrekk", source)
        self._path_form_row(form, "Work – operations", work)
        form.addRow(_muted("Ingen mapper opprettes og ingen uttrekk kopieres."))
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
    def _run_selected(self):
        if not self._active_id or self._worker is not None:
            return
        details = self.api.job_details(self._active_id)
        view = details.job
        if _is_waiting_status(view.status):
            QMessageBox.information(self, "Kontrollpunkt", "Bruk Fortsett ved kontrollpunkt for denne jobben.")
            return
        allow_rerun = (_is_completed_status(view.status)
                       or details.message == "Konfigurasjon endret - klar for ny kjøring")
        if allow_rerun:
            answer = QMessageBox.question(self, "Kjøre på nytt?",
                f"{view.job_id} er tidligere kjørt. Start en ny kjøring?\nEksisterende resultatfiler slettes ikke av GUI-et.")
            if answer != QMessageBox.StandardButton.Yes:
                return
        self._start_worker([(self._active_id, allow_rerun, False)])

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

    def _start_worker(self, jobs: list[tuple[str, bool, bool]]):
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
        self._append_log(f"Starter kjøring av {len(jobs)} jobb(er).")

        def run():
            try:
                for job_id, allow_rerun, continuing in jobs:
                    if self._batch_stop.is_set():
                        break
                    self._worker_messages.put(("selected", job_id))
                    ok = self.api.run_job(job_id, allow_rerun=allow_rerun, continue_waiting=continuing)
                    if not ok:
                        self._worker_messages.put(("info", f"{job_id}: Stoppet ved feil/avbrudd."))
                        break
            except Exception as exc:
                self._worker_messages.put(("error", str(exc)))
            finally:
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
                       self.ready_action, self.continue_action):
            action.setEnabled(not running)
        self.stop_action.setEnabled(running)
        self.overview_run.setEnabled(not running)
        self.overview_continue.setEnabled(not running)
        self.storage_edit_button.setEnabled(not running)
        self.workflow_preset_button.setEnabled(not running)
        self.workflow_checkpoint_button.setEnabled(not running)
        self.jobs_tree.setEnabled(not running)
        self._update_job_actions()

    def _poll(self):
        events = self.api.poll_events(150)
        for event in events:
            if event.kind in {"run.log", "run.error", "run.finished", "run.cancel_requested"}:
                message = event.message or (f"{event.job_id}: {event.kind}" if event.job_id else event.kind)
                self._append_log(message)
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
        except Empty:
            pass
        self._refresh(force=any(event.kind in {"joblist.opened", "run.state", "run.finished", "job.selected"} for event in events))

    def _append_log(self, message: str):
        content = str(message or "")
        if len(content) > 4500:
            content = content[:4500] + "\n[Loggvisning avkortet; råresultat bevares i DWM-arbeidsområdet.]"
        self.log_text.appendPlainText(content)

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
            return
        try:
            details = self.api.job_details(self._active_id)
        except Exception as exc:
            self._append_log("Kunne ikke lese jobbdetaljer: " + str(exc))
            return
        job = details.job
        self.overview_label.setText(f"{job.job_id}  ·  {job.name}  ·  {job.status}")
        self.progress_label.setText(f"Fremdrift: {job.progress:.0%}   |   Operasjoner: {job.current_operation}/{job.operation_count}   |   {details.message[:240]}")
        self.overview_storage.setText(
            f"Source: {_format_path(job.source_extraction)}\n"
            f"Work content: {_format_path(job.work_content)}\n"
            f"Work operations: {_format_path(job.effective_work_operations)}\n"
            f"AIP: {_format_path(job.archive_root)}"
        )
        self.storage_text.setPlainText("\n\n".join(f"{field}:\n{details.storage[field] or '(ikke angitt)'}" for field in STORAGE_FIELDS))
        self.workflow_label.setText(f"{job.job_id} · {len(details.operations)} operasjoner")
        for op in details.operations:
            item = QTreeWidgetItem([
                str(op.position), op.name,
                "OK" if op.completed else "—",
                "Ja" if op.checkpoint else "",
            ])
            item.setData(0, Qt.ItemDataRole.UserRole, op.operation_id)
            item.setToolTip(1, f"{op.operation_id} · {op.category}")
            self.workflow_tree.addTopLevelItem(item)
        self._open_report_root = Path(job.effective_work_operations) if job.effective_work_operations else None
        self.results_root_label.setText(str(self._open_report_root) if self._open_report_root else "Work operations ikke satt")
        self.depot_path_label.setText(f"Resultatmappe: {_format_path(job.effective_work_operations)}")
        if self._file_root is not None and self._file_root != self._open_report_root:
            # Never show files belonging to a previously selected extraction.
            self.file_tree.setModel(None)
            self._file_root = None
        self.overview_run.setEnabled(self._worker is None and not _is_waiting_status(job.status))
        self.overview_continue.setEnabled(self._worker is None and _is_waiting_status(job.status))
        self.run_action.setEnabled(self._worker is None and not _is_waiting_status(job.status))
        self.continue_action.setEnabled(self._worker is None and _is_waiting_status(job.status))

    def _set_empty_actions(self):
        self.overview_run.setEnabled(False)
        self.overview_continue.setEnabled(False)
        self.run_action.setEnabled(False)
        self.continue_action.setEnabled(False)

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
        self.config.setValue("qt/window_geometry", self.saveGeometry())
        self.config.setValue("qt/window_state", self.saveState(3))
        self.config.setValue("qt/complexity", self._complexity)
        self.config.sync()
        event.accept()
