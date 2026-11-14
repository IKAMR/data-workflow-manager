"""Keep Qt QComboBox popups beside their control on every DWM Qt screen.

Qt/Windows can reposition the private QComboBox popup *after* displaying it,
particularly when the combo lives inside a scrolled Setup tab. A stylesheet
hint alone does not prevent that second move. Observe the real Qt.Popup window
and correct Show, Move and Resize events (including delayed native moves).

This is a GUI-only filter: it never replaces a model, changes the selected
value, makes a popup modal, or affects non-combobox windows. It is installed
once on QApplication and also covers comboboxes created later by dialogs.
"""
from __future__ import annotations


def dropdown_origin(
    combo_x: int, combo_y: int, combo_width: int, combo_height: int,
    popup_width: int, popup_height: int,
    screen_x: int, screen_y: int, screen_width: int, screen_height: int,
    *, right_to_left: bool = False,
) -> tuple[int, int]:
    """Global popup top-left in logical Qt pixels, clamped to one screen.

    Put the popup immediately below its combo when it fits, otherwise above
    if that side has more room. Use the combo's screen, not the popup's screen:
    the latter may have been moved incorrectly to another monitor already.
    """
    combo_width = max(0, int(combo_width))
    combo_height = max(0, int(combo_height))
    popup_width = max(1, int(popup_width))
    popup_height = max(1, int(popup_height))
    screen_width = max(1, int(screen_width))
    screen_height = max(1, int(screen_height))
    screen_right = screen_x + screen_width
    screen_bottom = screen_y + screen_height

    x = combo_x + combo_width - popup_width if right_to_left else combo_x
    x = max(screen_x, min(x, screen_right - min(popup_width, screen_width)))

    below_y = combo_y + combo_height
    above_y = combo_y - popup_height
    room_below = max(0, screen_bottom - below_y)
    room_above = max(0, combo_y - screen_y)
    if popup_height <= room_below or room_below >= room_above:
        y = below_y
    else:
        y = above_y
    y = max(screen_y, min(y, screen_bottom - min(popup_height, screen_height)))
    return (x, y)


def install_dropdown_positioning(application, window=None) -> None:
    """Install a single application-wide filter without altering Qt themes.

    ``window`` is accepted for backwards compatibility with the a2 entrypoint;
    the filter is registered on QApplication to cover all future Setup dialogs.
    """
    if getattr(application, '_dwm_popup_anchor', None) is not None:
        return

    from PySide6.QtCore import QObject, QEvent, QPoint, QTimer, Qt
    from PySide6.QtGui import QGuiApplication
    from PySide6.QtWidgets import QComboBox, QWidget

    relevant = (QEvent.Type.Show, QEvent.Type.Move, QEvent.Type.Resize)

    class _ComboPopupAnchor(QObject):
        def __init__(self, parent):
            super().__init__(parent)
            self._moving = False

        def _correct(self, combo, popup) -> None:
            if self._moving:
                return
            try:
                if not combo.isVisible() or not popup.isVisible():
                    return
                combo_pos = combo.mapToGlobal(QPoint(0, 0))
                center = combo.mapToGlobal(QPoint(combo.width() // 2, combo.height() // 2))
                screen = QGuiApplication.screenAt(center) or combo.screen()
                if screen is None:
                    return
                bounds = screen.availableGeometry()
                x, y = dropdown_origin(
                    combo_pos.x(), combo_pos.y(), combo.width(), combo.height(),
                    popup.width(), popup.height(), bounds.x(), bounds.y(),
                    bounds.width(), bounds.height(),
                    right_to_left=combo.layoutDirection() == Qt.LayoutDirection.RightToLeft,
                )
                target = QPoint(x, y)
                if popup.pos() != target:
                    self._moving = True
                    try:
                        popup.move(target)
                    finally:
                        self._moving = False
            except RuntimeError:
                # A dialog/popup may be destroyed before a queued correction.
                return

        def eventFilter(self, obj, event) -> bool:
            if self._moving or event.type() not in relevant:
                return False
            # Qt creates QComboBoxPrivateContainer as QFrame(combo, Qt.Popup).
            # Filtering by its *parent combo* avoids touching menus, tooltips,
            # file chooser dialogs and any other popups in the application.
            if not isinstance(obj, QWidget) or not obj.isWindow():
                return False
            combo = obj.parentWidget()
            if not isinstance(combo, QComboBox):
                return False
            if not (obj.windowFlags() & Qt.WindowType.Popup):
                return False
            self._correct(combo, obj)
            if event.type() == QEvent.Type.Show:
                # Native Qt can move the popup after it is first displayed.
                # Correct it once after Show has finished and again after the
                # first native event cycle; subsequent Move events are caught.
                QTimer.singleShot(0, lambda c=combo, p=obj: self._correct(c, p))
                QTimer.singleShot(50, lambda c=combo, p=obj: self._correct(c, p))
            return False

    anchor = _ComboPopupAnchor(application)
    application._dwm_popup_anchor = anchor  # Retain the Python QObject wrapper.
    application.installEventFilter(anchor)
