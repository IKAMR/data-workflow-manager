"""Compact result navigation; a16.2 makes professional review pages direct buttons.

The underlying result QTabWidget, original pages, signals and evidence models
are unchanged. Group navigation uses the same original tabs; only the chooser
for 'Faglig vurdering' is replaced with two directly visible, checkable buttons.
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import (
    QButtonGroup, QCheckBox, QComboBox, QHBoxLayout, QLabel, QPushButton,
    QTabBar, QVBoxLayout, QWidget,
)

from app.depot_review_display_v020_a6 import readable_depot_review
from app.result_tabs_v020_a6 import grouped_result_titles


_REVIEW_GROUP = 'Faglig vurdering'
_REVIEW_TITLES = ('Periodevurdering', 'Depotvurdering')


class CompactResultNavigation(QWidget):
    """Four short groups and direct buttons for professional assessments.

    Legacy tab indexes and programmatic navigation remain authoritative.
    """

    def __init__(self, tabs, parent):
        super().__init__(parent)
        self.setObjectName('v020_a6_result_navigation')
        self.tabs = tabs
        self.groups = grouped_result_titles(
            tabs.tabText(index) for index in range(tabs.count()))
        self._last_by_group = {}
        self._syncing = False
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 2, 0, 4)
        layout.setSpacing(5)

        self.group_tabs = QTabBar(self)
        self.group_tabs.setObjectName('v020_a6_result_groups')
        self.group_tabs.setExpanding(False)
        self.group_tabs.setUsesScrollButtons(True)
        self.group_tabs.setElideMode(Qt.TextElideMode.ElideRight)
        for name, _titles in self.groups:
            self.group_tabs.addTab(name)
        layout.addWidget(self.group_tabs)

        # Existing selection remains available for all OTHER result groups.
        # Hiding the whole container removes the otherwise confusing 'Visning:'
        # label when direct assessment buttons are displayed.
        self._choice_area = QWidget(self)
        chooser = QHBoxLayout(self._choice_area)
        chooser.setContentsMargins(0, 0, 0, 0)
        chooser.addWidget(QLabel('Visning:', self._choice_area))
        self.view_choice = QComboBox(self._choice_area)
        self.view_choice.setObjectName('v020_a6_result_choice')
        self.view_choice.setMinimumWidth(190)
        chooser.addWidget(self.view_choice)
        chooser.addStretch(1)
        layout.addWidget(self._choice_area)

        self._review_area = QWidget(self)
        self._review_area.setObjectName('v021_a16_2_assessment_buttons')
        review_row = QHBoxLayout(self._review_area)
        review_row.setContentsMargins(0, 0, 0, 0)
        review_row.setSpacing(8)
        self._review_button_group = QButtonGroup(self._review_area)
        self._review_button_group.setExclusive(True)
        self.review_buttons = {}
        available = next((titles for name, titles in self.groups
                          if name == _REVIEW_GROUP), ())
        for title in _REVIEW_TITLES:
            if title not in available:
                continue
            button = QPushButton(title, self._review_area)
            button.setObjectName(
                'v021_a16_2_period_review' if title == 'Periodevurdering'
                else 'v021_a16_2_depot_review'
            )
            button.setCheckable(True)
            button.setMinimumWidth(178)
            button.setAccessibleName(title)
            button.setToolTip('Vis ' + title.lower() + ' for valgt uttrekk')
            # Clearly visible selection in both light and dark themes. The
            # inactive state inherits the application's existing button style.
            button.setStyleSheet(
                'QPushButton:checked {'
                ' background-color: #286e55; color: #ffffff;'
                ' border: 2px solid #a7dac6; font-weight: bold;'
                ' padding: 7px 14px; min-height: 24px;'
                '}'
                'QPushButton:!checked { padding: 7px 14px; min-height: 24px; }'
            )
            self._review_button_group.addButton(button)
            button.clicked.connect(
                lambda _checked=False, chosen=title: self._choose_title(chosen)
            )
            self.review_buttons[title] = button
            review_row.addWidget(button)
        review_row.addStretch(1)
        layout.addWidget(self._review_area)

        tabs.currentChanged.connect(self.sync_from_original)
        self.group_tabs.currentChanged.connect(self._group_changed)
        self.view_choice.currentIndexChanged.connect(self._choice_changed)
        self.sync_from_original(tabs.currentIndex())

    def _group_for(self, title: str) -> int:
        return next((index for index, (_, choices) in enumerate(self.groups)
                     if title in choices), 0)

    def _update_assessment_buttons(self, group_index: int, title: str) -> None:
        """Only professional assessment pages use direct buttons."""
        is_review = (
            0 <= group_index < len(self.groups)
            and self.groups[group_index][0] == _REVIEW_GROUP
            and bool(self.review_buttons)
        )
        self._choice_area.setVisible(not is_review)
        self._review_area.setVisible(is_review)
        for name, button in self.review_buttons.items():
            button.setChecked(is_review and name == title)

    def sync_from_original(self, index):
        if self._syncing or index < 0 or index >= self.tabs.count():
            return
        self._syncing = True
        try:
            title = self.tabs.tabText(index)
            group_index = self._group_for(title)
            self._last_by_group[group_index] = title
            self.group_tabs.blockSignals(True)
            self.group_tabs.setCurrentIndex(group_index)
            self.group_tabs.blockSignals(False)
            self.view_choice.blockSignals(True)
            self.view_choice.clear()
            for name in self.groups[group_index][1]:
                self.view_choice.addItem(name, name)
            self.view_choice.setCurrentIndex(self.view_choice.findData(title))
            self.view_choice.blockSignals(False)
            self._update_assessment_buttons(group_index, title)
        finally:
            self._syncing = False

    def _choose_title(self, title):
        for index in range(self.tabs.count()):
            if self.tabs.tabText(index) == title:
                self.tabs.setCurrentIndex(index)
                return

    def _group_changed(self, index):
        if self._syncing or index < 0 or index >= len(self.groups):
            return
        options = self.groups[index][1]
        if not options:
            return
        title = self._last_by_group.get(index)
        self._choose_title(title if title in options else options[0])

    def _choice_changed(self, _index):
        if not self._syncing and self.view_choice.currentData():
            self._choose_title(str(self.view_choice.currentData()))


class ReadableDepotDetails:
    """Keep the original JSON detail and decision services; offer a readable default."""

    def __init__(self, panel):
        self.panel = panel
        self._updating = False
        controls = QHBoxLayout()
        controls.addWidget(QLabel('Vurderingsgrunnlag:', panel))
        self.raw = QCheckBox('Vis rå JSON', panel)
        self.raw.setObjectName('v020_a6_raw_depot_details')
        controls.addWidget(self.raw)
        controls.addStretch(1)
        position = panel.layout().indexOf(panel.splitter)
        panel.layout().insertLayout(position, controls)
        self.raw.toggled.connect(self.refresh)
        panel.detail.textChanged.connect(self.refresh)
        self.refresh()

    def refresh(self, *_ignored):
        if self._updating:
            return
        row = self.panel.current_row()
        if self.raw.isChecked():
            from .depot_review_v019_a2 import _render, _review_payload
            text = _render(_review_payload(row)) if row is not None else ''
        else:
            text = readable_depot_review(row)
        if self.panel.detail.toPlainText() == text:
            return
        self._updating = True
        try:
            self.panel.detail.setPlainText(text)
            self.panel.detail.moveCursor(QTextCursor.MoveOperation.Start)
        finally:
            self._updating = False


def install_compact_result_navigation(viewer):
    """Apply once to a fully constructed legacy result center; no data writes."""
    if getattr(viewer, '_v020_a6_navigation', None) is not None:
        return viewer._v020_a6_navigation
    tabs = viewer.tabs
    nav = CompactResultNavigation(tabs, viewer)
    viewer.layout().insertWidget(viewer.layout().indexOf(tabs), nav)
    tabs.tabBar().hide()
    legacy_menu = getattr(viewer, 'tab_menu_button', None)
    if legacy_menu is not None:
        legacy_menu.hide()  # the four groups now expose all inherited tabs
    viewer._v020_a6_navigation = nav
    panel = getattr(viewer, '_a2_panel', None)
    if panel is not None:
        viewer._v020_a6_depot_details = ReadableDepotDetails(panel)
    from .result_side_layout_v020_a6 import install_responsive_side_panels
    install_responsive_side_panels(viewer)
    return nav
