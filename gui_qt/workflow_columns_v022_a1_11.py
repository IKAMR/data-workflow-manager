"""v0.2.2-a1.11: manually adjustable columns in Advanced > Arbeidsflyt.

The established QTreeWidget, operations, selected job, and runner are reused.
Only presentation is changed: Qt's previous Stretch/ResizeToContents
header policy prevented dragging column boundaries. User widths are stored
under the existing Qt window preferences, not in .n5jobs or Work.

Keep PySide6 imports local so pure width validation can run headlessly.
"""
from __future__ import annotations

import json


PREFERENCE_KEY = 'qt/a111_workflow_column_widths'
DEFAULT_WIDTHS = (38, 300, 88, 72)  # #, Deljobb, Status, Stopp
MIN_WIDTH = 30
MAX_WIDTH = 1200


def column_widths(raw: object) -> tuple[int, int, int, int]:
    """Read version-tolerant QSettings content; never apply corrupt widths."""
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except (ValueError, TypeError):
            return DEFAULT_WIDTHS
    if not isinstance(raw, (list, tuple)) or len(raw) != len(DEFAULT_WIDTHS):
        return DEFAULT_WIDTHS
    if any(type(width) is not int for width in raw):
        return DEFAULT_WIDTHS
    return tuple(max(MIN_WIDTH, min(MAX_WIDTH, width)) for width in raw)


def serialize_widths(widths) -> str:
    return json.dumps(list(column_widths(widths)), separators=(',', ':'))


def install_editable_workflow_columns(window) -> bool:
    """Unlock and remember *all four* Arbeitsflyt columns, once per window.

    Interactive header sections can be dragged. Double-clicking a divider
    invokes Qt's standard resize-to-contents, but only on explicit request.
    Fixed widths intentionally exceed a narrow dock's width, so Qt can offer
    a horizontal scrollbar rather than clipping full operation names.
    """
    if getattr(window, '_a111_workflow_columns_installed', False):
        return False

    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QHeaderView

    tree = window.workflow_tree
    header = tree.header()
    header.setStretchLastSection(False)
    header.setSectionsMovable(False)
    header.setMinimumSectionSize(MIN_WIDTH)
    for index in range(len(DEFAULT_WIDTHS)):
        header.setSectionResizeMode(index, QHeaderView.ResizeMode.Interactive)

    stored = window.config.value(PREFERENCE_KEY, None)
    sizes = column_widths(stored)
    for index, width in enumerate(sizes):
        header.resizeSection(index, width)

    # Only the user can decide that a narrower column should hide content.
    # Qt presents a horizontal scrollbar if the dock is too narrow.
    tree.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
    tree.setTextElideMode(Qt.TextElideMode.ElideRight)
    header.setToolTip(
        'Dra kolonnegrensene for å justere bredden. '
        'Dobbeltklikk en grense for å tilpasse til innholdet.'
    )

    def remember_width(_index: int, _old: int, _new: int) -> None:
        if not window.isVisible():
            return  # Ignore the first native layout/show event.
        current = tuple(header.sectionSize(i) for i in range(len(DEFAULT_WIDTHS)))
        window.config.setValue(PREFERENCE_KEY, serialize_widths(current))

    def fit_column(index: int) -> None:
        if 0 <= index < len(DEFAULT_WIDTHS):
            tree.resizeColumnToContents(index)
            # Cap the result; very long source descriptions must not create
            # columns wider than an ordinary monitor.
            if header.sectionSize(index) > MAX_WIDTH:
                header.resizeSection(index, MAX_WIDTH)

    header.sectionResized.connect(remember_width)
    header.sectionDoubleClicked.connect(fit_column)

    # Existing workflow tooltips show only operation ID/category. Retain them,
    # but prepend the full visible name when a row is hovered.
    tree.setMouseTracking(True)

    def show_full_operation_name(item, _column: int) -> None:
        if item is None:
            return
        name = item.text(1)
        old = item.toolTip(1)
        if name and not old.startswith(name + '\n') and old != name:
            item.setToolTip(1, name + ('\n' + old if old else ''))

    tree.itemEntered.connect(show_full_operation_name)
    window._a111_workflow_columns_installed = True
    return True
