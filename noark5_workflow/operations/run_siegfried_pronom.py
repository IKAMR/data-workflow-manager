"""DWM-owned Siegfried identification, separate from Arkade's PRONOM evidence.

Uses the same sf executable as SIARD Workflow Manager (read-only), but writes
its own immutable run directory below the selected DWM Work. Nothing is added
inside the Noark 5 source. No RAF/arkivformat approval is inferred from PUIDs.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import os
import subprocess
from pathlib import Path
import shutil
import uuid

from app.siegfried_tool_v0111_a3 import identify_siegfried_files, inspect_siegfried
from noark5_workflow.core.context import OperationContext
from noark5_workflow.core.operation import BaseOperation, ExecutionTarget, OperationDefinition
from noark5_workflow.core.result import OperationResult

# Protect memory: adapter returns file-level results while computing the groups.
# Exceeding the ceiling fails visibly, NEVER silently truncates a scan.
MAX_FILES_PER_SCAN = 250_000


def document_files(source: Path, *, cancelled_cb=None, max_files: int = MAX_FILES_PER_SCAN,
                   progress_cb=None, progress_interval: int = 500):
    """Discover actual files deterministically, never follow symlinked folders.

    Prefer the Noark 5 DOKUMENT content area. If a test extraction does not
    have DOKUMENT, scan its entire extraction and report that scope explicitly.
    """
    root = Path(source).resolve(strict=True)
    if not root.is_dir():
        raise ValueError('Uttrekksmappen finnes ikke.')
    document_roots = [p for p in root.iterdir()
                      if p.is_dir() and not p.is_symlink() and p.name.casefold() == 'dokument']
    scan_roots = document_roots or [root]
    selected_scope = 'DOKUMENT' if document_roots else 'Hele uttrekksmappen (DOKUMENT finnes ikke)'
    result: list[Path] = []
    for scan_root in scan_roots:
        for folder, dirs, files in os.walk(scan_root, topdown=True, followlinks=False):
            if cancelled_cb and cancelled_cb():
                raise InterruptedError('Siegfried-skanningen ble avbrutt.')
            dirs[:] = sorted((d for d in dirs if not (Path(folder) / d).is_symlink()),
                             key=str.casefold)
            for name in sorted(files, key=str.casefold):
                p = Path(folder) / name
                if p.is_symlink() or not p.is_file():
                    continue
                # resolve(strict) also rejects unexpected escapes on Windows.
                resolved = p.resolve(strict=True)
                if not resolved.is_relative_to(root):
                    raise ValueError('En fil peker utenfor Source: ' + str(p))
                result.append(resolved)
                if progress_cb is not None and progress_interval > 0 and len(result) % progress_interval == 0:
                    progress_cb(len(result))
                if len(result) > max_files:
                    raise ValueError(
                        f'Uttrekket har flere enn {max_files} dokumentfiler. '
                        'Siegfried-adapteren kan ikke behandle dette som én batchjobb ennå; '
                        'kjør ikke et ufullstendig testuttrekk.'
                    )
    if result and progress_cb is not None and (progress_interval <= 0 or len(result) % progress_interval):
        progress_cb(len(result))
    return result, selected_scope


def _sha256(path: Path) -> str:
    hash_value = hashlib.sha256()
    with path.open('rb') as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b''):
            hash_value.update(chunk)
    return hash_value.hexdigest()


class SiegfriedPronomOperation(BaseOperation):
    definition = OperationDefinition(
        operation_id='siegfried_pronom_identification',
        name='Siegfried – PRONOM filidentifikasjon',
        description='Identifiser filer med delt sf.exe og lagre kildebevarende PRONOM-evidens under Work.',
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
        stage = None
        try:
            ctx.progress(.02, 'Finner dokumentfiler')
            files, scope = document_files(
                Path(ctx.extraction_root), cancelled_cb=ctx.cancelled,
                progress_cb=lambda found: ctx.progress(.03, f'Finner dokumentfiler: {found} filer funnet'),
            )
            ctx.progress(.05, f'{len(files)} dokumentfiler funnet. Starter Siegfried ...')
            if not files:
                return OperationResult(False, 'Ingen dokumentfiler funnet for Siegfried. Ingen statistikk er skrevet.')
            work = Path(ctx.work_operations).resolve(strict=True)
            root = work / 'external_evidence' / 'siegfried'
            if (work / 'external_evidence').is_symlink() or root.is_symlink():
                raise ValueError('Evidensmappen kan ikke være en symbolsk lenke utenfor Work.')
            run_id = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '-' + uuid.uuid4().hex[:10]
            target = root / run_id
            stage = root / ('.partial-' + run_id)
            stage.mkdir(parents=True, exist_ok=False)
            raw = stage / 'siegfried_files.jsonl'
            ctx.log(f'[Siegfried] Kildeomfang: {scope}. Filer: {len(files)}. Eksekverer {status.executable}')
            with raw.open('w', encoding='utf-8', newline='\n') as output:
                parsed = identify_siegfried_files(
                    status.executable, Path(ctx.extraction_root), files,
                    file_progress_cb=lambda done, total: ctx.progress(
                        .06 + .88 * done / total,
                        f'Siegfried: {done} av {total} filer analysert'),
                    cancelled_cb=ctx.cancelled, raw_records=output,
                )
            if ctx.cancelled():
                raise InterruptedError('Siegfried-skanningen ble avbrutt.')
            # A bounded summary; the full original per-file match records remain
            # available as JSONL and are never reinterpreted as RAF results.
            model = {k: v for k, v in parsed.items() if k != 'files'}
            model.update({
                'format_version': 1,
                'evidence_type': 'dwm_siegfried_pronom_identification',
                'source_system': 'DWM / Siegfried',
                'run_id': run_id,
                'created_at': datetime.now(timezone.utc).isoformat(),
                'source_scope': scope,
                'siegfried_version': status.version,
                'siegfried_signature': status.signature,
                'raw_evidence': 'siegfried_files.jsonl',
            })
            (stage / 'pronom_statistics.json').write_text(
                json.dumps(model, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
            manifest = {
                'file_type': 'dwm-siegfried-run',
                'format_version': 1,
                'run_id': run_id,
                'job_id': str(ctx.metadata.get('job_id') or ''),
                'job_uid': str(ctx.metadata.get('job_uid') or ctx.metadata.get('job_uuid') or ''),
                'source_root': str(Path(ctx.extraction_root).resolve(strict=True)),
                'source_scope': scope,
                'program': status.executable,
                'program_version': status.version,
                'signature': status.signature,
                'raw_file': 'siegfried_files.jsonl',
                'raw_sha256': _sha256(raw),
                'normalized_file': 'pronom_statistics.json',
                'files_total': model['files_total'],
                'created_at': model['created_at'],
            }
            (stage / 'manifest.json').write_text(
                json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
            stage.rename(target)
            stage = None
            ctx.progress(1., 'Siegfried-identifikasjon fullført')
            return OperationResult(
                True,
                f'Siegfried identifiserte {model["identified"]} av {model["files_total"]} filer; '
                f'{model["unidentified"]} uidentifiserte, {model["ambiguous"]} flertydige. '
                f'Kilde: {scope}.',
                data={'run_id': run_id, 'evidence_type': model['evidence_type'],
                      'format_groups': len(model['format_groups']),
                      'files_total': model['files_total'],
                      'unidentified': model['unidentified'],
                      'output_dir': str(target)},
                outputs=[str(target / 'manifest.json'), str(target / 'pronom_statistics.json')],
            )
        except (OSError, ValueError, RuntimeError, TimeoutError,
                InterruptedError, subprocess.SubprocessError) as exc:
            return OperationResult(False, f'Siegfried-kjøringen kunne ikke fullføres: {exc}')
        finally:
            if stage is not None:
                shutil.rmtree(stage, ignore_errors=True)
