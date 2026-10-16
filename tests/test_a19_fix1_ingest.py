"""Regression tests for Mottak / Ingest fields, structure, uniqueness and event logging."""
from __future__ import annotations

import json
import sys
import tempfile
import types
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

from app.receiving_folders import (
    adjusted_label_folder, create_receiving_folders, load_profiles,
    plan_receiving_folders, resolve_receiving_base, suggested_folder_name,
    suggested_receipt_number,
)

PROFILE_FILE = Path(__file__).resolve().parents[1] / 'config' / 'receiving_folder_profiles.json'


class IngestFix1Tests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.disk = Path(tmp.name)
        self.root = self.disk / 'karantene-01'
        self.root.mkdir()
        self.profile = load_profiles(PROFILE_FILE)[0]

    def test_profile_tree_has_three_sibling_roots(self):
        plan = plan_receiving_folders(self.root, '1580 Test', self.profile,
                  {'label': '1580 Test'}, label='1580 Test', receipt_number='20261015-001')
        paths = {str(p.relative_to(plan.root)).replace('\\', '/') for p in plan.paths}
        self.assertEqual(paths, {'.'})
        self.assertEqual(plan.audit_path, plan.root / 'ingest.events.jsonl')

    def test_receipt_number_start_value_is_editable_not_in_folder_name(self):
        number = suggested_receipt_number(self.profile, now=datetime(2026, 10, 15, 18, 30, 12))
        self.assertEqual(number, '20261015-183012')
        plan = plan_receiving_folders(self.root, 'LABEL', self.profile,
                 {'label': 'LABEL'}, label='LABEL', receipt_number='IKAMR-E-888')
        self.assertEqual(plan.root.name, 'LABEL')
        self.assertEqual(plan.receipt_number, 'IKAMR-E-888')

    def test_missing_label_is_rejected(self):
        with self.assertRaises(ValueError):
            adjusted_label_folder('   ')

    def test_sanitization_does_not_change_original_label(self):
        original = 'ABC/12: Forsøk'
        folder = adjusted_label_folder(original)
        self.assertEqual(folder, 'ABC - 12 - Forsøk')
        self.assertEqual(original, 'ABC/12: Forsøk')

    def test_casefold_collision_is_rejected(self):
        (self.root / 'ABC').mkdir()
        with self.assertRaises(FileExistsError):
            plan_receiving_folders(self.root, 'abc', self.profile, {'label':'abc'})

    def test_root_must_exist_and_stay_on_disk(self):
        self.assertEqual(resolve_receiving_base(self.disk, 'karantene-01'), self.root)
        # The selected spelling must be stable even if canonicalization expands
        # Windows' 8.3 path components for permission/containment checks.
        self.assertEqual(resolve_receiving_base(self.disk, 'karantene-01'), self.disk / 'karantene-01')
        for bad in ('../escape', 'karantene-01/../escape', '/tmp', 'C:/Windows'):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                resolve_receiving_base(self.disk, bad)
        with self.assertRaises(ValueError):
            resolve_receiving_base(self.disk, 'does-not-exist')

    def test_selected_disk_alias_is_preserved_after_security_checks(self):
        # A directory alias emulates Windows 8.3-to-long-path expansion.
        alias = self.disk.parent / (self.disk.name + '_alias')
        try:
            alias.symlink_to(self.disk, target_is_directory=True)
        except (OSError, NotImplementedError):
            self.skipTest('Directory aliases require symlink permission on this platform')
        self.addCleanup(alias.unlink)
        self.assertEqual(resolve_receiving_base(alias, 'karantene-01'), alias / 'karantene-01')

    def test_cannot_plan_audit_log_outside_planned_dirs(self):
        from app.receiving_folders import ReceiveProfile
        bad = ReceiveProfile('bad','Bad','{label}',('content/sip',),audit_file='repository_operations/audit.jsonl')
        with self.assertRaisesRegex(ValueError, 'Loggmappen'):
            plan_receiving_folders(self.root, 'Test', bad, {'label':'Test'})

    def test_canonical_ingest_event_written_once(self):
        plan = plan_receiving_folders(self.root, 'Testmottak', self.profile,
                  {'label': 'Testmottak'}, label='Testmottak', receipt_number='R-002')
        events_module = types.ModuleType('noark5_workflow.core.events')
        store_module = types.ModuleType('noark5_workflow.sinks.event_store')
        class DummyEvent:
            @classmethod
            def now(cls, kind, **fields):
                return {'kind': kind, **fields}
        class DummySink:
            def __init__(self, path):
                self.path = path
            def handle(self, event):
                self.path.write_text(json.dumps(event, ensure_ascii=False))
        events_module.WorkflowEvent = DummyEvent
        store_module.GenericEventStoreSink = DummySink
        with patch.dict(sys.modules, {
            'noark5_workflow': types.ModuleType('noark5_workflow'),
            'noark5_workflow.core': types.ModuleType('noark5_workflow.core'),
            'noark5_workflow.core.events': events_module,
            'noark5_workflow.sinks': types.ModuleType('noark5_workflow.sinks'),
            'noark5_workflow.sinks.event_store': store_module,
        }):
            create_receiving_folders(plan)
        event = json.loads(plan.audit_path.read_text(encoding='utf-8'))
        self.assertEqual(event['kind'], 'ingest.receiving_folders.created')
        self.assertEqual(event['data']['receipt_number'], 'R-002')
        self.assertEqual(event['data']['label'], 'Testmottak')
        with self.assertRaises(FileExistsError):
            create_receiving_folders(plan)

    def test_failed_audit_logging_removes_only_new_empty_tree(self):
        plan = plan_receiving_folders(self.root, 'Temp', self.profile,
                  {'label': 'Temp'}, label='Temp', receipt_number='R-003')
        events_module = types.ModuleType('noark5_workflow.core.events')
        store_module = types.ModuleType('noark5_workflow.sinks.event_store')
        class DummyEvent:
            @classmethod
            def now(cls, kind, **kwargs): return None
        class FailingSink:
            def __init__(self, path): pass
            def handle(self, event): raise OSError('test audit failure')
        events_module.WorkflowEvent = DummyEvent
        store_module.GenericEventStoreSink = FailingSink
        with patch.dict(sys.modules, {
            'noark5_workflow': types.ModuleType('noark5_workflow'),
            'noark5_workflow.core': types.ModuleType('noark5_workflow.core'),
            'noark5_workflow.core.events': events_module,
            'noark5_workflow.sinks': types.ModuleType('noark5_workflow.sinks'),
            'noark5_workflow.sinks.event_store': store_module,
        }):
            with self.assertRaisesRegex(OSError,'test audit failure'):
                create_receiving_folders(plan)
        self.assertFalse(plan.root.exists())

    def test_label_from_info_is_not_automatic_receipt_number(self):
        from app.receiving_folders import ReceiveProfile
        folder = suggested_folder_name(ReceiveProfile('id','p','{label}',()),
                                       {'label':'SIP 0001','reference_code':'Other Agreement'})
        self.assertEqual(folder, 'SIP 0001')


if __name__ == '__main__':
    unittest.main()
