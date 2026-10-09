"""Non-destructive audit of older repository_operations storage locations."""
from __future__ import annotations
from pathlib import Path
import hashlib
import json


def _locations(work_operations: str | Path) -> tuple[Path, Path]:
    """Accept either repository_operations or repository_operations/dwm."""
    work = Path(work_operations)
    if work.name.lower() == 'dwm':
        return work.parent, work
    return work, work / 'dwm'


def audit_legacy_layout(work_operations: str | Path) -> dict:
    parent, active_root = _locations(work_operations)
    items = []
    for relative in ('external_evidence/result-bank.json', 'metadata/depot_metadata.json'):
        old = parent / relative
        current = active_root / relative
        if not old.is_file():
            continue
        digest = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
        items.append({'relative': relative, 'legacy': str(old), 'active': str(current),
                      'legacy_sha256': digest(old), 'active_sha256': digest(current) if current.is_file() else None,
                      'safe_to_automatically_remove': False})
    return {'kind': 'legacy_layout_audit', 'read_only': True, 'items': items}


def write_legacy_audit(work_operations: str | Path) -> Path:
    _, active_root = _locations(work_operations)
    output = active_root / 'external_evidence' / 'legacy-layout-audit.json'
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(audit_legacy_layout(work_operations), ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return output
