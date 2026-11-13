"""DWM v0.1.14-a1: persistent main geometry and same-screen popup placement.

Qt-independent screen calculations are kept separate for regression tests.
The settings identity is intentionally unchanged: IKAMR / DWM-Qt.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Rect:
    x: int
    y: int
    width: int
    height: int

    @property
    def right(self):
        return self.x + self.width

    @property
    def bottom(self):
        return self.y + self.height

    @property
    def cx(self):
        return self.x + self.width // 2

    @property
    def cy(self):
        return self.y + self.height // 2


def screen_for_main(main: Rect, screens: list[Rect]) -> Rect:
    """Select the screen with most intersection, never the primary by default."""
    if not screens:
        raise ValueError('Ingen skjermer tilgjengelige')

    def score(screen: Rect):
        horizontal = max(0, min(main.right, screen.right) - max(main.x, screen.x))
        vertical = max(0, min(main.bottom, screen.bottom) - max(main.y, screen.y))
        return (horizontal * vertical,
                -(abs(screen.cx - main.cx) + abs(screen.cy - main.cy)))

    return max(screens, key=score)


def visible_on_any(rect: Rect, screens: list[Rect], *, minimum: int = 60) -> bool:
    return any(max(0, min(rect.right, s.right) - max(rect.x, s.x)) >= minimum
               and max(0, min(rect.bottom, s.bottom) - max(rect.y, s.y)) >= minimum
               for s in screens)


def restored_main_rect(saved: Rect, screens: list[Rect], *,
                       saved_screen: str = '', screen_names: tuple[str, ...] = (),
                       saved_relative: tuple[int, int] | None = None,
                       frame_padding: tuple[int, int] = (24, 72)) -> Rect:
    """Restore absolute virtual-desktop coordinates, including a second monitor.

    Qt's native restoreGeometry can be displaced when Windows has displays
    with different DPI or when the primary display differs from the last one.
    This calculation does not use the primary display if the saved rectangle
    still lies on a connected display.
    """
    if not screens:
        return saved
    # Prefer the user's explicitly saved screen, even when the saved window
    # straddles the seam and overlaps the primary laptop screen.
    target = next((screen for screen, name in zip(screens, screen_names)
                   if saved_screen and name == saved_screen), None)
    if target is None:
        visible = [screen for screen in screens if visible_on_any(saved, [screen])]
        target = screen_for_main(saved, visible) if visible else screens[0]
    # If the monitor was rearranged since last startup, use its relative
    # location within the monitor, not a stale virtual desktop origin.
    new_x, new_y = saved.x, saved.y
    if (saved_relative is not None and saved_screen and target in screens
            and target not in [screen for screen in screens
                               if visible_on_any(saved, [screen])]):
        new_x = target.x + saved_relative[0]
        new_y = target.y + saved_relative[1]
    # A correctly saved client rectangle on the same connected screen needs
    # no added inset. In particular, do not pull user-positioned windows
    # away from the top/right edge on a secondary widescreen.
    if (target.x <= new_x and target.y <= new_y and
            new_x + saved.width <= target.right and
            new_y + saved.height <= target.bottom):
        return Rect(new_x, new_y, saved.width, saved.height)
    # Only recover a rectangle that has genuinely left the available screen.
    # QWidget.move uses client coordinates; availableGeometry constrains the
    # complete decorated window, which may be larger on high-DPI Windows.
    pad_x, pad_y = frame_padding
    usable_w = max(1, target.width - max(0, pad_x))
    usable_h = max(1, target.height - max(0, pad_y))
    width = min(max(1, saved.width), usable_w)
    height = min(max(1, saved.height), usable_h)
    inset_x = max(0, pad_x // 2)
    inset_y = max(0, pad_y // 2)
    return Rect(max(target.x + inset_x, min(new_x, target.right - width - inset_x)),
                max(target.y + inset_y, min(new_y, target.bottom - height - inset_y)),
                width, height)


def popup_on_main_screen(main: Rect, wanted: tuple[int, int],
                         minimum: tuple[int, int], screens: list[Rect],
                         *, beside: bool = False, gap: int = 10) -> Rect:
    """Keep the *entire* popup on the main window's screen.

    In 'beside' mode use spare space on the same monitor, otherwise overlap.
    Never move to the laptop screen just because it has unused space.
    """
    screen = screen_for_main(main, screens)
    width = min(max(1, wanted[0], minimum[0]), screen.width)
    height = min(max(1, wanted[1], minimum[1]), screen.height)
    if beside:
        right_x = main.right + gap
        if right_x + width <= screen.right:
            return Rect(right_x, max(screen.y, min(main.cy - height // 2,
                                                 screen.bottom - height)), width, height)
        left_x = main.x - gap - width
        if left_x >= screen.x:
            return Rect(left_x, max(screen.y, min(main.cy - height // 2,
                                                screen.bottom - height)), width, height)
    x = max(screen.x, min(main.cx - width // 2, screen.right - width))
    y = max(screen.y, min(main.cy - height // 2, screen.bottom - height))
    return Rect(x, y, width, height)


def install_window_positions(main_window):
    """Install after main UI setup. Qt is imported only for runtime usage."""
    from PySide6.QtCore import QObject, QEvent, QTimer
    from PySide6.QtWidgets import QApplication, QDialog, QWidget

    def rect(qrect):
        return Rect(qrect.x(), qrect.y(), qrect.width(), qrect.height())

    class WindowPositionController(QObject):
        def __init__(self, main):
            super().__init__(main)
            self.main = main
            self._ready = False
            self._positioning = False
            self._save_timer = QTimer(self)
            self._save_timer.setSingleShot(True)
            self._save_timer.setInterval(450)
            self._save_timer.timeout.connect(self._save_main)
            self._result_viewer = None
            # Read these before any Qt startup/Show events can rewrite them.
            self._startup_rect = self._load_main_rect()
            self._startup_maximized = main.config.value(
                'qt/a14_main_maximized', False, type=bool)
            self._result_timer = QTimer(self)
            self._result_timer.setSingleShot(True)
            self._result_timer.setInterval(450)
            self._result_timer.timeout.connect(self._save_result)
            QApplication.instance().installEventFilter(self)
            main.installEventFilter(self)
            QTimer.singleShot(0, self._initialize)

        def _screens(self):
            return [rect(s.availableGeometry()) for s in QApplication.screens()]

        def _load_main_rect(self):
            config = self.main.config
            if not config.value('qt/a14_main_valid', False, type=bool):
                return None
            try:
                numbers = [int(config.value('qt/a14_main_' + part))
                           for part in ('x', 'y', 'width', 'height')]
                if numbers[2] < 100 or numbers[3] < 100:
                    return None
                return Rect(*numbers)
            except (TypeError, ValueError):
                return None

        def _main_screen_info(self, frame):
            displays = QApplication.screens()
            screen = screen_for_main(frame, self._screens())
            for display in displays:
                if rect(display.availableGeometry()) == screen:
                    return screen, display.name()
            return screen, ''

        def _initialize(self):
            main = self.main
            screens = self._screens()
            if not screens:
                self._ready = True
                return
            if self._startup_rect is not None:
                saved = self._startup_rect
                # A QMainWindow layout can impose a larger effective minimum
                # than its explicit minimumSize(), particularly with Windows
                # display scaling. Clamp using that minimum before move/resize.
                minimum = main.minimumSizeHint()
                saved = Rect(saved.x, saved.y,
                             max(saved.width, minimum.width()),
                             max(saved.height, minimum.height()))
                stored_screen = str(main.config.value('qt/a14_main_screen', '') or '')
                try:
                    relative = (int(main.config.value('qt/a14_main_offset_x')),
                                int(main.config.value('qt/a14_main_offset_y')))
                except (TypeError, ValueError):
                    relative = None
                destination = restored_main_rect(
                    saved, screens, saved_screen=stored_screen,
                    screen_names=tuple(s.name() for s in QApplication.screens()),
                    saved_relative=relative)
                # Reapply after Qt's native restoreGeometry: on Windows Qt may
                # otherwise reset a saved second-screen position to the laptop.
                # Qt already restores a saved geometry. Do not force another
                # native geometry request for differences of a few DPI pixels:
                # Windows rounds those and logs QWindowsWindow::setGeometry.
                if main.isMaximized() or main.isMinimized():
                    main.showNormal()
                current = rect(main.geometry())
                tolerance = 24  # Windows frame/title-bar and DPI rounding.
                if (abs(current.width - destination.width) > tolerance
                        or abs(current.height - destination.height) > tolerance):
                    main.resize(destination.width, destination.height)
                if (abs(current.x - destination.x) > tolerance
                        or abs(current.y - destination.y) > tolerance):
                    main.move(destination.x, destination.y)
                if self._startup_maximized:
                    main.showMaximized()
            else:
                # Compatibility with older saved Qt geometry, without allowing
                # a partial overlap to place the window between screens.
                area = screen_for_main(rect(main.frameGeometry()), screens)
                frame = rect(main.frameGeometry())
                if not visible_on_any(frame, screens):
                    main.move(area.x + 24, area.y + 24)
                elif not main.isMaximized():
                    corrected = restored_main_rect(frame, screens)
                    if corrected != frame:
                        main.resize(corrected.width, corrected.height)
                        main.move(corrected.x, corrected.y)
            self._ready = True
            self._save_timer.start()

        def _save_main(self):
            main = self.main
            if not self._ready or not main.isVisible() or main.isMinimized():
                return
            screens = self._screens()
            # normalGeometry is the last non-maximized size/position; do not
            # persist fullscreen bounds as the preferred restored window.
            geometry = main.normalGeometry() if main.isMaximized() else main.geometry()
            frame = rect(geometry)
            if not visible_on_any(frame, screens):
                return
            config = main.config
            config.setValue('qt/window_geometry', main.saveGeometry())
            for part, value in zip(('x', 'y', 'width', 'height'),
                                   (frame.x, frame.y, frame.width, frame.height)):
                config.setValue('qt/a14_main_' + part, value)
            target, name = self._main_screen_info(frame)
            config.setValue('qt/a14_main_screen', name)
            config.setValue('qt/a14_main_offset_x', frame.x - target.x)
            config.setValue('qt/a14_main_offset_y', frame.y - target.y)
            config.setValue('qt/a14_main_maximized', main.isMaximized())
            config.setValue('qt/a14_main_valid', True)
            config.sync()

        def register_result_window(self, viewer):
            """A result viewer is independent; persist its geometry separately."""
            self._result_viewer = viewer
            viewer.installEventFilter(self)
            saved = self.main.config.value('qt/a14_result_geometry')
            was_maximized = self.main.config.value(
                'qt/a14_result_maximized', False, type=bool)
            if saved:
                try:
                    viewer.showNormal()
                    viewer.restoreGeometry(saved)
                except (TypeError, ValueError, RuntimeError):
                    saved = None
            screen = screen_for_main(rect(self.main.frameGeometry()), self._screens())
            geo = rect(viewer.frameGeometry())
            on_screen = (geo.x >= screen.x and geo.y >= screen.y
                         and geo.right <= screen.right and geo.bottom <= screen.bottom)
            if not saved or not on_screen:
                viewer.showNormal()
                self._place(viewer)
            if was_maximized:
                # Maximize on the monitor where DWM is, not the laptop.
                viewer.showMaximized()
            self._result_timer.start()

        def _save_result(self):
            viewer = self._result_viewer
            if viewer is None:
                return
            try:
                if not viewer.isVisible() or viewer.isMinimized():
                    return
                self.main.config.setValue('qt/a14_result_geometry', viewer.saveGeometry())
                self.main.config.setValue('qt/a14_result_maximized', viewer.isMaximized())
                self.main.config.sync()
            except RuntimeError:
                self._result_viewer = None

        def _belongs_to_dwm(self, widget):
            parent = widget.parentWidget()
            while parent is not None:
                if parent is self.main:
                    return True
                parent = parent.parentWidget()
            # Result/report viewers can be top-level independent windows.
            title = (widget.windowTitle() or '').casefold()
            return any(name in title for name in (
                'resultatvisning', 'kjøredetalj', 'kjørelogg', 'depotrapport',
                'dwm -', 'data workflow manager',
            ))

        def _place(self, widget):
            if self._positioning or not self._belongs_to_dwm(widget):
                return
            screens = self._screens()
            if not screens:
                return
            # A popup on a monitor may be legitimately large; clamp to that
            # monitor rather than pushing it to another display.
            main_rect = rect(self.main.frameGeometry())
            minsize = widget.minimumSize()
            size = widget.size()
            title = (widget.windowTitle() or '').casefold()
            beside = any(word in title for word in ('resultatvisning', 'kjøredetalj', 'kjørelogg'))
            wanted = popup_on_main_screen(
                main_rect, (size.width(), size.height()),
                (max(100, minsize.width()), max(80, minsize.height())), screens,
                beside=beside,
            )
            self._positioning = True
            try:
                if widget.width() != wanted.width or widget.height() != wanted.height:
                    widget.resize(wanted.width, wanted.height)
                widget.move(wanted.x, wanted.y)
            finally:
                self._positioning = False

        def eventFilter(self, watched, event):
            kind = event.type()
            if watched is self._result_viewer:
                if kind in (QEvent.Type.Move, QEvent.Type.Resize,
                            QEvent.Type.WindowStateChange):
                    self._result_timer.start()
                elif kind == QEvent.Type.Close:
                    # Save synchronously while the viewer is still alive.
                    self._result_timer.stop()
                    self._save_result()
                    self._result_viewer = None
            if watched is self.main:
                # Moving without resizing must persist as well.
                if self._ready and kind in (QEvent.Type.Move, QEvent.Type.Resize,
                                            QEvent.Type.WindowStateChange):
                    self._save_timer.start()
                elif self._ready and kind == QEvent.Type.Close:
                    self._save_timer.stop()
                    self._save_main()
            elif isinstance(watched, QWidget) and watched.isWindow() and isinstance(watched, QDialog):
                if kind == QEvent.Type.Show and self._ready:
                    self._place(watched)
            elif isinstance(watched, QWidget) and watched.isWindow():
                if kind == QEvent.Type.Show and self._ready:
                    self._place(watched)
            return False

    return WindowPositionController(main_window)
