"""Read-only detail modes and adaptive layouts for the Qt result center.

The original QPlainTextEdit must stay a child of its original QSplitter.  Never
use replaceWidget(), deleteLater() or reparenting: those invalidated the PySide6
C++ object in a5.3/a5.4.  The readable browser is a sibling, with a tab bar
for switching between the two viewers.

Arkade, PRONOM and period evidence use a full-height detail panel on the right;
other result tables use an automatic vertical split. Manual splitter settings
are stored per tab and layout direction and can be reset to automatic sizing.
"""
from __future__ import annotations

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QHBoxLayout, QLabel, QPlainTextEdit, QPushButton, QSplitter, QTabBar,
    QTextBrowser,
)

from app.result_display_v0110_a5 import (
    default_table_fraction, read_work_markdown, readable_html,
)
from .result_center_v018_a13 import DETAIL_ROLE, PATH_ROLE

_SIDE_DETAIL_TABS = frozenset({'Arkade 5', 'PRONOM', 'Periodevurdering'})
_SIDE_FRACTIONS = {'Arkade 5': 0.61, 'PRONOM': 0.65, 'Periodevurdering': 0.58}


class _NoExternalResourceBrowser(QTextBrowser):
    """Never fetch remote/local resources referenced by untrusted evidence."""

    def loadResource(self, resource_type, name):
        return None


