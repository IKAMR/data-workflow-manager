"""v0.1.10-a1: workbench Setup can select a storage profile atomically.

An existing .n5jobs or Work manifest is never migrated by changing Setup.
"""
from __future__ import annotations

from pathlib import Path
from typing import Mapping

from app.application_api import DwmApiError
from app.presentation_preferences_v0110_a3 import (
    DISPLAY_KEYS, validate_display_preferences,
)
from app.storage_profiles_v0110_a1 import require_storage_profile
from app.work_output_layout import validate_app_work_subfolder, validate_layout
from app.workbench_api_v019_a4 import DwmWorkbenchAPI as _PreviousWorkbenchAPI
from settings import save_config


class DwmWorkbenchAPI(_PreviousWorkbenchAPI):
    def save_setup(self, changes: Mapping[str, object]) -> dict:
        if 'storage_layout_profile' not in changes and not (set(changes) & DISPLAY_KEYS):
            return super().save_setup(changes)

        # The existing Setup method is intentionally strict about accepted keys.
        # Extend its validation with only the new storage-profile field, then
        # persist all changes in one write, not in two partial saves.
        allowed = {
            'arkade5_cli_path', 'arkade5_output_subfolder', 'noark5_discovery_workflow',
            'app_work_subfolder', 'temp_dir', 'run_log_dir', 'setup_dir',
            'job_list_dir', 'operation_visibility', 'storage_layout_profile',
            'appearance_mode', 'qt_accent_color', 'qt_popup_placement',
            'qt_palette_preset', 'qt_custom_colors',
            'sf_executable',  # v0.1.12: Siegfried path supplied by shared Setup.
        }
        unknown = set(changes) - allowed
        if unknown:
            raise DwmApiError('Ukjente Setup-innstillinger: ' + ', '.join(sorted(unknown)))
        try:
            display = validate_display_preferences(changes)
        except ValueError as exc:
            raise DwmApiError(str(exc)) from exc
        updated = {key: str(value or '').strip() for key, value in changes.items()
                   if key != 'operation_visibility' and key != 'qt_custom_colors'}
        updated.update(display)
        if 'storage_layout_profile' in changes:
            try:
                selected_profile = require_storage_profile(str(changes['storage_layout_profile'] or ''))
            except ValueError as exc:
                raise DwmApiError(str(exc)) from exc
            updated['storage_layout_profile'] = selected_profile
            # a2: distinguish an explicitly saved selection from the old default.
            updated['storage_layout_profile_selected'] = True
        if 'operation_visibility' in changes:
            try:
                visibility = int(changes['operation_visibility'])
            except (TypeError, ValueError) as exc:
                raise DwmApiError('Operasjonsnivaa maa vaere et tall fra 0 til 2.') from exc
            if visibility not in (0, 1, 2):
                raise DwmApiError('Operasjonsnivaa maa vaere 0, 1 eller 2.')
            updated['operation_visibility'] = visibility
        if 'arkade5_cli_path' in updated:
            selected = updated['arkade5_cli_path'].strip('"')
            if selected and not Path(selected).is_absolute():
                raise DwmApiError('Arkade 5 CLI maa angis med absolutt sti.')
            updated['arkade5_cli_path'] = selected
        if 'app_work_subfolder' in updated:
            updated['app_work_subfolder'] = validate_app_work_subfolder(updated['app_work_subfolder'])
        if 'arkade5_output_subfolder' in updated:
            from noark5_workflow.external_tools.arkade5_jobs import resolve_arkade5_output_subfolder
            resolve_arkade5_output_subfolder(
                {'arkade5_output_subfolder': updated['arkade5_output_subfolder']}, '2.13.1'
            )
        if 'noark5_discovery_workflow' in updated:
            from app.workflow_sequences import workflow_sequence_by_id
            sequence = workflow_sequence_by_id(updated['noark5_discovery_workflow'])
            if sequence is None or sequence.profile_id != 'noark5':
                raise DwmApiError('Ukjent standardprofil for Noark 5.')
        if 'app_work_subfolder' in updated:
            if self._work_references and updated['app_work_subfolder'] != str(
                self.settings.get('app_work_subfolder', 'dwm') or ''
            ):
                raise DwmApiError('Global DWM Work-undermappe kan ikke endres mens '
                                  'jobber har varige Work-referanser.')
            try:
                validate_layout(updated['app_work_subfolder'], self.output_subfolder_rule,
                                self._batch.jobs())
            except ValueError as exc:
                raise DwmApiError('Global DWM-undermappe gir ugyldig Work-oppsett: '
                                  + str(exc)) from exc

        with self._guard:
            self._assert_idle()
            saved = save_config(updated)  # all-or-nothing for Setup at the API boundary
            self.settings.update(updated)
            self._arkade_checker.invalidate()
        self._emit('setup.changed', message='Setup lagret etter brukerens godkjenning')
        return dict(saved)
