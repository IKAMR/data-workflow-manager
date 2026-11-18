"""Severity-aware Qt console messages and an accessible diagnostics window.

Qt warnings remain in the original stderr stream. Small, known Windows frame
rounding is not raised as a red alert; significant geometry failures remain
visible. A10.2 replaces QMessageBox's tiny details pane with a resizable
viewer whose entire text can be copied and whose size is remembered.
"""
from __future__ import annotations

import re

# Native Windows per-monitor DPI changes can change the main-window client
# dimensions by ~1-3% without losing content.  The older fixed 24-pixel
# threshold incorrectly marked a 26-pixel height adjustment on DISPLAY1 as
# a red error.  Keep the ordinary threshold for every other widget.
_MAIN_WINDOW_GEOMETRY = re.compile(r'on QWidgetWindow/"DwmMainWindowWindow"')

_GEOMETRY_WARNING = re.compile(
    r'QWindowsWindow::setGeometry: Unable to set geometry '
    r'(\d+)x(\d+)\+(-?\d+)\+(-?\d+) '
    r'\(frame: .*?\) .*?Resulting geometry: '
    r'(\d+)x(\d+)\+(-?\d+)\+(-?\d+)',
    re.DOTALL,
)


def is_minor_windows_geometry_adjustment(message: str, *, tolerance: int = 24) -> bool:
    """Ignore only harmless native client-size corrections, not real Qt errors.

    Qt/Windows changes main-window size slightly when a window moves between
    monitors with different DPI/title-bar metrics.  Position changes remain
    limited to the original absolute tolerance.  Only a recognized DWM main
    window may use up to 3% of its requested client width/height (maximum 48
    logical pixels); other dialogs keep the established 24-pixel limit.
    """
    content = str(message)
    match = _GEOMETRY_WARNING.search(content)
    if not match:
        return False
    original = [int(n) for n in match.groups()[:4]]
    resulting = [int(n) for n in match.groups()[4:]]
    if _MAIN_WINDOW_GEOMETRY.search(content) and min(original[:2]) >= 600:
        size_limits = [max(tolerance, min(48, (length * 3 + 99) // 100))
                       for length in original[:2]]
        limits = size_limits + [tolerance, tolerance]
    else:
        limits = [tolerance] * 4
    return all(abs(a - b) <= limit for a, b, limit in zip(original, resulting, limits))


def should_flag_qt_message(message_type: int, message: str = '') -> bool:
    """QtMsgType: Debug=0, Warning=1, Critical=2, Fatal=3, Info=4."""
    severity = int(getattr(message_type, 'value', message_type))
    if severity not in (1, 2, 3):
        return False
    if severity == 1 and is_minor_windows_geometry_adjustment(message):
        return False
    return True


def show_console_diagnostics(main, messages) -> None:
    """Show the full stored Qt messages, never truncate or alter them."""
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import (
        QApplication, QDialog, QHBoxLayout, QLabel, QPlainTextEdit,
        QPushButton, QVBoxLayout,
    )
    from app.window_geometry_v022_a10_2 import bounded_dialog_size

    details = '\n\n'.join(str(message) for message in messages)
    dialog = QDialog(main)
    dialog.setObjectName('a102_console_diagnostics')
    dialog.setWindowTitle('Advarsler fra konsollen – detaljer')
    dialog.setWindowFlag(Qt.WindowType.WindowMaximizeButtonHint, True)
    dialog.setSizeGripEnabled(True)
    screen = main.screen() or QApplication.primaryScreen()
    available = screen.availableGeometry() if screen else None
    config = getattr(main, 'config', None)
    def saved_number(key, default):
        if config is None:
            return default
        try:
            return int(config.value(key, default))
        except (TypeError, ValueError):
            return default
    width, height = bounded_dialog_size(
        saved_number('qt/a102_console_width', 900),
        saved_number('qt/a102_console_height', 540),
        available.width() if available else 1280,
        available.height() if available else 800,
    )
    dialog.resize(width, height)
    dialog.setMinimumSize(min(520, width), min(300, height))
    layout = QVBoxLayout(dialog)
    description = QLabel(f'{len(messages)} konsolladvarsel(er) registrert. '
                         'Meldingene er teknisk diagnostikk og betyr ikke '
                         'automatisk at Noark 5-kontrollen har feilet.', dialog)
    description.setWordWrap(True)
    layout.addWidget(description)
    viewer = QPlainTextEdit(dialog)
    viewer.setObjectName('a102_console_details')
    viewer.setReadOnly(True)
    viewer.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth)
    viewer.setPlainText(details)
    layout.addWidget(viewer, 1)
    footer = QHBoxLayout()
    copy_button = QPushButton('Kopier alle detaljer', dialog)
    copy_button.clicked.connect(lambda _checked=False: QApplication.clipboard().setText(details))
    footer.addWidget(copy_button)
    toggle_button = QPushButton('Skjul detaljer', dialog)
    def toggle_details(_checked=False):
        visible = not viewer.isVisible()
        viewer.setVisible(visible)
        toggle_button.setText('Skjul detaljer' if visible else 'Vis detaljer')
    toggle_button.clicked.connect(toggle_details)
    footer.addWidget(toggle_button)
    footer.addStretch(1)
    close_button = QPushButton('Lukk', dialog)
    close_button.clicked.connect(dialog.accept)
    footer.addWidget(close_button)
    layout.addLayout(footer)
    if available is not None:
        # Position on the owner's screen, using Qt's logical coordinates.
        owner = main.frameGeometry().center()
        x = max(available.x() + 12,
                min(owner.x() - width // 2, available.right() - width - 12))
        y = max(available.y() + 20,
                min(owner.y() - height // 2, available.bottom() - height - 20))
        dialog.move(x, y)
    dialog.exec()
    if config is not None and not dialog.isMaximized():
        config.setValue('qt/a102_console_width', dialog.width())
        config.setValue('qt/a102_console_height', dialog.height())


def install_console_alert(main, navigation):
    from PySide6.QtCore import QObject, Signal, Qt, qInstallMessageHandler
    from PySide6.QtWidgets import QPushButton
    import sys

    class Bridge(QObject):
        received = Signal(str)

    bridge = Bridge(main)
    messages = []
    indicator = QPushButton('⚑ Konsoll', main)
    indicator.setObjectName('a14_console_alert')
    indicator.setToolTip('Reelle Qt-advarsler og feil i DWM. Klikk for detaljer.')
    indicator.setStyleSheet(
        'QPushButton { color: white; background-color: #a62929; '
        'font-weight: bold; border: 1px solid #f59b9b; }')
    indicator.setVisible(False)
    navigation.addWidget(indicator)

    def on_message(message):
        messages.append(message)
        if len(messages) > 40:
            del messages[:-40]
        indicator.setText(f'⚑ Konsoll ({len(messages)})')
        indicator.setVisible(True)

    bridge.received.connect(on_message, Qt.ConnectionType.QueuedConnection)

    def show_messages():
        if not messages:
            return
        show_console_diagnostics(main, tuple(messages))
        messages.clear()
        indicator.setVisible(False)
    indicator.clicked.connect(show_messages)

    previous = [None]
    def handler(kind, context, message):
        if should_flag_qt_message(kind, message):
            bridge.received.emit(str(message))
        if previous[0] is not None:
            previous[0](kind, context, message)
        else:
            # Installing a handler replaces Qt's default stderr logger.
            try:
                sys.__stderr__.write(str(message) + '\n')
            except (AttributeError, OSError, ValueError):
                pass

    previous[0] = qInstallMessageHandler(handler)
    bridge.destroyed.connect(lambda _obj=None: qInstallMessageHandler(previous[0]))
    main._a14_console_qt_handler = handler
    main._a14_console_bridge = bridge
    return indicator
