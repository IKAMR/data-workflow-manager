"""a20.3: reconnectable export, no XPath restart, verified local staging."""
from __future__ import annotations

import errno
import json
from pathlib import Path
import tempfile
import threading
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from noark5_workflow.reporting import report_recovery_a203 as recovery


def _jobs(n, root):
    source = root / 'connected-source'
    source.mkdir(exist_ok=True)
    return tuple(SimpleNamespace(job_id=f'JOB-{i:03d}',
                  work_operations=source) for i in range(1, n+1))


def _fake_writer(calls, *, before_write=None):
    def writer(directory, jobs, options, *, prefix, formats, overwrite, on_warning):
        calls.append(len(jobs))
        if before_write is not None:
            before_write(len(calls))
        directory = Path(directory)
        directory.mkdir(parents=True, exist_ok=True)
        data = {'jobs': [{'job_id':j.job_id, 'depot_report':{'summary':{'folder_count':1}}}
                          for j in jobs]}
        (directory / (prefix+'index.json')).write_text(json.dumps(data), encoding='utf-8')
        (directory / (prefix+'index.html')).write_text('<h1>Rapport for '+str(len(jobs))+' jobber</h1>', encoding='utf-8')
        (directory / (prefix+'vedlegg-c-teknisk-evidens.html')).write_text('<h1>Teknisk evidens</h1>', encoding='utf-8')
        return directory / (prefix+'index.html')
    return writer


class ReportRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.jobs = _jobs(28, self.root)
        self.options = SimpleNamespace(enabled=['overview'], level='Full',
                                       extraction_appendix=False, archive_part_appendix=False)
        self.dest = self.root / 'output'
        self.state = self.root / 'local-state'

    def session(self, *, writer=None, probe=None, cancel=None, on_progress=None, **kwargs):
        return recovery.ReportRecoverySession(self.dest, self.jobs, self.options,
            prefix='1502_029-056', formats=('html','json'), writer=writer,
            probe=probe, cancelled=cancel, on_progress=on_progress,
            poll_seconds=.01, state_root=self.state, **kwargs)

    def test_28_jobs_uses_local_stage_and_preserves_trace(self):
        calls=[]
        session=self.session(writer=_fake_writer(calls))
        out=session.run()
        self.assertEqual(calls,[28])
        self.assertEqual(out.name,'1502_029-056_index.html')
        self.assertIn('28 jobber',out.read_text('utf8'))
        self.assertTrue((self.dest/'1502_029-056_index.json').is_file())
        self.assertFalse(session.session_dir.exists())
        log=session.log_path.read_text('utf8')
        self.assertIn('complete',log)
        self.assertIn('published',log)

    def test_disconnection_during_build_restarts_renderer_when_online(self):
        calls=[]
        online={'value':True}
        def fake_writer(attempt):
            if attempt==1:
                online['value']=False
                threading.Thread(target=lambda: (time.sleep(.04),online.update(value=True)),daemon=True).start()
                raise OSError(errno.EIO, 'K18 disconnected')
        seen=[]
        session=self.session(writer=_fake_writer(calls,before_write=fake_writer),
                probe=lambda: None if online['value'] else 'K18 ikke tilgjengelig',
                on_progress=lambda *items: seen.append(items[0]))
        result=session.run()
        self.assertEqual(calls,[28,28])
        self.assertEqual(result.name,'1502_029-056_index.html')
        self.assertIn('venter',seen)
        self.assertIn('complete',session.log_path.read_text('utf8'))

    def test_missing_external_bank_is_rechecked_after_reconnect(self):
        calls=[]
        self.options.enabled=('external',)
        folder=self.root/'connected-source'/'external_evidence'/'kdrs_query'
        folder.mkdir(parents=True)
        (folder/'import-manifest.json').write_text('{}','utf8')
        def source(directory,jobs,options,*,prefix,formats,overwrite,on_warning):
            calls.append(len(jobs))
            rows=[]
            for job in jobs:
                row={'job_id':job.job_id,'depot_report':{'summary':{'folder_count':1}}}
                row['external_evidence']={'diagnostics':
                    ['Ingen tilgjengelig importmappe for denne jobben'] if len(calls)==1 else [],
                    'kdrs_query':{'resources':[]}}
                rows.append(row)
            (directory/(prefix+'index.json')).write_text(json.dumps({'jobs':rows}),encoding='utf8')
            (directory/(prefix+'index.html')).write_text('<h1>Evidence</h1>','utf8')
        session=self.session(writer=source)
        self.assertTrue(session.run().exists())
        self.assertEqual(calls,[28,28])

    def test_disconnection_during_copy_resumes_without_rerender(self):
        calls=[]
        online={'value':True}
        original_replace=recovery.os.replace
        replacements={'failed':0}
        def intermittent(src,dst):
            if str(dst).endswith('index.json') and not replacements['failed']:
                replacements['failed']+=1
                online['value']=False
                threading.Thread(target=lambda:(time.sleep(.04),online.update(value=True)),daemon=True).start()
                raise OSError(errno.EIO, 'Output disk vanished')
            return original_replace(src,dst)
        session=self.session(writer=_fake_writer(calls),
               probe=lambda: None if online['value'] else 'målstasjon borte')
        with patch.object(recovery.os,'replace',side_effect=intermittent):
            result=session.run()
        self.assertTrue(result.exists())
        self.assertEqual(calls,[28])  # published from already staged files
        self.assertEqual(replacements['failed'],1)
        self.assertIn('publish_failed',session.log_path.read_text('utf8'))
        self.assertEqual(len(list(self.dest.iterdir())),3)

    def test_errno_22_online_not_mistaken_for_disk_loss(self):
        calls=[]
        def fail(_attempt):
            raise OSError(errno.EINVAL, 'Invalid argument')
        session=self.session(writer=_fake_writer(calls,before_write=fail))
        with self.assertRaises(OSError) as caught:
            session.run()
        self.assertEqual(caught.exception.errno,22)
        self.assertEqual(calls,[28,28])  # one bounded retry
        log=session.log_path.read_text('utf8')
        self.assertIn('Invalid argument',log)
        self.assertIn('traceback',log)
        self.assertNotIn('Venter på disk/arbeidsmappe',log)

    def test_completed_local_report_can_publish_if_source_unplugs_after_render(self):
        calls=[]
        original_source = self.root / 'connected-source'
        moved_source = self.root / 'offline-source'
        def progress(stage,*_):
            if stage == 'lokal_rapport_klar':
                original_source.rename(moved_source)
        session=self.session(writer=_fake_writer(calls),on_progress=progress)
        self.assertTrue(session.run().exists())
        self.assertEqual(calls,[28])
        self.assertFalse(original_source.exists())
        self.assertTrue(moved_source.exists())

    def test_user_cancels_while_waiting_for_storage(self):
        stopped=threading.Event()
        calls=[]
        def on_progress(stage,*rest):
            if stage=='venter':
                stopped.set()
        session=self.session(writer=_fake_writer(calls),
                probe=lambda:'K18 borte',cancel=stopped,on_progress=on_progress)
        with self.assertRaises(recovery.ExportStopped):
            session.run()
        self.assertEqual(calls,[])
        self.assertFalse(self.dest.exists())

    def test_existing_file_requires_approval_or_identical_hash(self):
        self.dest.mkdir()
        dest=self.dest/'1502_029-056_index.html'
        dest.write_text('Existing important report',encoding='utf8')
        calls=[]
        session=self.session(writer=_fake_writer(calls))
        with self.assertRaises(FileExistsError):
            session.run()
        self.assertEqual(dest.read_text('utf8'),'Existing important report')
        confirmed=[]
        session2=self.session(writer=_fake_writer(calls),
            confirm_overwrite=lambda paths:(confirmed.extend(paths),True)[1])
        session2.run()
        self.assertEqual(len(confirmed),1)
        self.assertIn('28 jobber',dest.read_text('utf8'))

    def test_html_only_still_has_local_json_integrity_check(self):
        calls=[]
        session=recovery.ReportRecoverySession(self.dest,self.jobs,self.options,
             formats=('html',),writer=_fake_writer(calls),state_root=self.state,
             poll_seconds=.01)
        result=session.run()
        self.assertEqual(calls,[28])
        self.assertEqual(result.name,'index.html')
        self.assertEqual([p.name for p in self.dest.iterdir()],['index.html','vedlegg-c-teknisk-evidens.html'])
        self.assertFalse((self.dest/'index.json').exists())

    def test_stage_readiness_detects_missing_job_not_silent_zero(self):
        calls=[]
        def corrupt_writer(directory,jobs,options,*,prefix,formats,overwrite,on_warning):
            calls.append('render')
            (directory/(prefix+'index.json')).write_text(json.dumps({'jobs':[{'job_id':'JOB-001'}]}),'utf8')
            (directory/(prefix+'index.html')).write_text('<p>partial</p>','utf8')
        session=self.session(writer=corrupt_writer)
        with self.assertRaisesRegex(RuntimeError,'feil antall jobber'):
            session.run()
        self.assertFalse(self.dest.exists())

    def test_disk_volume_identity_mismatch_blocks_wrong_disk(self):
        calls=[]
        session=self.session(writer=_fake_writer(calls))
        with patch.object(recovery,'_volume_serial',return_value=7):
            self.assertIsNone(session._probe())
        with patch.object(recovery,'_volume_serial',return_value=8):
            with self.assertRaises(recovery.StorageChanged):
                session._probe()
        self.assertEqual(calls,[])

    def test_session_does_not_call_new_analyses(self):
        import inspect
        src=inspect.getsource(recovery)
        self.assertNotIn('run_catalog(',src)
        self.assertNotIn('execute_xpath(',src)
        self.assertNotIn('run_arkade5_cli(',src)
        self.assertIn('from .report_service_a20 import write_report_package',src)


if __name__ == '__main__':
    unittest.main()
