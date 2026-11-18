"""Severity-aware Qt console messages and an accessible diagnostics window.

Qt warnings remain in the original stderr stream. Small, known Windows frame
rounding is not raised as a red alert; significant geometry failures remain
visible. A10.2 replaces QMessageBox's tiny details pane with a resizable
viewer whose entire text can be copied and whose size is remembered.
"""
from __future__ import annotations

import re

_GEOMETRY_WARNING = re.compile(
    r'QWindowsWindow::setGeometry: Unable to set geometry '
    r'(\d+)x(\d+)\+(-?\d+)\+(-?\d+) '
    r'\(frame: .*?\) .*?Resulting geometry: '
    r'(\d+)x(\d+)\+(-?\d+)\+(-?\d+)',
    re.DOTALL,
)


def is_minor_windows_geometry_adjustment(message: str, *, tolerance: int = 24) -> bool:
    """True only when every Windows geometry correction is small and bounded."""
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
