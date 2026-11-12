"""Read-only latest/history DWM Siegfried PRONOM results in a selected Work.

Keep direct Siegfried distinct from imported Arkade 5 PRONOM; summing both
sources as if they were additional documents would double count files.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

MAX_NORMALIZED_BYTES = 16_000_000
MAX_RUNS_PER_JOB = 120


def list_siegfried_runs(work_operations: str | Path) -> list[dict[str, Any]]:
    """Only bounded, validated Work-owned completed runs; never scan Source."""
    try:
        work = Path(work_operations).resolve(strict=True)
        root = work / 'external_evidence' / 'siegfried'
        if root.is_symlink() or not root.is_dir():
            return []
        candidates = sorted((p for p in root.iterdir() if p.is_dir() and not p.is_symlink()
                             and not p.name.startswith('.partial-')),
                            key=lambda x: x.name, reverse=True)[:MAX_RUNS_PER_JOB]
    except (OSError, ValueError):
        return []
    rows = []
    for folder in candidates:
        manifest_path = folder / 'manifest.json'
        model_path = folder / 'pronom_statistics.json'
        try:
            if manifest_path.is_symlink() or model_path.is_symlink():
                continue
            if not manifest_path.is_file() or not model_path.is_file():
                continue
            if model_path.stat().st_size > MAX_NORMALIZED_BYTES or manifest_path.stat().st_size > 500_000:
                continue
            if not model_path.resolve(strict=True).is_relative_to(work) or not manifest_path.resolve(strict=True).is_relative_to(work):
                continue
            manifest = json.loads(manifest_path.read_text(encoding='utf-8-sig'))
            model = json.loads(model_path.read_text(encoding='utf-8-sig'))
            if not isinstance(manifest, dict) or not isinstance(model, dict):
                continue
            if manifest.get('file_type') != 'dwm-siegfried-run':
                continue
            if model.get('evidence_type') != 'dwm_siegfried_pronom_identification':
                continue
            if manifest.get('run_id') != folder.name or model.get('run_id') != folder.name:
                continue
            groups = model.get('format_groups')
            if not isinstance(groups, list) or any(not isinstance(g, dict) for g in groups):
                continue
            if any(key not in model for key in ('identified', 'unidentified', 'ambiguous')):
                continue
            if sum(int(g.get('count', 0)) for g in groups) != int(model.get('files_total', -1)):
                continue
        except (OSError, ValueError, TypeError, UnicodeError):
            continue
        rows.append({'work': work, 'run_id': folder.name, 'manifest': manifest,
                     'model': model, 'model_path': model_path, 'folder': folder})
    return rows
