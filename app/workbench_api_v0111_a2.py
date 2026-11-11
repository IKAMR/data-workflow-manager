"""Shared Setup selection of format-assessment basis for both GUI frontends."""
from __future__ import annotations

from typing import Mapping

from app.application_api import DwmApiError
from app.format_assessment_v0111_a2 import require_format_source
from app.workbench_api_v0111_a1 import DwmWorkbenchAPI as _PreviousWorkbenchAPI
from settings import save_config


class DwmWorkbenchAPI(_PreviousWorkbenchAPI):
    def save_setup(self, changes: Mapping[str, object]) -> dict:
        if 'format_assessment_source' not in changes:
            return super().save_setup(changes)
        try:
            selected = require_format_source(changes['format_assessment_source'])
        except ValueError as exc:
            raise DwmApiError(str(exc)) from exc
        old = dict(changes)
        old.pop('format_assessment_source')
        # All existing Setup safety checks and their one-write operation remain
        # unchanged. Only the independent display-policy choice is new.
        saved = super().save_setup(old)
        with self._guard:
            self._assert_idle()
            saved = save_config({'format_assessment_source': selected})
            self.settings['format_assessment_source'] = selected
        self._emit('setup.changed', message='Grunnlag for formatvurdering valgt i Setup')
        return dict(saved)
