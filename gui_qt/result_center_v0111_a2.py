"""Selected file-format assessment: dated PUID policy or preserved Arkade RAF.

Keeps original Arkade/Siegfried statistics, PUIDs, source files, and the other
assessment visible. Only the displayed *primary* evaluation changes.
"""
from __future__ import annotations

import csv
from pathlib import Path

from PySide6.QtCore import QTimer
from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import QFileDialog, QMessageBox, QSizePolicy, QHeaderView

from app.result_display_v0110_a5 import readable_html

from app.format_assessment_v0111_a2 import (
    FORMAT_SOURCE_ARKADE_RAF, FORMAT_SOURCE_NASJONALARKIVET,
    historical_arkade_status, require_format_source,
)
from app.format_policy_v0110_a4 import evaluate_puid
from .result_center_v0110_a4 import (
    _FORMAT_STATUS_ROLE, ResultCenterWindow as _PreviousResultCenter,
)


def readable_pronom_details(original, columns, *, arkade_selected=False):
    """Prioritize selected PUID/assessment, preserving every original detail.

    Only the HTML presentation uses this reordered mapping. The stored
    evidence, original item data, and raw/JSON viewer are never rewritten.
    """
    values = tuple(str(value or '') for value in columns)
    if len(values) < 7:
        return original
    data = original if isinstance(original, dict) else {'Kildeevidens': original}
    displayed = {
        'Valgt format': {
            'PUID': values[1], 'Filtype': values[2], 'Versjon': values[3],
            'Antall': values[4], 'Valgt vurdering': values[6],
        },
    }
    order = ('historisk_arkade_raf', 'formatvurdering') if arkade_selected else (
        'formatvurdering', 'historisk_arkade_raf')
    for key in order:
        if key in data:
            displayed[key] = data[key]
    remaining = {key: value for key, value in data.items() if key not in order}
    if remaining:
        displayed['Øvrig evidens'] = remaining
    return displayed


