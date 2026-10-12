"""Regression coverage for the current GUI entrypoint's XSD runner wiring."""
import ast
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class A152XsdRuntimeTests(unittest.TestCase):
    def test_current_runtime_installs_a39(self):
        p = ROOT / 'gui' / 'persistent_app_a4_6_runtime.py'
        source = p.read_text(encoding='utf-8')
        ast.parse(source)
        self.assertIn('from noark5_workflow.core.job_runner_a39 import A39JobRunner', source)
        self.assertIn('self._a152_restore_xsd_continuation()', source)
        self.assertIn('batch.job_runner = runner', source)
        self.assertIn('source_factory=previous.source_factory', source)

    def test_existing_xsd_logic_is_nonblocking_only_for_findings(self):
        source = (ROOT / 'noark5_workflow' / 'core' / 'job_runner_a39.py').read_text(encoding='utf-8')
        self.assertIn('_NON_BLOCKING_OPERATION_ID = "validate_xml_schema"', source)
        self.assertIn('_NON_BLOCKING_MESSAGE_PREFIX = "XML/XSD-validering feilet med "', source)
        self.assertIn('job.mark_operation_completed(failed_index)', source)


if __name__ == '__main__':
    unittest.main()
