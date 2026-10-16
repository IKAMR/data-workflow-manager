"""a19-fix4: reusable ingest presets and continuous readable/portable logs."""
from __future__ import annotations

import json
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

from app.ingest_saved_profiles import load_ingest_profile, save_ingest_profile
from app.grouped_ingest import grouped_profiles, plan_receipt, plan_extraction, create_grouped_ingest

ROOT = Path(__file__).resolve().parents[1]
SETUP = ROOT / 'config' / 'receiving_folder_profiles.json'


def user_settings():
    return dict(setup_file=str(SETUP), folder_profile_id='ikamr_karantene',
                disk='K:\\', group='arkiv-karantene-01', owner_code='1579',
                default_mode='Mottak', label='Do not persist',
                receipt_number='E-1579-2026-0001', password='do not persist')


class SavedIngestProfileTests(unittest.TestCase):
    def setUp(self):
        t = tempfile.TemporaryDirectory()
        self.addCleanup(t.cleanup)
        self.path = Path(t.name) / 'profil.json'

    def test_profile_roundtrip_and_sensitive_values_excluded(self):
        save_ingest_profile(self.path, user_settings())
        loaded = load_ingest_profile(self.path)
        self.assertEqual(loaded['folder_profile_id'], 'ikamr_karantene')
        self.assertEqual(loaded['group'], 'arkiv-karantene-01')
        self.assertNotIn('receipt_number', loaded)
        self.assertNotIn('label', loaded)
        self.assertNotIn('password', self.path.read_text(encoding='utf-8'))
        self.assertNotIn('E-1579-2026-0001', self.path.read_text(encoding='utf-8'))

    def test_save_is_exclusive_replace_is_explicit(self):
        save_ingest_profile(self.path, user_settings())
        with self.assertRaises(FileExistsError):
            save_ingest_profile(self.path, user_settings())
        changed = user_settings()
        changed['group'] = 'arkiv-karantene-09'
        save_ingest_profile(self.path, changed, replace=True)
        self.assertEqual(load_ingest_profile(self.path)['group'], 'arkiv-karantene-09')

    def test_file_format_and_invalid_values_fail(self):
        with self.assertRaises(ValueError):
            save_ingest_profile(self.path.with_suffix('.txt'), user_settings())
        bad = user_settings()
        bad['default_mode'] = 'Slett'
        with self.assertRaises(ValueError):
            save_ingest_profile(self.path, bad)
        self.path.write_text('{"file_type":"other", "format_version":1}', encoding='utf-8')
        with self.assertRaises(ValueError):
            load_ingest_profile(self.path)


class FakeEvent:
    counter = 0

    @classmethod
    def now(cls, kind, **kwargs):
        cls.counter += 1
        return {
            'schema_version': 1,
            'kind': kind,
            'event_id': f'ID-{cls.counter:05}',
            'timestamp': '2026-10-15T19:01:00+02:00',
            'run_id': kwargs['run_id'],
            'success': True,
            'user': {'name': 'Depotansatt'},
            'data': kwargs['data'],
        }


class FakeSink:
    def __init__(self, path):
        self.path = Path(path)

    def handle(self, event):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open('a', encoding='utf-8') as f:
            f.write(json.dumps(event, ensure_ascii=False) + '\n')


