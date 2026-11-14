"""v0.2.0-a2: allow and validate GUI profile preferences in shared Setup.

Only three UI-specific keys are handled here. All existing Setup options
retain the strict validation of the established workbench API.
"""
from __future__ import annotations

from typing import Mapping

from app.application_api import DwmApiError
from app.ui_start_preferences_v020_a2 import UI_SETUP_KEYS, validate_ui_preferences
from app.workbench_api_v0111_a2 import DwmWorkbenchAPI as _PreviousWorkbenchAPI
from settings import save_config


class DwmWorkbenchAPI(_PreviousWorkbenchAPI):
    def save_setup(self, changes: Mapping[str, object]) -> dict:
        ui_changes = {key: value for key, value in changes.items()
                      if key in UI_SETUP_KEYS}
        if not ui_changes:
            return super().save_setup(changes)

        # Validate first; a bad GUI preference must not partially save the
        # other Setup fields. Strict legacy checks remain in the base API.
        try:
            validated = validate_ui_preferences(ui_changes)
        except ValueError as exc:
            raise DwmApiError(str(exc)) from exc

        ordinary = {key: value for key, value in changes.items()
                    if key not in UI_SETUP_KEYS}
        if ordinary:
            super().save_setup(ordinary)
        with self._guard:
            self._assert_idle()
            saved = save_config(validated)
            self.settings.update(validated)
        self._emit('setup.changed', message='Arbeidsprofil og oppstartspreferanser lagret')
        return dict(saved)