class ResultDetailModesMixin:
    def _a53_install_details(self):
        self._a53_details_ready = False
        self._a53_splitters = {}
        self._a53_browsers = {}
        self._a53_mode_selectors = {}
        self._a53_setting_layout = False
        try:
            mode = int(self._a4_settings.value('qt/result_detail_mode', 0) or 0)
        except (ValueError, TypeError):
            mode = 0
        if mode not in (0, 1):
            mode = 0

        for tab, tree in self._trees.items():
            splitter = tree.parentWidget()
            raw = self._details.get(tab)
            if not isinstance(splitter, QSplitter) or not isinstance(raw, QPlainTextEdit):
                continue

            # Keep the original raw editor in its original splitter: this
            # prevents the libshiboken "already deleted" crash from a5.3.
            browser = _NoExternalResourceBrowser()
            browser.setOpenLinks(False)
            browser.setOpenExternalLinks(False)
            browser.setReadOnly(True)
            browser.setPlaceholderText('Velg en rad for detaljer og lagret evidens.')
            splitter.insertWidget(1, browser)  # [table, readable, original raw]
            if tab in _SIDE_DETAIL_TABS:
                splitter.setOrientation(Qt.Orientation.Horizontal)
            splitter.setChildrenCollapsible(False)

            controls = QHBoxLayout()
            controls.addWidget(QLabel('Detaljer og evidens'))
            controls.addStretch(1)
            reset = QPushButton('Auto størrelse')
            reset.setToolTip('Tilpass panelene automatisk etter resultatene. '
                             'Nullstiller manuell panelstørrelse for denne fanen.')
            reset.clicked.connect(lambda _checked=False, key=tab: self._a53_auto_size(key))
            controls.addWidget(reset)
            selector = QTabBar()
            selector.addTab('Lesbar visning')
            selector.addTab('Råtekst / JSON')
            selector.setExpanding(False)
            selector.setToolTip('Lesbar presentasjon eller original kilde-/JSON-struktur. '
                               'Markdown vises formatert eller som kildetekst.')
            controls.addWidget(selector)
            page_layout = self._pages[tab].layout()
            insert_at = page_layout.indexOf(splitter)
            page_layout.insertLayout(insert_at if insert_at >= 0 else 0, controls)

            self._a53_splitters[tab] = splitter
            self._a53_browsers[tab] = browser
            self._a53_mode_selectors[tab] = selector
            if mode == 0:
                raw.hide()
                browser.show()
            else:
                browser.hide()
                raw.show()
            selector.setCurrentIndex(mode)
            selector.currentChanged.connect(
                lambda idx, key=tab: self._a53_select_detail_mode(key, idx))
            splitter.splitterMoved.connect(
                lambda _position, _index, key=tab: self._a53_store_splitter(key))

        self._a53_details_ready = True
        self.tabs.currentChanged.connect(self._a53_schedule_splitter)
        self._a53_schedule_splitter()

    def _a53_select_detail_mode(self, tab, index):
        if index not in (0, 1):
            return
        self._a4_settings.setValue('qt/result_detail_mode', index)
        self._a53_setting_layout = True
        try:
            for key, browser in self._a53_browsers.items():
                raw = self._details[key]
                if index == 0:
                    browser.show()
                    raw.hide()
                else:
                    raw.show()
                    browser.hide()
                selector = self._a53_mode_selectors[key]
                if selector.currentIndex() != index:
                    selector.blockSignals(True)
                    try:
                        selector.setCurrentIndex(index)
                    finally:
                        selector.blockSignals(False)
        finally:
            self._a53_setting_layout = False
        self._a53_schedule_splitter()

    def _show_detail(self, tab: str):
        # Base class writes to the original raw editor; never replace it.
        super()._show_detail(tab)
        if not getattr(self, '_a53_details_ready', False):
            return
        browser = self._a53_browsers.get(tab)
        if browser is None:
            return
        item = self._trees[tab].currentItem()
        if item is None or item.text(0).startswith(('Ingen lagret evidens',
                                                     'Ingen tilgjengelig Work')):
            browser.clear()
            return
        value = item.data(0, DETAIL_ROLE)
        markdown = read_work_markdown(
            item.data(0, PATH_ROLE), (shot.job.work for shot in self._snapshots))
        if markdown is not None:
            self._details[tab].setPlainText(markdown)
            browser.setMarkdown(markdown)
        else:
            browser.setHtml(readable_html(value))

    def _a53_fraction_key(self, tab):
        if tab in _SIDE_DETAIL_TABS:
            return 'qt/result_splitter_fraction_horizontal/' + tab
        return 'qt/result_splitter_fraction/' + tab

    def _a53_auto_size(self, tab):
        """Explicitly forget an old manually dragged size for this tab."""
        self._a4_settings.remove(self._a53_fraction_key(tab))
        if tab == self.tabs.tabText(self.tabs.currentIndex()):
            self._a53_schedule_splitter()

    def _a53_schedule_splitter(self, _index=None):
        if getattr(self, '_a53_details_ready', False):
            QTimer.singleShot(0, self._a53_apply_splitter)

    def _a53_apply_splitter(self):
        tab = self.tabs.tabText(self.tabs.currentIndex())
        splitter = self._a53_splitters.get(tab)
        table = self._trees.get(tab)
        if splitter is None or table is None:
            return
        lengths = splitter.sizes()
        # The readable and raw viewers are siblings, one hidden at any time.
        if len(lengths) != 3:
            return
        total = sum(lengths)
        if total < 200:
            return
        saved = self._a4_settings.value(self._a53_fraction_key(tab), None)
        ratio = None
        if saved is not None:
            try:
                ratio = float(saved)
                if not 0.12 <= ratio <= 0.85:
                    ratio = None
            except (ValueError, TypeError):
                ratio = None
        if ratio is None:
            if tab in _SIDE_DETAIL_TABS:
                ratio = _SIDE_FRACTIONS.get(tab, 0.60)
            else:
                count = sum(
                    not table.topLevelItem(i).isHidden()
                    and not table.topLevelItem(i).text(0).startswith(
                        ('Ingen lagret evidens', 'Ingen tilgjengelig Work'))
                    for i in range(table.topLevelItemCount())
                )
                # Fit a few rows closely; give long result lists a bounded
                # share. The remaining height is always usable for details.
                try:
                    header = max(24, table.header().height())
                    row = int(table.sizeHintForRow(0)) if count else 0
                    if row < 14:
                        row = max(17, table.fontMetrics().height() + 4)
                except (AttributeError, RuntimeError, TypeError, ValueError):
                    header, row = 30, 20
                target = header + count * row + 14
                max_fraction = 0.60 if tab == 'Arkivdeler' else 0.64
                ratio = max(0.12, min(max_fraction, target / total))
                if count == 0:
                    ratio = min(ratio, default_table_fraction(count, tab=tab))
        upper = int(total * ratio)
        lower = total - upper
        mode = self._a53_mode_selectors[tab].currentIndex()
        sizes = [upper, lower, 0] if mode == 0 else [upper, 0, lower]
        self._a53_setting_layout = True
        try:
            splitter.setSizes(sizes)
        finally:
            self._a53_setting_layout = False

    def _a53_store_splitter(self, tab):
        if (not getattr(self, '_a53_details_ready', False)
                or self._a53_setting_layout):
            return
        sizes = self._a53_splitters[tab].sizes()
        total = sum(sizes)
        if total >= 200 and sizes[0] > 0 and sum(sizes[1:]) > 0:
            ratio = sizes[0] / total
            self._a4_settings.setValue(self._a53_fraction_key(tab), round(ratio, 4))

    def showEvent(self, event):
        super().showEvent(event)
        self._a53_schedule_splitter()
