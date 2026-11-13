"""v0.1.14-a1 Fix 6: severity-aware Qt console warnings in Basic mode.

Only Qt warning/critical/fatal messages set the flag. Normal debug and info
messages do not imply an error. The original Qt console output is retained.
"""
from __future__ import annotations


# Windows sometimes rounds a requested client rectangle to fit its native
# title bar, borders, or current DPI. Keep these messages in stderr for
# diagnostics; only suppress the red alert for small, harmless adjustments.
import re

_GEOMETRY_WARNING = re.compile(
    r'QWindowsWindow::setGeometry: Unable to set geometry '
    r'(\d+)x(\d+)\+(-?\d+)\+(-?\d+) '
    r'\(frame: .*?\) .*?Resulting geometry: '
    r'(\d+)x(\d+)\+(-?\d+)\+(-?\d+)',
    re.DOTALL,
)


def is_minor_windows_geometry_adjustment(message: str, *, tolerance: int = 24) -> bool:
    """True only for a documented, bounded Qt/Windows geometry rounding."""
    match = _GEOMETRY_WARNING.search(str(message))
    if not match:
        return False
    original = [int(n) for n in match.groups()[:4]]
    resulting = [int(n) for n in match.groups()[4:]]
    return all(abs(a - b) <= tolerance for a, b in zip(original, resulting))


def should_flag_qt_message(message_type: int, message: str = '') -> bool:
    """QtMsgType: Debug=0, Warning=1, Critical=2, Fatal=3, Info=4."""
    severity = int(getattr(message_type, 'value', message_type))
    if severity not in (1, 2, 3):
        return False
    # Never silence a critical/fatal event, even if its wording is familiar.
    if severity == 1 and is_minor_windows_geometry_adjustment(message):
        return False
    return True


def install_console_alert(main, navigation):
    from PySide6.QtCore import QObject, Signal, Qt, qInstallMessageHandler
    from PySide6.QtWidgets import QPushButton, QMessageBox
    import sys

    class Bridge(QObject):
        received = Signal(str)

    bridge = Bridge(main)
    messages = []
    indicator = QPushButton('⚑ Konsoll', main)
    indicator.setObjectName('a14_console_alert')
    indicator.setToolTip('Reelle Qt-advarsler og feil i DWM. Klikk for detaljer.')
    indicator.setStyleSheet('QPushButton { color: white; background-color: #a62929; font-weight: bold; border: 1px solid #f59b9b; }')
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
        dialog = QMessageBox(main)
        dialog.setWindowTitle('Advarsler fra konsollen')
        dialog.setIcon(QMessageBox.Icon.Warning)
        dialog.setText(f'{len(messages)} konsolladvarsel(er) registrert.')
        dialog.setDetailedText('\n\n'.join(messages))
        dialog.setStandardButtons(QMessageBox.StandardButton.Ok)
        controller = getattr(main, '_a14_window_positions', None)
        if controller is not None:
            controller._place(dialog)
        dialog.exec()
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
    # Hold the Python callback and Qt signal bridge for DWM's entire lifetime.
    main._a14_console_qt_handler = handler
    main._a14_console_bridge = bridge
    return indicator
