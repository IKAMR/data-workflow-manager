import errno
from hashlib import sha256
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from noark5_workflow.operations.siegfried_publish_v027_a10 import publish_verified_siegfried


def make_stage(root):
    run_id = '20261120T203651Z-aebc1af28a'
    stage = Path(root) / ('.partial-' + run_id)
    stage.mkdir()
    raw = b'{"filename":"some.pdf","matches":[]}\n'
    inventory = b'{"path":"DOKUMENT/some.pdf"}\n'
    (stage / 'siegfried_files.jsonl').write_bytes(raw)
    (stage / 'file_inventory.jsonl').write_bytes(inventory)
    (stage / 'checkpoint.json').write_text(json.dumps({'run_id':run_id,'files_processed':1,
        'raw_bytes':len(raw),'raw_sha256':sha256(raw).hexdigest(),
        'inventory_sha256':sha256(inventory).hexdigest()}))
    (stage / 'manifest.json').write_text(json.dumps({'run_id':run_id,'files_total':1,
        'raw_sha256':sha256(raw).hexdigest(),
        'inventory_sha256':sha256(inventory).hexdigest()}))
    (stage / 'pronom_statistics.json').write_text(json.dumps({'run_id':run_id,'files_total':1}))
    (stage / 'diagnostics').mkdir()
    (stage / 'diagnostics' / 'index.jsonl').write_text('example\n')
    return stage, Path(root) / run_id


class TestPublish(unittest.TestCase):
    def test_normal_directory_rename(self):
        with TemporaryDirectory() as d:
            stage,target=make_stage(d)
            self.assertEqual(publish_verified_siegfried(stage,target),'rename')
            self.assertTrue((target/'manifest.json').exists())
            self.assertFalse(stage.exists())

    def test_winerror5_copy_preserves_partial(self):
        with TemporaryDirectory() as d:
            stage,target=make_stage(d)
            original=stage/'siegfried_files.jsonl'
            with (patch.object(Path,'rename',side_effect=PermissionError(errno.EACCES,'denied')),
                  patch('noark5_workflow.operations.siegfried_publish_v027_a10.time.sleep')):
                self.assertEqual(publish_verified_siegfried(stage,target),'copy')
            self.assertEqual(original.read_bytes(),(target/'siegfried_files.jsonl').read_bytes())
            self.assertTrue((target/'manifest.json').exists())
            self.assertTrue((stage/'checkpoint.json').exists())
            self.assertTrue((target/'diagnostics'/'index.jsonl').exists())

    def test_corrupt_checkpoint_rejected_before_rename(self):
        with TemporaryDirectory() as d:
            stage,target=make_stage(d)
            p=stage/'checkpoint.json'
            state=json.loads(p.read_text());state['raw_bytes']=20;p.write_text(json.dumps(state))
            with self.assertRaisesRegex(ValueError,'inkonsistent'):
                publish_verified_siegfried(stage,target)
            self.assertFalse(target.exists())

    def test_copy_failure_never_publishes_manifest_and_preserves_partial(self):
        with TemporaryDirectory() as d:
            stage,target=make_stage(d)
            import noark5_workflow.operations.siegfried_publish_v027_a10 as module
            real=module._copy_check
            def fail(src,dest,expected_digest=None):
                if src.name=='file_inventory.jsonl':
                    raise OSError('artificial disk error')
                return real(src,dest,expected_digest)
            with (patch.object(Path,'rename',side_effect=PermissionError(errno.EACCES,'denied')),
                  patch.object(module,'_copy_check',side_effect=fail),
                  patch.object(module.time,'sleep')):
                with self.assertRaises(OSError):
                    publish_verified_siegfried(stage,target)
            self.assertFalse((target/'manifest.json').exists())
            self.assertTrue(stage.exists())


if __name__=='__main__':
    unittest.main()
