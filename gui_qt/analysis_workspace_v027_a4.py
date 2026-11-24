"""v0.2.7-a4: scoped review comments in the existing Analyse workspace.

A3 panes, charts, controls and classic Advanced results remain unchanged.
Only an explicit user save appends a note to Work/depot_annotations.json.
"""
from __future__ import annotations

from html import escape
import re

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import (
    QComboBox, QDialog, QDialogButtonBox, QFormLayout, QHBoxLayout,
    QLabel, QMessageBox, QPushButton, QTextBrowser, QPlainTextEdit,
    QVBoxLayout,
)

from app.analysis_workspace_v027_a2 import METRICS, rule_findings
from app.analysis_workspace_v027_a3 import (
    favorite_key, matches_filter, period_review_rows, result_state,
)
from app.analysis_annotations_v027_a4 import (
    AREAS_BY_KIND, Target, annotated_record_ids, comment_badge,
    comment_counts, comment_matches, control_context, item_findings,
    make_target, read_comments, save_comment, value_groups, part_scope,
)
from .analysis_workspace_v027_a2 import AnalysisWorkspaceDialog as _A2Workspace
from .analysis_workspace_v027_a3 import AnalysisWorkspaceDialogV3


COMMENT_TYPES = (
    ('Merknad', 'note'), ('Avvik / begrunnelse', 'deviation'),
    ('Spørsmål', 'question'), ('Oppfølging', 'follow_up'),
)
LEVEL_LABELS = (
    ('Hovedområde', 'area'), ('Delresultat', 'control'),
    ('Verdigruppe', 'group'), ('Enkeltforekomst', 'item'),
)


def _label_for(kind, payload):
    if kind == 'metadata':
        return str(payload.get('metadata_id') or '') + ' – ' + str(payload.get('label') or '')
    if kind == 'format':
        return str(payload.get('puid') or '') + ' – ' + str(payload.get('name') or '')
    if kind == 'year':
        return 'År ' + str(payload)
    if kind == 'period_finding':
        return str(payload.get('summary') or 'Periodevurdering')
    return str(kind).replace('_', ' ').capitalize()


