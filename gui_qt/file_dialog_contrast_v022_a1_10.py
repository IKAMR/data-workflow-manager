"""Accessible parent-directory icon for Qt's non-native file dialogs.

Qt's standard SP_FileDialogToParent asset may render nearly black on DWM's
forest-green dark palette.  This is a presentation-only correction: it does
not change the file picker, its initial directory, or any persistence path.

Qt is imported only when the desktop application installs the filter; the
contrast calculation can be tested without a GUI toolkit.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class NavigationColors:
    ink: str
    background: str
    border: str
    hover: str


def _linear_component(channel: int) -> float:
    value = min(255, max(0, int(channel))) / 255.0
    return value / 12.92 if value <= 0.04045 else ((value + 0.055) / 1.055) ** 2.4


def relative_luminance(rgb: tuple[int, int, int]) -> float:
    """WCAG luminance for a palette RGB value."""
    return sum(weight * _linear_component(channel) for weight, channel in
               zip((0.2126, 0.7152, 0.0722), rgb))


def contrast_ratio(first: tuple[int, int, int], second: tuple[int, int, int]) -> float:
    light, dark = sorted((relative_luminance(first), relative_luminance(second)),
                         reverse=True)
    return (light + 0.05) / (dark + 0.05)


def navigation_colors(button_rgb: tuple[int, int, int]) -> NavigationColors:
    """Choose readable icon and outline against any active DWM palette."""
    background = tuple(min(255, max(0, int(v))) for v in button_rgb)
    # Pure extremes guarantee >= 4.5:1 against any opaque RGB button color.
    light_ink = (255, 255, 255)
    dark_ink = (0, 0, 0)
    foreground = max((light_ink, dark_ink),
                     key=lambda color: contrast_ratio(background, color))

    def as_hex(rgb):
        return '#%02x%02x%02x' % rgb

    def blend(weight):
        return tuple(round(b * (1 - weight) + f * weight)
                     for b, f in zip(background, foreground))

    return NavigationColors(
        ink=as_hex(foreground),
        background=as_hex(background),
        border=as_hex(blend(0.60)),
        hover=as_hex(blend(0.18)),
    )


def button_stylesheet(colors: NavigationColors) -> str:
    """A visible border, hover state and keyboard focus on the *one* button."""
    return (
        'QToolButton#toParentButton {'
        f'background-color: {colors.background}; color: {colors.ink}; '
        f'border: 2px solid {colors.border}; border-radius: 5px; padding: 3px;'
        '} '
        'QToolButton#toParentButton:hover {'
        f'background-color: {colors.hover};'
        '} '
        'QToolButton#toParentButton:focus {'
        f'border: 2px solid {colors.ink};'
        '} '
        'QToolButton#toParentButton:disabled {'
        f'background-color: {colors.background}; border: 1px solid {colors.border};'
        '}'
    )


def install_file_dialog_navigation_contrast(application):
    """Fix the Up icon in each existing non-native Qt QFileDialog.

    QFileDialog.getSaveFileName(..., DontUseNativeDialog) internally creates a
    widget-based QFileDialog. An application event filter sees its Show event,
    then updates only the toParentButton using a high-contrast vector arrow.
    The built-in navigation action/shortcut stays attached to that button.
    """
    if getattr(application, '_dwm_file_dialog_contrast_filter', None) is not None:
        return application._dwm_file_dialog_contrast_filter

    from PySide6.QtCore import QEvent, QObject, QSize, Qt, QTimer
    from PySide6.QtGui import (QColor, QIcon, QPainter, QPainterPath, QPalette,
                               QPen, QPixmap)
    from PySide6.QtWidgets import QFileDialog, QToolButton

    def arrow_icon(ink: str) -> QIcon:
        pixmap = QPixmap(64, 64)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        try:
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            painter.setPen(QPen(QColor(ink), 6, Qt.PenStyle.SolidLine,
                                Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
            arrow = QPainterPath()
            arrow.moveTo(12, 31)
            arrow.lineTo(32, 11)
            arrow.lineTo(52, 31)
            arrow.moveTo(32, 13)
            arrow.lineTo(32, 52)
            painter.drawPath(arrow)
        finally:
            painter.end()
        return QIcon(pixmap)

    class FileDialogContrastFilter(QObject):
        def fix_dialog(self, dialog) -> bool:
            try:
                if not isinstance(dialog, QFileDialog):
                    return False
                # Native Windows dialogs have no Qt toolbar and are untouched.
                button = dialog.findChild(QToolButton, 'toParentButton')
                if button is None:
                    return False
                color = button.palette().color(QPalette.ColorRole.Button)
                colors = navigation_colors((color.red(), color.green(), color.blue()))
                button.setIcon(arrow_icon(colors.ink))
                button.setIconSize(QSize(22, 22))
                button.setStyleSheet(button_stylesheet(colors))
                button.setToolTip('Opp ett mappenivå (Ctrl+pil opp)')
                button.setAccessibleName('Opp ett mappenivå')
                return True
            except RuntimeError:
                # File dialog may have been closed before the queued Show pass.
                return False

        def eventFilter(self, watched, event):
            if (isinstance(watched, QFileDialog)
                    and event.type() == QEvent.Type.Show):
                # Qt may finish populating internal toolbar children on Show.
                QTimer.singleShot(0, lambda dialog=watched: self.fix_dialog(dialog))
            return False  # Never swallow a file dialog's native events.

    installed = FileDialogContrastFilter(application)
    application.installEventFilter(installed)
    application._dwm_file_dialog_contrast_filter = installed
    return installed
