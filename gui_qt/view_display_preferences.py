"""Shared desktop presentation preferences for Qt evidence/result views.

This holds UI preferences only. No archive source or job result is changed.
"""
from __future__ import annotations

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QPlainTextEdit

_ORGANIZATION = 'IKAMR'
_APPLICATION = 'DataWorkflowManager'
_WORD_WRAP_KEY = 'result_views/word_wrap'


def word_wrap_enabled() -> bool:
    """Default on, also for an existing user who has no stored preference."""
    value = QSettings(_ORGANIZATION, _APPLICATION).value(_WORD_WRAP_KEY, True)
    if isinstance(value, bool):
        return value
    return str(value).lower() not in ('false', '0', 'no', 'off')


def save_word_wrap_enabled(enabled: bool) -> None:
    QSettings(_ORGANIZATION, _APPLICATION).setValue(_WORD_WRAP_KEY, bool(enabled))


def apply_word_wrap(enabled: bool, *views) -> None:
    """Use one setting across supported Qt item views and plain XML editors."""
    for view in views:
        if isinstance(view, QPlainTextEdit):
            view.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth if enabled
                                 else QPlainTextEdit.LineWrapMode.NoWrap)
        else:
            view.setWordWrap(bool(enabled))