class IngestLoggingTests(unittest.TestCase):
    def setUp(self):
        t = tempfile.TemporaryDirectory()
        self.addCleanup(t.cleanup)
        self.disk = Path(t.name)
        self.group = self.disk / 'arkiv-karantene-01'
        self.group.mkdir()
        self.profile = grouped_profiles(SETUP)[0]
        FakeEvent.counter = 0
        modules = {
            'noark5_workflow': types.ModuleType('noark5_workflow'),
            'noark5_workflow.core': types.ModuleType('noark5_workflow.core'),
            'noark5_workflow.sinks': types.ModuleType('noark5_workflow.sinks'),
            'noark5_workflow.core.events': types.ModuleType('noark5_workflow.core.events'),
            'noark5_workflow.sinks.event_store': types.ModuleType('noark5_workflow.sinks.event_store'),
        }
        modules['noark5_workflow.core.events'].WorkflowEvent = FakeEvent
        modules['noark5_workflow.sinks.event_store'].GenericEventStoreSink = FakeSink
        mock = patch.dict(sys.modules, modules)
        mock.start()
        self.addCleanup(mock.stop)

    def receipt(self):
        p = plan_receipt(self.disk, self.group, self.profile,
                         '1579', 'E-1579-2026-0001', '1548_001 System')
        create_grouped_ingest(p)
        return p

    def extract(self, id):
        p = plan_extraction(self.disk, self.group, self.profile,
            '1579', 'E-1579-2026-0001', id + ' System', id, '2026-10-15')
        create_grouped_ingest(p)
        return p

    def test_receipt_is_flat_and_logged_at_root(self):
        r = self.receipt()
        self.assertTrue((r.root/'depot-log.txt').is_file())
        self.assertFalse((r.root/'repository_operations').exists())
        self.assertTrue(r.audit_path.is_file())
        txt = (r.root/'depot-log.txt').read_text(encoding='utf-8')
        self.assertIn('Mottaksmappe opprettet', txt)
        self.assertIn('E-1579-2026-0001', txt)
        self.assertIn('Depotansatt', txt)
        self.assertIn('ID-00001', txt)
        self.assertIn('Leveransestatus: Venter på manuell nedlasting', txt)

    def test_two_extractions_share_receipt_history_but_not_each_others(self):
        receipt = self.receipt()
        first = self.extract('1548_001')
        second = self.extract('1551_001')
        recorded = [json.loads(x) for x in receipt.audit_path.read_text(encoding='utf-8').splitlines()]
        self.assertEqual(len(recorded), 3)
        self.assertEqual([x['event_id'] for x in recorded], ['ID-00001', 'ID-00002', 'ID-00003'])
        root_text = (receipt.root/'depot-log.txt').read_text(encoding='utf-8')
        self.assertEqual(root_text.count('Hendelse: '), 3)
        for idx, plan in enumerate((first, second), 2):
            folder = plan.root/'repository_operations'
            local = [json.loads(x) for x in (folder/'ingest.events.jsonl').read_text(encoding='utf-8').splitlines()]
            self.assertEqual([x['event_id'] for x in local], ['ID-00001', f'ID-{idx:05}'])
            text = (folder/'depot-log.txt').read_text(encoding='utf-8')
            self.assertIn('Mottaksmappe opprettet', text)
            self.assertIn('Uttrekksmappe opprettet', text)
            self.assertIn(plan.extraction_id, text)
            self.assertNotIn('E-1579-2026-0002', text)
        self.assertNotIn('1551_001', (first.root/'repository_operations'/'depot-log.txt').read_text())

    def test_legacy_receipt_gets_readable_history_when_first_extraction_created(self):
        r = self.receipt()
        (r.root/'depot-log.txt').unlink()
        self.extract('1548_001')
        text = (r.root/'depot-log.txt').read_text(encoding='utf-8')
        self.assertEqual(text.count('Hendelse: '), 2)
        self.assertIn('Mottaksmappe opprettet', text)
        self.assertIn('Uttrekksmappe opprettet', text)

    def test_info_xml_selection_is_logged_without_copying_or_download(self):
        import hashlib
        xml = self.disk / 'source_info.xml'
        xml.write_text('<mets>original</mets>', encoding='utf-8')
        original = xml.read_bytes()
        plan = plan_receipt(self.disk, self.group, self.profile, '1579',
                            'E-1579-2026-0001', '1548_001 Test', xml)
        create_grouped_ingest(plan)
        records = [json.loads(x) for x in plan.audit_path.read_text(encoding='utf-8').splitlines()]
        self.assertEqual(records[0]['data']['info_xml'], str(xml))
        self.assertEqual(records[0]['data']['info_xml_sha256'], hashlib.sha256(original).hexdigest())
        self.assertEqual(records[0]['data']['delivery_state'], 'awaiting_download')
        receipt_log = (plan.root / 'depot-log.txt').read_text(encoding='utf-8')
        self.assertIn(str(xml), receipt_log)
        self.assertIn('SHA-256 info.xml:', receipt_log)
        self.assertIn('Venter på manuell nedlasting', receipt_log)
        self.assertEqual(xml.read_bytes(), original)
        self.assertEqual({x.name for x in plan.root.iterdir()},
                         {'ingest.events.jsonl', 'depot-log.txt'})

    def test_preexisting_fix4_log_is_retained_and_root_log_backfilled(self):
        receipt = self.receipt()
        legacy_dir = receipt.root / 'repository_operations'
        legacy_dir.mkdir()
        legacy_text = legacy_dir / 'depot-log.txt'
        original_text = (receipt.root / 'depot-log.txt').read_text(encoding='utf-8')
        legacy_text.write_text(original_text, encoding='utf-8')
        (receipt.root / 'depot-log.txt').unlink()
        self.extract('1548_001')
        self.assertEqual(legacy_text.read_text(encoding='utf-8'), original_text)
        new_log = (receipt.root / 'depot-log.txt').read_text(encoding='utf-8')
        self.assertEqual(new_log.count('Hendelse: '), 2)
        self.assertTrue((receipt.root / 'ingest.events.jsonl').is_file())

    def test_failed_readable_log_preserves_audited_receipt(self):
        r = plan_receipt(self.disk, self.group, self.profile,
                         '1579', 'E-1579-2026-0001', 'LABEL')
        with patch('app.ingest_operation_log.format_record', side_effect=OSError('disk full')):
            with self.assertRaisesRegex(RuntimeError, 'Hendelsesloggen'):
                create_grouped_ingest(r)
        self.assertTrue(r.root.is_dir())
        self.assertTrue(r.audit_path.is_file())

    def test_gui_exposes_all_three_profile_actions(self):
        s = (ROOT/'gui'/'grouped_ingest_dialog.py').read_text(encoding='utf-8')
        for label in ('Åpne profil', 'Lagre profil', 'Lagre som ny profil'):
            self.assertIn(label, s)
        self.assertIn("self.receipt_var.set('')", s)


if __name__ == '__main__':
    unittest.main()
