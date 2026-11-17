"""Restore startup defaults without changing depot profile or job data.

The existing portable Setup reset remains the only full reset operation.
This function changes only the two persisted startup navigation preferences.
"""
from __future__ import annotations

from app.ui_start_preferences_v020_a2 import UI_DEFAULTS, validate_ui_preferences


STARTUP_KEYS = ('ui_startup_mode', 'ui_startup_page')


def startup_defaults() -> dict[str, str]:
    """DWM opens directly in Kontroll / Enkel, regardless of work profile."""
    return validate_ui_preferences({key: UI_DEFAULTS[key] for key in STARTUP_KEYS})


def restore_startup(api) -> dict[str, str]:
    """Use the shared Setup API, which handles validation and persistence.

    Never modify jobs, the active Work, or any Source file. Abort on any API
    failure; leave the dialog open so the user can review the error.
    """
    if api.running:
        raise RuntimeError('Innstillinger kan ikke tilbakestilles mens en jobb kjører.')
    changes = startup_defaults()
    api.save_setup(changes)
    api.reload_setup()
    return changes
