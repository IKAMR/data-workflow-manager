"""a5.6: Qt-free behavioral guards for side panes, tabs, and readable details.

Windows PySide6 still requires a manual GUI pass. These tests execute the
actual new layout methods using the lifetime-regression stand-ins.
"""
from __future__ import annotations

import ast
from pathlib import Path
import unittest

from app.result_display_v0110_a5 import readable_html
from test_v0110_a5_4_detail_widget_lifetime import Window

ROOT = Path(__file__).resolve().parents[1]
VIEWER = ROOT / 'gui_qt' / 'result_detail_view_v0110_a5.py'
CENTER = ROOT / 'gui_qt' / 'result_center_v0110_a4.py'


class SidePaneTests(unittest.TestCase):
    def test_side_layouts_have_full_height_detail_panes(self):
        w = Window()
        w._a53_install_details()
        for name, expected in [('Arkade 5', .61), ('PRONOM', .65),
                               ('Periodevurdering', .58)]:
            w.tabs.active = name
            w._a53_apply_splitter()
            splitter = w._a53_splitters[name]
            upper, readable, raw = splitter.sizes()
            self.assertEqual(splitter.orientation, 'horizontal')
            self.assertEqual(raw, 0)
            self.assertAlmostEqual(upper / (upper + readable), expected, delta=.006)

    def test_single_row_shrinks_height_and_large_table_is_bounded(self):
        w = Window()
        w._a53_install_details()
        w.tabs.active = 'Oversikt'
        w._a53_apply_splitter()
        sizes = w._a53_splitters['Oversikt'].sizes()
        self.assertLessEqual(sizes[0], int(sum(sizes) * .16))
        self.assertGreater(sizes[1], sizes[0])

        w.tabs.active = 'Arkivdeler'
        # Simulate 25 actual rows in the results, not 25 placeholders.
        w._trees['Arkivdeler'].rows *= 25
        w._a53_apply_splitter()
        sizes = w._a53_splitters['Arkivdeler'].sizes()
        self.assertLessEqual(sizes[0] / sum(sizes), .65)
        self.assertGreater(sizes[1], 0)

    def test_horizontal_manual_width_persists_and_auto_reset_works(self):
        w = Window()
        w._a53_install_details()
        w.tabs.active = 'PRONOM'
        splitter = w._a53_splitters['PRONOM']
        splitter.setSizes([490, 210, 0])
        w._a53_store_splitter('PRONOM')
        self.assertAlmostEqual(float(w._a4_settings.value(
            'qt/result_splitter_fraction_horizontal/PRONOM')), .7, delta=.001)
        w._a53_apply_splitter()
        self.assertAlmostEqual(splitter.sizes()[0] / sum(splitter.sizes()), .7, delta=.006)
        w._a53_auto_size('PRONOM')
        w._a53_apply_splitter()
        self.assertAlmostEqual(splitter.sizes()[0] / sum(splitter.sizes()), .65, delta=.006)

    def test_modes_are_tabs_and_raw_widget_is_never_replaced(self):
        source = VIEWER.read_text(encoding='utf-8')
        self.assertIn('QTabBar()', source)
        self.assertIn("selector.addTab('Lesbar visning')", source)
        self.assertIn("selector.addTab('Råtekst / JSON')", source)
        self.assertIn("'Periodevurdering'", source)
        self.assertIn('splitter.setOrientation(Qt.Orientation.Horizontal)', source)
        self.assertNotIn('splitter.replaceWidget(', source)
        w = Window()
        w._a53_install_details()
        before = dict(w._details)
        w._a53_select_detail_mode('Arkade 5', 1)
        w._a53_select_detail_mode('PRONOM', 0)
        for key, raw in before.items():
            self.assertIs(raw, w._details[key])
            raw.setPlainText('Still alive ' + key)
            self.assertEqual(raw.toPlainText(), 'Still alive ' + key)


