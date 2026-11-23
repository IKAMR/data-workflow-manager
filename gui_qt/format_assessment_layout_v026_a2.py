"""Readable, full-width Setup format assessment for v0.2.6-a2.

Only the presentation changes. The selected authority, current setting,
notifications and the saved format-assessment semantics remain unchanged.
Use the same single spanning QFormLayout row used by External Tools to
avoid multiline QLabel geometry collapsing in narrow form columns.
"""
from __future__ import annotations


def _build_format_assessment_tab(self) -> None:
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import (
        QComboBox, QGroupBox, QLabel, QSizePolicy, QVBoxLayout, QWidget,
    )
    from app.format_assessment_v0111_a2 import (
        DEFAULT_FORMAT_SOURCE, FORMAT_SOURCES, chosen_format_source,
    )

    def note(message: str, parent: QWidget) -> QLabel:
        label = QLabel(message, parent)
        label.setTextFormat(Qt.TextFormat.PlainText)
        label.setWordWrap(True)
        label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        label.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )
        label.setMinimumWidth(0)
        return label

    content, form = self._tab('Filformatvurdering')
    host = QWidget(content)
    host.setMinimumWidth(0)
    stack = QVBoxLayout(host)
    stack.setContentsMargins(8, 12, 8, 18)
    stack.setSpacing(18)
    form.addRow(host)  # one full-width row, no multiline field/label pairs

    source_group = QGroupBox('Grunnlag for vurdering', host)
    source_layout = QVBoxLayout(source_group)
    source_layout.setContentsMargins(18, 23, 18, 18)
    source_layout.setSpacing(12)

    self.format_source = QComboBox(source_group)
    for key, caption, _description in FORMAT_SOURCES:
        self.format_source.addItem(caption, key)
    try:
        current = chosen_format_source(self.settings)
    except ValueError:
        current = DEFAULT_FORMAT_SOURCE
    selected = self.format_source.findData(current)
    self.format_source.setCurrentIndex(max(0, selected))
    source_layout.addWidget(self.format_source)

    source_layout.addWidget(note('Hva betyr valget?', source_group))
    self.format_explanation = note('', source_group)
    source_layout.addWidget(self.format_explanation)
    stack.addWidget(source_group)

    interpretation_group = QGroupBox('Vurdering og evidens', host)
    interpretation = QVBoxLayout(interpretation_group)
    interpretation.setContentsMargins(18, 23, 18, 18)
    interpretation.addWidget(note(
        'Identifikasjon (PUID/format) og historisk Arkade-evidens beholdes '
        'uendret ved profilbytte. Nasjonalarkivets liste er en datert JSON-kopi; '
        'lokale vedtak og konkrete leveringsavtaler kan kreve egen vurdering. '
        'Egendefinerte versjonerte JSON-profiler kan fortsatt lastes inn '
        'fra PRONOM-visningen. Ingen AIP godkjennes automatisk.',
        interpretation_group,
    ))
    stack.addWidget(interpretation_group)

    siegfried_group = QGroupBox('Siegfried / PRONOM', host)
    siegfried_layout = QVBoxLayout(siegfried_group)
    siegfried_layout.setContentsMargins(18, 23, 18, 18)
    siegfried_layout.addWidget(note(
        'Siegfried konfigureres under Eksterne verkt\u00f8y. Begge '
        'applikasjonene kan bruke samme installerte program; '
        'formatvurderingene holdes atskilt.',
        siegfried_group,
    ))
    stack.addWidget(siegfried_group)
    stack.addStretch(1)

    self.format_source.currentIndexChanged.connect(
        self._update_format_description
    )
    self._update_format_description()


def install_format_assessment_layout() -> None:
    """Extend Setup *after* the existing startup layer has loaded it.

    Headless startup tests intentionally replace the Setup installer with a
    minimal stub. Do not eagerly import the real Qt-based Setup in that case.
    On normal startup the real Setup class is already registered in sys.modules.
    Repeated installation is harmless and existing behavior is inherited.
    """
    import sys

    module = sys.modules.get('gui_qt.setup_format_v0111_a2')
    if module is None:
        return
    base = module.DwmSetupDialog
    if getattr(base, '_v026_a2_format_layout', False):
        return

    class SetupWithReadableFormat(base):
        _v026_a2_format_layout = True

    SetupWithReadableFormat._build_format_assessment_tab = (
        _build_format_assessment_tab
    )
    module.DwmSetupDialog = SetupWithReadableFormat
