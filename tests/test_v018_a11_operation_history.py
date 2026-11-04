"""A11: durable subjob execution records and a13-ready Work result references."""
from __future__ import annotations

import ast
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

from noark5_workflow.core.operation_history_a11 import (
    OperationHistoryStore, record_operation, result_paths,
)

ROOT = Path(__file__).resolve().parents[1]


class A11OperationHistoryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.uid = str(uuid4())
        self.work = self.root / 'repository_operations' / 'dwm'
        self.work.mkdir(parents=True)
        (self.work / 'job.json').write_text(json.dumps({
            'job_uid': self.uid,
            'file_type': 'dwm-work-job',
        }), encoding='utf-8')
        self.store = OperationHistoryStore(self.work, self.uid)
        self.run_id = '20261104T033000Z-abc123ef'

    def _append(self, **kw):
        values = dict(run_id=self.run_id, job_id='JOB-001',
                      operation_id='metadata_inventory',
                      operation_name='Metadataoversikt', run_kind='workflow',
                      execution_status='completed', execution_ok=True,
                      message='Utført', result=SimpleNamespace(outputs=[],data={}))
        values.update(kw)
        return self.store.append(**values)

    def test_reading_missing_history_is_read_only(self):
        self.assertEqual(self.store.list_runs(), ())
        self.assertFalse(self.store.path.exists())
        self.assertFalse(self.store.path.parent.exists())

    def test_append_only_and_reopen(self):
        first = self._append()
        second = self._append(operation_id='validate_xml_schema',
                              execution_ok=False, message='XSD-avvik')
        self.assertNotEqual(first.event_id, second.event_id)
        rows = OperationHistoryStore(self.work, self.uid).list_runs()
        self.assertEqual([x.operation_id for x in rows],
                         ['validate_xml_schema', 'metadata_inventory'])
        self.assertFalse(rows[0].execution_ok)
        self.assertEqual(rows[0].execution_status, 'completed')
        self.assertEqual(len(self.store.path.read_text().splitlines()), 2)

    def test_filter_by_deljobb_keeps_execution_history(self):
        self._append(run_id='run-a')
        self._append(run_id='run-b')
        self._append(operation_id='arkade5_pronom_analysis')
        rows = self.store.list_runs(operation_id='metadata_inventory')
        self.assertEqual([x.run_id for x in rows], ['run-b', 'run-a'])
        self.assertEqual(self.store.list_runs(limit=1)[0].operation_id,
                         'arkade5_pronom_analysis')
        self.assertEqual(self.store.list_runs(limit=0), ())

    def test_accurate_status_for_blocked_and_exception(self):
        self._append(execution_status='blocked', execution_ok=None, message='CLI mangler')
        self._append(execution_status='exception', execution_ok=None, message='Teknisk feil')
        self.assertEqual([x.execution_status for x in self.store.list_runs()],
                         ['exception', 'blocked'])
        self.assertTrue(all(x.execution_ok is None for x in self.store.list_runs()))

    def test_work_identity_mismatch_prevents_write(self):
        with self.assertRaisesRegex(ValueError, 'annen varig'):
            OperationHistoryStore(self.work, str(uuid4())).append(
                run_id='run-a', job_id='JOB-001', operation_id='metadata',
                operation_name='Metadata', execution_status='completed', execution_ok=True)
        self.assertFalse(self.store.path.exists())

    def test_joblist_number_can_change_without_losing_history(self):
        self._append(job_id='JOB-001')
        self._append(job_id='JOB-011', run_id='run-two')
        rows = self.store.list_runs()
        self.assertEqual([x.job_id_at_time for x in rows], ['JOB-011', 'JOB-001'])
        self.assertEqual({x.job_uid for x in rows}, {self.uid})

    def test_separate_work_jobs_can_use_same_job_number(self):
        self._append()
        other = self.root / 'second' / 'dwm'
        other.mkdir(parents=True)
        second_uid = str(uuid4())
        (other / 'job.json').write_text(json.dumps({'job_uid': second_uid}), encoding='utf-8')
        OperationHistoryStore(other, second_uid).append(
            run_id=self.run_id, job_id='JOB-001', operation_id='pronom',
            operation_name='PRONOM', execution_status='completed', execution_ok=True)
        self.assertEqual(len(self.store.list_runs()), 1)
        self.assertEqual(OperationHistoryStore(other, second_uid).list_runs()[0].operation_id,
                         'pronom')

    def test_work_only_result_links_reject_source_aip_and_missing(self):
        html = self.work / 'noark5_reports' / 'depot' / 'report.html'
        html.parent.mkdir(parents=True)
        html.write_text('report', encoding='utf-8')
        outside = self.root / 'Source' / 'arkivstruktur.xml'
        outside.parent.mkdir(); outside.write_text('source')
        aip = self.root / 'AIP' / 'mets.xml'
        aip.parent.mkdir(); aip.write_text('aip')
        result = SimpleNamespace(outputs=[str(html), str(outside), str(aip),
                                                  'noark5_reports/depot/report.html', '../Source/arkivstruktur.xml'],
                                 data={'report_html': str(html), 'output_dir': str(html.parent),
                                       'missing_file': str(self.work / 'not-present')})
        paths = result_paths(self.work, result)
        self.assertEqual(paths, ('noark5_reports/depot/report.html', 'noark5_reports/depot'))
        self._append(result=result)
        links = self.store.result_links(operation_id='metadata_inventory')
        self.assertEqual(len(links), 2)
        self.assertTrue(all(link.path.exists() for link in links))
        self.assertTrue(all(self.work.resolve() in link.path.parents for link in links))

    def test_changed_result_is_not_returned_as_valid_link(self):
        folder = self.work / 'wf' / 'results'
        folder.mkdir(parents=True)
        file = folder / 'raw.json'
        file.write_text('{}')
        self._append(result=SimpleNamespace(outputs=[str(file)], data={}))
        file.unlink()
        self.assertEqual(self.store.result_links(operation_id='metadata_inventory'), ())

    def test_latest_run_avoids_stale_links_from_an_earlier_run(self):
        f = self.work / 'old.json'; f.write_text('{}')
        self._append(run_id='first', result=SimpleNamespace(outputs=[str(f)],data={}))
        self._append(run_id='second', result=SimpleNamespace(outputs=[],data={}))
        self.assertEqual(self.store.result_links(operation_id='metadata_inventory'), ())
        self.assertEqual(len(self.store.result_links(operation_id='metadata_inventory',
                                                     run_id='first')), 1)

    def test_raw_result_reference_is_preserved(self):
        file = self.work / 'wf' / 'results' / 'raw-results.jsonl'
        file.parent.mkdir(parents=True)
        file.write_text('[]')
        result = SimpleNamespace(outputs=[], data={'_result_ref': {'result_id': 'r-123',
                                'raw_store': str(file)}})
        row = self._append(result=result)
        self.assertEqual(row.result_id, 'r-123')
        self.assertEqual(row.work_results, ('wf/results/raw-results.jsonl',))

    def test_damaged_last_record_does_not_hide_previous(self):
        self._append()
        with self.store.path.open('a', encoding='utf-8') as handle:
            handle.write('{incomplete}\n')
            handle.write(json.dumps({'schema_version':1,'job_uid':str(uuid4())})+'\n')
        self.assertEqual(len(self.store.list_runs()), 1)

    def test_reject_missing_uid_and_unapproved_work(self):
        uid = str(uuid4())
        with self.assertRaises(ValueError):
            OperationHistoryStore(self.root / 'not-approved', uid).append(
                run_id='first', job_id='JOB-001', operation_id='metadata',
                operation_name='Metadata', execution_status='completed', execution_ok=True)
        self.assertFalse((self.root/'not-approved').exists())

    def test_only_real_runs_are_written_not_job_cursor_snapshots(self):
        # A job may report 9/9 via job-state.json. History stays empty until
        # an actual operation is executed under a real run identity.
        (self.work / 'job-state.json').write_text(json.dumps({'state': {
            'progress': 1.0, 'next_operation_index': 9}}))
        self.assertEqual(self.store.list_runs(), ())

    def test_selective_context_preserves_own_run_and_kind(self):
        op = SimpleNamespace(definition=SimpleNamespace(operation_id='arkade5_pronom_analysis',
                                                         name='Arkade PRONOM'))
        ctx = SimpleNamespace(metadata={'job_id': 'JOB-002'},
                              settings={'_current_job_uid': self.uid,
                                        '_current_run_id': self.run_id,
                                        '_current_run_kind':'subjob'},
                              work_operations=self.work)
        record_operation(ctx, op, status='completed',
                         result=SimpleNamespace(ok=True, message='Arkade CLI fullført',
                                                outputs=[], data={}))
        row = self.store.list_runs()[0]
        self.assertEqual(row.run_kind, 'subjob')
        self.assertEqual(row.operation_id, 'arkade5_pronom_analysis')
        self.assertEqual(row.run_id, self.run_id)
        self.assertTrue(row.execution_ok)

    def test_unidentified_legacy_runs_do_not_create_history(self):
        op = SimpleNamespace(definition=SimpleNamespace(operation_id='op', name='Op'))
        ctx = SimpleNamespace(metadata={'job_id':'JOB-001'}, settings={}, work_operations=self.work)
        self.assertIsNone(record_operation(ctx, op, status='completed',
                                           result=SimpleNamespace(ok=True,data={},outputs=[])))
        self.assertEqual(self.store.list_runs(), ())


