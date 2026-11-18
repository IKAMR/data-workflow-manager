"""Scoped combobox anchor: a10 fixes Setup dropdowns without global Qt filters.

A previous app-wide event filter was intentionally disabled after Windows
stability problems. Install this only on the two Setup workflow combo popups.
"""
from __future__ import annotations

from gui_qt.combobox_popup_v020_a2 import dropdown_origin


def anchor_setup_combo(combo) -> None:
    from PySide6.QtCore import QObject, QEvent, QPoint, QTimer, Qt
    from PySide6.QtGui import QGuiApplication

    if getattr(combo, '_a10_popup_anchor', None) is not None:
        return
    popup = combo.view().window()

    class _LocalAnchor(QObject):
        def __init__(self, owner):
            super().__init__(owner)
            self.moving = False

        def reposition(self):
            if self.moving:
                return
            try:
                if not combo.isVisible() or not popup.isVisible():
                    return
                local = combo.mapToGlobal(QPoint(0, 0))
                center = combo.mapToGlobal(QPoint(combo.width() // 2, combo.height() // 2))
                screen = QGuiApplication.screenAt(center) or combo.screen()
                if screen is None:
                    return
                b = screen.availableGeometry()
                x, y = dropdown_origin(
                    local.x(), local.y(), combo.width(), combo.height(),
                    popup.width(), popup.height(), b.x(), b.y(), b.width(), b.height(),
                    right_to_left=combo.layoutDirection() == Qt.LayoutDirection.RightToLeft,
                )
                destination = QPoint(x, y)
                if popup.pos() != destination:
                    self.moving = True
                    try:
                        popup.move(destination)
                    finally:
                        self.moving = False
            except RuntimeError:
                pass  # Popup may have been destroyed by Qt.

        def eventFilter(self, watched, event):
            if watched is not popup or self.moving:
                return False
            if event.type() in (QEvent.Type.Show, QEvent.Type.Move, QEvent.Type.Resize):
                self.reposition()
                if event.type() == QEvent.Type.Show:
                    QTimer.singleShot(0, self.reposition)
                    QTimer.singleShot(50, self.reposition)
            return False

    anchor = _LocalAnchor(combo)
    combo._a10_popup_anchor = anchor
    popup.installEventFilter(anchor)