class AnalyseCommentDialog(QDialog):
    """Select the exact persistence target before one explicit append."""

    def __init__(self, snapshot, kind, payload, part_index,
                 existing_comments, *, preferred_uid='', parent=None):
        super().__init__(parent)
        self.snapshot = snapshot
        self.kind = kind
        self.payload = payload
        self.area, self.control, self.initial_scope = control_context(
            snapshot, kind, payload, part_index)
        self.selected_target: Target | None = None
        self.setWindowTitle('Kommentarer – ' + _label_for(kind, payload))
        self.resize(750, 640)
        layout = QVBoxLayout(self)
        heading = QLabel('Kommentarer til ' + _label_for(kind, payload), self)
        heading.setWordWrap(True)
        heading.setStyleSheet('font-weight: 600; font-size: 15px;')
        layout.addWidget(heading)
        explain = QLabel('Velg hvilket nivå merknaden gjelder. Felles merknader vises på '
                         'underordnede resultater uten at de kopieres. '
                         'Kommentar er ikke et faglig vedtak.', self)
        explain.setWordWrap(True)
        layout.addWidget(explain)

        form = QFormLayout()
        self.scope = QComboBox(self)
        if self.initial_scope.startswith('part:'):
            self.scope.addItem('Valgt arkivdel (' + self.initial_scope[5:] + ')',
                               self.initial_scope)
            self.scope.addItem('Hele uttrekket / alle arkivdeler', 'extract')
        else:
            self.scope.addItem('Hele uttrekket', 'extract')
        form.addRow('Omfang', self.scope)

        self.level = QComboBox(self)
        for label, key in LEVEL_LABELS:
            self.level.addItem(label, key)
        self.level.setCurrentIndex(self.level.findData('control'))
        form.addRow('Kommentarnivå', self.level)

        self.group = QComboBox(self)
        form.addRow('Verdigruppe', self.group)
        self.instance = QComboBox(self)
        form.addRow('Forekomst', self.instance)

        self.note_type = QComboBox(self)
        for label, key in COMMENT_TYPES:
            self.note_type.addItem(label, key)
        form.addRow('Type', self.note_type)
        layout.addLayout(form)

        label = QLabel('Tidligere kommentarer som gjelder dette delresultatet', self)
        layout.addWidget(label)
        previous = QTextBrowser(self)
        previous.setMinimumHeight(85)
        previous.setMaximumHeight(145)
        relevant = comment_matches(snapshot, kind, payload, part_index,
                                   existing_comments)
        if relevant:
            parts = []
            for relation, row in relevant[-60:]:
                person = (row.get('user') or {}).get('name') or (row.get('user') or {}).get('username') or ''
                parts.append('<p><b>' + escape(relation) + '</b> · '
                             + escape(str(row.get('created_at') or '')) + ' · '
                             + escape(str(person)) + '<br>'
                             + escape(str(row.get('text') or '')) + '</p>')
            previous.setHtml(''.join(parts))
        else:
            previous.setPlainText('Ingen kommentarer til dette delresultatet.')
        layout.addWidget(previous)

        self.text = QPlainTextEdit(self)
        self.text.setPlaceholderText('Skriv begrunnelse, spørsmål eller oppfølging…')
        self.text.setMinimumHeight(85)
        layout.addWidget(self.text, 1)

        self.target_hint = QLabel('', self)
        self.target_hint.setWordWrap(True)
        layout.addWidget(self.target_hint)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel, parent=self)
        save = buttons.addButton('Lagre kommentar', QDialogButtonBox.ButtonRole.AcceptRole)
        save.clicked.connect(self._validate)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self.scope.currentIndexChanged.connect(self._update_choices)
        self.level.currentIndexChanged.connect(self._update_visibility)
        self.group.currentIndexChanged.connect(self._update_items)
        self.instance.currentIndexChanged.connect(self._update_target_hint)
        self._update_choices()
        if preferred_uid:
            # The link can point to a finding in any observed value group.
            # Select that group first, then its exact persisted UID.
            scope = str(self.scope.currentData() or 'extract')
            for finding in item_findings(snapshot, kind, payload, scope):
                if str(finding.get('finding_uid') or '') == preferred_uid:
                    group_index = self.group.findData(str(finding.get('value') or ''))
                    if group_index >= 0:
                        self.group.setCurrentIndex(group_index)
                    self.level.setCurrentIndex(self.level.findData('item'))
                    instance_index = self.instance.findData(preferred_uid)
                    if instance_index >= 0:
                        self.instance.setCurrentIndex(instance_index)
                    break

    def _update_choices(self, *_args):
        selected_scope = str(self.scope.currentData() or 'extract')
        previous_group = str(self.group.currentData() or '')
        self.group.blockSignals(True)
        try:
            self.group.clear()
            for value, count in value_groups(
                    self.snapshot, self.kind, self.payload, selected_scope):
                basis = 'observerte' if selected_scope == 'extract' else 'avviksfunn'
                self.group.addItem(f'{value} ({count} {basis})', value)
            if previous_group:
                position = self.group.findData(previous_group)
                if position >= 0:
                    self.group.setCurrentIndex(position)
        finally:
            self.group.blockSignals(False)
        self._update_items()
        self._update_visibility()

    def _update_items(self, *_args):
        prior = self.instance.currentData()
        self.instance.blockSignals(True)
        try:
            self.instance.clear()
            scope = str(self.scope.currentData() or 'extract')
            # For item-level comments one exact persisted UID is mandatory.
            for finding in item_findings(self.snapshot, self.kind, self.payload,
                                         scope, str(self.group.currentData() or '')):
                uid = str(finding.get('finding_uid'))
                object_id = str(finding.get('object_id') or '')
                self.instance.addItem(str(finding.get('value') or '') + ' · '
                                      + object_id[:16] + '…', uid)
            if prior:
                index = self.instance.findData(prior)
                if index >= 0:
                    self.instance.setCurrentIndex(index)
        finally:
            self.instance.blockSignals(False)
        self._update_visibility()

    def _update_visibility(self, *_args):
        level = str(self.level.currentData() or '')
        self.group.setEnabled(level in ('group', 'item') and self.group.count() > 0)
        self.instance.setEnabled(level == 'item' and self.instance.count() > 0)
        self._update_target_hint()

    def _target(self):
        level = str(self.level.currentData() or '')
        scope = str(self.scope.currentData() or 'extract')
        group = str(self.group.currentData() or '') if level in ('group', 'item') else ''
        uid = str(self.instance.currentData() or '') if level == 'item' else ''
        if level == 'item':
            # A single finding always belongs to its native archive part,
            # regardless of the current 'whole extraction' browser filter.
            # Otherwise part B would inherit a note intended for part A.
            actual = next((f for f in item_findings(self.snapshot, self.kind,
                                                   self.payload, scope, group)
                           if str(f.get('finding_uid') or '') == uid), None)
            if actual is None:
                raise ValueError('Ingen entydig lagret forekomst er valgt')
            native_id = str(actual.get('archive_part_id') or '')
            if native_id:
                scope = 'part:' + native_id
        return make_target(level, scope, self.area, self.control, group, uid)

    def _update_target_hint(self, *_args):
        try:
            target = self._target()
            actual_scope = ('Arkivdel ' + target.scope[5:]
                            if target.scope.startswith('part:') else 'Hele uttrekket')
            self.target_hint.setText('Merknaden knyttes til: ' + target.area + ' / '
                                     + actual_scope + ' / '
                                     + self.level.currentText() + (' / ' + target.group if target.group else ''))
        except ValueError:
            self.target_hint.setText('Velg en konkret verdigruppe eller forekomst, '
                                     'eller kommenter hele delresultatet.')

    def _validate(self):
        if not self.text.toPlainText().strip():
            QMessageBox.information(self, 'Kommentar', 'Skriv en kommentar før lagring.')
            return
        try:
            self.selected_target = self._target()
        except ValueError as exc:
            QMessageBox.warning(self, 'Kommentar', str(exc))
            return
        self.accept()

    def annotation(self):
        return (self.selected_target, self.text.toPlainText().strip(),
                str(self.note_type.currentData() or 'note'))


