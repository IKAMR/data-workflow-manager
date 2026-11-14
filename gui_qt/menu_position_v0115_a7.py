"""Correct main QMenu popups displaced by the global dialog position handler.

The old global position handler treats all top-level QWidget windows as dialogs.
A QMenu is also a top-level QWidget and must be anchored to its QMenuBar action.
We correct only main menu popups, not independent dialogs or submenu geometry.
"""
from __future__ import annotations

from PySide6.QtCore import QObject, QEvent, QTimer, QPoint
from PySide6.QtWidgets import QMenu


def menu_anchor(menu_bar, action, menu):
    """Screen coordinates of the corresponding main-menu action."""
    rect = menu_bar.actionGeometry(action)
    return menu_bar.mapToGlobal(QPoint(rect.left(), rect.bottom() + 1))


class MainMenuPlacementGuard(QObject):
    def __init__(self, window):
        super().__init__(window)
        self.window = window
        self.bar = window.menuBar()
        self._menus = {}
        for action in self.bar.actions():
            menu = action.menu()
            if menu is not None:
                self._menus[menu] = action
                menu.installEventFilter(self)

    def eventFilter(self, watched, event):
        if event.type() == QEvent.Type.Show and watched in self._menus:
            # The legacy application-wide handler may move menus on Show; defer
            # until the event has finished so the native menu ends at its anchor.
            QTimer.singleShot(0, lambda menu=watched: self._restore(menu))
        return False

    def _restore(self, menu):
        if not isinstance(menu, QMenu) or not menu.isVisible():
            return
        action = self._menus.get(menu)
        if action is None:
            return
        desired = menu_anchor(self.bar, action, menu)
        screen = self.window.screen()
        if screen is not None:
            area = screen.availableGeometry()
            desired.setX(max(area.left(), min(desired.x(), area.right() - menu.width() + 1)))
            desired.setY(max(area.top(), min(desired.y(), area.bottom() - menu.height() + 1)))
        menu.move(desired)


def install_main_menu_guard(window):
    existing = getattr(window, '_a7_main_menu_guard', None)
    if existing is None:
        window._a7_main_menu_guard = MainMenuPlacementGuard(window)
    return window._a7_main_menu_guard
