"""Verify that a20 overlay does not remove the established archive-part route."""
from pathlib import Path
import ast
import unittest


ROOT=Path(__file__).resolve().parents[1]


class A20RepositoryContractTest(unittest.TestCase):
    def test_period_assessment_retains_native_archive_part_functions(self):
        path=ROOT/'noark5_workflow/reporting/period_assessment_a16.py'
        if not path.exists():
            self.skipTest('Full a19 repository not present in isolated delta test')
        module=ast.parse(path.read_text(encoding='utf-8'))
        functions={node.name for node in module.body if isinstance(node,ast.FunctionDef)}
        for name in ('save_assessment','save_part_assessment','load_assessment',
                     'load_part_assessment','part_review_candidate'):
            self.assertIn(name,functions)

    def test_period_dialog_keeps_whole_and_archive_part_selection(self):
        path=ROOT/'gui/period_assessment_dialog_a16.py'
        if not path.exists():
            self.skipTest('Full a19 repository not present in isolated delta test')
        source=path.read_text(encoding='utf-8')
        self.assertIn('Hele uttrekket',source)
        self.assertIn('save_part_assessment',source)
        self.assertIn('review_scope',source)

    def test_a20_gui_uses_common_report_service(self):
        source=(ROOT/'gui/report_selected_dialog_a16.py').read_text(encoding='utf-8')
        self.assertIn('report_service_a20 import write_report_package',source)
        self.assertIn("'CSV'",source)
        self.assertIn('open_period_assessment_dialog',source)
        self.assertNotIn('report_package_a16 import write_report_package',source)

    def test_legacy_report_u2_and_period_adapter_preserved(self):
        path=ROOT/'noark5_workflow/reporting/report_package_a16.py'
        if not path.exists():
            self.skipTest('Full a19 repository not present in isolated delta test')
        source=path.read_text(encoding='utf-8')
        self.assertIn('collect_u2_archive_parts',source)
        self.assertIn('render_archive_part_annex',source)
        self.assertIn('collect_period_sources',source)
        self.assertIn('build_source_comparison',source)


if __name__=='__main__':
    unittest.main()
