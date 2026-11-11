"""Headless behavioral checks against the a5.3 Qt-layer methods."""
from __future__ import annotations

import ast
from pathlib import Path
from types import SimpleNamespace
import unittest

from app.result_display_v0110_a5 import technical_test_name, arkade_tests_from_depot

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'gui_qt' / 'result_center_v0110_a4.py'
DETAIL_ROLE = 32


def extract(method_name):
    module = ast.parse(SOURCE.read_text(encoding='utf-8'))
    klass = next(n for n in module.body if isinstance(n, ast.ClassDef)
                 and n.name == 'ResultCenterWindow')
    method = next(n for n in klass.body if isinstance(n, ast.FunctionDef)
                  and n.name == method_name)
    ns = {
        'load_technical_test_names': lambda: {'kdrs.c06': 'Klasser', 'c06': 'Klasser'},
        'technical_test_name': technical_test_name,
        'arkade_tests_from_depot': arkade_tests_from_depot,
        'DETAIL_ROLE': DETAIL_ROLE,
    }
    exec(compile(ast.fix_missing_locations(ast.Module(body=[method], type_ignores=[])),
                 str(SOURCE), 'exec'), ns)
    return ns[method_name]


class FakeItem:
    def __init__(self, fields, details=None):
        self.fields = list(fields)
        self.details = details
        self.tooltips = {}

    def text(self, index):
        return self.fields[index] if index < len(self.fields) else ''

    def setText(self, index, value):
        while len(self.fields) <= index:
            self.fields.append('')
        self.fields[index] = value

    def setToolTip(self, index, value):
        self.tooltips[index] = value

    def data(self, _col, _role):
        return self.details

    def setData(self, _col, _role, data):
        self.details = data


class FakeTable:
    def __init__(self, items):
        self.items = items
        self.headers = ()

    def setHeaderLabels(self, names):
        self.headers = tuple(names)

    def topLevelItemCount(self):
        return len(self.items)

    def topLevelItem(self, n):
        return self.items[n]

    def clear(self):
        self.items.clear()


class FakeDetails:
    def __init__(self):
        self.cleared = False

    def clear(self):
        self.cleared = True


class FakeWindow:
    _a53_enrich_result_tables = extract('_a53_enrich_result_tables')

    def __init__(self, imports):
        self._trees = {
            'Tekniske kontroller': FakeTable([
                FakeItem(['Job', 'C06', 'N5.08', 'ok', 'Ukjent', 'Ukjent'],
                         {'test_id': 'kdrs.c06', 'legacy_job_id': 'C06', 'status': 'ok'}),
            ]),
            'Arkade 5': FakeTable([
                FakeItem(['Ingen lagret evidens for denne kilden', '', '', '', '', '']),
            ]),
        }
        self._details = {'Arkade 5': FakeDetails()}
        self._snapshots = [SimpleNamespace(
            job=SimpleNamespace(name='Job'),
            depot={'external_validation': {'arkade5': {'imports': imports}}},
            results=SimpleNamespace(depot_report_path=Path('/work/report.json')),
        )]

    def _row(self, tab, values, *, details=None, file=None):
        item = FakeItem(values, details)
        self._trees[tab].items.append(item)
        return item


class GuiContractTests(unittest.TestCase):
    def test_names_are_inserted_without_reordering_status_or_counts(self):
        w = FakeWindow([])
        w._a53_enrich_result_tables()
        row = w._trees['Tekniske kontroller'].items[0]
        self.assertEqual(w._trees['Tekniske kontroller'].headers, (
            'Uttrekk', 'Test-ID', 'Testnavn', 'Noark-punkt', 'Status', 'Kontroller', 'Avvik'))
        self.assertEqual(row.fields, ['Job', 'C06', 'Klasser', 'N5.08', 'ok', 'Ukjent', 'Ukjent'])
        self.assertEqual(row.details['testnavn_fra_testkatalog'], 'Klasser')
        self.assertEqual(row.details['status'], 'ok')

    def test_real_arkade_results_reappear_from_stored_report(self):
        w = FakeWindow([{
            'import_id': '2.13.1-run', 'source_sha256': 'abc',
            'coverage': {'arkade_control_areas': [
                {'arkade_test_id': 'N5.08', 'arkade_test_name': 'Klasser',
                 'arkade': {'present': True, 'status': 'ok', 'number_of_errors': 0}},
                {'arkade_test_id': 'N5.09', 'arkade_test_name': 'Andre',
                 'arkade': {'present': False, 'status': 'not_present'}},
            ]},
        }])
        w._a53_enrich_result_tables()
        rows = w._trees['Arkade 5'].items
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].fields, ['Job', 'N5.08', 'Klasser', 'ok', 0, '2.13.1-run'])
        self.assertEqual(rows[0].details['kilde_sha256'], 'abc')
        self.assertTrue(w._details['Arkade 5'].cleared)

    def test_unverified_import_keeps_diagnostic_not_invented_test(self):
        w = FakeWindow([{'import_id': 'I-1'}])
        w._a53_enrich_result_tables()
        rows = w._trees['Arkade 5'].items
        self.assertEqual(len(rows), 1)
        self.assertIn('Ingen lagret evidens for Arkade-tester', rows[0].text(0))

    def test_generic_viewer_is_wired_and_preserves_raw_pane(self):
        source = SOURCE.read_text(encoding='utf-8')
        viewer = (ROOT / 'gui_qt' / 'result_detail_view_v0110_a5.py').read_text(encoding='utf-8')
        self.assertIn('ResultCenterWindow(ResultDetailModesMixin, _PreviousResultCenter)', source)
        self.assertIn('self._a53_install_details()', source)
        self.assertIn('self._a53_enrich_result_tables()', source)
        self.assertIn('def _show_detail(self, tab: str)', viewer)
        self.assertIn('super()._show_detail(tab)', viewer)
        self.assertIn('splitter.insertWidget(1, browser)', viewer)
        self.assertIn('raw = self._details.get(tab)', viewer)
        self.assertIn('browser.setMarkdown(markdown)', viewer)
        self.assertIn('browser.setHtml(readable_html(value))', viewer)
        self.assertIn('setOpenLinks(False)', viewer)
        self.assertIn("'qt/result_detail_mode'", viewer)
        self.assertIn("'qt/result_splitter_fraction/'", viewer)
        self.assertIn('splitter.splitterMoved.connect', viewer)