class A11ExecutorIntegrationTests(unittest.TestCase):
    @staticmethod
    def _execute_method():
        source=(ROOT/'noark5_workflow'/'executors'/'local.py').read_text(encoding='utf-8')
        tree=ast.parse(source)
        klass=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='LocalExecutor')
        method=next(n for n in klass.body if isinstance(n,ast.FunctionDef) and n.name=='execute')
        method.decorator_list=[]
        ns={'record_operation': record_operation,
            'persist_operation_raw_result': lambda operation,result,ctx: None,
            'OperationResult': lambda ok,message: SimpleNamespace(ok=ok, message=message, outputs=[], data={}, warnings=[]),
            'UserIdentity': SimpleNamespace(from_mapping=lambda obj: None),
            'WorkflowEvent': SimpleNamespace(now=lambda *a,**k: SimpleNamespace()),
            'event_dispatcher_for': lambda ctx: SimpleNamespace(emit=lambda *a,**k: None),
        }
        exec(compile(ast.fix_missing_locations(ast.Module(body=[method],type_ignores=[])),
                     '<local_executor_a11>','exec'),ns)
        return ns['execute']

    def test_executor_records_completion_and_validation_findings(self):
        with tempfile.TemporaryDirectory() as temp:
            work=Path(temp)/'dwm';work.mkdir()
            uid=str(uuid4());(work/'job.json').write_text(json.dumps({'job_uid':uid}))
            state={}
            ctx=SimpleNamespace(metadata={'job_id':'JOB-001'},
                                settings={'_current_run_id':'RUN-42','_current_job_uid':uid,
                                          '_current_run_kind':'workflow'},
                                work_operations=work,
                                set_result=lambda op,data:state.update({op:data}))
            op=SimpleNamespace(definition=SimpleNamespace(operation_id='xsd',name='XSD'),
                               can_run=lambda ctx:(True,''),
                               run=lambda ctx:SimpleNamespace(ok=False, message='XSD-avvik',
                                                                data={}, outputs=[], warnings=['avvik']))
            outcome=self._execute_method()(None,op,ctx)
            self.assertFalse(outcome.ok)
            rows=OperationHistoryStore(work,uid).list_runs()
            self.assertEqual(len(rows),1)
            self.assertEqual(rows[0].execution_status,'completed')
            self.assertFalse(rows[0].execution_ok)
            self.assertEqual(rows[0].warning_count,1)
            self.assertIn('xsd',state)

    def test_executor_blocked_and_exception_are_historic(self):
        with tempfile.TemporaryDirectory() as temp:
            work=Path(temp)/'dwm';work.mkdir()
            uid=str(uuid4());(work/'job.json').write_text(json.dumps({'job_uid':uid}))
            ctx=SimpleNamespace(metadata={'job_id':'JOB-001'},
                                settings={'_current_run_id':'RUN-42','_current_job_uid':uid},
                                work_operations=work)
            op=SimpleNamespace(definition=SimpleNamespace(operation_id='cli',name='CLI'),
                               can_run=lambda ctx:(False,'missing executable'))
            self.assertFalse(self._execute_method()(None,op,ctx).ok)
            def broken(ctx):raise RuntimeError('disk error')
            op.can_run=lambda ctx:(True,'')
            op.run=broken
            with self.assertRaisesRegex(RuntimeError,'disk error'):
                self._execute_method()(None,op,ctx)
            self.assertEqual([r.execution_status for r in OperationHistoryStore(work,uid).list_runs()],
                             ['exception','blocked'])