class FlatDetailPresentationTests(unittest.TestCase):
    def test_nested_details_use_one_flat_table_not_tables_in_tables(self):
        details = {
            'arkade_kontroll': {
                'arkade': {'number_of_errors': 10461, 'result_count': 10582},
                'arkade_test_id': 'N5.29',
                'note_nb': 'DWM har dokumentformatdata',
            },
            'import_id': '2024-Jan-test',
        }
        html = readable_html(details)
        self.assertEqual(html.count('<table'), 1)
        self.assertEqual(html.count('</table>'), 1)
        self.assertIn('Arkade-kontroll', html)
        self.assertIn('Antall feil', html)
        self.assertIn('10461', html)
        self.assertIn('N5.29', html)
        self.assertIn('Import-ID', html)
        self.assertIn('DWM har dokumentformatdata', html)

    def test_lists_are_bounded_and_untrusted_markup_is_escaped(self):
        html = readable_html({'<iframe>': [{'a': '<script>alert(1)</script>'}]})
        self.assertNotIn('<iframe>', html)
        self.assertNotIn('<script>', html)
        self.assertIn('&lt;script&gt;', html)
        self.assertEqual(html.count('<table'), 1)
        huge = readable_html({'vurderingspunkter': [{'i': n} for n in range(100)]}, max_nodes=9)
        self.assertIn('Avkortet', huge)
        self.assertIn('Råtekst / JSON', huge)


class ColumnLayoutTests(unittest.TestCase):
    def test_test_names_are_wide_and_no_source_column_disappears(self):
        tree = ast.parse(CENTER.read_text(encoding='utf-8'))
        cls = next(n for n in tree.body if isinstance(n, ast.ClassDef)
                   and n.name == 'ResultCenterWindow')
        method = next(n for n in cls.body if isinstance(n, ast.FunctionDef)
                      and n.name == '_a56_configure_columns')
        self.assertNotIn('setHeaderLabels', ast.unparse(method))
        class Row:
            def __init__(self, values):
                self.values = values
                self.tips = {}
            def setToolTip(self, index, value): self.tips[index] = value
            def text(self, index): return self.values[index]
        class Header:
            def __init__(self): self.mode = None
            def setSectionResizeMode(self, index, mode): self.mode = (index, mode)
        class Tree:
            def __init__(self, values):
                self.values = values
                self.columns = {}
                self.row = Row(values)
                self._header = Header()
            def header(self): return self._header
            def columnCount(self): return len(self.values)
            def setColumnWidth(self, i, width): self.columns[i] = width
            def topLevelItemCount(self): return 1
            def topLevelItem(self, _index): return self.row
        stubs = {
            'Tekniske kontroller': Tree(['Work', 'C06', 'Klasser', 'N5.08', 'ok', '0', '0']),
            'Arkade 5': Tree(['Work', 'N5.29', 'Antall av ulike dokumentformater', 'error', '10461', 'ID']),
            'PRONOM': Tree(['Work', 'fmt/16', 'PDF', '1.2', '123', 'Ikke gyldig', 'Akseptert']),
            'Periodevurdering': Tree(['Work', 'Arkivdel', 'Ukjent', '2001-2006', 'ikke_vurdert', '–']),
        }
        ns = {'QHeaderView': type('QHeaderView', (), {'ResizeMode': type('R', (),
                 {'Interactive': 'interactive'})})}
        exec(compile(ast.fix_missing_locations(ast.Module(body=[method], type_ignores=[])),
                     str(CENTER), 'exec'), ns)
        obj = type('Fake', (), {'_trees': stubs, '_a56_configure_columns': ns['_a56_configure_columns']})()
        obj._a56_configure_columns()
        self.assertEqual(stubs['PRONOM']._header.mode, (0, 'interactive'))
        self.assertGreaterEqual(stubs['Tekniske kontroller'].columns[2], 370)
        self.assertGreaterEqual(stubs['Arkade 5'].columns[2], 325)
        self.assertIn(5, stubs['Arkade 5'].columns)  # import ID preserved
        self.assertEqual(stubs['Arkade 5'].row.tips[2], 'Antall av ulike dokumentformater')


if __name__ == '__main__':
    unittest.main()
