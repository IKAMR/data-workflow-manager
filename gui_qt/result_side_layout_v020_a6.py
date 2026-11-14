"""a6 side-panel sizing for ordinary-width result windows.

Do not reparent the established Qt objects. Preserve native splitters,
read-only evidence, raw JSON and user-dragged panel sizes.
"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QTimer
from PySide6.QtGui import QTextOption
from PySide6.QtWidgets import QHeaderView, QPushButton, QTextEdit

from app.result_side_evidence_v020_a6 import readable_side_evidence
from .result_center_v018_a13 import DETAIL_ROLE, PATH_ROLE

_SIDE_TABS = ('Arkade 5', 'PRONOM', 'Periodevurdering')
_DEFAULT_TABLE_FRACTIONS = {
    'Arkade 5': 0.50,
    'PRONOM': 0.51,
    'Periodevurdering': 0.50,
}


def first_column_width(tree, *, max_width: int = 130) -> int:
    """Width for actual extraction labels, rather than a static 165 px."""
    metrics = tree.fontMetrics()
    header_item = tree.headerItem()
    title = header_item.text(0) if header_item is not None else 'Uttrekk'
    width = metrics.horizontalAdvance(title) + 26
    for i in range(min(tree.topLevelItemCount(), 80)):
        row = tree.topLevelItem(i)
        if row is not None and not row.isHidden():
            width = max(width, metrics.horizontalAdvance(row.text(0)) + 22)
    return max(77, min(max_width, width))


class ResponsiveSideResultPanels:
    """Only presentation changes; no files, reports or decisions are written."""

    def __init__(self, viewer):
        self.viewer = viewer
        self._pending = False
        self._rendering = False
        for title in _SIDE_TABS:
            tree = viewer._trees.get(title)
            splitter = viewer._a53_splitters.get(title)
            browser = viewer._a53_browsers.get(title)
            if tree is None or splitter is None or browser is None:
                continue
            tree.setMinimumWidth(230)
            browser.setMinimumWidth(285)
            browser.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
            browser.setWordWrapMode(QTextOption.WrapMode.WrapAtWordBoundaryOrAnywhere)
            tree.itemSelectionChanged.connect(lambda key=title: self._render_detail(key))
            tree.model().modelReset.connect(self._schedule)
            tree.model().rowsInserted.connect(self._schedule)
            page = viewer._pages.get(title)
            if page is not None:
                for button in page.findChildren(QPushButton):
                    if button.text() == 'Auto størrelse':
                        button.clicked.connect(self._schedule)
        viewer.tabs.currentChanged.connect(self._schedule)
        self._schedule()

    def _schedule(self, *_unused):
        if self._pending:
            return
        self._pending = True
        QTimer.singleShot(0, self._apply)

    def _render_detail(self, title):
        if self._rendering:
            return
        viewer = self.viewer
        tree = viewer._trees.get(title)
        browser = viewer._a53_browsers.get(title)
        if tree is None or browser is None:
            return
        item = tree.currentItem()
        if item is None or item.text(0).startswith(
                ('Ingen lagret evidens', 'Ingen tilgjengelig Work')):
            browser.clear()
            return
        # Keep the inherited Markdown renderer for Markdown source files.
        source = str(item.data(0, PATH_ROLE) or '')
        if Path(source).suffix.lower() in ('.md', '.markdown'):
            return
        self._rendering = True
        try:
            browser.setHtml(readable_side_evidence(item.data(0, DETAIL_ROLE)))
        finally:
            self._rendering = False

    def _apply(self):
        self._pending = False
        viewer = self.viewer
        title = viewer.tabs.tabText(viewer.tabs.currentIndex())
        if title not in _SIDE_TABS:
            return
        tree = viewer._trees.get(title)
        splitter = viewer._a53_splitters.get(title)
        if tree is None or splitter is None:
            return
        tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
        tree.setColumnWidth(0, first_column_width(tree))
        self._render_detail(title)

        # Preserve a manually dragged position. The existing Auto button
        # clears this key, then our scheduled pass applies the new default.
        setting = 'qt/result_splitter_fraction_horizontal/' + title
        if viewer._a4_settings.value(setting, None) is not None:
            return
        sizes = splitter.sizes()
        if len(sizes) != 3 or sum(sizes) < 420:
            return
        first = round(sum(sizes) * _DEFAULT_TABLE_FRACTIONS[title])
        last = sum(sizes) - first
        mode = viewer._a53_mode_selectors[title].currentIndex()
        target = [first, last, 0] if mode == 0 else [first, 0, last]
        if all(abs(a - b) <= 3 for a, b in zip(sizes, target)):
            return
        old_flag = viewer._a53_setting_layout
        viewer._a53_setting_layout = True
        try:
            splitter.setSizes(target)
        finally:
            viewer._a53_setting_layout = old_flag


def install_responsive_side_panels(viewer):
    old = getattr(viewer, '_v020_a6_side_panels', None)
    if old is not None:
        return old
    if not all(hasattr(viewer, name) for name in
               ('_a53_splitters', '_a53_browsers', '_a53_mode_selectors', '_trees')):
        return None
    handle = ResponsiveSideResultPanels(viewer)
    viewer._v020_a6_side_panels = handle
    return handle
