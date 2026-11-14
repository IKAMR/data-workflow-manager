"""a6: responsive result grouping, readable depot evidence and toolbar placement."""
from __future__ import annotations

import ast
from pathlib import Path
from types import SimpleNamespace
import tomllib
import unittest

from app.depot_review_display_v020_a6 import readable_depot_review
from app.result_tabs_v020_a6 import GROUP_DEFINITIONS, grouped_result_titles
from version import VERSION
from tests.version_assertions import assert_release_at_least

ROOT = Path(__file__).resolve().parents[1]


def fake_row(**changes):
    value = {
        'scope': 'uttrekk', 'title': 'Hele uttrekket', 'job_name': 'Testuttak',
        'job_id': 'JOB-001', 'native_id': '', 'technical_status': 'ok',
        'professional_status': 'Ikke vurdert', 'period_status': 'Ikke vurdert',
        'deviation_count': None, 'history_count': 0, 'updated_at': '',
        'warning': '', 'details': {},
    }
    value.update(changes)
    return SimpleNamespace(**value)


class GroupingTests(unittest.TestCase):
    def test_every_current_tab_retained_exactly_once(self):
        original = ('Oversikt', 'Arkivdeler', 'Årsfordeling', 'Tekniske kontroller',
                    'Arkade 5', 'PRONOM', 'KDRS Query', 'Periodevurdering',
                    'Depotrapporter', 'Evidensfiler', 'Kildeoversikt',
                    'Arkade-dekning', 'Depotvurdering')
        groups = grouped_result_titles(original)
        self.assertEqual(len(groups), 4)
        self.assertEqual([heading for heading, _ in groups],
                         [heading for heading, _ in GROUP_DEFINITIONS])
        classified = [title for _, titles in groups for title in titles]
        self.assertEqual(set(classified), set(original))
        self.assertEqual(len(classified), len(original))
        self.assertIn('Depotvurdering', groups[3][1])
        self.assertIn('Periodevurdering', groups[3][1])
        self.assertIn('KDRS Query', groups[1][1])

    def test_new_unknown_tab_remains_accessible(self):
        groups = grouped_result_titles(('Depotvurdering', 'Nye analyser', 'KDRS Query'))
        self.assertIn('Nye analyser', groups[0][1])
        self.assertIn('Depotvurdering', groups[3][1])

    def test_empty_tab_list_does_not_fail(self):
        self.assertEqual(len(grouped_result_titles(())), 4)
        self.assertTrue(all(not rows for _, rows in grouped_result_titles(())))


class ReadabilityTests(unittest.TestCase):
    def test_unknown_is_not_approved_or_a_numeric_zero(self):
        result = readable_depot_review(fake_row())
        self.assertIn('Ikke vurdert', result)
        self.assertIn('Ikke oppgitt', result)
        self.assertIn('Ingen faglig beslutning er registrert', result)
        self.assertNotIn('Automatisk godkjent', result)

    def test_readable_depot_decision_preserves_reason_user_time(self):
        row = fake_row(professional_status='Akseptert med avvik', history_count=1,
            updated_at='2026-11-14T19:00:00+01:00', details={
              'rapportert_oversikt': {'archive_count': 1, 'archive_part_count': 4,
                                       'folder_count': 132, 'registration_count': 467},
              'faglig_beslutning': {
                  'status': 'accepted_with_deviation', 'reason': 'Sjekket avvik',
                  'assessed_at': '2026-11-14T19:00:00+01:00',
                  'user': {'name': 'Fagperson'}},
              'periode_oppgitt': '2008–2022',
              'vurderingspunkter': [{'message': 'Manglende dokument-ID'}],
              'evidenskilder': [{'kilde': 'Arkade 5', 'import_id': 'a1',
                                'antall': 12, 'status': 'importert'}],
              'rapport': 'I:/Work/depot_validation_report.json',
              'rapport_sha256': 'a'*64,
            })
        result=readable_depot_review(row)
        for item in ('Akseptert med avvik', 'Sjekket avvik', 'Fagperson',
                     '132', '467', '2008–2022', 'Manglende dokument-ID',
                     'Arkade 5', 'I:/Work/depot_validation_report.json', 'a'*64):
            self.assertIn(item, result)

    def test_archive_part_deviations_are_not_whole_extraction_deviations(self):
        result = readable_depot_review(fake_row(scope='arkivdel', title='Arkivdel X',
            native_id='system-123', details={
                'vurderingspunkter': [{'message': 'UTTREKK_AVVIK'}],
                'avvik_per_arkivdel': [{'message': 'ARKIVDEL_AVVIK'}],
                'evidenskilder': [{'kilde': 'KDRS Query'}],
            }))
        self.assertIn('system-123', result)
        self.assertIn('ARKIVDEL_AVVIK', result)
        self.assertNotIn('UTTREKK_AVVIK', result)
        self.assertIn('opptalt på uttrekksnivå', result)

    def test_content_limits_and_no_disk_access(self):
        notes = [{'message': f'punkt{i}'} for i in range(25)]
        row = fake_row(details={'vurderingspunkter': notes,
                                'evidenskilder': [{'kilde':'A'}]*30})
        result=readable_depot_review(row, max_findings=3, max_sources=2)
        self.assertIn('punkt2', result)
        self.assertNotIn('punkt3', result)
        self.assertIn('Ytterligere 22', result)
        self.assertIn('Ytterligere 28', result)
        text=(ROOT/'app/depot_review_display_v020_a6.py').read_text(encoding='utf-8')
        for forbidden in ('open(', '.read_text(', '.write_text(', 'record_depot_review('):
            self.assertNotIn(forbidden, text)


