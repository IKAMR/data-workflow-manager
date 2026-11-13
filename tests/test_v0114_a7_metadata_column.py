"""Regression for compact Noark metadata ID column."""
import ast
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class MetadataColumnTest(unittest.TestCase):
    def test_compact_column_and_mapping_from_reference(self):
        source = (ROOT / 'gui_qt/standard_values_v0114_a2.py').read_text(encoding='utf-8')
        ast.parse(source)
        self.assertIn("QTableWidget(len(findings), 7, splitter)", source)
        self.assertIn("'M-ID'", source)
        self.assertIn("'Forekomster'", source)
        self.assertIn('reference_for_finding(finding.test_id, finding.field, finding.version)', source)
        self.assertIn("reference['metadata_id'] if reference else '–'", source)
        self.assertIn('extract_display_name(finding.job_name, finding.report_path)', source)
        self.assertIn('self.table.setColumnWidth(1, 65)', source)
        self.assertIn('self.table.itemSelectionChanged.connect(self._show_selected)', source)

    def test_dialog_opens_large_on_parent_monitor(self):
        source = (ROOT / 'gui_qt/standard_values_v0114_a2.py').read_text(encoding='utf-8')
        ast.parse(source)
        self.assertIn('QGuiApplication.screenAt(parent_center)', source)
        self.assertIn('screen.availableGeometry()', source)
        self.assertIn('area.width() * 0.92', source)
        self.assertIn('area.height() * 0.92', source)
        self.assertIn('splitter.setChildrenCollapsible(False)', source)
        self.assertNotIn('self.resize(1040, 670)', source)
        self.assertIn('splitter.setSizes([255,', source)

    def test_distributed_plan_is_preserved(self):
        plan = (ROOT / 'docs/NOARK5-CANONICAL-RESULTS-AND-KNOWLEDGE-ROADMAP.md').read_text(encoding='utf-8')
        for term in ('Depotserver', 'Klient', 'Bruker', 'GitHub', 'KDRS',
                     'eksport/import', 'konflikt', 'M300'):
            with self.subTest(term=term):
                self.assertIn(term, plan)


if __name__ == '__main__':
    unittest.main()