class A11GuiContractTests(unittest.TestCase):
    def test_api_has_read_only_work_queries(self):
        source=(ROOT/'app'/'workbench_api_v018_a3.py').read_text(encoding='utf-8')
        self.assertIn('def operation_history(',source)
        self.assertIn('def operation_result_links(',source)
        self.assertIn('OperationHistoryStore(ref.parent, uid)',source)

    def test_qt_dock_and_normal_window_support_operation_history_and_links(self):
        source=(ROOT/'gui_qt'/'main_window.py').read_text(encoding='utf-8')
        detached=(ROOT/'gui_qt'/'detached_log_window_v018_a9.py').read_text(encoding='utf-8')
        for token in ('run_history_tree', '_a11_refresh_operation_history',
                      '_a11_open_operation_results', 'self.api.operation_result_links(',
                      'self.api.operation_history(', 'Vis kjørelogg'):
            self.assertIn(token, source)
        for token in ('class DetachedRunWindow', 'historyLogRequested',
                      'historyResultsRequested','def set_history(', 'QTreeWidget'):
            self.assertIn(token, detached)
        self.assertIn('super().__init__(None, Qt.WindowType.Window)', detached)
        self.assertNotIn('Qt.WindowType.WindowStaysOnTopHint', detached)

    def test_run_kind_is_context_local_not_global_setup(self):
        self.assertIn('runtime_settings["_current_run_kind"] = "workflow"',
            (ROOT/'app'/'application_api.py').read_text(encoding='utf-8'))
        self.assertIn('runtime_settings["_current_run_kind"] = "subjob"',
            (ROOT/'app'/'subjob_execution_v018_a9.py').read_text(encoding='utf-8'))
        self.assertIn('record_operation(ctx, operation, status="completed", result=result)',
            (ROOT/'noark5_workflow'/'executors'/'local.py').read_text(encoding='utf-8'))