class PresentationContractTests(unittest.TestCase):
    def test_qt_entrypoint_uses_direct_a6_subclass(self):
        main=(ROOT/'gui_qt/__main__.py').read_text(encoding='utf-8')
        self.assertIn('from gui_qt.main_v020_a6 import DwmMainWindow', main)
        driver=(ROOT/'gui_qt/main_v020_a6.py').read_text(encoding='utf-8')
        self.assertIn('super()._a12_open_result_center(',driver)
        self.assertIn('install_compact_result_navigation(viewer)',driver)
        self.assertNotIn('sys.modules',driver)

    def test_original_result_pages_retained_and_original_navigation_observed(self):
        path=ROOT/'gui_qt/result_navigation_v020_a6.py'
        source=path.read_text(encoding='utf-8')
        ast.parse(source)
        self.assertIn('tabs.currentChanged.connect(self.sync_from_original)',source)
        self.assertIn('self.tabs.setCurrentIndex(index)',source)
        self.assertIn('tabs.tabBar().hide()',source)
        self.assertIn("getattr(viewer, '_a2_panel'", source)
        self.assertNotIn('removeTab(',source)
        self.assertNotIn('insertTab(',source)
        self.assertNotIn('setParent(',source)

    def test_depot_json_remains_available_and_no_review_write(self):
        source=(ROOT/'gui_qt/result_navigation_v020_a6.py').read_text(encoding='utf-8')
        self.assertIn("QCheckBox('Vis rå JSON'",source)
        self.assertIn('_review_payload(row)',source)
        self.assertIn('readable_depot_review(row)',source)
        self.assertNotIn('record_depot_review(',source)

    def test_a5_buttons_are_always_beside_filter(self):
        source=(ROOT/'gui_qt/production_progress_v020_a5.py').read_text(encoding='utf-8')
        self.assertEqual(source.count("QPushButton('Fortsett sist', body)"),1)
        self.assertEqual(source.count("QPushButton('Oppdater status', body)"),1)
        nav_start=source.index('history_row = QHBoxLayout()')
        nav_end=source.index('content.addLayout(history_row)',nav_start)
        row=source[nav_start:nav_end]
        self.assertIn('history_row.addWidget(self.history_filter)',row)
        self.assertIn('history_row.addWidget(self.resume)',row)
        self.assertIn('history_row.addWidget(self.refresh_button)',row)

    def test_version_distribution(self):
        assert_release_at_least(self, f'VERSION = "{VERSION}"', "0.2.0", 6)
        with (ROOT/'pyproject.toml').open('rb') as file:
            self.assertEqual(tomllib.load(file)['project']['version'],VERSION.replace('-a','a'))


if __name__ == '__main__':
    unittest.main()
