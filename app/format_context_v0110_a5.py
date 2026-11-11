"""Source/date context for side-by-side format assessment (read-only).

The Arkade RAF observation, the PRONOM PUID, and the institution's current
policy lookup are distinct pieces of evidence. Import time is NOT test time;
a policy snapshot date is NOT a legal effective date.
"""
from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, Iterable, Mapping

from app.format_policy_v0110_a4 import FormatPolicy, evaluate_puid

_MAX_MANIFEST_BYTES = 2_000_000


def _string(value: Any) -> str:
    return str(value).strip() if value is not None else ''


def read_pronom_import_context(normalized_file: str | Path, import_id: str) -> dict[str, str]:
    """Read only the manifest beside the SAME normalized PRONOM evidence.

    On missing/corrupt/ambiguous evidence, return empty metadata. Never search
    another import or silently inherit data from a different run.
    """
    empty = {'imported_at': '', 'original_csv': '', 'original_csv_sha256': ''}
    if not normalized_file or not import_id:
        return dict(empty)
    try:
        file = Path(normalized_file)
        if file.name != 'pronom_statistics.json' or file.parent.name != 'normalized':
            return dict(empty)
        root = file.parent.parent
        if (root.name != import_id or root.is_symlink() or
                file.parent.is_symlink() or file.is_symlink()):
            return dict(empty)
        manifest_file = root / 'manifest.json'
        if manifest_file.is_symlink() or not manifest_file.is_file():
            return dict(empty)
        if manifest_file.stat().st_size > _MAX_MANIFEST_BYTES:
            return dict(empty)
        record = json.loads(manifest_file.read_text(encoding='utf-8-sig'))
        if not isinstance(record, dict) or _string(record.get('import_id')) != import_id:
            return dict(empty)
        evidence = record.get('pronom_evidence') or {}
        stats = evidence.get('statistics') if isinstance(evidence, dict) else {}
        stats = stats if isinstance(stats, dict) else {}
        return {
            'imported_at': _string(record.get('imported_at')),
            'original_csv': _string(stats.get('original_name')),
            'original_csv_sha256': _string(stats.get('sha256')),
        }
    except (OSError, UnicodeError, ValueError, TypeError):
        return dict(empty)


def comparison_labels(policy: FormatPolicy | None, import_dates: Iterable[str]) -> tuple[str, str]:
    """Human-readable source context, with dates explicitly typed."""
    dates = sorted(set(_string(d) for d in import_dates if _string(d)))
    when = ', '.join(dates[:2]) + (f' (+{len(dates)-2} til)' if len(dates) > 2 else '') if dates else 'Ikke oppgitt'
    arkade = ('A · Arkade 5 / Siegfried: RAF-220301 er en beholdt historisk '
              f'klassifisering. Importtid: {when}. Importtid er ikke testdato.')
    if policy is None:
        selected = 'B · Valgt regelprofil: Ingen. PUID-er vurderes ikke mot en institusjonsliste.'
    else:
        selected = (f'B · Valgt regelprofil: {policy.title} | Utgave: {policy.edition} | '
                    f'Datert kopi: {policy.captured_at}. Kopidato er ikke ikrafttredelsesdato.')
    return arkade, selected


def export_comparison_csv(
    target: str | Path,
    rows: Iterable[Mapping[str, Any]],
    policy: FormatPolicy | None,
    *,
    overwrite: bool = False,
) -> Path:
    """Export explicitly selected observations; never touch source or Work.

    Contains both separate evaluations AND their independent provenance dates.
    """
    target = Path(target)
    if target.suffix.casefold() != '.csv':
        raise ValueError('Eksportfilen må ha filendelsen .csv.')
    header = (
        'Uttrekk', 'Format-ID / PUID', 'Filtype', 'Versjon', 'Antall',
        'Arkade RAF (historisk observasjon)', 'Vurdering', 'Forklaring',
        'Regelprofil', 'Utgave', 'Profil SHA-256', 'Kilde URL', 'Kilde/import',
        'Arkade importert (ikke testdato)', 'PRONOM kildefil', 'PRONOM kilde SHA-256',
        'Profil kopidato (ikke ikrafttredelsesdato)', 'Profil myndighet/kilde',
    )
    with target.open('w' if overwrite else 'x', encoding='utf-8-sig', newline='') as stream:
        writer = csv.writer(stream, delimiter=';')
        writer.writerow(header)
        for row in rows:
            decision = evaluate_puid(row.get('format_id'), policy)
            count = row.get('count', 0)
            try:
                count = max(0, int(_string(count).replace(' ', '').replace('\u202f', '')))
            except (TypeError, ValueError):
                count = 0
            writer.writerow((
                _string(row.get('job')), _string(row.get('format_id')),
                _string(row.get('file_type')), _string(row.get('version')), count,
                _string(row.get('raf')), decision.label, decision.explanation,
                policy.policy_id if policy else '', policy.edition if policy else '',
                policy.sha256 if policy else '', policy.source_url if policy else '',
                _string(row.get('evidence_source')), _string(row.get('imported_at')),
                _string(row.get('original_csv')), _string(row.get('original_csv_sha256')),
                policy.captured_at if policy else '', policy.authority if policy else '',
            ))
    return target
