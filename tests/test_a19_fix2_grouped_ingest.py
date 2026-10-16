"""a19-fix2: grouped receipt + independent extraction folders, identity and audit."""
import json
import sys
import tempfile
import types
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

from app.grouped_ingest import (
    create_grouped_ingest, grouped_profiles, plan_receipt, plan_extraction,
    suggest_receipt_number,
)

PROFILE_FILE = Path(__file__).resolve().parents[1] / 'config' / 'receiving_folder_profiles.json'


class FakeEvent:
    @classmethod
    def now(cls, kind, **kwargs):
        return {'kind': kind, 'data': kwargs['data'], 'user':kwargs.get('user'),
                'run_id': kwargs['run_id']}


class FakeSink:
    def __init__(self, path): self.path = path
    def handle(self, event):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open('a', encoding='utf-8') as f:
            f.write(json.dumps(event, ensure_ascii=False) + '\n')


class GroupedIngestTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.disk = Path(tmp.name)
        self.group = self.disk / 'arkiv-karantene-01'
        self.group.mkdir()
        self.other_group = self.disk / 'arkiv-karantene-02'
        self.other_group.mkdir()
        self.profile = grouped_profiles(PROFILE_FILE)[0]
        modules = {
          'noark5_workflow':types.ModuleType('noark5_workflow'),
          'noark5_workflow.core':types.ModuleType('noark5_workflow.core'),
          'noark5_workflow.core.events':types.ModuleType('noark5_workflow.core.events'),
          'noark5_workflow.sinks':types.ModuleType('noark5_workflow.sinks'),
          'noark5_workflow.sinks.event_store':types.ModuleType('noark5_workflow.sinks.event_store'),
        }
        modules['noark5_workflow.core.events'].WorkflowEvent = FakeEvent
        modules['noark5_workflow.sinks.event_store'].GenericEventStoreSink = FakeSink
        p = patch.dict(sys.modules, modules)
        p.start()
        self.addCleanup(p.stop)

    def make_receipt(self, number='E-1579-2026-0001', label='1548_001 Test (1999-2020)',
                     group=None):
        plan = plan_receipt(self.disk, group or self.group, self.profile,
                            '1579', number, label)
        create_grouped_ingest(plan)
        return plan

    def read_events(self, receipt):
        return [json.loads(v) for v in receipt.audit_path.read_text().splitlines()]

    def test_profile_is_external_and_three_sibling_top_folders(self):
        self.assertEqual(self.profile.group_prefix, 'arkiv-karantene-')
        self.assertEqual(self.profile.extraction_pattern,
                         '{date}_{extraction_id}_{receipt_number}')
        self.make_receipt()
        plan = plan_extraction(self.disk, self.group, self.profile,
                               '1579','E-1579-2026-0001','1548_001 Test (1999-2020)',
                               '1548_001','2026-10-15')
        names = {str(p.relative_to(plan.root)).replace('\\','/') for p in plan.paths}
        self.assertEqual(names, {'.','content','content/sip','content/tar',
                                 'descriptive_metadata', 'repository_operations',
                                 'repository_operations/abstract','repository_operations/quarantine',
                                 'repository_operations/utilities'})
        self.assertEqual(plan.root.parent, self.group)

    def test_selected_disk_alias_is_preserved_in_receipt_paths(self):
        # Validates canonical containment while retaining a caller's short path.
        alias = self.disk.parent / (self.disk.name + '_alias')
        try:
            alias.symlink_to(self.disk, target_is_directory=True)
        except (OSError, NotImplementedError):
            self.skipTest('Directory aliases require symlink permission on this platform')
        self.addCleanup(alias.unlink)
        plan = plan_receipt(alias, alias / self.group.name, self.profile,
                            '1579', 'E-1579-2026-0001', '1548_001 Test')
        self.assertEqual(plan.root.parent, alias / self.group.name)
        self.assertEqual(plan.disk, alias)

    def test_group_and_subfolders_are_configurable_not_hardcoded(self):
        config=json.loads(PROFILE_FILE.read_text(encoding='utf-8'))
        custom=config['profiles'][0]['grouped_ingest']
        custom['group_prefix']='depot-intake-'
        custom['extraction_pattern']='{receipt_number}_{extraction_id}_{date}'
        custom['extraction_folders']=['payload/raw','meta','operations/log']
        custom['receipt_log']='audit.jsonl'
        path=self.disk/'custom.json'
        path.write_text(json.dumps(config),encoding='utf-8')
        profile=grouped_profiles(path)[0]
        g=self.disk/'depot-intake-7'
        g.mkdir()
        r=plan_receipt(self.disk,g,profile,'1579','E-1579-2026-0009','1548_001 Example')
        create_grouped_ingest(r)
        x=plan_extraction(self.disk,g,profile,'1579','E-1579-2026-0009',
                          '1548_001 Example','1548_001','2026-10-15')
        self.assertEqual(x.root.name,'E-1579-2026-0009_1548_001_2026-10-15')
        self.assertEqual(x.audit_path,r.root/'audit.jsonl')
        self.assertIn(x.root/'operations'/'log',x.paths)

    def test_receipt_naming_and_label_not_used_for_folder(self):
        plan = plan_receipt(self.disk, self.group, self.profile,
                           '1579', 'E-1579-2026-0001', '1548_001 CosDoc (1999-2018)')
        self.assertEqual(plan.root.name, 'E-1579-2026-0001')
        self.assertEqual(plan.label, '1548_001 CosDoc (1999-2018)')
        self.assertFalse(plan.root.exists())
        self.assertEqual(plan.paths, (plan.root,))  # receipt: no subdirectories

    def test_receipt_logs_creation_and_extraction_in_same_event_store(self):
        receipt = self.make_receipt()
        plan = plan_extraction(self.disk,self.group,self.profile,'1579',receipt.receipt_number,
                               '1548_001 Historisk', '1548_001','2026-10-15')
        create_grouped_ingest(plan)
        self.assertTrue(plan.root.is_dir())
        events = self.read_events(receipt)
        self.assertEqual([v['kind'] for v in events],
                         ['ingest.receipt.created', 'ingest.extraction.created'])
        self.assertEqual(events[0]['data']['owner_municipality'], '1579')
        self.assertEqual(events[1]['data']['extraction_id'], '1548_001')
        self.assertEqual(events[1]['data']['receiving_path'], str(receipt.root))
        self.assertEqual(events[1]['data']['created_path'],str(plan.root))
        self.assertFalse((self.group / 'E-1579-2026-0001' / 'content').exists())

    def test_two_historical_extractions_same_receipt(self):
        r = self.make_receipt()
        for aid in ('1548_001','1551_001'):
            p = plan_extraction(self.disk,self.group,self.profile,'1579',r.receipt_number,
                                aid + ' System',aid,'2026-10-15')
            create_grouped_ingest(p)
        self.assertTrue((self.group/'2026-10-15_1548_001_E-1579-2026-0001').exists())
        self.assertTrue((self.group/'2026-10-15_1551_001_E-1579-2026-0001').exists())
        self.assertEqual(len(self.read_events(r)), 3)

    def test_suggest_sequence_across_groups_on_same_disk(self):
        self.make_receipt(number='E-1579-2026-0003')
        self.make_receipt(number='E-1579-2026-0011',group=self.other_group)
        self.make_receipt(number='E-1579-2025-0070',group=self.other_group)
        self.assertEqual(suggest_receipt_number(self.disk,self.profile,'1579',year=2026),
                         'E-1579-2026-0012')
        self.assertEqual(suggest_receipt_number(self.disk,self.profile,'1505',year=2026),
                         'E-1505-2026-0001')
        self.assertEqual(suggest_receipt_number(self.disk,self.profile,'1579',year=2025),
                         'E-1579-2025-0071')

    def test_duplicate_receipt_refused_across_groups(self):
        self.make_receipt()
        with self.assertRaises(FileExistsError):
            plan_receipt(self.disk,self.other_group,self.profile,'1579',
                         'E-1579-2026-0001','A label')

    def test_owner_code_is_independent_of_historical_creator(self):
        self.make_receipt()
        p = plan_extraction(self.disk,self.group,self.profile,'1579',
                            'E-1579-2026-0001','1548_001 Historical','1548_001','2026-10-15')
        self.assertEqual(p.owner_code,'1579')
        self.assertEqual(p.extraction_id,'1548_001')

    def test_wrong_owner_cannot_plan_receipt_or_extraction(self):
        with self.assertRaises(ValueError):
            plan_receipt(self.disk,self.group,self.profile,'1548','E-1579-2026-0001','x')
        self.make_receipt()
        with self.assertRaises(ValueError):
            plan_extraction(self.disk,self.group,self.profile,'1548','E-1579-2026-0001',
                            '1548_001','1548_001','2026-10-15')

    def test_duplicate_extraction_same_date_refused(self):
        self.make_receipt()
        args=(self.disk,self.group,self.profile,'1579','E-1579-2026-0001',
              '1548_001','1548_001','2026-10-15')
        p=plan_extraction(*args)
        create_grouped_ingest(p)
        with self.assertRaises(FileExistsError):
            plan_extraction(*args)

    def test_preexisting_receipt_without_log_fails_before_writing(self):
        (self.group / 'E-1579-2026-0001').mkdir()
        plan=plan_extraction(self.disk,self.group,self.profile,'1579',
                   'E-1579-2026-0001','1548_001','1548_001','2026-10-15')
        with self.assertRaisesRegex(ValueError,'mangler hendelseslogg'):
            create_grouped_ingest(plan)
        self.assertFalse(plan.root.exists())

    def test_bad_date_and_extraction_id_fail(self):
        self.make_receipt()
        args=(self.disk,self.group,self.profile,'1579',
              'E-1579-2026-0001','1548_001')
        for ident in ('foo','../x','1579_01'):
            with self.subTest(ident=ident),self.assertRaises(ValueError):
                plan_extraction(*args,ident,'2026-10-15')
        for bad in ('2026-13-01','20261015','2026-02-30'):
            with self.subTest(bad=bad),self.assertRaises(ValueError):
                plan_extraction(*args,'1548_001',bad)

    def test_group_must_be_real_direct_child_of_disk(self):
        with self.assertRaises(ValueError):
            plan_receipt(self.disk,self.disk,self.profile,'1579','E-1579-2026-0001','A')
        (self.disk/'other').mkdir()
        with self.assertRaises(ValueError):
            plan_receipt(self.disk,self.disk/'other',self.profile,'1579','E-1579-2026-0001','A')

    def test_failed_receipt_audit_rolls_back_unlogged_empty_folder(self):
        import noark5_workflow.sinks.event_store as es
        with patch.object(es,'GenericEventStoreSink') as sink:
            sink.return_value.handle.side_effect=OSError('disk write failed')
            p=plan_receipt(self.disk,self.group,self.profile,'1579','E-1579-2026-0001','A')
            with self.assertRaises(OSError):
                create_grouped_ingest(p)
            self.assertFalse(p.root.exists())

    def test_source_info_hash_in_event_and_original_unchanged(self):
        import hashlib
        xml=self.disk/'info.xml'
        xml.write_text('<x>test</x>',encoding='utf-8')
        orig=xml.read_bytes()
        p=plan_receipt(self.disk,self.group,self.profile,'1579','E-1579-2026-0001','LABEL',xml)
        create_grouped_ingest(p)
        self.assertEqual(xml.read_bytes(),orig)
        self.assertEqual(self.read_events(p)[0]['data']['info_xml_sha256'],hashlib.sha256(orig).hexdigest())

    def test_no_files_are_copied(self):
        p=self.make_receipt()
        self.assertEqual({x.name for x in p.root.iterdir()}, {'ingest.events.jsonl', 'depot-log.txt'})
        self.assertFalse((p.root/'repository_operations').exists())

    def test_gui_wiring_is_primary_grouped_dialog(self):
        root=Path(__file__).resolve().parents[1]
        s=(root/'gui'/'receiving_folder_dialog.py').read_text(encoding='utf-8')
        self.assertIn('from .grouped_ingest_dialog import GroupedIngestDialog',s)
        gui=(root/'gui'/'grouped_ingest_dialog.py').read_text(encoding='utf-8')
        self.assertIn('create_grouped_ingest(plan, actor=actor)',gui)
        self.assertLess(gui.index('messagebox.askyesno('), gui.index('create_grouped_ingest(plan, actor=actor)'))


if __name__=='__main__':
    unittest.main()
