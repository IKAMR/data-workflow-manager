from __future__ import annotations

import re
import tempfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable, Iterable, Mapping, Sequence

from .arkade5 import configured_arkade5_cli, inspect_arkade5_cli
from noark5_workflow.external_evidence.arkade5_discovery import discover_arkade5_reports_in_roots
from noark5_workflow.core.work_paths import resolve_dwm_work_root
from .cli_runner import ExternalCliRequest, ExternalCliRunResult, run_external_cli

ARKADE5_NOARK5 = "noark5_test"
ARKADE5_PRONOM = "pronom_analysis"
ARKADE5_OPERATIONS = (ARKADE5_NOARK5, ARKADE5_PRONOM)
DEFAULT_ARKADE5_OUTPUT_SUBFOLDER = "arkade5_<ver>"

_SAFE = re.compile(r"[^A-Za-z0-9._-]+")
_WINDOWS_FORBIDDEN = set('<>:"/\\|?*')


def _safe(value: str) -> str:
    cleaned = _SAFE.sub("_", str(value or "").strip()).strip("._")
    return cleaned or "unnamed"


def _run_token() -> str:
    return datetime.now().astimezone().strftime("%Y%m%d-%H%M%S-%f")


def _job_source(job) -> Path | None:
    source = getattr(job, "active_extraction_root", None)
    if source is None:
        source = getattr(job, "source_extraction", None)
    if source is None:
        return None
    return Path(source)


def _job_work(job) -> Path | None:
    value = getattr(job, "work_operations", None)
    return Path(value) if value is not None else None


def _job_label(job) -> str:
    return str(getattr(job, "name", "") or getattr(job, "job_id", "job"))


def _version_token(version: str) -> str:
    value = str(version or "unknown").strip()
    if value.lower().startswith("v"):
        return value
    return f"v{value}"


def resolve_arkade5_output_subfolder(settings: Mapping[str, object], version: str) -> str:
    """Resolve the user-configured Arkade output subfolder.

    ``<ver>`` expands to the detected version including the leading ``v``.
    The result is deliberately one relative folder name below Work - operations;
    Arkade's own output layout is then kept intact below operation folders.
    """
    template = str(
        settings.get("arkade5_output_subfolder", DEFAULT_ARKADE5_OUTPUT_SUBFOLDER)
        or DEFAULT_ARKADE5_OUTPUT_SUBFOLDER
    ).strip()
    resolved = template.replace("<ver>", _version_token(version))
    if not resolved or resolved in {".", ".."}:
        raise ValueError("Arkade 5 output-undermappe kan ikke være tom.")
    if Path(resolved).is_absolute() or any(ch in _WINDOWS_FORBIDDEN for ch in resolved):
        raise ValueError(
            "Arkade 5 output-undermappe må være ett relativt mappenavn uten sti-separatorer."
        )
    return resolved


@dataclass(frozen=True)
class Arkade5PlannedRun:
    job_id: str
    job_name: str
    operation: str
    source: Path
    work_operations: Path
    output_dir: Path
    processing_dir: Path | None
    args: tuple[str, ...]
    run_id: str
    tool_version: str


@dataclass(frozen=True)
class Arkade5JobRun:
    plan: Arkade5PlannedRun | None
    ok: bool
    skipped: bool = False
    message: str = ""
    result: ExternalCliRunResult | None = None
    generated_reports: tuple[Path, ...] = ()


@dataclass(frozen=True)
class Arkade5BatchRunSummary:
    runs: tuple[Arkade5JobRun, ...]
    auto_import: object | None = None

    @property
    def total(self) -> int:
        return len(self.runs)

    @property
    def succeeded(self) -> int:
        return sum(row.ok for row in self.runs)

    @property
    def failed(self) -> int:
        return sum((not row.ok) and (not row.skipped) for row in self.runs)

    @property
    def skipped(self) -> int:
        return sum(row.skipped for row in self.runs)


