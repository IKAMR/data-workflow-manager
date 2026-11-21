"""v0.2.4-a3: anchored dropdowns while retaining conservative Qt startup."""
from __future__ import annotations

import os

from gui_qt.main_v024_a2 import DwmMainWindow as _A2Window


class DwmMainWindow(_A2Window):
    def __init__(self, api):
        super().__init__(api)
        # The old QApplication-wide event filter caused concern about native
        # Windows faults. Only install the targeted QComboBox-local observer on
        # a real Qt main window. Fake startup windows must stay importable.
        if not (hasattr(self, 'findChildren')
                and getattr(self, '_v024_a2_actions_ready', False)
                and os.environ.get('DWM_SAFE_MODE') != '1'):
            return
        from PySide6.QtWidgets import QApplication
        from gui_qt.combobox_anchor_v024_a3 import install_local_dropdown_anchors
        application = QApplication.instance()
        if application is not None:
            install_local_dropdown_anchors(application, self)
