"""DWM-owned Siegfried identification, separate from Arkade PRONOM.

Since v0.2.2-a5 the Noark workflow uses streaming, bounded parallel sf
processes (100 files per batch) with durable ordered Work checkpoints.
The former 250,000-file hard limit is removed; Source remains read-only and
previous completed runs are immutable.
"""
from __future__ import annotations

from pathlib import Path
import subprocess

from app.siegfried_tool_v0111_a3 import inspect_siegfried
from noark5_workflow.core.context import OperationContext
from noark5_workflow.core.operation import BaseOperation, ExecutionTarget, OperationDefinition
from noark5_workflow.core.result import OperationResult
from .siegfried_stream_v022_a4 import MAX_SF_WORKERS, iter_document_files, scan_document_tree


def document_files(source: Path, *, cancelled_cb=None, max_files: int | None = None,
                   progress_cb=None, progress_interval: int = 500):
    """Legacy list-returning discovery helper; independent of the a4 scanner.

    Kept self-contained because the earlier a3.5 regression tests isolate this
    function via AST. Production uses scan_document_tree(), never this list.
    An optional explicit max_files remains available to list-based callers,
    but it must not impose a limit on production Siegfried execution.
    """
    import os

    root = Path(source).resolve(strict=True)
    if not root.is_dir():
        raise ValueError('Uttrekksmappen finnes ikke.')
    document_roots = [p for p in root.iterdir()
                      if p.is_dir() and not p.is_symlink() and p.name.casefold() == 'dokument']
    scan_roots = document_roots or [root]
    scope = 'DOKUMENT' if document_roots else 'Hele uttrekksmappen (DOKUMENT finnes ikke)'
    files = []
    for scan_root in scan_roots:
        for folder, dirs, names in os.walk(scan_root, topdown=True, followlinks=False):
            if cancelled_cb and cancelled_cb():
                raise InterruptedError('Siegfried-skanningen ble avbrutt.')
            dirs[:] = sorted((name for name in dirs
                              if not (Path(folder) / name).is_symlink()), key=str.casefold)
            for name in sorted(names, key=str.casefold):
                path = Path(folder) / name
                if path.is_symlink() or not path.is_file():
                    continue
                resolved = path.resolve(strict=True)
                if not resolved.is_relative_to(root):
                    raise ValueError('En fil peker utenfor Source: ' + str(path))
                files.append(resolved)
                if progress_cb is not None and progress_interval > 0 and len(files) % progress_interval == 0:
                    progress_cb(len(files))
                if max_files is not None and len(files) > max_files:
                    raise ValueError(f'For mange filer for en listebasert skanning: {max_files}')
    if files and progress_cb is not None and (progress_interval <= 0 or len(files) % progress_interval):
        progress_cb(len(files))
    return files, scope


class SiegfriedPronomOperation(BaseOperation):
    definition = OperationDefinition(
        operation_id='siegfried_pronom_identification',
        name='Siegfried – PRONOM filidentifikasjon',
        description='Strømmende, gjenopptakbar Siegfried-identifikasjon; lagrer PRONOM-evidens under Work.',
        execution_target=ExecutionTarget.EITHER,
        category='Systemspesifikt',
    )
    raw_result_record = True

    def can_run(self, ctx: OperationContext) -> tuple[bool, str]:
        if not ctx.work_operations:
            return False, 'Work - operations må være definert.'
        if not ctx.extraction_root:
            return False, 'Source - extraction må være definert.'
        status = inspect_siegfried(str(ctx.settings.get('sf_executable') or ''))
        return (status.ok, '' if status.ok else status.message)

    def run(self, ctx: OperationContext) -> OperationResult:
        status = inspect_siegfried(str(ctx.settings.get('sf_executable') or ''))
        if not status.ok:
            return OperationResult(False, status.message)
        if ctx.work_operations is None or ctx.extraction_root is None:
            return OperationResult(False, 'Source og Work må være angitt.')
        try:
            configured_workers = ctx.settings.get('siegfried_max_workers', 2)
            # Never truncate a fractional or boolean worker setting silently.
            if (type(configured_workers) not in (int, str) or
                    (isinstance(configured_workers, str) and
                     not configured_workers.strip().isdigit())):
                raise ValueError(f'Siegfried-prosessantall må være et heltall fra 1 til {MAX_SF_WORKERS}.')
            workers = int(configured_workers)
            if workers < 1 or workers > MAX_SF_WORKERS:
                raise ValueError(f'Siegfried-prosessantall må være et heltall fra 1 til {MAX_SF_WORKERS}.')
            ctx.progress(.02, 'Finner dokumentfiler (strømmende opptelling)')
            run = scan_document_tree(
                source=Path(ctx.extraction_root),
                work=Path(ctx.work_operations),
                executable=status.executable,
                version=status.version,
                signature=status.signature,
                job_id=str(ctx.metadata.get('job_id') or ''),
                job_uid=str(ctx.metadata.get('job_uid') or ctx.metadata.get('job_uuid') or ''),
                cancelled_cb=ctx.cancelled,
                workers=workers,
                log_cb=ctx.log,
                discovery_cb=lambda found: ctx.progress(
                    .03, f'Finner dokumentfiler: {found} filer funnet'),
                progress_cb=lambda done, total: ctx.progress(
                    .06 + .88 * done / max(1, total),
                    f'Siegfried: {done} av {total} filer analysert'),
            )
            model = run['model']
            target = run['target']
            ctx.progress(1., 'Siegfried-identifikasjon fullført')
            return OperationResult(
                True,
                f'Siegfried identifiserte {model["identified"]} av {model["files_total"]} filer; '
                f'{model["unidentified"]} uidentifiserte, {model["ambiguous"]} flertydige. '
                f'Kilde: {model["source_scope"]}. '
                f'{"Gjenopptatt fra kontrollpunkt." if run["resumed"] else ""}',
                data={'run_id': run['run_id'], 'evidence_type': model['evidence_type'],
                      'format_groups': len(model['format_groups']),
                      'files_total': model['files_total'],
                      'unidentified': model['unidentified'],
                      'output_dir': str(target), 'resumed': run['resumed'],
                      'siegfried_process_workers': workers},
                outputs=[str(target / 'manifest.json'), str(target / 'pronom_statistics.json')],
            )
        except (OSError, ValueError, RuntimeError, TimeoutError,
                InterruptedError, subprocess.SubprocessError) as exc:
            return OperationResult(False, f'Siegfried-kjøringen kunne ikke fullføres: {exc}')