def build_arkade5_plan(
    settings: Mapping[str, object],
    jobs: Iterable[object],
    operations: Sequence[str],
) -> tuple[Arkade5PlannedRun, ...]:
    """Create Arkade 5 CLI invocations for selected DWM jobs.

    The configured Arkade folder is one level below each job's Work - operations.
    DWM only adds ``noark5`` and ``pronom`` to keep the two Arkade operations
    separate. Arkade itself owns the structure and filenames below those folders.
    """
    selected_ops = tuple(op for op in operations if op in ARKADE5_OPERATIONS)
    if not selected_ops:
        return ()

    cli = configured_arkade5_cli(settings)
    if cli is None:
        raise ValueError("Arkade 5 CLI er ikke konfigurert.")

    status = inspect_arkade5_cli(settings)
    if not status.ok:
        raise ValueError(status.message)
    version = status.version or "unknown"
    arkade_folder = resolve_arkade5_output_subfolder(settings, version)

    temp_setting = str(settings.get("temp_dir", "") or "").strip()
    temp_root = Path(temp_setting) if temp_setting else Path(tempfile.gettempdir()) / "data-workflow-manager"

    plans: list[Arkade5PlannedRun] = []
    for job in jobs:
        source = _job_source(job)
        work = _job_work(job)
        if source is None or work is None:
            continue
        if not source.exists():
            continue

        job_id = str(getattr(job, "job_id", "") or "JOB")
        job_name = _job_label(job)

        for operation in selected_ops:
            run_id = f"{job_id}-{operation}-{_run_token()}"
            operation_folder = "noark5" if operation == ARKADE5_NOARK5 else "pronom"
            output_dir = work / arkade_folder / operation_folder
            processing_dir: Path | None = None

            if operation == ARKADE5_NOARK5:
                processing_dir = temp_root / "arkade5" / _safe(job_id) / run_id
                args = (
                    "test",
                    "-a", str(source),
                    "-p", str(processing_dir),
                    "-o", str(output_dir),
                    "-t", "Noark5",
                    "-l", "nb",
                )
            else:
                args = (
                    "analyse",
                    "-f", str(source),
                    "-o", str(output_dir),
                    "-F", "filformatinfo",
                    "-l", "nb",
                )

            plans.append(
                Arkade5PlannedRun(
                    job_id=job_id,
                    job_name=job_name,
                    operation=operation,
                    source=source,
                    work_operations=work,
                    output_dir=output_dir,
                    processing_dir=processing_dir,
                    args=args,
                    run_id=run_id,
                    tool_version=version,
                )
            )

    return tuple(plans)


def run_arkade5_plan(
    settings: Mapping[str, object],
    plans: Sequence[Arkade5PlannedRun],
    *,
    on_progress: Callable[[int, int, Arkade5PlannedRun, str], None] | None = None,
    on_output: Callable[[int, int, Arkade5PlannedRun, str, str], None] | None = None,
) -> Arkade5BatchRunSummary:
    cli = configured_arkade5_cli(settings)
    if cli is None:
        raise ValueError("Arkade 5 CLI er ikke konfigurert.")

    rows: list[Arkade5JobRun] = []
    total = len(plans)
    for index, plan in enumerate(plans, start=1):
        if on_progress:
            on_progress(index, total, plan, "starter")

        plan.output_dir.mkdir(parents=True, exist_ok=True)
        if plan.processing_dir is not None:
            plan.processing_dir.mkdir(parents=True, exist_ok=True)

        # Capture the report paths that existed before this exact run.  After
        # Arkade returns, DWM can therefore identify only the reports created
        # by this invocation instead of rediscovering/importing older reports.
        reports_before: set[str] = set()
        if plan.operation == ARKADE5_NOARK5:
            try:
                reports_before = {
                    str(item.path.resolve()).casefold()
                    for item in discover_arkade5_reports_in_roots(
                        work_operations=plan.output_dir,
                        work_root=None,
                        source_root=None,
                    )
                }
            except Exception:
                reports_before = set()

        # Arkade owns output_dir. All DWM-owned execution evidence follows the
        # global App-undermappe i Work rule and therefore stays outside the
        # external tool's native output tree.
        evidence_id = _safe(plan.run_id)
        dwm_dir = (
            resolve_dwm_work_root(plan.work_operations, settings=settings)
            / "external_runs" / "arkade5" / _safe(plan.job_id)
            / _safe(plan.operation) / evidence_id
        )
        dwm_dir.mkdir(parents=True, exist_ok=True)
        stdout_path = dwm_dir / "stdout.txt"
        stderr_path = dwm_dir / "stderr.txt"
        manifest_path = dwm_dir / "manifest.json"

        def _output(stream_name: str, text: str) -> None:
            if on_output is not None:
                on_output(index, total, plan, stream_name, text)

        result = run_external_cli(
            ExternalCliRequest(
                executable=cli,
                args=plan.args,
                stdout_path=stdout_path,
                stderr_path=stderr_path,
                manifest_path=manifest_path,
                tool_id="arkade5",
                operation_id=plan.operation,
                job_id=plan.job_id,
                run_id=plan.run_id,
                metadata={
                    "tool_version": plan.tool_version,
                    "source_extraction": str(plan.source),
                    "work_operations": str(plan.work_operations),
                    "arkade_output_dir": str(plan.output_dir),
                    "arkade_processing_dir": str(plan.processing_dir or ""),
                },
            ),
            on_output=_output if on_output is not None else None,
        )
        message = "Fullført" if result.ok else (
            result.launch_error or
            ("Timeout" if result.timed_out else f"Exit code {result.exit_code}")
        )
        generated_reports: tuple[Path, ...] = ()
        if result.ok and plan.operation == ARKADE5_NOARK5:
            try:
                reports_after = discover_arkade5_reports_in_roots(
                    work_operations=plan.output_dir,
                    work_root=None,
                    source_root=None,
                )
                generated_reports = tuple(
                    item.path
                    for item in reports_after
                    if str(item.path.resolve()).casefold() not in reports_before
                )
            except Exception:
                generated_reports = ()

        rows.append(
            Arkade5JobRun(
                plan=plan,
                ok=result.ok,
                message=message,
                result=result,
                generated_reports=generated_reports,
            )
        )

        if on_progress:
            on_progress(index, total, plan, "ferdig" if result.ok else "feil")

    return Arkade5BatchRunSummary(tuple(rows))