class AnalysisWorkspaceDialogV4(AnalysisWorkspaceDialogV3):
    """A4 adds sidecar comments; all A3 chart and panel methods are reused."""

    def __init__(self, snapshot, parent=None):
        self._a4_comments = ()
        self._a4_error = ''
        self._read_annotations(snapshot)
        super().__init__(snapshot, parent)
        self.setObjectName('dwm_analysis_v027_a4')
        self.setWindowTitle('Analyse – ' + snapshot.job_id + ' – ' + snapshot.job_name)
        self.status_filter.addItem('Med kommentarer', 'comments')

        self.comment_button = QPushButton('💬 Kommentarer…', self.detail_panel)
        self.comment_button.setToolTip('Kommenter hovedområde, delresultat, '
                                       'verdigruppe eller enkeltforekomst')
        self.comment_button.clicked.connect(self._edit_comments)
        self.comment_count = QLabel('', self.detail_panel)
        bar = QHBoxLayout()
        bar.addWidget(self.comment_button)
        bar.addWidget(self.comment_count, 1)
        self.detail_panel.layout().insertLayout(1, bar)
        self.detail.setOpenLinks(False)
        self.detail.anchorClicked.connect(self._follow_comment_link)
        self.footer.setText('Resultater fra Work · kommentarer lagres separat; originaldata og vedtak endres ikke')
        self._detail_changed()
        if self._a4_error:
            self._warn_annotation_state()

    def _read_annotations(self, snapshot):
        try:
            self._a4_comments = read_comments(snapshot.report_path)
            self._a4_error = ''
        except (OSError, ValueError, TypeError) as exc:
            self._a4_comments = ()
            self._a4_error = str(exc)

    def _warn_annotation_state(self):
        self.comment_button.setEnabled(False)
        self.comment_count.setText('Kommentarer kan ikke leses: ' + self._a4_error)

    def _selection(self):
        r = self.table.currentRow()
        if 0 <= r < len(self._table_payloads):
            return self._table_payloads[r]
        return None

    def _rows(self, headers, data, payloads):
        """A3 filtering plus a genuinely cross-area 'Med kommentarer' filter."""
        if self._area_index() == 1:
            additions = period_review_rows(self.snapshot, self._part_index(), self._year())
            if additions:
                headers = ('År / kontroll',) + tuple(headers[1:])
                data = list(data) + [
                    ((('År ' + str((item.get('year_evidence') or {}).get('year'))
                       + ' – dokumentaktivitet')
                      if (item.get('year_evidence') or {}).get('year')
                      else 'Ulike observerte periodegrenser'),)
                    + tuple(None for _ in METRICS) for item in additions]
                payloads = list(payloads) + [('period_finding', item) for item in additions]
        filter_key = str(self.status_filter.currentData() or 'all')
        query = self.search.text().strip().casefold()
        selected, pairs = [], []
        for row, (kind, payload) in zip(data, payloads):
            category, display_status = result_state(
                self.snapshot, kind, payload, self._part_index())
            fav = favorite_key(self.snapshot, kind, payload) in self._favorites
            try:
                comments = comment_matches(self.snapshot, kind, payload,
                                           self._part_index(), self._a4_comments)
            except ValueError:
                comments = ()
            if filter_key == 'comments':
                if not comments:
                    continue
            elif not matches_filter(category, filter_key, fav):
                continue
            haystack = ' '.join(str(x) for x in row).casefold()
            if kind == 'metadata':
                haystack += ' ' + str(payload.get('metadata_id') or '').casefold()
            if kind == 'period_finding':
                haystack += ' ' + str(payload.get('category') or '').casefold()
            if query and query not in haystack:
                continue
            selected.append(tuple(row) + (comment_badge(comments), display_status))
            pairs.append((kind, payload))
        _A2Workspace._rows(self, tuple(headers) + ('Kommentar', 'Kontrollstatus'),
                           selected, pairs)
        if not selected:
            self.detail.setHtml('<p>Ingen delresultater som samsvarer med valgt filter.</p>')
        self._update_favorite_button()

    def _detail_changed(self):
        super()._detail_changed()
        selected = self._selection()
        if selected is None:
            if hasattr(self, 'comment_button'):
                self.comment_button.setEnabled(False)
                self.comment_count.setText('Velg et delresultat')
            return
        kind, payload = selected
        try:
            notes = comment_matches(self.snapshot, kind, payload,
                                    self._part_index(), self._a4_comments)
        except ValueError:
            notes = ()
        direct, inherited, child = comment_counts(notes)
        if hasattr(self, 'comment_count'):
            self.comment_button.setEnabled(not bool(self._a4_error))
            self.comment_count.setText(
                f'{direct} direkte · {inherited} arvede · {child} underordnede merknader')
        html = '<hr><h3>💬 Kommentarer til resultatet</h3>'
        if notes:
            for relation, item in notes[-50:]:
                user = item.get('user') or {}
                html += ('<p><b>' + escape(relation.capitalize()) + '</b> · '
                         + escape(str(item.get('created_at') or '')) + ' · '
                         + escape(str(user.get('name') or user.get('username') or ''))
                         + '<br>' + escape(str(item.get('text') or '')) + '</p>')
        else:
            html += '<p>Ingen kommentarer til dette resultatet.</p>'
        if kind == 'metadata' and self.snapshot.findings_complete:
            actual = item_findings(self.snapshot, kind, payload, 'extract')
            if self._part_index() is not None:
                chosen = part_scope(self.snapshot, self._part_index())
                actual = item_findings(self.snapshot, kind, payload, chosen or 'extract')
            if actual:
                html += '<h4>Konkrete forekomster – klikk for å kommentere</h4><ol>'
                for f in actual[:150]:
                    uid = str(f.get('finding_uid') or '')
                    text = str(f.get('value') or '') + ' · Objekt ' + str(f.get('object_id') or '')
                    mark = self._item_marker(kind, payload, f)
                    html += ('<li><a href="analysis-finding:' + escape(uid, quote=True)
                             + '">' + escape(text) + '</a> ' + escape(mark) + '</li>')
                html += '</ol>'
        cursor = self.detail.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        cursor.insertHtml(html)
        self._sync_popup()

    def _item_marker(self, kind, payload, finding):
        uid = str(finding.get('finding_uid') or '')
        raw = str(finding.get('value') or '')
        scope = 'part:' + str(finding.get('archive_part_id') or '')
        area, control, _row_scope = control_context(self.snapshot, kind, payload, None)
        count, inherited = 0, 0
        for target, note in annotated_record_ids(self._a4_comments):
            if target.area != area:
                continue
            if target.scope not in ('extract', scope):
                continue
            if target.level == 'area' or target.control == control:
                if target.level == 'group' and target.group != raw:
                    continue
                if target.level == 'item' and target.item != uid:
                    continue
                if (target.level == 'item' and target.item == uid
                        and target.scope == scope):
                    count += 1
                elif target.level in ('area', 'control', 'group', 'item'):
                    inherited += 1
        return ('💬 ' + str(count) if count else '↳ 💬 ' + str(inherited)
                if inherited else '')

    def _follow_comment_link(self, url: QUrl):
        raw = url.toString()
        if not raw.startswith('analysis-finding:'):
            return
        uid = raw.split(':', 1)[1]
        if not re.fullmatch(r'[a-fA-F0-9]{32,128}', uid):
            return
        self._edit_comments(preferred_uid=uid)

    def _identity(self):
        from app.identity_provider import LocalUserProfileIdentityProvider
        provider = LocalUserProfileIdentityProvider()
        value = provider.current_identity()
        if value is not None:
            return value
        answer = QMessageBox.question(
            self, 'Brukerprofil',
            'En lagret kommentar krever registrert brukerprofil. Opprette profil nå?',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes)
        if answer != QMessageBox.StandardButton.Yes:
            return None
        from .depot_review_v019_a2 import ReviewUserProfileDialog
        if ReviewUserProfileDialog(self).exec() != QDialog.DialogCode.Accepted:
            return None
        return LocalUserProfileIdentityProvider().current_identity()

    def _edit_comments(self, _checked=False, *, preferred_uid=''):
        if self._a4_error:
            QMessageBox.warning(self, 'Kommentarer', self._a4_error)
            return
        selected = self._selection()
        if selected is None:
            QMessageBox.information(self, 'Kommentarer', 'Velg et delresultat først.')
            return
        kind, payload = selected
        try:
            editor = AnalyseCommentDialog(
                self.snapshot, kind, payload, self._part_index(),
                self._a4_comments, preferred_uid=preferred_uid, parent=self)
        except ValueError as exc:
            QMessageBox.warning(self, 'Kommentarer', str(exc))
            return
        if editor.exec() != QDialog.DialogCode.Accepted:
            return
        user = self._identity()
        if user is None:
            return
        target, text, note_type = editor.annotation()
        if target is None:
            return
        try:
            label = _label_for(kind, payload) + ' / ' + editor.level.currentText()
            if target.group:
                label += ' / ' + target.group
            if target.item:
                label += ' / ' + target.item
            save_comment(self.snapshot, target, label, text, note_type, user)
            self._read_annotations(self.snapshot)
            self._refresh()
            # Stay on the reviewed delresultat after an explicit save.
            for index, item in enumerate(self._table_payloads):
                if item[0] == kind and item[1] == payload:
                    self.table.selectRow(index)
                    break
        except (OSError, ValueError, TypeError) as exc:
            QMessageBox.warning(self, 'Kommentarer', str(exc))

    def _switch_details_mode(self, *_args):
        super()._switch_details_mode(*_args)
        popup = self._detail_popup
        if popup is not None and not hasattr(popup, 'a4_comment_button'):
            popup.a4_comment_button = QPushButton('💬 Kommentarer…', popup)
            popup.layout().insertWidget(1, popup.a4_comment_button)
            popup.a4_comment_button.clicked.connect(self._edit_comments)
            popup.browser.setOpenLinks(False)
            popup.browser.anchorClicked.connect(self._follow_comment_link)
            popup.a4_comment_button.setEnabled(not bool(self._a4_error))

    def _reload(self):
        # A new report may have a different hash/sidecar. Never silently copy
        # annotations from an older report to the new analysis snapshot.
        super()._reload()
        self._read_annotations(self.snapshot)
        if hasattr(self, 'comment_button'):
            self.comment_button.setEnabled(not bool(self._a4_error))
            if self._a4_error:
                self._warn_annotation_state()
        self._refresh()


def install_analysis_workspace_v4(window) -> bool:
    """Switch only the new Analyse factory, not the original Advanced viewer."""
    if not getattr(window, '_analysis_v027_a3_installed', False):
        return False
    window._analysis_dialog_class = AnalysisWorkspaceDialogV4
    window._analysis_v027_a4_installed = True
    return True