class ResultCenterWindow(_PreviousResultCenter):
    def __init__(self, *args, format_assessment_source=FORMAT_SOURCE_NASJONALARKIVET,
                 **kwargs):
        self._a2_source = require_format_source(format_assessment_source)
        super().__init__(*args, **kwargs)
        self._a2_apply_source()
        self._a24_compact_pronom()

    def _a24_compact_pronom(self):
        """Give PRONOM results all remaining height, not the top text rows.

        Keep the original QSplitter and both viewer widgets intact: replacing
        widgets previously caused PySide6 C++ lifetime crashes in a5.
        """
        page = self._pages['PRONOM']
        layout = page.layout()
        splitter = self._a53_splitters['PRONOM']
        layout.setSpacing(5)
        layout.setContentsMargins(8, 8, 8, 8)
        for widget in (
            self.format_summary, self.format_arkade_source,
            self.format_profile_source, self.format_note,
        ):
            widget.setSizePolicy(
                QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)
        # The header/filters/provenance take only their natural size. The
        # horizontal result table + side-detail pane gets every extra pixel.
        for index in range(layout.count()):
            entry = layout.itemAt(index)
            layout.setStretch(index, 1 if entry.widget() is splitter else 0)
        splitter.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._a24_pronom_layout_ready = True
        self._a53_schedule_splitter()

    def _a56_configure_columns(self):
        # Retain existing widths for other result tabs. The a5.6 PRONOM widths
        # predate its full-height, side-by-side layout and clip the final column.
        super()._a56_configure_columns()
        self._a25_fit_pronom_columns()

    def _a25_fit_pronom_columns(self):
        """Reserve readable width for the current format assessment column.

        The repeated extraction name, compact IDs and numbers do not need as
        much room as the assessment. Qt stretches the *last* section to the
        remaining width, including when the user drags the panel divider.
        Earlier sections remain manually adjustable; no source data changes.
        """
        table = self._trees.get('PRONOM')
        if table is None:
            return
        header = table.header()
        for column, width in ((0, 86), (1, 107), (2, 179),
                              (3, 62), (4, 55), (5, 94)):
            if column < table.columnCount():
                header.setSectionResizeMode(column, QHeaderView.ResizeMode.Interactive)
                table.setColumnWidth(column, width)
        if table.columnCount() > 6:
            # Avoid squeezing the important last column to a narrow sliver.
            header.setSectionResizeMode(6, QHeaderView.ResizeMode.Stretch)
            header.setStretchLastSection(True)
            table.headerItem().setText(5, 'RAF-220301')
        for index in range(table.topLevelItemCount()):
            row = table.topLevelItem(index)
            for column in (1, 2, 5, 6):
                if column < row.columnCount():
                    row.setToolTip(column, row.text(column))

    def _a24_reset_pronom_scroll(self):
        """Start at top after Qt has laid out newly rendered evidence."""
        if not getattr(self, '_a53_details_ready', False):
            return
        for widget in (self._a53_browsers.get('PRONOM'),
                       self._details.get('PRONOM')):
            if widget is not None:
                try:
                    widget.moveCursor(QTextCursor.MoveOperation.Start)
                    widget.verticalScrollBar().setValue(0)
                except RuntimeError:
                    # A pending resize/selection callback during window close.
                    pass

    def _show_detail(self, tab: str):
        super()._show_detail(tab)
        if tab != 'PRONOM' or not getattr(self, '_a53_details_ready', False):
            return
        item = self._trees['PRONOM'].currentItem()
        if item is not None and not item.text(0).startswith(
                ('Ingen lagret evidens', 'Ingen tilgjengelig Work')):
            from .result_center_v018_a13 import DETAIL_ROLE
            original = item.data(0, DETAIL_ROLE)
            columns = tuple(item.text(index) for index in range(item.columnCount()))
            browser = self._a53_browsers.get('PRONOM')
            if browser is not None:
                presented = readable_pronom_details(
                    original, columns,
                    arkade_selected=self._a2_source == FORMAT_SOURCE_ARKADE_RAF)
                browser.setHtml(readable_html(presented))
        self._a24_reset_pronom_scroll()
        QTimer.singleShot(0, self._a24_reset_pronom_scroll)

    def _a53_select_detail_mode(self, tab, index):
        super()._a53_select_detail_mode(tab, index)
        if tab == 'PRONOM':
            QTimer.singleShot(0, self._a24_reset_pronom_scroll)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        # Recalculate either the saved manual fraction or the automatic
        # row-aware split after Qt has applied the new window geometry.
        # This applies to Arkivdeler and other tabs, not only PRONOM.
        if getattr(self, '_a53_details_ready', False):
            self._a53_schedule_splitter()

    def _a4_change_policy(self, _index=None, *, persist=True):
        # A user may deliberately select "Ingen formatvurdering". Distinguish
        # that from the empty preference stored by older versions so the new
        # institutional default does not override an explicit future choice.
        if persist:
            no_assessment = not str(self.format_policy_combo.currentData() or '').strip()
            self._a4_settings.setValue('qt/format_policy_none_explicit', no_assessment)
        return super()._a4_change_policy(_index, persist=persist)

    def _a2_apply_source(self):
        if self._a2_source == FORMAT_SOURCE_ARKADE_RAF:
            combo = self.format_status_combo
            combo.blockSignals(True)
            try:
                combo.clear()
                for text, code in (
                    ('Alle historiske statuser', ''),
                    ('Gyldig arkivformat', 'valid'),
                    ('Gyldig med forbehold', 'conditional'),
                    ('Ikke gyldig arkivformat', 'invalid'),
                    ('Ukjent', 'unknown'),
                ):
                    combo.addItem(text, code)
            finally:
                combo.blockSignals(False)
            self._trees['PRONOM'].headerItem().setText(6, 'Valgt vurdering (Arkade)')
            self._a4_filter_pronom()
        else:
            # Setup selects the dated built-in baseline; a manual JSON load in
            # PRONOM remains possible and can still be independently assessed.
            # The combo has "Ingen formatvurdering" at index 0. Previously the
            # profile's zero-based index was used directly, selecting "Ingen"
            # in place of the built-in Nasjonalarkivet JSON at combo index 1.
            # Keep an explicitly selected custom profile or deliberate "Ingen".
            explicit_none = str(self._a4_settings.value(
                'qt/format_policy_none_explicit', False)).strip().casefold() in (
                    'true', '1', 'yes')
            if (not str(self.format_policy_combo.currentData() or '').strip()
                    and not explicit_none
                    and not getattr(self, '_a5_missing_policy_warning', '')):
                for policy in self._a4_profiles:
                    if policy.path.name == 'nasjonalarkivet_2026-11-10.json':
                        index = self.format_policy_combo.findData(str(policy.path))
                        if index > 0:
                            # Emits currentIndexChanged: loads and persists the
                            # policy using the existing validation path.
                            self.format_policy_combo.setCurrentIndex(index)
                        break
            self._trees['PRONOM'].headerItem().setText(6, 'Valgt regelprofil')
            self._a4_filter_pronom()

    def _a4_filter_pronom(self, _ignored=None):
        if self._a2_source != FORMAT_SOURCE_ARKADE_RAF:
            return super()._a4_filter_pronom(_ignored)
        if not getattr(self, '_a4_ready', False):
            return
        status_filter = str(self.format_status_combo.currentData() or '')
        needle = self.format_search.text().strip().casefold()
        visible = 0
        totals = {'valid': 0, 'conditional': 0, 'invalid': 0, 'unknown': 0}
        for item, row in self._a4_format_rows:
            legacy = historical_arkade_status(row.get('raf'))
            item.setText(6, legacy.label)
            item.setData(0, _FORMAT_STATUS_ROLE, legacy.code)
            item.setToolTip(6, 'Historisk Arkade 5 / RAF-220301. Ikke en vurdering '
                                'mot gjeldende regelverk eller en godkjenning.')
            matches = (not status_filter or status_filter == legacy.code) and (
                not needle or any(needle in item.text(col).casefold()
                                  for col in range(item.columnCount()))
            )
            item.setHidden(not matches)
            if matches:
                visible += 1
                try:
                    count = int(str(row.get('count') or '').replace(' ', ''))
                    if count > 0:
                        totals[legacy.code] += count
                except (TypeError, ValueError):
                    pass
        table = self._trees['PRONOM']
        for index in range(table.topLevelItemCount()):
            item = table.topLevelItem(index)
            if item.text(0).startswith('Ingen lagret evidens'):
                item.setHidden(bool(status_filter or needle))
        if self._a4_format_rows:
            self.format_summary.setText(
                f'Viser {visible} av {len(self._a4_format_rows)} formatgrupper. '
                f'Historisk gyldig: {totals["valid"]} filer | '
                f'Med forbehold: {totals["conditional"]} | '
                f'Ikke gyldig: {totals["invalid"]} | '
                f'Ukjent: {totals["unknown"]}.'
            )
        else:
            self.format_summary.setText(
                'Ingen lagret Arkade/Siegfried PRONOM-statistikk i valgt Work. '
                'Kjør Arkade 5 PRONOM-analyse eller importer eksisterende evidens.'
            )
        self.format_arkade_source.setText(
            'Valgt grunnlag i Setup: Arkade 5 / RAF-220301 (historisk). '
            'Gyldig, med forbehold og ikke gyldig gjengis fra lagret Arkade-status.'
        )
        self.format_profile_source.setText(
            'Valgt datert JSON-regelprofil er fortsatt tilgjengelig '
            'som separat sammenligning. Historisk Arkade-status er ikke '
            'et vedtak etter gjeldende arkivregelverk.'
        )

    def _a4_export_pronom(self):
        if self._a2_source != FORMAT_SOURCE_ARKADE_RAF:
            return super()._a4_export_pronom()
        rows = [row for item, row in self._a4_format_rows if not item.isHidden()]
        if not rows:
            QMessageBox.information(self, 'Formatvurdering', 'Ingen historisk formatstatistikk å eksportere.')
            return
        saved_dir = str(self._a4_settings.value('qt/last_report_output_dir', '') or '')
        folder = Path(saved_dir) if saved_dir and Path(saved_dir).is_dir() else Path.home()
        filename, _ = QFileDialog.getSaveFileName(
            self, 'Eksporter historisk formatvurdering',
            str(folder / 'dwm-arkade-historisk.csv'), 'CSV (*.csv)',
        )
        if not filename:
            return
        dest = Path(filename)
        if not dest.suffix:
            dest = dest.with_suffix('.csv')
        if dest.exists() and QMessageBox.question(
                self, 'Eksisterende eksportfil', f'Overskrive eksisterende fil?\n{dest}',
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No) != QMessageBox.StandardButton.Yes:
            return
        try:
            with dest.open('w' if dest.exists() else 'x', encoding='utf-8-sig', newline='') as stream:
                writer = csv.writer(stream, delimiter=';')
                writer.writerow((
                    'Uttrekk', 'PUID', 'Format', 'Versjon', 'Antall',
                    'Arkade RAF original', 'Arkade status (historisk)',
                    'Separat PUID-vurdering', 'Regelprofil', 'Utgave',
                    'Profil SHA-256', 'Grunnlag', 'Kilde/import', 'Importert dato', 'PRONOM kildefil',
                ))
                for row in rows:
                    decision = evaluate_puid(row.get('format_id'), self._a4_format_policy)
                    writer.writerow((
                        row.get('job'), row.get('format_id'), row.get('file_type'),
                        row.get('version'), row.get('count'), row.get('raf'),
                        historical_arkade_status(row.get('raf')).label, decision.label,
                        self._a4_format_policy.title if self._a4_format_policy else '',
                        self._a4_format_policy.edition if self._a4_format_policy else '',
                        self._a4_format_policy.sha256 if self._a4_format_policy else '',
                        'Arkade 5 / RAF-220301 (historisk)',
                        row.get('evidence_source'), row.get('imported_at'),
                        row.get('original_csv'),
                    ))
        except (OSError, ValueError) as exc:
            QMessageBox.warning(self, 'Eksportfeil', str(exc))
            return
        self._a4_settings.setValue('qt/last_report_output_dir', str(dest.parent))
        QMessageBox.information(self, 'Formatvurdering', f'Eksportert {len(rows)} rader til:\n{dest}')
