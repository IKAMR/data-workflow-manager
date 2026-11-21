"""Per-popup anchoring for QComboBox, without a QApplication event filter.

The old global Qt popup filter was disabled by default after intermittent native
startup faults.  A3 uses the same tested geometry, but observes only the actual
private popup windows belonging to discovered QComboBox widgets.  Future dialogs
are found through the ordinary focusChanged signal (not an event filter).
No model, selection, keyboard handling, theme or other popup is replaced.
"""
from __future__ import annotations

from gui_qt.combobox_popup_v020_a2 import dropdown_origin


def install_local_dropdown_anchors(application, main_window) -> None:
    """Attach safely to all present/future combo boxes, once per QApplication.

    Keep DWM_SAFE_MODE fully opt-out; this routine is called by the a3 main
    window only for real Qt widgets and only outside safe mode.
    """
    if getattr(application, '_dwm_local_combo_anchor_v024_a3', None) is not None:
        return

    from PySide6.QtCore import QObject, QEvent, QPoint, QTimer, Qt
    from PySide6.QtGui import QGuiApplication
    from PySide6.QtWidgets import QComboBox, QWidget

    watched = (QEvent.Type.Show, QEvent.Type.Move, QEvent.Type.Resize)
    marker = 'dwm_local_combo_anchor_v024_a3'

    class _Anchor(QObject):
        def __init__(self, parent):
            super().__init__(parent)
            self._correcting = False

        def _attach(self, combo):
            try:
                if not isinstance(combo, QComboBox):
                    return
                popup = combo.view().window()  # creates Qt's private popup
                if (not isinstance(popup, QWidget) or not popup.isWindow()
                        or not (popup.windowFlags() & Qt.WindowType.Popup)):
                    return
                if popup.property(marker):
                    return
                popup.installEventFilter(self)  # only this combo's own popup
                popup.setProperty(marker, True)
            except RuntimeError:
                return  # combo destroyed during a modal dialog transition

        def _focus_changed(self, _old, now):
            if now is None:
                return
            try:
                # Anchor only the combo being used. Creating private popup
                # containers for every combo on startup can destabilize Qt;
                # focusChanged also covers controls in future dialogs.
                parent = now
                while parent is not None:
                    if isinstance(parent, QComboBox):
                        self._attach(parent)
                        return
                    parent = parent.parentWidget()
            except RuntimeError:
                return

        def _correct(self, popup):
            if self._correcting:
                return
            try:
                combo = popup.parentWidget()
                if (not isinstance(combo, QComboBox) or not combo.isVisible()
                        or not popup.isVisible()):
                    return
                p = combo.mapToGlobal(QPoint(0, 0))
                center = combo.mapToGlobal(QPoint(combo.width() // 2, combo.height() // 2))
                screen = QGuiApplication.screenAt(center) or combo.screen()
                if screen is None:
                    return
                area = screen.availableGeometry()
                x, y = dropdown_origin(
                    p.x(), p.y(), combo.width(), combo.height(),
                    popup.width(), popup.height(),
                    area.x(), area.y(), area.width(), area.height(),
                    right_to_left=(combo.layoutDirection() == Qt.LayoutDirection.RightToLeft),
                )
                new_pos = QPoint(x, y)
                if popup.pos() != new_pos:
                    self._correcting = True
                    try:
                        popup.move(new_pos)
                    finally:
                        self._correcting = False
            except RuntimeError:
                return  # Qt object closed while a queued correction was pending

        def eventFilter(self, obj, event):
            if self._correcting or event.type() not in watched:
                return False
            if not isinstance(obj, QWidget):
                return False
            try:
                if not obj.property(marker):
                    return False
                if not isinstance(obj.parentWidget(), QComboBox):
                    return False
                if not (obj.windowFlags() & Qt.WindowType.Popup):
                    return False
                self._correct(obj)
                if event.type() == QEvent.Type.Show:
                    # Qt/Windows can relocate a popup once more after Show.
                    # The popup-local Move filter catches further native moves.
                    QTimer.singleShot(0, lambda p=obj: self._correct(p))
                    QTimer.singleShot(50, lambda p=obj: self._correct(p))
            except RuntimeError:
                return False
            return False

    anchor = _Anchor(application)
    application._dwm_local_combo_anchor_v024_a3 = anchor
    application.focusChanged.connect(anchor._focus_changed)
    # No eager popup creation. Mouse/keyboard focus installs on demand.
    focus = application.focusWidget()
    if focus is not None:
        anchor._focus_changed(None, focus)
