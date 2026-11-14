"""a16: read-only existing DIAS linkage and no new package generator."""
from __future__ import annotations
import tempfile
import unittest
import importlib.util
import sys
import types
from pathlib import Path
from unittest.mock import patch
# Allow the focused test to run against a delta-only checkout too.
import noark5_workflow.analysis as package
if importlib.util.find_spec('noark5_workflow.analysis.canonical_results') is None:
    module = types.ModuleType('noark5_workflow.analysis.canonical_results')
    module._validate_work = lambda path: (Path(path), {'job_uid': 'test'})
    sys.modules[module.__name__] = module
    package.canonical_results = module
if importlib.util.find_spec('noark5_workflow.analysis.canonical_matrix_v0115_a11') is None:
    module = types.ModuleType('noark5_workflow.analysis.canonical_matrix_v0115_a11')
    module.load_external_status = lambda path: {'state': 'not_analyzed', 'sources': {}}
    sys.modules[module.__name__] = module
    package.canonical_matrix_v0115_a11 = module
from noark5_workflow.analysis import dias_preservation_link_v0115_a16 as link

class DiasLinkTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.work = Path(self.tmp.name)
        self.check = patch.object(link, '_validate_work', return_value=(self.work, {'job_uid': 'test'}))
        self.check.start(); self.addCleanup(self.check.stop)

    def test_not_created_does_not_create_directories(self):
        before = tuple(self.work.iterdir())
        report = link.inspect_dias_preservation_link(self.work)
        self.assertEqual(report['evidence_state'], 'not_created')
        self.assertEqual(tuple(self.work.iterdir()), before)
        self.assertFalse(report['dias_aip_created_by_this_check'])
        self.assertFalse(report['sip_retention_decision_by_this_check'])
        self.assertFalse(report['approval_registered_by_this_check'])

    def test_existing_folder_without_manifest_is_not_approved(self):
        (self.work / link.OUT).mkdir(parents=True)
        report = link.inspect_dias_preservation_link(self.work)
        self.assertEqual(report['evidence_state'], 'manifest_missing')
        self.assertFalse(report['approval_registered_by_this_check'])

    def test_staged_verified_is_not_aip(self):
        (self.work / link.OUT).mkdir(parents=True)
        (self.work / link.OUT / link.INDEX).write_text('{"open_requirements":["Unresolved"]}')
        with patch.object(link, 'verify_candidate', return_value={'verified': True, 'files': 8}):
            report = link.inspect_dias_preservation_link(self.work)
        self.assertEqual(report['evidence_state'], 'verified_evidence_candidate')
        self.assertEqual(report['open_requirements'], ['Unresolved'])
        self.assertFalse(report['dias_aip_created_by_this_check'])

    def test_integrity_failure_is_visible(self):
        (self.work / link.OUT).mkdir(parents=True)
        (self.work / link.OUT / link.INDEX).write_text('{"open_requirements": []}')
        with patch.object(link, 'verify_candidate', return_value={'verified': False, 'files': 1}):
            report = link.inspect_dias_preservation_link(self.work)
        self.assertEqual(report['evidence_state'], 'evidence_integrity_failed')

if __name__ == '__main__': unittest.main()
