"""a2.2: Arkade5Check uses severity='ok', not an 'ok' attribute.

Preserve a complete read-only dependency preflight before any joblist switch,
and reject warnings/failed probes without creating a job or modifying Work.
"""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
import ast
import tempfile
import unittest

from app.basic_start_v0111_a1 import (
    BASIC_ARKADE_WORKFLOW_ID, BASIC_WORKFLOW_ID, BasicControlPlan,
    require_basic_arkade_cli, select_or_create_basic_job,
)


class FakeApi:
    def __init__(self, status):
        self.status = status
        self.calls = []

    def check_arkade5_cli(self):
        self.calls.append('check')
        return self.status

    def workspace(self):
        self.calls.append('workspace')
        return SimpleNamespace(jobs=[])

    def create_job(self, **kwargs):
        self.calls.append('create')
        return SimpleNamespace(job_id='JOB-001')

    def update_storage(self, job_id, paths):
        self.calls.append('storage')

    def set_workflow(self, job_id, operation_ids):
        self.calls.append('workflow')

    def use_selected_work_directly(self, job_id):
        self.calls.append('direct')


def plan_for(tmp, workflow_id):
    root = Path(tmp)
    return BasicControlPlan(
        root / 'source', root / 'work', root / 'work', 'standard_enkel',
        ('arkade5_noark5_test', 'arkade5_pronom_analysis') if workflow_id == BASIC_ARKADE_WORKFLOW_ID
        else ('metadata_inventory',),
        workflow_id,
    )


class ArkadeCliContractTests(unittest.TestCase):
    def test_successful_arkade5check_has_severity_but_no_ok(self):
        """The exact user-reported success message must start the extended job."""
        with tempfile.TemporaryDirectory() as temp:
            (Path(temp) / 'work').mkdir()
            plan = plan_for(temp, BASIC_ARKADE_WORKFLOW_ID)
            result = SimpleNamespace(
                severity='ok', version='2.13.1',
                message='Arkade 5 CLI svarer. Versjon: 2.13.1.',
            )
            self.assertFalse(hasattr(result, 'ok'))
            api = FakeApi(result)
            job, created = select_or_create_basic_job(api, plan)
            self.assertTrue(created)
            self.assertEqual(job, 'JOB-001')
            self.assertEqual(api.calls, ['check', 'workspace', 'create', 'storage', 'workflow', 'direct'])
            self.assertEqual(list((Path(temp) / 'work').iterdir()), [])

    def test_warnings_errors_and_missing_status_fail_closed(self):
        for severity in ('warning', 'error', '', None):
            with self.subTest(severity=severity), tempfile.TemporaryDirectory() as temp:
                (Path(temp) / 'work').mkdir()
                plan = plan_for(temp, BASIC_ARKADE_WORKFLOW_ID)
                api = FakeApi(SimpleNamespace(
                    severity=severity, ok=True,
                    message='Krever kontroll i Setup',
                ))
                with self.assertRaisesRegex(ValueError, 'Arkade 5 CLI er ikke klar'):
                    select_or_create_basic_job(api, plan)
                self.assertEqual(api.calls, ['check'])

    def test_standard_workflow_does_not_require_external_cli(self):
        with tempfile.TemporaryDirectory() as temp:
            (Path(temp) / 'work').mkdir()
            api = FakeApi(None)
            job, created = select_or_create_basic_job(api, plan_for(temp, BASIC_WORKFLOW_ID))
            self.assertTrue(created)
            self.assertEqual(job, 'JOB-001')
            self.assertNotIn('check', api.calls)

    def test_missing_checker_blocks_extended_job(self):
        with tempfile.TemporaryDirectory() as temp:
            plan = plan_for(temp, BASIC_ARKADE_WORKFLOW_ID)
            with self.assertRaisesRegex(ValueError, 'kan ikke kontrolleres'):
                require_basic_arkade_cli(object(), plan)

    def test_joblist_confirmation_cannot_run_before_cli_preflight(self):
        """Prevent blank new joblists after a failed CLI version probe."""
        path = Path(__file__).resolve().parents[1] / 'gui_qt' / 'basic_main_v0111_a1.py'
        module = ast.parse(path.read_text(encoding='utf-8'))
        cls = next(n for n in module.body if isinstance(n, ast.ClassDef) and n.name == 'DwmMainWindow')
        method = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == '_start_basic_control')
        calls = [(n.lineno, n.func.id) for n in ast.walk(method)
                 if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)]
        preflight = next(line for line, name in calls if name == 'require_basic_arkade_cli')
        create_or_reuse = next(line for line, name in calls if name == 'select_or_create_basic_job')
        self.assertLess(preflight, create_or_reuse)
        # The confirmation occurs only inside the subsequent `match is None` branch.
        confirmation = next(n for n in ast.walk(method) if isinstance(n, ast.Assign)
                            and any(isinstance(t, ast.Name) and t.id == 'answer' for t in n.targets))
        self.assertLess(preflight, confirmation.lineno)


if __name__ == '__main__':
    unittest.main()
