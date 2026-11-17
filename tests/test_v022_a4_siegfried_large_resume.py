"""v0.2.2-a4: large-input Siegfried, completed-batch resume and Work isolation.

No real Siegfried install or source files from an archive are required.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from noark5_workflow.core.context import OperationContext
from noark5_workflow.operations.run_siegfried_pronom import SiegfriedPronomOperation, document_files
from noark5_workflow.operations import siegfried_stream_v022_a4 as stream


class SiegfriedA4Tests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.source = self.base / 'Source'
        self.docs = self.source / 'DOKUMENT'
        self.docs.mkdir(parents=True)
        self.work = self.base / 'Work'
        self.work.mkdir()
        self.log = self.base / 'sf-calls.jsonl'
        self.sf = self.base / ('sf.exe' if os.name == 'nt' else 'sf')
        self.sf.write_text('#!' + sys.executable + '\n' + '''
import json,os,sys
from pathlib import Path
if '-version' in sys.argv:
    print('siegfried 1.11.9 PRONOM signature V125')
    raise SystemExit(0)
files=sys.argv[4:]
with Path(os.environ['DWM_A4_FAKE_LOG']).open('a',encoding='utf-8') as log:
    log.write(json.dumps(files)+'\\n')
fail=Path(os.environ['DWM_A4_FAKE_FAIL'])
if fail.exists():
    fail.unlink()
    print('simulated failing batch',file=sys.stderr)
    raise SystemExit(5)
records=[]
for f in files:
    if Path(f).suffix == '.bin':
        matches=[]
    else:
        matches=[{'id':'fmt/354','format':'PDF/A','version':'1b'}]
    records.append({'filename':f,'matches':matches})
print(json.dumps({'files':records}))
''', encoding='utf-8')
        self.sf.chmod(0o755)
        self.fail = self.base / 'fail-once.flag'
        self.env_patch = patch.dict(os.environ, {'DWM_A4_FAKE_LOG':str(self.log),
                                                'DWM_A4_FAKE_FAIL':str(self.fail)})
        self.env_patch.start()
        self.addCleanup(self.env_patch.stop)

    def _fake_batch(self, executable, paths, *, cancelled_cb=None, timeout=600):
        # Windows can't execute a text file named sf.exe. Simulate the exact
        # subprocess boundary there while retaining real subprocess tests on POSIX.
        with self.log.open('a', encoding='utf-8') as handle:
            handle.write(json.dumps(paths) + '\n')
        if self.fail.exists():
            self.fail.unlink()
            raise RuntimeError('Siegfried avsluttet med kode 5: simulated failing batch')
        return [{'filename': p, 'matches': [] if Path(p).suffix == '.bin'
                 else [{'id': 'fmt/354', 'format': 'PDF/A', 'version': '1b'}]}
                for p in paths]

    def docs_create(self, n: int):
        for i in range(n):
            ext = '.bin' if i % 9 == 0 else '.pdf'
            (self.docs / f'doc-{i:05d}{ext}').write_bytes(b'%PDF')

    def run_scan(self, *, cancelled_cb=None, progress_cb=None, version='siegfried 1.11.9'):
        if os.name == 'nt':
            with patch.object(stream, '_run_sf_batch', side_effect=self._fake_batch):
                return self._run_scan_impl(cancelled_cb, progress_cb, version)
        return self._run_scan_impl(cancelled_cb, progress_cb, version)

    def _run_scan_impl(self, cancelled_cb, progress_cb, version):
        return stream.scan_document_tree(source=self.source, work=self.work,
               executable=str(self.sf), version=version, signature='PRONOM signature V125',
               job_id='JOB-001', job_uid='uuid-1', cancelled_cb=cancelled_cb,
               progress_cb=progress_cb)

    def partials(self):
        folder=self.work/'external_evidence'/'siegfried'
        return sorted(folder.glob('.partial-*')) if folder.is_dir() else []

    def completed(self):
        folder=self.work/'external_evidence'/'siegfried'
        return sorted(p for p in folder.iterdir() if p.is_dir() and not p.name.startswith('.'))

    def test_scan_uses_dokument_only_and_publishes_old_format(self):
        self.docs_create(3)
        (self.source/'arkivstruktur.xml').write_text('<arkiv/>')
        result=self.run_scan()
        self.assertFalse(result['resumed'])
        model=result['model']
        self.assertEqual(model['files_total'],3)
        self.assertEqual(model['identified'],2)
        self.assertEqual(model['unidentified'],1)
        self.assertEqual(model['source_scope'],'DOKUMENT')
        folder=result['target']
        self.assertEqual((folder/'manifest.json').is_file(),True)
        manifest=json.loads((folder/'manifest.json').read_text('utf-8'))
        raw=folder/'siegfried_files.jsonl'
        self.assertEqual(manifest['raw_sha256'],hashlib.sha256(raw.read_bytes()).hexdigest())
        self.assertEqual(sum(g['count'] for g in model['format_groups']),3)
        self.assertTrue((self.source/'arkivstruktur.xml').is_file())
        self.assertEqual(self.partials(),[])

    def test_205_files_use_100_path_batches_and_sequential_processes(self):
        self.docs_create(205)
        report=self.run_scan()
        calls=[json.loads(line) for line in self.log.read_text('utf-8').splitlines()]
        self.assertEqual(list(map(len,calls)),[100,100,5])
        self.assertEqual(report['model']['files_total'],205)
        self.assertEqual(len((report['target']/'siegfried_files.jsonl').read_text('utf-8').splitlines()),205)

    def test_failed_second_batch_is_resumable_without_rescanning_first(self):
        self.docs_create(205)
        calls=[]
        def count(done,total):
            calls.append(done)
            if done==100:
                self.fail.touch()
        with self.assertRaisesRegex(RuntimeError,'kode 5'):
            self.run_scan(progress_cb=count)
        self.assertEqual(len(self.partials()),1)
        stage=self.partials()[0]
        checkpoint=json.loads((stage/'checkpoint.json').read_text('utf-8'))
        self.assertEqual(checkpoint['files_processed'],100)
        self.assertEqual(len((stage/'siegfried_files.jsonl').read_text('utf-8').splitlines()),100)
        complete=self.run_scan()
        self.assertTrue(complete['resumed'])
        self.assertEqual(complete['model']['files_total'],205)
        calls=[json.loads(line) for line in self.log.read_text('utf-8').splitlines()]
        self.assertEqual(list(map(len,calls)),[100,100,100,5])
        self.assertEqual(self.partials(),[])

    def test_cancel_after_batch_retains_checkpoint_and_resumes(self):
        self.docs_create(102)
        cancel=[False]
        def on_progress(done,total):
            if done==100:
                cancel[0]=True
        with self.assertRaises(InterruptedError):
            self.run_scan(cancelled_cb=lambda: cancel[0],progress_cb=on_progress)
        self.assertEqual(len(self.partials()),1)
        self.assertEqual(self.run_scan()['files_total'],102)
        calls=[json.loads(line) for line in self.log.read_text('utf-8').splitlines()]
        self.assertEqual(list(map(len,calls)),[100,2])

    def test_changed_source_starts_separate_run_and_preserves_old_partial(self):
        self.docs_create(103)
        def fail(done,total):
            if done==100:self.fail.touch()
        with self.assertRaises(RuntimeError):
            self.run_scan(progress_cb=fail)
        previous=self.partials()[0]
        self.assertEqual(json.loads((previous/'checkpoint.json').read_text())['files_processed'],100)
        doc=self.docs/'doc-00101.pdf'
        doc.write_bytes(b'UPDATED DATA')
        result=self.run_scan()
        self.assertFalse(result['resumed'])
        self.assertTrue(previous.exists())
        self.assertEqual(result['model']['files_total'],103)

    def test_changed_sf_version_does_not_resume_old_partial(self):
        self.docs_create(101)
        def fail(done,total):
            if done==100:self.fail.touch()
        with self.assertRaises(RuntimeError):
            self.run_scan(progress_cb=fail)
        self.assertFalse(self.run_scan(version='siegfried 2.0')['resumed'])
        self.assertEqual(len(self.partials()),1)

    def test_wrong_job_work_is_rejected_without_publishing(self):
        self.docs_create(1)
        (self.work/'job.json').write_text(json.dumps({'file_type':'dwm-work-job',
                'job_uid':'uuid-other','job':{'job_id':'JOB-002'}}))
        with self.assertRaisesRegex(ValueError,'jobb-ID'):
            self.run_scan()
        self.assertEqual(self.partials(),[])

    def test_source_work_overlap_is_rejected(self):
        self.docs_create(1)
        with self.assertRaisesRegex(ValueError,'overlappende'):
            stream.scan_document_tree(source=self.source,work=self.source,
                executable=str(self.sf),version='sf',signature='',job_id='JOB-001')

    def test_symlinks_excluded_without_path_escape(self):
        self.docs_create(1)
        outside=self.base/'outside.pdf';outside.write_bytes(b'a')
        try:
            (self.docs/'escape.pdf').symlink_to(outside)
        except (OSError, NotImplementedError):
            self.skipTest('Systemet tillater ikke symlenker')
        result=self.run_scan()
        self.assertEqual(result['files_total'],1)

    def test_250000_default_limit_removed_from_compatibility_discovery(self):
        self.docs_create(2)
        files,scope=document_files(self.source)
        self.assertEqual(len(files),2)
        with self.assertRaises(ValueError):
            document_files(self.source,max_files=1)
        # The workflow uses inventory_files() and never calls document_files().
        from noark5_workflow.operations import run_siegfried_pronom as operation
        from app.siegfried_tool_v0111_a3 import SiegfriedCheck
        status = SiegfriedCheck(True, str(self.sf), 'siegfried 1.11.9', 'PRONOM signature V125')
        with patch.object(operation,'document_files',side_effect=AssertionError('not used')), \
             patch.object(operation,'inspect_siegfried',return_value=status):
            if os.name == 'nt':
                with patch.object(stream, '_run_sf_batch', side_effect=self._fake_batch):
                    result = operation.SiegfriedPronomOperation().run(
                        OperationContext(self.source, work_operations=self.work,
                            settings={'sf_executable':str(self.sf)},
                            metadata={'job_id':'JOB-001'}))
            else:
                result = operation.SiegfriedPronomOperation().run(
                    OperationContext(self.source, work_operations=self.work,
                        settings={'sf_executable':str(self.sf)},
                        metadata={'job_id':'JOB-001'}))
            self.assertTrue(result.ok, result.message)

    def test_250001_synthetic_inventory_is_unbounded_and_batches_remain_small(self):
        """Cheap synthetic large-file test; no 2 TB archive or sf.exe needed."""
        from itertools import repeat
        from types import SimpleNamespace
        import stat as statmod

        class SyntheticFile:
            def stat(self, *, follow_symlinks=True):
                return SimpleNamespace(st_mode=statmod.S_IFREG, st_size=4096,
                                       st_mtime_ns=1700000000000000000)
            def is_symlink(self):
                return False
            def is_junction(self):
                return False
            def relative_to(self, _root):
                return Path('DOKUMENT') / 'synthetic.pdf'

        inventory = self.base / 'large-inventory.jsonl'
        n = 250001
        with patch.object(stream, 'iter_document_files',
                          return_value=(repeat(SyntheticFile(), n), 'DOKUMENT')):
            info = stream.inventory_files(self.source, inventory)
        self.assertEqual(info['files_total'], n)
        self.assertEqual(info['source_scope'], 'DOKUMENT')
        sizes = [len(chunk) for chunk in stream._batches(inventory, self.source,
                                                         skip=0, executable=str(self.sf))]
        self.assertEqual(sum(sizes), n)
        self.assertTrue(all(1 <= x <= 100 for x in sizes))
        self.assertEqual(sizes[-1], 1)

    def test_resume_rejects_tampered_committed_evidence(self):
        self.docs_create(103)
        def fail(done,total):
            if done==100:self.fail.touch()
        with self.assertRaises(RuntimeError):
            self.run_scan(progress_cb=fail)
        old=self.partials()[0]
        raw=old/'siegfried_files.jsonl'
        raw.write_bytes(raw.read_bytes().replace(b'fmt/354',b'fmt/123',1))
        result=self.run_scan()
        self.assertFalse(result['resumed'])
        self.assertTrue(old.exists())
        self.assertEqual(result['files_total'],103)

    def test_resume_discards_only_uncommitted_tail(self):
        self.docs_create(103)
        def fail(done, total):
            if done == 100:
                self.fail.touch()
        with self.assertRaises(RuntimeError):
            self.run_scan(progress_cb=fail)
        old = self.partials()[0]
        with (old / 'siegfried_files.jsonl').open('ab') as output:
            output.write(b'{"half_written":')
        result = self.run_scan()
        self.assertTrue(result['resumed'])
        raw = result['target'] / 'siegfried_files.jsonl'
        rows = [json.loads(line) for line in raw.read_text('utf-8').splitlines()]
        self.assertEqual(len(rows), 103)
        self.assertFalse(any('half_written' in row for row in rows))

    def test_missing_dokument_falls_back_to_extraction(self):
        self.docs.rmdir()
        (self.source / 'arkivstruktur.xml').write_text('<arkiv/>')
        paths, scope = document_files(self.source)
        self.assertEqual([p.name for p in paths], ['arkivstruktur.xml'])
        self.assertIn('Hele uttrekksmappen', scope)
        self.assertEqual(self.run_scan()['model']['files_total'], 1)

    def test_completed_run_is_not_overwritten_on_repeat(self):
        self.docs_create(1)
        first=self.run_scan()
        second=self.run_scan()
        self.assertNotEqual(first['run_id'],second['run_id'])
        self.assertEqual(len(self.completed()),2)


if __name__=='__main__':
    unittest.main()