if __name__=='__main__':
    unittest.main()

class A11WorkbenchReadModelTests(unittest.TestCase):
    """The actual API method bodies, with only unrelated registry/UI omitted."""
    @staticmethod
    def _methods():
        code=(ROOT/'app'/'workbench_api_v018_a3.py').read_text(encoding='utf-8')
        tree=ast.parse(code)
        klass=next(x for x in tree.body if isinstance(x,ast.ClassDef) and x.name=='DwmWorkbenchAPI')
        methods=[x for x in klass.body if isinstance(x,ast.FunctionDef) and x.name in
                 {'operation_history','operation_result_links'}]
        class ApiError(RuntimeError): pass
        ns={'OperationHistoryStore':OperationHistoryStore,'DwmApiError':ApiError}
        exec(compile(ast.fix_missing_locations(ast.Module(body=methods,type_ignores=[])),
                     '<a11_workbench_reads>','exec'),ns)
        return ns, ApiError

    def test_api_return_only_matching_work_uuid_without_joblist_id_dependency(self):
        with tempfile.TemporaryDirectory() as temp:
            work=Path(temp)/'dwm'; work.mkdir()
            uid=str(uuid4()); ref=work/'job.json'
            ref.write_text(json.dumps({'job_uid':uid}))
            file=work/'report.html';file.write_text('ok')
            store=OperationHistoryStore(work,uid)
            store.append(run_id='RUN-1',job_id='JOB-001',operation_id='metadata',
                         operation_name='Metadata',execution_status='completed',execution_ok=True,
                         result=SimpleNamespace(outputs=[str(file)],data={}))
            ns,_=self._methods()
            facade=SimpleNamespace(_work_references={'JOB-007':ref},
                                   _unavailable_work_ids=set(),
                                   _require_job=lambda _id:SimpleNamespace(
                                       job_uid=uid,workflow_ids=['metadata']))
            # AST-loaded functions are bound to a facade, without GUI/registry.
            lines=ns['operation_history'](facade,'JOB-007')
            self.assertEqual(len(lines),1)
            self.assertEqual(lines[0].job_uid,uid)
            self.assertEqual(lines[0].job_id_at_time,'JOB-001')
            links=ns['operation_result_links'](facade,'JOB-007','metadata')
            self.assertEqual(len(links),1)
            # Windows may resolve an 8.3 temp path (TORBJO~1.AAS) to its
            # long spelling; both names must identify the same file.
            self.assertTrue(links[0].path.samefile(file))
            facade._unavailable_work_ids.add('JOB-007')
            self.assertEqual(ns['operation_history'](facade,'JOB-007'),())
            self.assertEqual(ns['operation_result_links'](facade,'JOB-007','metadata'),())

    def test_deleted_work_reference_is_not_replaced_by_stale_joblist_snapshot(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'unavailable'/'job.json'
            uid=str(uuid4())
            facade=SimpleNamespace(_work_references={'JOB-001':path},
                                   _unavailable_work_ids=set(),
                                   _require_job=lambda _id:SimpleNamespace(
                                       job_uid=uid,workflow_ids=['metadata']))
            ns,_=self._methods()
            self.assertEqual(ns['operation_history'](facade,'JOB-001'),())
            self.assertEqual(ns['operation_result_links'](facade,'JOB-001','metadata'),())
            self.assertFalse(path.parent.exists())

class A11RecoveryContractTests(unittest.TestCase):
    def test_history_survives_recovery_without_original_joblist(self):
        from noark5_workflow.core.job import Job
        from noark5_workflow.core.work_job_store import WorkJobStore
        with tempfile.TemporaryDirectory() as temp:
            work=Path(temp)/'separate-disk'/'dwm';work.mkdir(parents=True)
            uid=str(uuid4())
            job=Job('JOB-001',name='Original archive',workflow_ids=['metadata_inventory'])
            job.job_uid=uid
            store=WorkJobStore(work)
            store.write(job,event_kind='work.initialized')
            OperationHistoryStore(work,uid).append(
                run_id='RUN-42',job_id='JOB-001',operation_id='metadata_inventory',
                operation_name='Metadataoversikt',execution_status='completed',execution_ok=True)
            # No .n5jobs exists. Recovery uses only Work state and definition.
            restored=store.load()
            restored.job_id='JOB-027'
            self.assertEqual(restored.job_uid,uid)
            ns,_=A11WorkbenchReadModelTests._methods()
            facade=SimpleNamespace(_work_references={'JOB-027':store.definition_path},
                                   _unavailable_work_ids=set(),
                                   _require_job=lambda _id:restored)
            rows=ns['operation_history'](facade,'JOB-027')
            self.assertEqual(len(rows),1)
            self.assertEqual(rows[0].job_id_at_time,'JOB-001')

    def test_work_links_are_bounded_without_recursive_source_scans(self):
        with tempfile.TemporaryDirectory() as temp:
            work=Path(temp)/'dwm';work.mkdir()
            files=[]
            for i in range(50):
                file=work/f'result{i}.json';file.write_text('{}');files.append(str(file))
            result=SimpleNamespace(outputs=files, data={})
            self.assertLessEqual(len(result_paths(work,result)),24)
