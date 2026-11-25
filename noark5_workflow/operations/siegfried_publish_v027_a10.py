"""Crash-conscious publication of verified Siegfried evidence on Windows.

A completed .partial run may contain millions of checked records.  Windows can
refuse renaming a directory (WinError 5) even after readers have been closed.
This module retains the original .partial evidence and, only after a failed
rename, copies it to the final non-hidden directory, publishing manifest.json
last.  It does not run sf.exe or change the original evidence.
"""
from __future__ import annotations

import errno
from hashlib import sha256
import json
import os
from pathlib import Path
import shutil
import time
from typing import Callable

_CHUNK = 4 * 1024 * 1024
_MARKER = '.dwm-siegfried-publishing.json'


def _unsafe_link(path: Path) -> bool:
    return path.is_symlink() or bool(getattr(path, 'is_junction', lambda: False)())


def _is_windows_rename_denied(exc: OSError) -> bool:
    return getattr(exc, 'winerror', None) == 5 or exc.errno in (errno.EACCES, errno.EPERM)


def _copy_check(source: Path, dest: Path, expected_digest: str | None = None) -> None:
    """Copy without modifying source; validate digest of copied bytes."""
    digest = sha256()
    with source.open('rb') as inp, dest.open('xb') as out:
        while True:
            data = inp.read(_CHUNK)
            if not data:
                break
            out.write(data)
            digest.update(data)
        out.flush()
        os.fsync(out.fileno())
    if expected_digest and digest.hexdigest() != expected_digest:
        raise ValueError(f'SHA-256 stemmer ikke for {source.name}. Publisering avbrutt.')
    shutil.copystat(source, dest, follow_symlinks=False)


def _contents(stage: Path):
    """Enumerate only ordinary files/dirs; never follow links outside Work."""
    for directory, folders, files in os.walk(stage, followlinks=False):
        base = Path(directory)
        for name in folders:
            if _unsafe_link(base / name):
                raise ValueError('Lenke/junction i Siegfried-evidens: ' + name)
        for name in files:
            src = base / name
            if _unsafe_link(src) or not src.is_file():
                raise ValueError('Utrygg evidensfil: ' + str(src))
            yield src, src.relative_to(stage)


def publish_verified_siegfried(stage: Path, target: Path, *,
                                log_cb: Callable[[str], None] | None = None) -> str:
    """Publish a fully verified stage; return 'rename' or 'copy'.

    Caller MUST verify the session, inventory, record order, checkpoint SHA,
    and all result counts before invoking. Original stage is never deleted by
    copy fallback. An incomplete destination is cleaned up when possible;
    marker-based recovery avoids overwriting unrelated files on retry.
    """
    stage, target = Path(stage), Path(target)
    if not stage.is_dir() or _unsafe_link(stage) or _unsafe_link(target.parent):
        raise ValueError('Ugyldig Siegfried-arbeidsmappe.')
    if target.exists():
        raise FileExistsError('Resultatmappe finnes allerede: ' + str(target))
    if stage.parent != target.parent or stage.name != '.partial-' + target.name:
        raise ValueError('Siegfried-kilde og mål må tilhøre samme kjøring og mappe.')
    checkpoint = json.loads((stage / 'checkpoint.json').read_text(encoding='utf-8'))
    manifest = json.loads((stage / 'manifest.json').read_text(encoding='utf-8'))
    stats = json.loads((stage / 'pronom_statistics.json').read_text(encoding='utf-8'))
    total = checkpoint.get('files_processed')
    if (type(total) is not int or total <= 0 or
        total != manifest.get('files_total') or total != stats.get('files_total') or
        checkpoint.get('run_id') != target.name or manifest.get('run_id') != target.name or
        stats.get('run_id') != target.name or
        checkpoint.get('raw_sha256') != manifest.get('raw_sha256') or
        checkpoint.get('inventory_sha256') != manifest.get('inventory_sha256') or
        checkpoint.get('raw_bytes') != (stage / 'siegfried_files.jsonl').stat().st_size):
        raise ValueError('Ufullstendig eller inkonsistent Siegfried-resultat. Ingen publisering.')
    # Validate all paths before creating any public output.
    items = list(_contents(stage))
    if not any(rel.as_posix() == 'manifest.json' for _, rel in items):
        raise ValueError('Siegfried-manifest mangler.')
    for attempt in range(3):
        try:
            stage.rename(target)
            return 'rename'
        except OSError as exc:
            if not _is_windows_rename_denied(exc):
                raise
            if attempt < 2:
                if log_cb:
                    log_cb(f'[Siegfried] Mappeomdoping nektet, forsok {attempt + 1}/3; '
                           'prover pa nytt uten a endre resultatene.')
                time.sleep(1.0)
    if log_cb:
        log_cb('[Siegfried] Windows nektet mappeomdoping etter 3 forsok. '
               'Forsoker sikker kopipublisering; original .partial beholdes.')
    # The original remains untouched, but copying needs space for another
    # full evidence set. Fail before allocating a public result directory.
    bytes_needed = sum(src.stat().st_size for src, rel in items if rel.as_posix() != 'manifest.json')
    available = shutil.disk_usage(target.parent).free
    if available < bytes_needed + 64 * 1024 * 1024:
        raise OSError('For lite ledig diskplass for sikker Siegfried-kopipublisering: '
                      f'trenger minst {bytes_needed + 64 * 1024 * 1024} byte; '
                      f'ledig {available} byte.')
    # On Windows a locked directory may be unrenameable while all contained
    # files remain readable. Copy without touching the original checkpoint.
    created = False
    try:
        target.mkdir(exist_ok=False)
        created = True
        (target / _MARKER).write_text(json.dumps({'run_id': target.name,
                                                   'state': 'copying'}, sort_keys=True), encoding='utf-8')
        # manifest LAST: it is the discoverable success marker for DWM readers.
        for src, rel in items:
            if rel.as_posix() == 'manifest.json':
                continue
            dest = target / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            expected = (checkpoint['raw_sha256'] if rel.as_posix() == 'siegfried_files.jsonl'
                        else checkpoint['inventory_sha256'] if rel.as_posix() == 'file_inventory.jsonl'
                        else None)
            if log_cb and src.stat().st_size >= 64 * 1024 * 1024:
                log_cb(f'[Siegfried] Kopierer bevart evidens: {rel} ({src.stat().st_size} byte).')
            _copy_check(src, dest, expected)
        manifest_tmp = target / '.manifest-pending'
        _copy_check(stage / 'manifest.json', manifest_tmp)
        os.replace(manifest_tmp, target / 'manifest.json')
        # Marker is kept to distinguish copy-published runs for auditing.
        (target / _MARKER).write_text(json.dumps({'run_id': target.name,
                                                   'state': 'complete',
                                                   'preserved_partial': stage.name}, sort_keys=True),
                                          encoding='utf-8')
        if log_cb:
            log_cb('[Siegfried] Kontrollert kopipublisering fullfort. '
                   f'Original .partial er bevart: {stage}')
        return 'copy'
    except Exception:
        # Remove only a new destination created by this call, never stage.
        # If Windows prevents cleanup, incomplete target has NO manifest.
        if created:
            try:
                (target / 'manifest.json').unlink(missing_ok=True)
                shutil.rmtree(target)
            except OSError:
                if log_cb:
                    log_cb('[Siegfried] Ufullstendig kopimappe kunne ikke ryddes. '
                           f'Undersok {target} for nytt forsok; original .partial er urort.')
        raise
