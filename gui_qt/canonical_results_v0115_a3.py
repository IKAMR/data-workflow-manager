"""Opt-in canonical Work projection dialog for the existing DWM Qt frontend.

No changes to the runner, saved job, raw evidence or Source. Users explicitly
choose each evidence file and confirm before a canonical snapshot is replaced.
"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QObject, QThread, Signal, QSettings, QTimer
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QTreeWidget, QTreeWidgetItem,
    QHeaderView, QPushButton, QMessageBox, QPlainTextEdit, QFileDialog, QSplitter,
    QWidget, QGridLayout,
)

from noark5_workflow.analysis.canonical_work_adapter import (
    discover_work_sources, canonical_report,
)
from noark5_workflow.analysis.canonical_results import build_canonical_results

from app.canonical_selection_v0115_a3 import ALLOWED, selected_sources
from .canonical_layout_v0115_a9 import content_split, button_columns, text_visual_lines
from noark5_workflow.analysis.canonical_context_v0115_a4 import build_context
from noark5_workflow.analysis.canonical_external_v0115_a5 import discover_external_candidates
from noark5_workflow.analysis.canonical_control_plan_v0115_a6 import coverage_report
from noark5_workflow.analysis.canonical_control_requirements_v0115_a7 import evaluate_control_profile
from noark5_workflow.analysis.canonical_outcomes_v0115_a8 import evaluate_recorded_outcomes
from noark5_workflow.analysis.canonical_external_import_v0115_a10 import (
    analyze_external_results, discover_analysis_candidates, previous_analysis_selection,
)
from app.canonical_external_selection_v0115_a10 import selected_external_rows
from noark5_workflow.analysis.canonical_matrix_v0115_a11 import (
    evaluate_control_matrix, load_external_status,
)
from noark5_workflow.analysis.canonical_qa_report_v0115_a12 import build_qa_draft, OUTPUT as QA_OUT
from noark5_workflow.analysis.canonical_completion_v0115_a14 import build_completion_draft, OUTPUT as COMPLETION_OUT
from noark5_workflow.analysis.canonical_preservation_v0115_a15 import prepare_candidate, verify_candidate, OUT as AIP_OUT
from noark5_workflow.analysis.dias_preservation_link_v0115_a16 import inspect_dias_preservation_link


class _Task(QObject):
    finished = Signal(object, object)

    def __init__(self, work: Path, selection: dict | None):
        super().__init__()
        self.work = work
        self.selection = selection

    def run(self):
        try:
            if self.selection is None:
                result = discover_work_sources(self.work)
                # Discover in the same background task, never in a nested dialog.
                from app.canonical_external_selection_v0115_a10 import external_row_metadata
                candidates = discover_analysis_candidates(self.work)
                previous = previous_analysis_selection(self.work, candidates)
                result['external_candidates'] = external_row_metadata(candidates, previous)
                result['external_status'] = load_external_status(self.work)
            elif '__a10_external' in self.selection:
                result = {'a10_external': analyze_external_results(self.work, self.selection['__a10_external'])}
            elif '__a16_dias_link' in self.selection:
                result = {'a16_dias_link': inspect_dias_preservation_link(self.work)}
            elif '__a15_candidate' in self.selection:
                result = {'a15_candidate': prepare_candidate(self.work)}
            elif '__a14_completion' in self.selection:
                result = {'a14_completion': build_completion_draft(self.work, self.selection['__a14_completion'])}
            elif '__a12_qa_draft' in self.selection:
                result = {'a12_qa_draft': build_qa_draft(self.work, self.selection['__a12_qa_draft'])}
            elif '__a11_matrix' in self.selection:
                result = {'a11_matrix': evaluate_control_matrix(self.work, self.selection['__a11_matrix'])}
            elif '__a8_outcomes' in self.selection:
                result = {'a8_outcomes': evaluate_recorded_outcomes(self.work, self.selection['__a8_outcomes'])}
            elif '__a7_profile' in self.selection:
                result = {'a7_profile': evaluate_control_profile(self.work, self.selection['__a7_profile'])}
            elif '__a6_coverage' in self.selection:
                result = {'a6_coverage': coverage_report(self.work)}
            elif '__a5_discover_external' in self.selection:
                result = {'a5_candidates': discover_external_candidates(self.work)}
            elif '__a4_context' in self.selection:
                context = build_context(self.work, **self.selection['__a4_context'])
                result = {'a4_context': context['summary']}
            else:
                document = build_canonical_results(self.work, **self.selection,
                                                   write=True)
                result = canonical_report(document)
            self.finished.emit(result, None)
        except Exception as exc:
            self.finished.emit(None, str(exc))


class CanonicalResultsDialog(QDialog):
    def __init__(self, work: str | Path, parent=None):
        super().__init__(parent)
        self.work = Path(work)
        self.setWindowTitle('Kanoniske resultatdata - Work')
        self.resize(940, 680)
        self.setMinimumSize(660, 440)
        self._thread = None
        self._task = None
        self._settings = QSettings("IKAMR", "DWM-Qt")
        layout = QVBoxLayout(self)
        heading = QLabel('Resultatkilder i valgt Work')
        layout.addWidget(heading)
        work_label = QLabel(str(self.work))
        work_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        work_label.setWordWrap(True)
        layout.addWidget(work_label)
        self.selection_status = QLabel('Laster resultatkilder fra valgt Work...')
        self.selection_status.setWordWrap(True)
        layout.addWidget(self.selection_status)
        self.tree = QTreeWidget(self)
        self.tree.setHeaderLabels(['Bruk', 'Kilde / resultatfil i Work', 'Status', 'Tester / bytes'])
        self.tree.setRootIsDecorated(False)
        self.tree.setSortingEnabled(True)
        self.tree.itemChanged.connect(self._selection_changed)
        self.tree.header().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.tree.header().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        splitter = QSplitter(Qt.Orientation.Vertical, self)
        splitter.setChildrenCollapsible(False)
        splitter.addWidget(self.tree)
        note = QLabel('Kilder velges manuelt. Eldre og ikke-stottede kilder tas ikke med. '
                      'Dette er en indeks over evidens, ikke en depotgodkjenning.')
        note.setWordWrap(True)
        note.setObjectName("canonicalSourceNote")
        self.report = QPlainTextEdit(self)
        self.report.setReadOnly(True)
        self.report.setPlaceholderText('Resultatdekning vises etter lagring.')
        splitter.addWidget(self.report)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 1)
        # Dynamic content sizing replaces a6's fixed / persisted ratio.
        self._auto_split_change = False
        self._manual_split = False
        self._last_view = 'sources'
        self._layout_timer = QTimer(self)
        self._layout_timer.setSingleShot(True)
        self._layout_timer.timeout.connect(self._apply_content_layout)
        splitter.splitterMoved.connect(self._splitter_moved)
        self.splitter = splitter
        layout.addWidget(splitter, 1)
        layout.addWidget(note)
        button_host = QWidget(self)
        buttons = QGridLayout(button_host)
        buttons.setContentsMargins(0, 0, 0, 0)
        buttons.setHorizontalSpacing(8)
        buttons.setVerticalSpacing(6)
        self.refresh_button = QPushButton('Finn resultatkilder')
        self.refresh_button.clicked.connect(self.refresh)
        self.coverage_button = QPushButton('Kontrolldekning')
        self.coverage_button.clicked.connect(lambda: self._start({'__a6_coverage': True}))
        self.profile_button = QPushButton('Kontrollplan (utkast)...')
        self.profile_button.clicked.connect(self.select_profile)
        self.outcomes_button = QPushButton('Kontrollutfall / KS...')
        self.outcomes_button.clicked.connect(self.select_outcome_profile)
        self.matrix_button = QPushButton('Dekningsmatrise (utkast)...')
        self.completion_button = QPushButton('Ferdigstillingsrapport (utkast)...')
        self.completion_button.clicked.connect(self.create_completion_report)
        self.aip_button = QPushButton('Evidenskandidat (Work)...')
        self.aip_button.clicked.connect(self.create_aip_candidate)
        self.dias_link_button = QPushButton('DIAS AIP – koblingskontroll')
        self.dias_link_button.clicked.connect(lambda: self._start({'__a16_dias_link': True}))
        self.qa_button = QPushButton('KS-rapport til arkivskaper (utkast)...')
        self.qa_button.clicked.connect(self.create_qa_report)
        self.matrix_button.clicked.connect(self.select_matrix_profile)
        self.external_discover_button = QPushButton('Finn ekstern evidens')
        self.external_discover_button.clicked.connect(lambda: self._start({'__a5_discover_external': True}))
        self.build_button = QPushButton('Opprett resultatindeks...')
        self.build_button.clicked.connect(self.create_snapshot)
        self.external_analyze_button = QPushButton('Analyser valgte eksterne resultater')
        self.external_analyze_button.clicked.connect(self.analyze_external)
        self.context_button = QPushButton('Koble vurderinger / ekstern evidens...')
        self.context_button.clicked.connect(self.create_context)
        self.close_button = QPushButton('Lukk')
        self.close_button.clicked.connect(self.reject)
        self._action_buttons = [
            self.refresh_button, self.external_discover_button,
            self.coverage_button, self.profile_button, self.outcomes_button, self.matrix_button,
            self.qa_button, self.completion_button, self.aip_button, self.dias_link_button,
            self.build_button, self.context_button, self.external_analyze_button, self.close_button,
        ]
        self._button_host = button_host
        self._button_grid = buttons
        self._button_columns = 0
        self._reflow_buttons()
        layout.addWidget(button_host)
        self._busy = False
        self.refresh()
        QTimer.singleShot(0, self._reflow_buttons)
        QTimer.singleShot(0, self._schedule_content_layout)

    def _set_busy(self, busy: bool):
        self._busy = busy
        self.refresh_button.setEnabled(not busy)
        self.build_button.setEnabled(not busy)
        self.external_discover_button.setEnabled(not busy)
        self.coverage_button.setEnabled(not busy)
        self.profile_button.setEnabled(not busy)
        self.outcomes_button.setEnabled(not busy)
        self.matrix_button.setEnabled(not busy)
        self.qa_button.setEnabled(not busy)
        self.completion_button.setEnabled(not busy)
        self.aip_button.setEnabled(not busy)
        self.dias_link_button.setEnabled(not busy)
        self.context_button.setEnabled(not busy)
        self.external_analyze_button.setEnabled(not busy)
        self.close_button.setEnabled(not busy)
        self.tree.setEnabled(not busy)
        if not busy and self._last_view == 'sources':
            self._selection_changed()

    def _start(self, selection: dict | None):
        if self._busy:
            return
        self._set_busy(True)
        self.report.setPlainText('Leser Work...')
        self._set_view('loading')
        thread = QThread(self)
        task = _Task(self.work, selection)
        task.moveToThread(thread)
        thread.started.connect(task.run)
        task.finished.connect(self._complete)
        task.finished.connect(lambda *_args: self._schedule_content_layout())
        task.finished.connect(thread.quit)
        thread.finished.connect(task.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(self._clear_thread)
        self._thread = thread
        self._task = task
        thread.start()

    def _clear_thread(self):
        self._thread = None
        self._task = None
        self._set_busy(False)

    def _complete(self, result, error):
        if error:
            self.report.setPlainText('FEIL: ' + error)
            QMessageBox.warning(self, 'Kanoniske resultatdata', error)
            return
        if 'a16_dias_link' in result:
            status = result['a16_dias_link']
            lines = [
                'DIAS AIP – KOBLINGSKONTROLL (SKRIVEBESKYTTET)',
                'Eksisterende pakkemodul: ' + status['dias_operation'],
                'info.xml / METS-mapping: ' + status['dias_metadata'],
                'DIAS metadata i GUI/Work: ' + status['dias_info_bridge'],
                '',
                'Evidenskandidat i Work: ' + status['evidence_candidate'],
                'Evidensstatus: ' + status['evidence_state'],
                'Verifiserte evidensfiler: ' + str(status['evidence_files']),
                'Åpne forhold: ' + str(len(status['open_requirements'])),
                '',
                'Pakkingen utføres av den eksisterende DIAS-modulen, ikke denne kontrollen.',
                'AIP-destinasjon og hvilke original-/arkivversjoner som bevares styres i pakkeprosessen.',
                'Arkivskapers bekreftelse og depotets beslutning må dokumenteres separat.',
                'Ingen AIP, AIC, info.xml eller godkjenning er opprettet eller endret.',
            ]
            self.report.setPlainText('\n'.join(lines))
            self._set_view('dias_link')
            self.selection_status.setText('DIAS-kobling kontrollert – ingen pakking utført.')
        elif 'a15_candidate' in result:
            package = result['a15_candidate']
            lines = ['BEVARINGSPAKKE – PAKKEKANDIDAT (IKKE GODKJENT)',
                     'Staging i Work: '+package['output'],
                     f"Kopierte og SHA-256-verifiserte filer: {package['files']}",
                     f"Manglende evidenskilder: {package['missing']}",
                     'Manifest: '+package['output']+'/manifest-sha256.json',
                     '', 'Ingen arkivskaperaksept, depotgodkjenning eller journalføring.',
                     'Source er ikke inkludert. Dette er ikke en ferdig AIP.']
            self.report.setPlainText('\n'.join(lines))
            self._set_view('aip_candidate')
            self.selection_status.setText('Pakkekandidat opprettet i Work – ikke godkjent.')
        elif 'a14_completion' in result:
            report = result['a14_completion']
            info = report['summary']
            self.report.setPlainText(
                'FERDIGSTILLINGS- OG BESLUTNINGSGRUNNLAG - UTKAST (IKKE GODKJENT)\n'
                f"Lagret: {report['output']}\n"
                f"Uavklarte betingelser: {info['open_conditions']}\n"
                f"Rapporterte feil-/advarselsposter: {info['issues']}\n"
                f"KS-rapportutkast tilgjengelig: {'JA' if info['has_qa_draft'] else 'NEI'}\n"
                'Arkivskapers aksept: IKKE REGISTRERT\n'
                'Depotgodkjenning: IKKE REGISTRERT\n'
                'Journalføring: IKKE REGISTRERT\n'
                'Dette er et dokumentasjonsutkast. Ingen beslutning eller Source endres.')
            self._set_view('completion_report')
            self.selection_status.setText('Ferdigstillingsutkast lagret i Work. Ingen godkjenning registrert.')
        elif 'a12_qa_draft' in result:
            report = result['a12_qa_draft']
            summary = report['summary']
            self.report.setPlainText(
                'KVALITETSSIKRINGSRAPPORT – UTKAST (IKKE GODKJENT)\n'
                f"Opprettet: {report['output']}\n"
                f"Påkrevde områder med evidens: {summary['required_evidence']}/{summary['required_categories']}\n"
                f"Arkade rapporterte tester med feil: {summary['reported_arkade_errors']}\n"
                f"Detaljerte feil-/advarselsposter: {summary['detailed_issue_records']}\n"
                'Arkivskapers aksept: IKKE REGISTRERT\n'
                'Depotgodkjenning: IKKE REGISTRERT\n\n'
                'Rapporten er lagret i Work og kan åpnes i nettleser og skrives ut.\n'
                'Original evidens og kanonisk resultatindeks er uendret.')
            self._set_view('qa_report')
            self.selection_status.setText('KS-utkast lagret i Work. Ingen godkjenning registrert.')
        elif 'a10_external' in result:
            data = result['a10_external']
            info = data['summary']
            lines = ['EKSTERNE RESULTATER - ANALYSE (IKKE GODKJENNING)',
                     f"Valgte filer: {info['selected_files']}",
                     f"Normaliserte testposter (ikke verifisert status): {info['reported_external_test_records']}",
                     f"Siegfried formatidentifikasjoner: {info['format_identification_files']}",
                     f"Filer som ikke kunne tolkes: {info['unparsed_files']}", '']
            for source in data['sources']:
                entry = source['analysis']
                lines.append(source['evidence']['work_relative_path'])
                lines.append(f"  Format: {entry['source_format']} | Tolkning: {entry['interpretation']}")
                if entry.get('reason'):
                    lines.append('  ' + entry['reason'])
                if entry.get('record_count') is not None:
                    lines.append(f"  Registrerte testposter: {entry['record_count']}")
                if entry.get('format_rows') is not None:
                    lines.append(f"  PRONOM-formatrader: {entry['format_rows']} | Filer: {entry['reported_total_files']}")
                if entry.get('reported_status_counts') is not None:
                    lines.append(f"  Arkade rapportert status: {entry['reported_status_counts']}")
                if entry.get('file_records') is not None:
                    lines.append(f"  Formatidentifiserte filposter: {entry['file_records']}")
            lines.extend(['', 'Lagret: noark5_evidence/canonical-external-analysis.json',
                         'Ingen kontroll er godkjent av denne analysen.'])
            self.report.setPlainText('\n'.join(lines))
            self._set_view('external_analysis')
            analyzed_paths = {x['evidence']['work_relative_path']:
                              x['analysis']['interpretation'] for x in data['sources']}
            for i in range(self.tree.topLevelItemCount()):
                row = self.tree.topLevelItem(i)
                meta = row.data(0, Qt.ItemDataRole.UserRole)
                if meta and meta[0] == 'external':
                    interpretation = analyzed_paths.get(meta[1])
                    if interpretation:
                        row.setText(2, 'Ikke tolket' if interpretation == 'not_parsed' else 'Analysert')
                    else:
                        row.setText(2, 'Ekstern - ikke analysert')
            self.selection_status.setText(
                f"Lagret samlet analyse av {info['selected_files']} eksterne filer. "
                f"{info['reported_external_test_records']} Arkade-testposter; "
                f"{info['unparsed_files']} ukjente filer. Originalene er uendret.")
        elif 'a11_matrix' in result:
            matrix = result['a11_matrix']
            summary = matrix['summary']
            lines = ['DEKNINGSMATRISE - ARBEIDSUTKAST (IKKE GODKJENT)',
                     'Profil: ' + matrix['profile_id'],
                     'Ekstern analyse: ' + matrix['external_analysis_state'],
                     f"Paa krevde kategorier med evidens: {summary['required_with_registered_evidence']}/{summary['required_categories']}",
                     f"Arkade rapporterte feil: {summary['reported_arkade_errors']}",
                     'Kravoppfyllelse: IKKE VERIFISERT',
                     'Arkivskapers aksept / depotgodkjenning: IKKE REGISTRERT', '']
            for item in matrix['controls']:
                lines.append(f"{item['title']} [{item['requirement']}]: {item['assessment']}")
                lines.append(f"  DWM-observasjoner: {item['internal_observations']}; eksterne testposter: {item['external_test_records']}")
                if item['external_status_counts']:
                    lines.append('  Arkade rapportert status: ' + str(item['external_status_counts']))
                if item['pronom_format_rows']:
                    lines.append(f"  PRONOM-formatrader: {item['pronom_format_rows']}")
                if item['requirement'] == 'conditional':
                    lines.append('  Betingelse: IKKE FAGLIG VURDERT')
            lines.extend(['', matrix['warning']])
            self.report.setPlainText('\n'.join(lines))
            self._set_view('matrix')
        elif 'a8_outcomes' in result:
            review = result['a8_outcomes']
            info = review['summary']
            lines = ['KONTROLLUTFALL / KS-GRUNNLAG - UTKAST',
                     f"Profil: {review['profile_id']} (ikke godkjent)",
                     f"Pavkrevd evidens registrert: {info['required_with_registered_evidence']}/{info['required_categories']}",
                     'Kravoppfyllelse: IKKE VERIFISERT',
                     'Arkivskapers aksept: IKKE REGISTRERT',
                     'Depotgodkjenning: IKKE REGISTRERT', '']
            for item in review['controls']:
                lines.append(f"{item['title']} [{item['requirement']}]: {item['reported_outcome']}")
                for source in item['sources']:
                    counts = ', '.join(f'{key}={val}' for key, val in source['reported_status_counts'].items())
                    lines.append(f"  {source['source_kind']} ({counts}): {source['interpretation']}")
            lines.extend(['', 'SPORSMAL TIL KVALITETSSIKRING'])
            lines.extend('- ' + q for q in review['quality_assurance_preparation']['open_questions'])
            lines.append('Bare faktagrunnlag. Ingen automatisk godkjenning.')
            self.report.setPlainText('\n'.join(lines))
            self._set_view('outcomes')
        elif 'a7_profile' in result:
            report = result['a7_profile']
            summary = report['summary']
            lines = ['KONTROLLPLAN - UTKAST (ikke godkjent)',
                     'Profil: ' + report['profile_id'],
                     f"Påkrevde kontrollomrader med registrert evidens: {summary['required_with_registered_evidence']}/{summary['required_categories']}",
                     'Kravoppfyllelse: IKKE VERIFISERT',
                     'Ingen teknisk eller depotfaglig godkjenning.', '']
            for item in report['controls']:
                lines.append(f"{item['title']} [{item['requirement']}]: {item['evidence_state']} ({item['observation_count']} observasjoner)")
            lines.append('Kontrollprofilen er et arbeidsutkast. Kontrollutfall og anvendelighet ma vurderes.')
            self.report.setPlainText('\n'.join(lines))
            self._set_view('profile')
        elif 'a6_coverage' in result:
            report = result['a6_coverage']
            summary = report['summary']
            lines = [f"Kontrollområder med registrert evidens: {summary['categories_with_registered_evidence']}/{summary['categories']}",
                     'Dette er registrert kjøring, IKKE godkjent kontrolldekning.',
                     f"Faglig kontekstindeks: {report['context_status']}",
                     'Påkrevd kontrollprofil: IKKE valgt/verifisert', '']
            for control in report['controls']:
                lines.append(f"{control['title']}: {control['presence']} ({control['observation_count']} observasjoner)")
            lines.append('Kontrollplanen må senere knyttes til versjonert Noark-/leveranseprofil.')
            self.report.setPlainText('\n'.join(lines))
            self._set_view('coverage')
        elif 'a5_candidates' in result:
            rows = result['a5_candidates']
            lines = [f'Eksterne evidenskandidater funnet: {len(rows)}',
                     'Ingen filer er valgt eller analysert. Velg dem eksplisitt ved kobling:']
            lines.extend('  ' + x['path'] for x in rows)
            if len(rows) >= 150:
                lines.append('Listen er avgrenset til 150 filer.')
            self.report.setPlainText('\n'.join(lines))
            self._set_view('external')
        elif 'a4_context' in result:
            self._set_view('context')
            totals = result['a4_context']
            self.report.setPlainText(
                'Kanonisk kontekstindeks lagret: noark5_evidence/canonical-context.json\n'
                f"Faglige vurderinger: {totals['human_assessments']}\n"
                f"Eksterne evidensfiler (ikke tolket): {totals['external_unparsed_files']}\n"
                f"Vurderinger uten test-ID-kobling: {totals['unlinked_assessments']}\n"
                f"Faglig ikke-verifiserte vurderinger: {totals['unverified_assessments']}\n"
                f"Siegfried JSON identifisert: {totals['identified_siegfried_files']}\n"
                'Testreferanse er IKKE en faglig verifisert M-ID-kobling.\n'
                'Formatidentifikasjon er IKKE testgodkjenning eller depotaksept.')
        elif 'candidates' in result:
            self._set_view('sources')
            self.tree.blockSignals(True)
            try:
                self.tree.clear()
                for category, candidates in result['candidates'].items():
                    for candidate in candidates:
                        status = candidate['status']
                        row = QTreeWidgetItem(['', 'DWM: ' + candidate['path'], status,
                            str(candidate.get('tests', candidate.get('bytes', '')))])
                        row.setData(0, Qt.ItemDataRole.UserRole,
                                    (category, candidate['path'], status))
                        row.setFlags(row.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                        row.setCheckState(0, Qt.CheckState.Unchecked)
                        if status not in ALLOWED.get(category, set()):
                            row.setDisabled(True)
                        self.tree.addTopLevelItem(row)
                for candidate in result.get('external_candidates', []):
                    source_state = result.get('external_status', {}).get('sources', {}).get(candidate['path'])
                    text_state = {'analyzed': 'Analysert', 'not_parsed': 'Ikke tolket',
                                  'source_missing_or_changed': 'Endret kilde'}.get(source_state, 'Ekstern - ikke analysert')
                    row = QTreeWidgetItem(['', candidate['label'] + ': ' + candidate['path'],
                                           text_state, str(candidate['bytes'])])
                    row.setData(0, Qt.ItemDataRole.UserRole,
                                ('external', candidate['path'], 'candidate'))
                    row.setFlags(row.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                    row.setCheckState(0, Qt.CheckState.Checked if candidate['selected']
                                      else Qt.CheckState.Unchecked)
                    row.setToolTip(1, candidate['path'])
                    self.tree.addTopLevelItem(row)
            finally:
                self.tree.blockSignals(False)
            self._selection_changed()
            self.report.setPlainText(
                'Velg kilder øverst. Bruk «Opprett resultatindeks» for DWM-kilder, '
                'eller «Analyser valgte eksterne resultater» for Arkade/Siegfried.\n'
                'Analysefilen erstattes ved ny analyse; originale kildefiler endres aldri. '
                'Ingen kontroll blir automatisk godkjent.')
        else:
            self._set_view('snapshot')
            lines = [f"Observasjoner: {result['observations']}",
                     f"Jobb-ID: {result['extraction_stable_id']}",
                     'Kildedekning (ingen summering av arkivdata):']
            for row in result['source_coverage']:
                lines.append(f"  {row['source_kind']}: {row['observations']} "
                             f"(tilgjengelig {row['available']}, "
                             f"mangler {row['unavailable']}, ukjent {row['unknown']})")
            lines.append('Lagret: noark5_evidence/canonical-results.json')
            self.report.setPlainText('\n'.join(lines))

    def _selected_external(self):
        rows = []
        for i in range(self.tree.topLevelItemCount()):
            row = self.tree.topLevelItem(i)
            metadata = row.data(0, Qt.ItemDataRole.UserRole)
            if metadata:
                rows.append((metadata[0], metadata[1],
                             row.checkState(0) == Qt.CheckState.Checked))
        return selected_external_rows(rows)

    def _selection_changed(self, *_args):
        if not hasattr(self, 'selection_status'):
            return
        count = len(self._selected_external())
        total = sum(1 for i in range(self.tree.topLevelItemCount())
                    if (self.tree.topLevelItem(i).data(0, Qt.ItemDataRole.UserRole)
                        or (None,))[0] == 'external')
        self.selection_status.setText(
            f'Eksterne resultatfiler valgt: {count} av {total}. '
            'Analyser valgte lagrer én samlet analyse og erstatter forrige analysefil. '
            'Originalene endres ikke.')
        if hasattr(self, 'external_analyze_button'):
            self.external_analyze_button.setEnabled(not self._busy and count > 0)

    def _set_view(self, view: str):
        # Explicitly changing the shown dataset releases manual splitter control;
        # ordinary resizes of the same view keep the user's split ratio.
        if view != self._last_view:
            self._manual_split = False
            self._last_view = view
        self._schedule_content_layout()

    def _schedule_content_layout(self):
        if hasattr(self, '_layout_timer') and not self._manual_split:
            self._layout_timer.start(0)

    def _splitter_moved(self, _position, _index):
        if not self._auto_split_change:
            self._manual_split = True

    def _apply_content_layout(self):
        if self._manual_split or not self.splitter.isVisible():
            return
        sizes = self.splitter.sizes()
        total = sum(sizes)
        if total < 210:
            return
        # Use actual tree rows and text font metrics, not a fixed 20/80 ratio.
        rows = self.tree.topLevelItemCount()
        item_height = max(self.tree.fontMetrics().lineSpacing() + 6, 22)
        tree_need = self.tree.header().height() + 16 + rows * item_height
        fm = self.report.fontMetrics()
        lines = self.report.toPlainText().split('\n')
        usable_width = max(100, self.report.viewport().width() - 16)
        avg_char = max(5.0, fm.horizontalAdvance('abcdefghijklmnopqrstuvwxyz') / 26.0)
        wrap_count = text_visual_lines(lines, usable_width, avg_char)
        report_need = 24 + wrap_count * max(1, fm.lineSpacing())
        if self._last_view in ('matrix', 'qa_report', 'completion_report', 'aip_candidate', 'dias_link'):
            report_need += min(160, total // 5)  # reserve room for longer review text
        wanted = content_split(total, tree_need, report_need,
                               tree_min=112, report_min=115)
        self._auto_split_change = True
        try:
            self.splitter.setSizes(list(wanted))
        finally:
            self._auto_split_change = False

    def _reflow_buttons(self):
        if not hasattr(self, '_button_grid'):
            return
        grid = self._button_grid
        available = max(350, self.width() - 32)
        widths = [b.sizeHint().width() + 6 for b in self._action_buttons]
        columns = button_columns(available, widths, spacing=8)
        if columns == self._button_columns:
            return
        self._button_columns = columns
        for button in self._action_buttons:
            grid.removeWidget(button)
        for i, button in enumerate(self._action_buttons):
            grid.addWidget(button, i // columns, i % columns)
        for col in range(len(self._action_buttons)):
            grid.setColumnStretch(col, 1 if col < columns else 0)
        self._button_host.updateGeometry()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, '_button_grid'):
            self._reflow_buttons()
            self._schedule_content_layout()

    def create_aip_candidate(self):
        """Create an explicitly unapproved, verified package candidate in Work."""
        if (self.work / AIP_OUT).exists():
            QMessageBox.information(self, 'Pakkekandidat finnes',
                'Eksisterende kandidat overskrives ikke. Behold den og gi den et nytt navn før ny klargjøring.')
            return
        answer = QMessageBox.question(
            self, 'Evidenskandidat i Work',
            'Kopiere tilgjengelig dokumentert evidens og rapportutkast til en egen '
            'kandidat i Work?\n\nPlassering: ' + str(self.work / AIP_OUT) + '\n\n'
            'Originalene og Source endres ikke. Dette er IKKE en ferdig AIP eller depotgodkjenning.',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No)
        if answer == QMessageBox.StandardButton.Yes:
            self._start({'__a15_candidate': True})

    def create_completion_report(self):
        """Explicitly create an unapproved completion/decision worksheet."""
        profile = Path(__file__).resolve().parents[1] / 'config' / 'noark5' / 'control-profile-dwm-draft-v1.json'
        output = self.work / COMPLETION_OUT
        verb = 'Erstatt' if output.is_file() else 'Opprett'
        answer = QMessageBox.question(
            self, 'Ferdigstillingsrapport – utkast',
            f'{verb} ferdigstillingsutkast i valgt Work?\n\n{COMPLETION_OUT}\n\n'
            'Uavklarte forhold vises. Ingen aksept, godkjenning eller journalføring registreres.',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No)
        if answer == QMessageBox.StandardButton.Yes:
            self._start({'__a14_completion': str(profile)})

    def create_qa_report(self):
        """Generate a separate, explicitly unapproved HTML draft within Work."""
        profile = Path(__file__).resolve().parents[1] / 'config' / 'noark5' / 'control-profile-dwm-draft-v1.json'
        output = self.work / QA_OUT
        verb = 'Erstatt eksisterende' if output.is_file() else 'Opprett'
        answer = QMessageBox.question(
            self, 'KS-rapport – arbeidsutkast',
            f'{verb} KS-rapport i valgt Work?\n\n{QA_OUT}\n\n'
            'Dette er et arbeidsutkast for arkivskaper, ikke en bekreftelse eller depotgodkjenning. '
            'Eksisterende kontrollresultater og Source endres ikke.',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No)
        if answer == QMessageBox.StandardButton.Yes:
            self._start({'__a12_qa_draft': str(profile)})

    def select_matrix_profile(self):
        """Click explicitly selects the bundled, unapproved draft profile."""
        profile = Path(__file__).resolve().parents[1] / 'config' / 'noark5' / 'control-profile-dwm-draft-v1.json'
        self._start({'__a11_matrix': str(profile)})

    def select_outcome_profile(self):
        """Select explicit draft profile; do not infer one from Work."""
        default = Path(__file__).resolve().parents[1] / 'config' / 'noark5' / 'control-profile-dwm-draft-v1.json'
        chosen, _ = QFileDialog.getOpenFileName(
            self, 'Velg kontrollprofil for kontrollutfall (utkast)', str(default),
            'JSON (*.json);;Alle filer (*)',
            options=QFileDialog.Option.DontUseNativeDialog)
        if chosen:
            self._start({'__a8_outcomes': chosen})

    def select_profile(self):
        """Require an intentional choice of a draft requirement profile."""
        default = Path(__file__).resolve().parents[1] / 'config' / 'noark5' / 'control-profile-dwm-draft-v1.json'
        chosen, _ = QFileDialog.getOpenFileName(
            self, 'Velg kontrollprofil (utkast)', str(default),
            'JSON (*.json);;Alle filer (*)',
            options=QFileDialog.Option.DontUseNativeDialog)
        if chosen:
            self._start({'__a7_profile': chosen})

    def refresh(self):
        self._start(None)

    def create_snapshot(self):
        rows = []
        for i in range(self.tree.topLevelItemCount()):
            row = self.tree.topLevelItem(i)
            category, path, status = row.data(0, Qt.ItemDataRole.UserRole)
            if category == 'external':
                continue
            rows.append((category, path,
                         row.checkState(0) == Qt.CheckState.Checked, status))
        try:
            selection = selected_sources(rows)
        except ValueError as exc:
            QMessageBox.information(self, 'Velg kilder', str(exc))
            return
        target = self.work / 'noark5_evidence' / 'canonical-results.json'
        replace = target.is_file()
        message = ('Erstatt eksisterende kanonisk resultatindeks?' if replace else
                   'Opprett kanonisk resultatindeks fra de valgte kildene?')
        message += '\n\nOriginale resultater og Source endres ikke.'
        if QMessageBox.question(self, 'Bekreft resultatindeks', message,
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No) != QMessageBox.StandardButton.Yes:
            return
        self._start(selection)

    def analyze_external(self):
        """Analyze checked external rows directly in this dialog; no nested popup."""
        if not (self.work / 'noark5_evidence' / 'canonical-results.json').is_file():
            self.report.setPlainText('Opprett kanonisk resultatindeks foerst.')
            self._set_view('error')
            return
        files = self._selected_external()
        if not files:
            self.report.setPlainText('Ingen eksterne filer valgt. Kryss av ønskede Arkade-/Siegfried-filer øverst.')
            self._set_view('sources')
            return
        # Explicit action, and the on-screen status makes the replacement clear.
        # Only the generated analysis projection is replaced, not source evidence.
        self._start({'__a10_external': files})
        self.selection_status.setText(f'Analyserer {len(files)} valgte eksterne filer ...')

    def create_context(self):
        """Require explicit operator selection; no implicit ingestion of source XML."""
        canonical = self.work / 'noark5_evidence' / 'canonical-results.json'
        if not canonical.is_file():
            QMessageBox.information(self, 'Kanonisk resultatindeks',
                                    'Opprett resultatindeksen foerst.')
            return
        assessment_default = self.work / 'noark5_evidence' / 'experience_assessments.json'
        selected, _ = QFileDialog.getOpenFileName(
            self, 'Velg faglige vurderinger (valgfritt)',
            str(assessment_default if assessment_default.is_file() else self.work / 'noark5_evidence'),
            'JSON (*.json);;Alle filer (*)',
            options=QFileDialog.Option.DontUseNativeDialog)
        external, _ = QFileDialog.getOpenFileNames(
            self, 'Velg eksterne evidensfiler i Work (valgfritt)',
            str(self.work), 'Alle filer (*)',
            options=QFileDialog.Option.DontUseNativeDialog)
        if not selected and not external:
            return
        if QMessageBox.question(
                self, 'Koble evidens til kanonisk indeks',
                'Opprett/erstatt en separat kontekstindeks for de valgte filene?\n'
                'Kildene blir ikke endret. Bare gjenkjent Siegfried JSON tolkes som formatidentifikasjon; Arkade-filer uten kjent skjema beholdes som referanser.',
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No) != QMessageBox.StandardButton.Yes:
            return
        self._start({'__a4_context': {
            'assessments_path': selected or None,
            'external_paths': tuple(external),
        }})

    def reject(self):
        if not self._busy:
            super().reject()

    def closeEvent(self, event):
        if self._busy:
            event.ignore()
        else:
            super().closeEvent(event)


def install_canonical_results_menu(window):
    """Attach an opt-in GUI action without changing established result widgets."""
    menu = next((a.menu() for a in window.menuBar().actions()
                 if a.menu() is not None and a.text().replace('&', '') == 'Rapport'), None)
    if menu is None:
        return False
    action = QAction('Kanoniske resultatdata...', window)
    def launch():
        if getattr(window, '_worker', None) is not None:
            QMessageBox.warning(window, 'Pågående kjøring',
                                'Avslutt kontrollkjøringen før resultatindeksen bygges.')
            return
        active = getattr(window, '_active_id', None)
        if not active:
            QMessageBox.information(window, 'Velg jobb', 'Velg en eksisterende jobb først.')
            return
        try:
            job = window.api.job_details(active).job
            work = getattr(job, 'effective_work_operations', None)
            if not work:
                raise ValueError('Jobben mangler valgt Work operations.')
        except Exception as exc:
            QMessageBox.warning(window, 'Arbeidsområde', str(exc))
            return
        dialog = CanonicalResultsDialog(work, window)
        # Modal ownership: no dangling child or QThread when parent window closes.
        dialog.exec()
    action.triggered.connect(launch)
    menu.addAction(action)
    window._a15_canonical_action = action
    from .menu_position_v0115_a7 import install_main_menu_guard
    install_main_menu_guard(window)
    return True
