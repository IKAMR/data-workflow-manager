"""Conservative Qt startup feature policy after intermittent Windows faults.

Keep this module independent of PySide6. Normal start is deliberately as
conservative as the previously successful start-safe.bat: both application-
wide event filters and the competing Basic geometry timer are disabled.

No job lists, workflow settings, archived data, or Work files are read/written.
Experiment with exactly one feature at a time by setting an environment
variable to the literal string "1" for one *process*, not in stored Setup.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping


@dataclass(frozen=True)
class QtStartupFeatures:
    safe_mode: bool
    dialog_filter: bool
    popup_filter: bool
    basic_auto_fit: bool


def select_qt_startup_features(environ: Mapping[str, str]) -> QtStartupFeatures:
    """Return explicitly enabled features; DWM_SAFE_MODE always overrides.

    Default=all three disabled. These opt-ins are for controlled debugging,
    not a dependency of either Basic/Advanced workflows or Noark execution.
    """
    safe = environ.get('DWM_SAFE_MODE') == '1'
    return QtStartupFeatures(
        safe_mode=safe,
        dialog_filter=not safe and environ.get('DWM_ENABLE_QT_DIALOG_FILTER') == '1',
        popup_filter=not safe and environ.get('DWM_ENABLE_QT_POPUP_FILTER') == '1',
        basic_auto_fit=not safe and environ.get('DWM_ENABLE_QT_BASIC_AUTOFIT') == '1',
    )
