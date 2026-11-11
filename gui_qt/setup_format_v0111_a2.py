"""Add two explicit assessment bases to the existing Setup, no migrations."""
from __future__ import annotations

from PySide6.QtWidgets import QComboBox, QLabel

from app.siegfried_shared_v0111_a2 import find_siegfried_executable
from app.format_assessment_v0111_a2 import (
    DEFAULT_FORMAT_SOURCE, FORMAT_SOURCES, chosen_format_source,
)
from gui_qt.setup_v0110_a3 import DwmSetupDialog as _PreviousSetupDialog


class DwmSetupDialog(_PreviousSetupDialog):
    def __init__(self, api, parent=None):
        super().__init__(api, parent)
        self._build_format_assessment_tab()

    def _build_format_assessment_tab(self):
        _content, form = self._tab('Filformatvurdering')
        self.format_source = QComboBox(self)
        for key, label, _description in FORMAT_SOURCES:
            self.format_source.addItem(label, key)
        try:
            current = chosen_format_source(self.settings)
        except ValueError:
            current = DEFAULT_FORMAT_SOURCE
        index = self.format_source.findData(current)
        self.format_source.setCurrentIndex(max(0, index))
        form.addRow('Grunnlag for vurdering:', self.format_source)
        self.format_explanation = QLabel()
        self.format_explanation.setWordWrap(True)
        form.addRow('Hva betyr valget?', self.format_explanation)
        detail = QLabel(
            'Identifikasjon (PUID/format) og historisk Arkade-evidens beholdes '
            'uendret ved profilbytte. Nasjonalarkivets liste er en datert JSON-kopi; '
            'lokale vedtak og konkrete leveringsavtaler kan kreve egen vurdering. '
            'Egendefinerte versjonerte JSON-profiler kan fortsatt lastes inn '
            'fra PRONOM-visningen. Ingen AIP godkjennes automatisk.'
        )
        detail.setWordWrap(True)
        form.addRow('', detail)
        shared = find_siegfried_executable()
        sf_status = QLabel(
            ('Eksisterende Siegfried funnet: ' + str(shared)) if shared else
            'Ingen eksisterende Siegfried oppdaget. SIARD Workflow Manager '
            'kan installere Siegfried for begge programmer.'
        )
        sf_status.setWordWrap(True)
        form.addRow('Delt Siegfried-installasjon:', sf_status)
        self.format_source.currentIndexChanged.connect(self._update_format_description)
        self._update_format_description()

    def _update_format_description(self, _index=None):
        current = str(self.format_source.currentData() or '')
        description = next((item[2] for item in FORMAT_SOURCES if item[0] == current), '')
        self.format_explanation.setText(description)

    def _updates(self) -> dict:
        updates = super()._updates()
        updates['format_assessment_source'] = str(self.format_source.currentData() or '')
        return updates
