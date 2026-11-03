"""Independent, normally stacked log and Kjøreløp windows for Qt workbench.

Unlike QDockWidget's floating Qt.Tool window, this *unparented* Qt.Window
can sit behind the DWM main window when the two windows overlap on one screen.
It contains a read-only mirror of the docked log, not a second log source.
"""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QHBoxLayout, QLabel, QPlainTextEdit, QProgressBar, QPushButton,
    QVBoxLayout, QWidget,
)


class DetachedJobLogWindow(QWidget):
    redockRequested = Signal()
    runSelected = Signal(str)
    refreshRequested = Signal()
    followChanged = Signal(bool)

    def __init__(self) -> None:
        # Deliberately NO owner/parent: Qt.Tool and owned windows stay above the
        # main window on Windows. This must be a regular, independently stacked
        # top-level window, not another floating QDockWidget.
        super().__init__(None, Qt.WindowType.Window)
        self.setObjectName("DwmDetachedJobLog")
        self.setWindowTitle("Kjørelogg – Data Workflow Manager")
        self.setMinimumSize(480, 300)
        self.resize(940, 540)

        content = QVBoxLayout(self)
        header = QHBoxLayout()
        header.addWidget(QLabel("Kjøring:"))
        self.run_combo = QComboBox()
        self.run_combo.setMinimumWidth(120)
        self.run_combo.currentIndexChanged.connect(self._selected_run_changed)
        header.addWidget(self.run_combo, 1)
        refresh = QPushButton("Oppdater")
        refresh.clicked.connect(lambda _checked=False: self.refreshRequested.emit())
        header.addWidget(refresh)
        content.addLayout(header)

        self.log_text = QPlainTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        content.addWidget(self.log_text, 1)

        footer = QHBoxLayout()
        self.follow = QCheckBox("Følg siste linje")
        self.follow.toggled.connect(self.followChanged.emit)
        footer.addWidget(self.follow)
        dock_button = QPushButton("Fest til hovedvindu")
        dock_button.clicked.connect(lambda _checked=False: self.redockRequested.emit())
        footer.addWidget(dock_button)
        footer.addStretch(1)
        content.addLayout(footer)

    def set_runs(self, entries: list[tuple[str, str]], selected: str | None) -> None:
        self.run_combo.blockSignals(True)
        try:
            self.run_combo.clear()
            for label, run_id in entries:
                self.run_combo.addItem(label, run_id)
            if selected is not None:
                idx = self.run_combo.findData(selected)
                if idx >= 0:
                    self.run_combo.setCurrentIndex(idx)
        finally:
            self.run_combo.blockSignals(False)

    def set_follow(self, enabled: bool) -> None:
        self.follow.blockSignals(True)
        try:
            self.follow.setChecked(enabled)
        finally:
            self.follow.blockSignals(False)

    def set_log_text(self, content: str) -> None:
        scrollbar = self.log_text.verticalScrollBar()
        old_position = scrollbar.value()
        self.log_text.setPlainText(content)
        if self.follow.isChecked():
            scrollbar.setValue(scrollbar.maximum())
        else:
            scrollbar.setValue(min(old_position, scrollbar.maximum()))

    def _selected_run_changed(self, _index: int) -> None:
        run_id = self.run_combo.currentData()
        if run_id is not None:
            self.runSelected.emit(str(run_id))

    def closeEvent(self, event) -> None:
        # Closing the viewer must not throw away the dock or the log history.
        # The main window owns the transition back to the docked view.
        event.ignore()
        self.redockRequested.emit()


class _DragToDetachLabel(QLabel):
    """Title-text drag opens a normal viewer instead of a floating Qt.Tool."""

    detached = Signal()

    def __init__(self, text: str, parent: QWidget) -> None:
        super().__init__(text, parent)
        self._press = None
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        self.setToolTip("Dra ut til eget vindu, eller trykk Eget vindu")

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._press = event.globalPosition().toPoint()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        if self._press is not None and (
            event.globalPosition().toPoint() - self._press
        ).manhattanLength() >= 12:
            self._press = None
            self.setCursor(Qt.CursorShape.OpenHandCursor)
            self.detached.emit()
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        self._press = None
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        super().mouseReleaseEvent(event)


class DetachableDockTitleBar(QWidget):
    """Safe title bar: detach via explicit button or drag, never native Qt float.

    Qt's QDockWidget floating windows are owned Qt.Tool windows; unlike a
    normal window, they remain on top of the workbench on Windows. This title
    bar deliberately disables that native operation for log and run panels.
    """

    detachRequested = Signal()
    hideRequested = Signal()

    def __init__(self, title: str) -> None:
        super().__init__()
        self.setObjectName("DwmSafeDockTitle")
        self.setStyleSheet(
            "QWidget#DwmSafeDockTitle { background: #202a39; } "
            "QLabel { color: #dce5f2; font-weight: 600; }"
        )
        row = QHBoxLayout(self)
        row.setContentsMargins(9, 2, 4, 2)
        row.setSpacing(5)
        self.drag_label = _DragToDetachLabel(title, self)
        self.drag_label.detached.connect(self.detachRequested.emit)
        row.addWidget(self.drag_label, 1)
        self.detach_button = QPushButton("Eget vindu")
        self.detach_button.setToolTip("Åpne som et vanlig Windows-vindu")
        self.detach_button.clicked.connect(lambda _checked=False: self.detachRequested.emit())
        row.addWidget(self.detach_button)
        close_button = QPushButton("×")
        close_button.setToolTip("Skjul panelet; åpne igjen fra Vis-menyen")
        close_button.setFixedWidth(26)
        close_button.clicked.connect(lambda _checked=False: self.hideRequested.emit())
        row.addWidget(close_button)


class DetachedRunWindow(QWidget):
    """Independent normal window showing only Kjøreløp, not the job log."""

    redockRequested = Signal()

    def __init__(self) -> None:
        super().__init__(None, Qt.WindowType.Window)
        self.setObjectName("DwmDetachedRunProgress")
        self.setWindowTitle("Kjøreløp – Data Workflow Manager")
        self.setMinimumSize(480, 300)
        self.resize(940, 540)

        content = QVBoxLayout(self)
        self.summary = QLabel("Kjøreløp for valgt jobb")
        self.summary.setWordWrap(True)
        content.addWidget(self.summary)
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        content.addWidget(self.progress)
        self.events = QPlainTextEdit()
        self.events.setReadOnly(True)
        self.events.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.events.setMaximumBlockCount(1000)
        content.addWidget(self.events, 1)
        footer = QHBoxLayout()
        footer.addWidget(QLabel("Kjøreløp: deljobber og fremdrift. Ikke detaljlogg."))
        footer.addStretch(1)
        redock = QPushButton("Fest til hovedvindu")
        redock.clicked.connect(lambda _checked=False: self.redockRequested.emit())
        footer.addWidget(redock)
        content.addLayout(footer)

    def set_run_data(self, summary: str, percent: int, events: str) -> None:
        self.summary.setText(summary)
        self.progress.setValue(percent)
        if events != self.events.toPlainText():
            scroll = self.events.verticalScrollBar()
            previous = scroll.value()
            near_bottom = previous >= scroll.maximum() - 3
            self.events.setPlainText(events)
            scroll.setValue(scroll.maximum() if near_bottom else min(previous, scroll.maximum()))

    def closeEvent(self, event) -> None:
        event.ignore()
        self.redockRequested.emit()
