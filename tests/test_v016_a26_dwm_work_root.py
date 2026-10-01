from pathlib import Path
from tempfile import TemporaryDirectory

from noark5_workflow.core.work_paths import resolve_dwm_work_root


def test_dwm_work_root_uses_configured_subfolder():
    with TemporaryDirectory() as tmp:
        root = Path(tmp) / "repository_operations"
        assert resolve_dwm_work_root(root, settings={"app_work_subfolder": "dwm"}) == root / "dwm"


def test_blank_dwm_subfolder_means_work_operations_root():
    with TemporaryDirectory() as tmp:
        root = Path(tmp) / "repository_operations"
        assert resolve_dwm_work_root(root, settings={"app_work_subfolder": ""}) == root


def test_dwm_work_root_is_idempotent():
    root = Path("X:/package/repository_operations/dwm")
    assert resolve_dwm_work_root(root, settings={"app_work_subfolder": "dwm"}) == root


def test_arkade_native_output_stays_outside_dwm_area():
    source = Path("noark5_workflow/external_tools/arkade5_jobs.py").read_text(encoding="utf-8")
    assert 'output_dir = work / arkade_folder / operation_folder' in source
    assert 'resolve_dwm_work_root(plan.work_operations, settings=settings)' in source
    assert '/ "external_runs" / "arkade5"' in source
    assert 'plan.output_dir / "_dwm"' not in source


def test_auto_import_resolves_dwm_root():
    source = Path("noark5_workflow/external_tools/arkade5_auto_import.py").read_text(encoding="utf-8")
    assert "resolve_dwm_work_root(plan.work_operations)" in source


def test_manual_arkade_import_resolves_dwm_root():
    source = Path("noark5_workflow/job_batch_actions.py").read_text(encoding="utf-8")
    assert "list_arkade5_imports(resolve_dwm_work_root(work_operations))" in source
    assert 'kwargs["work_operations"] = resolve_dwm_work_root(kwargs["work_operations"])' in source
