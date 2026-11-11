"""a5 headless GUI contracts and filtered-summary regression check."""
from __future__ import annotations

import ast
from pathlib import Path
import re
import unittest

from version import VERSION

from app.format_context_v0110_a5 import comparison_labels
from app.format_policy_v0110_a4 import (
    STATUS_ACCEPTED, STATUS_CLARIFY, STATUS_UNIDENTIFIED, STATUS_NOT_ASSESSED,
    summarize_format_assessments,
)

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / 'gui_qt' / 'result_center_v0110_a4.py'


class FakeItem:
    def __init__(self, values, status):
        self.values, self.status, self.hidden = values, status, False
    def data(self, _col, _role):
        return self.status
    def text(self, col):
        return self.values[col]
    def columnCount(self):
        return len(self.values)
    def setHidden(self, value):
        self.hidden = bool(value)


class FakeCombo:
    def __init__(self, value):
        self.value = value
    def currentData(self):
        return self.value


class FakeField:
    def __init__(self, value=''):
        self.value = value
    def text(self):
        return self.value
    def setText(self, value):
        self.value = value


class FakeTable:
    def __init__(self, rows):
        self.rows = rows
    def topLevelItemCount(self):
        return len(self.rows)
    def topLevelItem(self, index):
        return self.rows[index]


def load_filter_method():
    source = ast.parse(SRC.read_text(encoding='utf-8'))
    klass = next(x for x in source.body if isinstance(x, ast.ClassDef)
                 and x.name == 'ResultCenterWindow')
    method = next(x for x in klass.body if isinstance(x, ast.FunctionDef)
                  and x.name == '_a4_filter_pronom')
    module = ast.Module(body=[method], type_ignores=[])
    ns = dict(STATUS_ACCEPTED=STATUS_ACCEPTED, STATUS_CLARIFY=STATUS_CLARIFY,
              STATUS_UNIDENTIFIED=STATUS_UNIDENTIFIED, STATUS_NOT_ASSESSED=STATUS_NOT_ASSESSED,
              summarize_format_assessments=summarize_format_assessments,
              comparison_labels=comparison_labels, _FORMAT_STATUS_ROLE=99)
    exec(compile(ast.fix_missing_locations(module), str(SRC), 'exec'), ns)
    return ns['_a4_filter_pronom']


class ResultCenterA5Contract(unittest.TestCase):
    def test_integration_keeps_active_qt_runtime_and_discovery(self):
        code = SRC.read_text(encoding='utf-8')
        main = (ROOT / 'gui_qt' / 'main_window.py').read_text(encoding='utf-8')
        self.assertIn('from .result_center_v0110_a4 import ResultCenterWindow as EvidenceResultCenter', main)
        self.assertIn('Vis filformatvurderinger (PRONOM)', code)
        self.assertIn('TO UAVHENGIGE VURDERINGER', code)
        self.assertIn('Arkade RAF-220301 (historisk)', code)
        self.assertIn('Valgt regelprofil (uavhengig)', code)
        self.assertIn('Kilder og datoer…', code)
        self.assertIn('read_pronom_import_context', code)
        self.assertIn('export_comparison_csv', code)
        self.assertNotIn('shutil.copy', code)
        self.assertNotIn('.mkdir(', code)
        self.assertNotIn('manuell_konvertering', code)

    def test_versions_are_synced(self):
        # The completed 0.1.10 release is newer than the a5 milestone.
        match = re.fullmatch(r'(\d+)\.(\d+)\.(\d+)(?:-a(\d+)(?:\.(\d+))*)?', VERSION)
        self.assertIsNotNone(match, VERSION)
        release = tuple(int(match.group(i)) for i in (1, 2, 3))
        self.assertGreaterEqual(release, (0, 1, 10))
        if release == (0, 1, 10) and match.group(4) is not None:
            self.assertGreaterEqual(int(match.group(4)), 5)
        module = (ROOT / 'version.py').read_text(encoding='utf-8')
        self.assertIn(f'VERSION = "{VERSION}"', module)
        project = (ROOT / 'pyproject.toml').read_text(encoding='utf-8')
        self.assertIn(f'version = "{VERSION.replace("-a", "a")}"', project)

    def test_filter_summary_only_counts_visible_observations(self):
        method = load_filter_method()
        first = FakeItem(['utt', 'fmt/101', 'XML', '1.0', '2', 'Gyldig',
                          'Akseptert i valgt profil'], STATUS_ACCEPTED)
        second = FakeItem(['utt', 'fmt/999999', 'BIN', '', '12', 'Ikke gyldig',
                           'Til avklaring'], STATUS_CLARIFY)
        class FakeWindow:
            _a4_filter_pronom = method
            _a4_ready = True
            _a5_missing_policy_warning = ''
        w = FakeWindow()
        w._a4_format_policy = None
        w._a4_format_rows = [
            (first, {'format_id': 'fmt/101', 'count': 2, 'imported_at': '2026-11-10'}),
            (second, {'format_id': 'fmt/999999', 'count': 12, 'imported_at': '2026-10-10'}),
        ]
        w.format_status_combo = FakeCombo('')
        w.format_search = FakeField('fmt/101')
        w.format_summary = FakeField()
        w.format_arkade_source = FakeField()
        w.format_profile_source = FakeField()
        w._trees = {'PRONOM': FakeTable([first, second])}
        w._a4_filter_pronom()
        self.assertFalse(first.hidden)
        self.assertTrue(second.hidden)
        self.assertIn('1 av 2', w.format_summary.value)
        self.assertIn('Ikke vurdert: 2', w.format_summary.value)
        self.assertNotIn('12 filer', w.format_summary.value)
        self.assertIn('2026-11-10', w.format_arkade_source.value)
        self.assertNotIn('2026-10-10', w.format_arkade_source.value)


if __name__ == '__main__':
    unittest.main()
