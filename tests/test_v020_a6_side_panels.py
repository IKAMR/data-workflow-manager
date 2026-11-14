"""a6: narrow-screen read models and safe Qt connection contract."""
from __future__ import annotations

import ast
from html import unescape
from pathlib import Path
from types import SimpleNamespace
import unittest

from app.result_side_evidence_v020_a6 import readable_side_evidence

ROOT = Path(__file__).resolve().parents[1]
SIDE = ROOT / 'gui_qt' / 'result_side_layout_v020_a6.py'
NAV = ROOT / 'gui_qt' / 'result_navigation_v020_a6.py'


class CompactSideEvidenceTests(unittest.TestCase):
    def test_long_hex_and_uuids_are_wrapped_without_nested_tables(self):
        digest = 'e7ffdd0b2a813b7e8b26976a06ed43b96348f0ed192221145d4ea2778efb10e'
        html = readable_side_evidence({
            'import_id': '20261113-e7ffdd0b2a81', 'sha256': digest,
            'test': {'has_results': False, 'number_of_errors': 0},
            'resultsets': [],
        })
        self.assertNotIn('<table', html)
        self.assertIn('Import-ID', html)
        self.assertIn('Antall feil', html)
        self.assertIn('SHA-256', html)
        self.assertIn('&#8203;', html)
        flattened = unescape(html).replace(chr(8203), '')
        self.assertIn(digest, flattened)
        self.assertIn('20261113-e7ffdd0b2a81', flattened)
        self.assertIn('Nei', flattened)
        self.assertIn('0', flattened)

    def test_html_escapes_untrusted_evidence_and_keeps_raw_original(self):
        source = {'value': '<script>bad()</script>', 'url': 'I:\\reports\\x' * 15}
        original = repr(source)
        html = readable_side_evidence(source)
        self.assertNotIn('<script>', html)
        self.assertIn('&lt;script&gt;', html)
        self.assertEqual(repr(source), original)

    def test_bound_large_nested_sources(self):
        model = {'data': [{'number': i} for i in range(10000)]}
        html = readable_side_evidence(model, max_nodes=30)
        self.assertLess(len(html), 5000)
        self.assertIn('forkortet', html)


class SidePanelWiringTests(unittest.TestCase):
    def test_installer_hook_runs_after_existing_group_navigation(self):
        source = NAV.read_text('utf-8')
        self.assertIn('install_responsive_side_panels(viewer)', source)
        self.assertLess(source.index('viewer._v020_a6_navigation = nav'),
                        source.index('install_responsive_side_panels(viewer)'))
        ast.parse(source)

    def test_width_adapts_to_actual_extraction_name(self):
        tree = ast.parse(SIDE.read_text('utf-8'))
        fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef)
                  and n.name == 'first_column_width')
        module = ast.fix_missing_locations(ast.Module(body=[fn], type_ignores=[]))
        namespace = {}
        exec(compile(module, str(SIDE), 'exec'), namespace)

        class Row:
            def __init__(self, text): self.value = text
            def isHidden(self): return False
            def text(self, index): return self.value

        class Tree:
            def __init__(self, texts): self.rows = [Row(t) for t in texts]
            def fontMetrics(self):
                return SimpleNamespace(horizontalAdvance=lambda t: len(t) * 8)
            def headerItem(self): return Row('Uttrekk')
            def topLevelItemCount(self): return len(self.rows)
            def topLevelItem(self, i): return self.rows[i]

        width = namespace['first_column_width'](Tree(['content'] * 90))
        self.assertGreaterEqual(width, 77)
        self.assertLess(width, 130)
        self.assertEqual(namespace['first_column_width'](Tree(['A' * 200])), 130)

    def test_keeps_saved_manual_split_and_original_raw_view(self):
        source = SIDE.read_text('utf-8')
        self.assertIn('viewer._a4_settings.value(setting, None)', source)
        self.assertIn('viewer._a53_setting_layout = True', source)
        self.assertIn('browser.setHtml(readable_side_evidence', source)
        self.assertNotIn('replaceWidget(', source)
        self.assertNotIn('deleteLater(', source)
        self.assertIn('Auto størrelse', source)
        ast.parse(source)


if __name__ == '__main__':
    unittest.main()
